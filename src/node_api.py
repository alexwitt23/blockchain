import copy
import hashlib
import json
import os
import pickle
import redis
import threading

import flask
from flask import request
import requests
import uuid

NODE_IDX = str(uuid.uuid4())
_NODE_PORT = os.environ.get("PORT", 5000)
_NETWORK_IP = os.environ.get("NETWORK_IP", "0.0.0.0")
_REDIS_IP = os.environ.get("REDIS_IP", "0.0.0.0")
_BLOCK_CHAIN = redis.StrictRedis(host=_REDIS_IP, port=6379, db=0)
app = flask.Flask("blockchain")


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
        block = json.dumps(block, sort_keys=True)

        for key in _BLOCK_CHAIN.scan_iter(f"ledger-{NODE_IDX}:*"):
            _BLOCK_CHAIN.delete(key)

        new_hash = hashlib.sha256(block.encode()).hexdigest()
        nonce = 0
        while new_hash[:2] != "000":
            new_block = block + str(nonce)
            new_hash = hashlib.sha256(new_block.encode()).hexdigest()
            nonce += 1
        block = json.loads(block)

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
    # Send this transaction to all the nodes.
    transaction = request.get_json(force=True)
    _BLOCK_CHAIN.set(
        f"ledger-{NODE_IDX}:{transaction['timestamp']}", pickle.dumps(transaction)
    )
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
