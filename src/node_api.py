import ast
import copy
import hashlib
import json
import time
import logging
import os
import pathlib
import pickle
import redis
import threading
import operator
import random

import flask
from flask import request
import requests
import uuid

NODE_IDX = str(uuid.uuid4()).replace("-", ".")
_NETWORK_IP = os.environ.get("NETWORK_IP", "0.0.0.0")
_REDIS_IP = os.environ.get("REDIS_IP", "0.0.0.0")
_BLOCK_CHAIN = redis.StrictRedis(host=_REDIS_IP, port=6379, db=0)
app = flask.Flask("blockchain")
_LOG_DIR = pathlib.Path("logging")
_LOG_DIR.mkdir(exist_ok=True, parents=True)
logging.basicConfig(
    filename=_LOG_DIR / f"{NODE_IDX}.txt",
    format="%(asctime)s %(message)s",
    level=logging.DEBUG,
)


class FullNode:
    """This is a full node object."""

    def __init__(self):
        self.node_idx = NODE_IDX
        self.ledger_size = 2
        self.ledger = []
        self.block_num = 0
        self.previous_hash = "0" * 64
        self.block_chain = []
        self.transaction_timestamps = set()
        self.num_transactions_per_block = 1
        
        # Resolve the initial chain
        self.resolve_chain()

    def check_valid_chain(self, blockchain):
        """Check that a given blockchain is valid."""
        logging.info("Checking for valid blockchain")
        previous_hash = None
        for block in blockchain:
            if previous_hash is None:
                previous_hash = block["previous_hash"]
            if not block["previous_hash"] == previous_hash:
                return False

            original_block = {
                key: value
                for key, value in block.items()
                if key not in ["hash", "nonce", "mined-by"]
            }
            original_block = json.dumps(original_block, sort_keys=True)
            original_block = str(original_block) + str(block["nonce"])
            assert (
                hashlib.sha256(str(original_block).encode()).hexdigest()
                == block["hash"]
            )

            previous_hash = block["hash"]

        return True

    def update_chain(self, blockchain):
        if len(blockchain) > len(self.block_chain):
            self.block_chain = copy.deepcopy(blockchain)

    def mine_block(self):
        """Inifinite loop to look for new transactions in the node's database.
        If there are some number of transactions, load them and begin to mine
        the block."""

        while True:

            # Collect all the transactions from the ledger. Keep transactions in a
            # separate key.
            # TODO(alex): is there a limit to the number of transactions per block?
            block = {"transactions": {}}
            this_block_keys = set()

            # Loop through and find the oldest timestamp
            timestamps = []
            for key in _BLOCK_CHAIN.scan_iter(f"ledger-{NODE_IDX}:*"):
                timestamps.append(key.decode("utf-8").split(":", 1)[-1])
            timestamps.sort()

            if timestamps:
                earliest = timestamps[0]
                key = f"ledger-{NODE_IDX}:{earliest}".encode()
                this_block_keys.add(key)
                data = json.loads(_BLOCK_CHAIN.get(key))
                key = key.decode("utf-8")
                block["transactions"][key.split(":", 1)[-1]] = data
            

            # If there are no transactions for this block, wait.
            if not timestamps:
                logging.info("No new transactions to mine.")
                time.sleep(2.0)
                continue

            # Add the previous block's hash to this block.
            block.update({"previous_hash": self.previous_hash})
            logging.info(f"[MINING] Mining new block: {json.dumps(block, indent=2)}")

            block = json.dumps(block, sort_keys=True)
            # Remove the transactions in the ledger that are being considered in
            # for this block.
            for key in _BLOCK_CHAIN.scan_iter(f"ledger-{NODE_IDX}:*"):
                if key in this_block_keys:
                    logging.info(f"Removing {key} from the ledger.")
                    _BLOCK_CHAIN.delete(key)

            new_hash = hashlib.sha256(block.encode()).hexdigest()
            nonce = -1
            while new_hash[:2] != "00":
                nonce += 1
                new_block = block + str(nonce)
                new_hash = hashlib.sha256(new_block.encode()).hexdigest()
                logging.info(f"[MINING] Trying nonce: {nonce}")

            logging.info(f"Sucessful hash: {new_hash}")

            block = ast.literal_eval(block)
    
            block.update({"nonce": nonce, "hash": new_hash, "mined-by": NODE_IDX})
            logging.info(f"New block: {json.dumps(block, indent=2)}")

            self.block_chain.append(block)
            self.previous_hash = new_hash

            # Check if this block is already in our database. This happens when this node
            # copies from another node while still mining.
            if not _BLOCK_CHAIN.exists(f"blockchain-{NODE_IDX}-{self.block_num}"):
                # Now we mined a new block, add this to the nodes copy of the blockchain
                _BLOCK_CHAIN.set(
                    f"blockchain-{NODE_IDX}-{self.block_num}",
                    json.dumps(block, sort_keys=True),
                )
                self.block_num += 1

    def _copy_chain(self, node_idx):
        """Copy the blockchain from node_idx to this node."""
        self.block_num = 0
        num_blocks = len(list(_BLOCK_CHAIN.scan_iter(f"blockchain-{node_idx}-*")))
        for idx in range(num_blocks):
            self.block_num += 1
            # Get the block number
            block = _BLOCK_CHAIN.get(f"blockchain-{node_idx}-{idx}")
            _BLOCK_CHAIN.set(f"blockchain-{NODE_IDX}-{idx}", block)

            # Also make sure to add the block's transactions to this node's list 
            # so we don't remine the same transactions.
            block = json.loads(block)
            for transaction in block["transactions"]:
                self.transaction_timestamps.add(transaction)
            
            # Keep track of the previous block
            self.previous_hash = block["hash"]
            logging.info(self.previous_hash)
        
        logging.info(f"Copyied chain from {node_idx} to {NODE_IDX}.")

    def check_chain_valid(self, node_idx: str):
        """Loop through the given node's blocks and validate its chain. If the chain
        is valid, make this the accepted chain."""
        all_node_blocks = list(_BLOCK_CHAIN.scan_iter(f"blockchain-{node_idx}-*"))

        # If the other chain is the same length is ours, no need to merge.
        if len(all_node_blocks) == self.block_num:
            return
        # Extract all the blocks from this node in order so we can validate the
        # hashes of the chain.
        blockchain = []
        for idx in range(len(all_node_blocks)):
            blockchain.append(json.loads(_BLOCK_CHAIN.get(f"blockchain-{node_idx}-{idx}")))

        if self.check_valid_chain(blockchain):
            logging.info(f"Found valid chain from {node_idx}. Updating {NODE_IDX} copy.")
            self._copy_chain(node_idx)

    def resolve_chain(self):
        # First scan all the copies of the other node's blockchains to resolve
        # conflicts. We want to get each node's chain, validate the hashes are right,
        # then if the other chain is longer than ours, we take the longer chain
        # as the truth. We need to sort all the keys based on node IDs.
        all_node_blocks = list(_BLOCK_CHAIN.scan_iter("blockchain-*"))
        # If there are no other blockchains from any nodes, we've likely just started.
        if not all_node_blocks:
            return
        # Parse out the various node ids. The format is blockchain-nodeid-blocknumber
        node_id_block_nums = [key.decode().split("-")[1]  for key in all_node_blocks]
        node_ids = set(node_id_block_nums)
        # Knowing the number of blocks per node chain and the unique node ids, the
        # large nodal block chain can be found.
        node_chain_lengths = {node: node_id_block_nums.count(node) for node in node_ids}
        node_longest_chain, longest_length = max(node_chain_lengths.items(), key=operator.itemgetter(1))
        # If the node with the longest chain is this node itself, don't do anything. If 
        # is it not this node, resolve the chain.
        if not node_longest_chain == NODE_IDX and longest_length != self.block_num:
            self.check_chain_valid(node_longest_chain)

    def check_for_updates(self):
        """Run an infinite loop to look for any new transactions that have been
        executed. If there is any new transaction, add it to a the node's database.
        """
        while True:
            self.resolve_chain()

            # Scan the master ledger than copy to this node's ledger. In real life this
            # copy would be local to the node, here we just reuse the same database but
            # with a different key to simulate a different
            for key in _BLOCK_CHAIN.scan_iter("transaction:*"):
                # TODO(alex): workaround here, fix eventually.
                key_ = f"{key}"
                if key_ not in self.transaction_timestamps:
                    self.transaction_timestamps.add(key_)
                    _BLOCK_CHAIN.set(f"ledger-{NODE_IDX}:{key}", _BLOCK_CHAIN.get(key))
                    logging.info(f"Found new transaction:{key.decode()}")
            
            logging.info("No new transactions from transaction API.")

            # This simulates different internet times, processing capabilities. Without
            # this, there would no need to resolve conflicts because every node would
            # move at the same speed.
            time.sleep(random.randint(1, 5))


if __name__ == "__main__":

    node = FullNode()
    thread = threading.Thread(target=node.check_for_updates)
    thread.daemon = True
    thread.start()
    thread = threading.Thread(target=node.mine_block)
    thread.daemon = True
    thread.start()

    thread.join()
