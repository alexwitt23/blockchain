import ast
import copy
import hashlib
import json
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
_NODE_PORT = os.environ.get("PORT")
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
        block = {}
        for key in _BLOCK_CHAIN.scan_iter(f"ledger-{NODE_IDX}:*"):
            data = pickle.loads(_BLOCK_CHAIN.get(key))
            key = key.decode("utf-8")
            block[key.split(":", 1)[-1]] = data

        block.update({"previous_hash": self.previous_hash})
        block = str(block)
        for key in _BLOCK_CHAIN.scan_iter(f"ledger-{NODE_IDX}:*"):
            _BLOCK_CHAIN.delete(key)

        new_hash = hashlib.sha256(block.encode()).hexdigest()
        nonce = -1
        while new_hash[:2] != "00":
            nonce += 1
            new_block = block + str(nonce)
            new_hash = hashlib.sha256(new_block.encode()).hexdigest()
            logging.info(f"Trying nonce: {nonce}")
        
        logging.info(f"Sucessful hash: {new_hash}")

        block = ast.literal_eval(block)

        block.update({"nonce": nonce, "hash": new_hash})
        self.block_chain.append(block)
        self.previous_hash = new_hash
        self.block_num += 1

        # Now with a new mined block, send out the chain
        block_chain = copy.deepcopy(self.block_chain)

        headers = {"content-type": "application/json"}
        return requests.post(
            f"http://{_NETWORK_IP}:5001/block/new?sender={NODE_IDX}",
            headers=headers,
            data=json.dumps(block_chain, sort_keys=True),
        ).content


node = FullNode()


@app.route(f"/nodes/{NODE_IDX}/transaction/new", methods=["POST"])
def project_transaction():
    """"""
    logging.info("Recieved new transaction.")
    # Send this transaction to all the nodes.
    transaction = request.get_json(force=True)
    _BLOCK_CHAIN.set(
        f"ledger-{NODE_IDX}:{transaction['timestamp']}", pickle.dumps(transaction)
    )
    logging.info("Mining new block")
    thread = threading.Thread(target=node.mine_block)
    thread.daemon = True
    thread.start()

    return flask.jsonify("Transaction added to ledger."), 201


@app.route(f"/nodes/{NODE_IDX}/resolve", methods=["POST"])
def resolve_chain():
    """"""
    # Send this transaction to all the nodes.
    chain = request.get_json(force=True)
    if not node.check_valid_chain(chain):
        print("Invalid chain. Someone is doing something malicious!")
    else:
        node.update_chain(chain)

    return flask.jsonify("Transaction added to ledger."), 201


@app.route(f"/nodes/{NODE_IDX}/blockchain", methods=["GET"])
def get_history():
    """"""
    return json.dumps(node.block_chain), 201



if __name__ == "__main__":
    try:
        # Register this node to the network
        requests.get(
            f"http://{_NETWORK_IP}:5001/node/new?node_id={NODE_IDX}&node_port={_NODE_PORT}"
        )
        app.run(host="0.0.0.0", port=_NODE_PORT, debug=True, use_reloader=False)
    finally:
        # Delete the node from the network
        requests.get(f"http://{_NETWORK_IP}:5001/node/delete?node_id={NODE_IDX}")
