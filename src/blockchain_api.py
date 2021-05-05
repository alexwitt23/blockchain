"""This file defines the REST API that mining nodes use to communicate with each other.
This is also the API new users and transactions can be created through."""

import hashlib
import json
import os

import flask
from flask import request
import redis
import requests

NODE_NETWORK = set()

_REDIS_IP = os.environ.get("REDIS_IP", "0.0.0.0")
rd = redis.StrictRedis(host=_REDIS_IP, port=6379, db=0)
app = flask.Flask("blockchain")


@app.route("/node/new", methods=["GET"])
def add_node():
    """"""
    # Send this transaction to all the nodes.
    node_id = request.args.get("node_id")
    NODE_NETWORK.add(node_id)
    return flask.jsonify("Node added to network"), 201


@app.route("/transaction/new", methods=["POST"])
def project_transaction():
    """"""
    # Send this transaction to all the nodes.
    transaction = request.get_json(force=True)
    rd.set(transaction["timestamp"], json.dumps(transaction, sort_keys=True))
    headers = {"content-type": "application/json"}
    for node_idx in NODE_NETWORK:
        requests.post(
            f"http://0.0.0.0:5002/nodes/{node_idx}/transaction/new",
            headers=headers,
            data=json.dumps(transaction, sort_keys=True),
        ).content

    return flask.jsonify("Transaction added to ledger."), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
