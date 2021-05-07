"""This file defines the REST API that mining nodes use to communicate with each other.
This is also the API new users and transactions can be created through."""
import ast
import hashlib
import json
import os
import operator
import copy

import flask
from flask import request
import redis
import requests

NODE_NETWORK = {}

_REDIS_IP = os.environ.get("REDIS_IP", "0.0.0.0")
_RD = redis.StrictRedis(host=_REDIS_IP, port=6379, db=0)
app = flask.Flask("blockchain")
app.config["JSON_SORT_KEYS"] = False

for key in _RD.scan_iter("*"):
    _RD.delete(key)


@app.route("/transaction/new", methods=["POST"])
def project_transaction():
    """"""
    # Send this transaction to all the nodes.
    transaction = request.get_json(force=True)
    _RD.set(
        f"transaction:{transaction['timestamp']}",
        json.dumps(transaction, sort_keys=True),
    )

    return flask.jsonify("Transaction added to ledger."), 201


@app.route("/history", methods=["GET"])
def get_history():
    """Get the blockchain that is most agreed upon. This mean the shortest chain.
    The longest chain hasn't always been validated.

    curl 0.0.0.0:5001/history
    """
    # This logic is very similar to the src/node_api.py update.
    all_node_blocks = list(_RD.scan_iter("blockchain-*"))
    if not all_node_blocks:
        return flask.jsonify("No history yet."), 201

    # Parse out the various node ids. The format is blockchain-nodeid-blocknumber
    node_id_block_nums = [key.decode().split("-")[1] for key in all_node_blocks]
    node_ids = set(node_id_block_nums)
    # Knowing the number of blocks per node chain and the unique node ids, the
    # large nodal block chain can be found.
    node_chain_lengths = {node: node_id_block_nums.count(node) for node in node_ids}
    node_shortest_chain, _ = min(node_chain_lengths.items(), key=operator.itemgetter(1))
    all_node_blocks = list(_RD.scan_iter(f"blockchain-{node_shortest_chain}-*"))
    blockchain = []
    for idx in range(len(all_node_blocks)):
        blockchain.append(
            json.loads(_RD.get(f"blockchain-{node_shortest_chain}-{idx}"))
        )

    return flask.jsonify(blockchain), 201


@app.route("/history/nodes", methods=["GET"])
def get_all_chains():
    """Get the blockchain that is most agreed upon. This mean the shortest chain.
    The longest chain hasn't always been validated.

    curl 0.0.0.0:5001/history
    """
    # This logic is very similar to the src/node_api.py update.
    all_node_blocks = list(_RD.scan_iter("blockchain-*"))
    if not all_node_blocks:
        return flask.jsonify("No history yet."), 201

    # Parse out the various node ids. The format is blockchain-nodeid-blocknumber
    node_id_block_nums = [key.decode().split("-")[1] for key in all_node_blocks]
    node_ids = set(node_id_block_nums)
    # Knowing the number of blocks per node chain and the unique node ids, the
    # large nodal block chain can be found.
    node_chain_lengths = {node: node_id_block_nums.count(node) for node in node_ids}
    node_shortest_chain, _ = min(node_chain_lengths.items(), key=operator.itemgetter(1))
    all_node_blocks = list(_RD.scan_iter(f"blockchain-{node_shortest_chain}-*"))
    blockchain = {}
    for node, num_blocks in node_chain_lengths.items():
        blockchain[node] = {}
        for idx in range(num_blocks):
            print(idx)
            blockchain[node][f"block-{idx}"] = json.loads(
                _RD.get(f"blockchain-{node}-{idx}")
            )

    return flask.jsonify(blockchain), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
