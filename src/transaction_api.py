"""This file defines the REST API were transaction can be executed."""

import datetime
import json
import os
import pickle

import flask
from flask import request
import redis
import requests
import rsa

HOST_IP = os.environ.get("HOST", "0.0.0.0")
app = flask.Flask("transaction")
_REDIS_IP = os.environ.get("REDIS_IP", "0.0.0.0")
_RD = redis.StrictRedis(host=_REDIS_IP, port=6379, db=0)


@app.route("/user/new", methods=["POST"])
def create_user():
    """
    curl 0.0.0.0:5000/user/new -d '{"username": "myname", "password": "password"}' -H 'Content-Type: application/json'
    """
    new_user = request.get_json(force=True)

    # TODO(shawn): Check if username is in the database and return and error if it is
    ...

    (pubkey, private) = rsa.newkeys(512)

    new_user.update(
        {
            "private_key": private.save_pkcs1().decode("utf-8"),
            "public_key": pubkey.save_pkcs1().decode("utf-8"),
        }
    )
    _RD.set(new_user["username"], pickle.dumps(new_user))

    return flask.jsonify("Account created!"), 201


@app.route("/user/delete", methods=["GET"])
def delete_user():
    """
    curl 0.0.0.0:5000/user/delete?username=myname'
    """
    # TODO(shawn): Remove the user from the database
    ...


@app.route("/transaction/new", methods=["POST"])
def create_transaction():
    """
    curl 0.0.0.0:5000/transaction/new -d '{"from": {"username": "myname", "password": "password"}, "to": "notme", "amount": 100}' -H 'Content-Type: application/json'
    """
    # Take the from's username and password and extract the private to sign the transaction.
    transaction = request.get_json(force=True)
    from_username = transaction["from"]["username"]

    # TODO: Check that the from user exists
    # TODO: Check that the to user exists

    info = pickle.loads(_RD.get(from_username))
    private_key = rsa.PrivateKey.load_pkcs1(info["private_key"])
    signature = rsa.sign(
        json.dumps(transaction).encode("utf-8").strip(), private_key, "SHA-1"
    )
    # Update the transaction with the signed payment and the timestamp
    transaction.update(
        {
            "from": {
                "username": info["public_key"],
                "signature": signature.decode("latin-1"),
            },
            "timestamp": str(datetime.datetime.now().isoformat())
        }
    )

    headers = {"content-type": "application/json"}
    return requests.post(
        "http://0.0.0.0:5001/transaction/new",
        headers=headers,
        data=json.dumps(transaction, sort_keys=True),
    ).content


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
