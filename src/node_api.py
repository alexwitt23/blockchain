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

import flask
from flask import request
import requests
import uuid

NODE_IDX = str(uuid.uuid4())
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
        self.previous_hash = "0" * 10
        self.block_chain = []
        self.transaction_timestamps = set()
        self.num_transactions_per_block = 2

        # Fetch the current state of the blockchain. We want to keep this in order.
        self.num_blocks = len(list(_BLOCK_CHAIN.scan_iter("block-*")))
        logging.info(list(_BLOCK_CHAIN.scan_iter("block-*")))
        logging.info(f"Initializing node with blockchain history. Found {self.num_blocks} blocks.")
        for block in range(self.num_blocks):
            key = f"block-{block}".encode()
            logging.info(f"Retrieving {key}.")
            block = json.loads(_BLOCK_CHAIN.get(key), encoding="utf-8")
            # Now add all the transactions of this block to the history. This is
            # so we know which transactions are new or not.
            for transaction in block["transactions"]:
                self.transaction_timestamps.add(transaction)
            self.previous_hash = block["previous_hash"]
        logging.info(self.transaction_timestamps)
        

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
                if key not in ["hash", "nonce"]
            }
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
            transactions = 0
            this_block_keys = set()
            for key in _BLOCK_CHAIN.scan_iter(f"ledger-{NODE_IDX}:*"):
                this_block_keys.add(key)
                data = json.loads(_BLOCK_CHAIN.get(key))
                key = key.decode("utf-8")
                block["transactions"][key.split(":", 1)[-1]] = data
                transactions += 1
                if transactions - 1 > self.num_transactions_per_block:
                    break

            # If there are no transactions for this block, wait.
            if not block["transactions"]:
                logging.info("No new transactions to mine.")
                time.sleep(2.0)
                continue

            # Add the previous block's hash to this block.
            block.update({"previous_hash": self.previous_hash})
            logging.info(f"[MINING] Mining new block: {json.dumps(block, indent=2)}")
            
            block = str(block)
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

            block.update({"nonce": nonce, "hash": new_hash})
            logging.info(f"New block: {json.dumps(block, indent=2)}")

            self.block_chain.append(block)

            self.previous_hash = new_hash

            # Now with a new mined block, send out the chain.
            _BLOCK_CHAIN.set(
                f"block-{self.block_num}", json.dumps(block, sort_keys=True)
            )
            self.block_num += 1
    
    def check_for_transactions(self):
        """Run an infinite loop to look for any new transactions that have been
        executed. If there is any new transaction, add it to a the node's database.
        """
        while True:
            # Scan the master ledger than copy to this node's ledger. In real life this
            # copy would be local to the node, here we just reuse the same database but
            # with a different key to simulate a different
            for key in _BLOCK_CHAIN.scan_iter("transaction:*"):
                # TODO(alex): workaround here, fix eventually.
                key_ = f"{key}"
                if key_ not in self.transaction_timestamps:
                    self.transaction_timestamps.add(key_)
                    _BLOCK_CHAIN.set(
                        f"ledger-{NODE_IDX}:{key}", _BLOCK_CHAIN.get(key)
                    )             
                    logging.info(f"Found new transaction:{key.decode()}")
            
            time.sleep(2.0)


if __name__ == "__main__":

    node = FullNode()
    thread = threading.Thread(target=node.check_for_transactions)
    thread.daemon = True
    thread.start()
    thread = threading.Thread(target=node.mine_block)
    thread.daemon = True
    thread.start()