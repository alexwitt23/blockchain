"""This file defines the REST API that mining nodes use to communicate with each other.
This is also the API new users and transactions can be created through."""

import hashlib
import json
import os
import copy

import flask
from flask import request
import redis
import requests

NODE_NETWORK = {}

_NODES_IP = os.environ.get("NODES_IP", "0.0.0.0")
_REDIS_IP = os.environ.get("REDIS_IP", "0.0.0.0")
rd = redis.StrictRedis(host=_REDIS_IP, port=6379, db=0)
app = flask.Flask("blockchain")


@app.route("/node/new", methods=["GET"])
def add_node():
    """Add a node to the network registry."""
    # Send this transaction to all the nodes.
    node_id = request.args.get("node_id")
    node_port = request.url.split(":")[-1].replace("/","")
    print(node_id, request)
    NODE_NETWORK[node_id] = node_port
    return flask.jsonify("Node added to network"), 201


@app.route("/node/delete", methods=["GET"])
def remove_node():
    """"""
    node_id = request.args.get("node_id")
    del NODE_NETWORK[node_id]
    return flask.jsonify("Node added to network"), 201


@app.route("/transaction/new", methods=["POST"])
def project_transaction():
    """"""
    # Send this transaction to all the nodes.
    transaction = request.get_json(force=True)
    rd.set(transaction["timestamp"], json.dumps(transaction, sort_keys=True))
    headers = {"content-type": "application/json"}
    for node_idx, node_port in NODE_NETWORK.items():
        requests.post(
            f"http://{_NODES_IP}:{node_port}/nodes/{node_idx}/transaction/new",
            headers=headers,
            data=copy.copy(json.dumps(transaction, sort_keys=True)),
        ).content

    return flask.jsonify("Transaction added to ledger."), 201


@app.route("/block/new", methods=["POST"])
def distribute_chain():
    """"""
    # Send this chain to all the nodes.
    sender_node = request.args.get("sender")
    block_chain = request.get_json(force=True)
    headers = {"content-type": "application/json"}
    for node_idx, node_port in NODE_NETWORK.items():
        if node_idx != sender_node:
            requests.post(
                f"http://{_NODES_IP}:{node_port}/nodes/{node_idx}/resolve",
                headers=headers,
                data=copy.copy(json.dumps(block_chain, sort_keys=True)),
            ).content

    return flask.jsonify("Transaction added to ledger."), 201

@app.route("/history", methods=["GET"])
def get_history():
    """
    curl 0.0.0.0:5001/history
    """
    for node_idx, node_port in NODE_NETWORK.items():
        print(node_idx, node_port)
        response = requests.get(f"http://{_NODES_IP}:{node_port}/nodes/{node_idx}/blockchain")

    return_str = ""
    for block in response.content:
        return_str += str(block) + "\n"

    return flask.jsonify(response.content), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
