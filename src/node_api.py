
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
        self.previous_hash = "0" * 20
        self.block_chain = []

    def mine_block(self):
        block = ""
        for key in _BLOCK_CHAIN.scan_iter("ledger:*"):
            data = pickle.loads(_BLOCK_CHAIN.get(key))
            block += json.dumps(data)

        for key in _BLOCK_CHAIN.scan_iter("ledger:*"):
            _BLOCK_CHAIN.delete(key)

        new_hash = hashlib.sha256(block.encode()).hexdigest()
        nonce = 0
        while new_hash[:2] != "00":
            new_block = block + str(nonce)
            new_hash = hashlib.sha256(new_block.encode()).hexdigest()
            nonce += 1
        block = json.loads(block)
        block.update(
            {"nonce": nonce, "previous_hash": self.previous_hash, "hash": new_hash}
        )
        self.block_chain.append(block)
        self.previous_hash = new_hash
        for block in self.block_chain:
            print(block, "\n")
        # _BLOCK_CHAIN.set(f"block-chain:{self.block_num}", pickle.dumps(block))

        self.block_num += 1


node = FullNode()


@app.route(f"/nodes/{NODE_IDX}/transaction/new", methods=["POST"])
def project_transaction():
    """"""
    # Send this transaction to all the nodes.
    transaction = request.get_json(force=True)
    _BLOCK_CHAIN.set(f"ledger:{transaction['timestamp']}", pickle.dumps(transaction))
    thread = threading.Thread(target=node.mine_block)
    thread.daemon = True
    thread.start()

    return flask.jsonify("Transaction added to ledger."), 201


if __name__ == "__main__":
    # Register this node to the network
    requests.get(f"http://{_NETWORK_IP}:5001/node/new?node_id={NODE_IDX}")
    app.run(host="0.0.0.0", port=5002, debug=True, use_reloader=False)
