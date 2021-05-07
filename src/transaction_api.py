"""This API allows the creation and deletion of users and RSA secured transactions."""

import datetime
import json
import os
import pickle

import flask
from flask import request
import redis
import requests
import rsa

_BLOCKCHAIN_IP = os.environ.get("BLOCKCHAIN_IP", "0.0.0.0")
app = flask.Flask("transaction")
_REDIS_IP = os.environ.get("REDIS_IP", "0.0.0.0")
_RD = redis.StrictRedis(host=_REDIS_IP, port=6379, db=0)
for key in _RD.scan_iter("*"):
    _RD.delete(key)


def create_user(username: str, password: str):
    """Function to create a user and add it to the database."""
    # Check if username is in the database and return and error if it is
    if _RD.exists(username):
        return f"The username '{username}' already exists! Please choose another", 409

    new_user = {"username": username, "password": password}
    # Generate a new public and private key used to sign transactions.
    (pubkey, private) = rsa.newkeys(512)

    # Update the user's info with the keys.
    new_user.update(
        {
            "private_key": private.save_pkcs1().decode("utf-8"),
            "public_key": pubkey.save_pkcs1().decode("utf-8"),
        }
    )
    # Write the user's information to the database.
    _RD.set(new_user["username"], pickle.dumps(new_user))

    return f"Account created for '{username}'.", 201


@app.route("/user/new", methods=["POST"])
def new_user():
    """Create a new user who can execute transactions.

    Example:
        curl 0.0.0.0:5000/user/new \
            -d '{"username": "myname", "password": "password"}' \
            -H 'Content-Type: application/json'
    """
    new_user = request.get_json(force=True)
    output, code = create_user(new_user["username"], new_user["password"])

    return flask.jsonify(output), code


@app.route("/user/delete", methods=["POST"])
def delete_user():
    """Delete a user from the account database.
    
    Example: curl 0.0.0.0:5000/user/delete -d '{"username": "myname", "password": "password"}' -H 'Content-Type: application/json'

    """
    # Remove the user from the database if the user exists and the password is right.
    user = request.get_json(force=True)
    username = user["username"]
    password = user["password"]
    if not _RD.exists(username):
        return flask.jsonify(f"No user for '{username}' exists."), 404

    user_info = pickle.loads(_RD.get(username))

    if user_info["password"] != password:
        return flask.jsonify("Incorrect password!"), 404
    else:
        _RD.delete(username)
        return flask.jsonify(f"User '{username}' deleted."), 404


@app.route("/transaction/new", methods=["POST"])
def create_transaction():
    """Execute a new transaction. There needs to be a 'from' and 'to' keys in the data.
    The 'from' dictionary should have a user name and password.

    Example:
        curl 0.0.0.0:5000/transaction/new \
        -d '{"from": {"username": "genesis", "password": "password"}, "to": "foo", "amount": 100}' \
        -H 'Content-Type: application/json'
    """
    # Take the from's username and password and extract the private to sign the transaction.
    transaction = request.get_json(force=True)
    from_username = transaction["from"]["username"]
    password = transaction["from"]["password"]
    to_username = transaction["to"]

    # Check that the from user exists.
    if not _RD.exists(from_username):
        return flask.jsonify("You must have an account to send money!"), 404

    # Load the from user and verify the password.
    user_info = pickle.loads(_RD.get(from_username))
    if user_info["password"] != password:
        return flask.jsonify("Incorrect password!"), 404

    # Check that the to user exists.
    if not _RD.exists(to_username):
        return flask.jsonify("You must send money to someone with an account!"), 404
    
    private_key = rsa.PrivateKey.load_pkcs1(user_info["private_key"])
    signature = rsa.sign(json.dumps(transaction).encode(), private_key, "SHA-256")
    # Update the transaction with the signed payment and the timestamp
    transaction.update(
        {
            "from": {
                "username": from_username,
                "public-key": user_info["public_key"],
                "signature": signature.decode("utf-8", "ignore"),
            },
            "timestamp": str(datetime.datetime.now().isoformat()),
        }
    )

    headers = {"content-type": "application/json"}
    return requests.post(
        f"http://{_BLOCKCHAIN_IP}:5001/transaction/new",
        headers=headers,
        data=json.dumps(transaction, sort_keys=True),
    ).content


if __name__ == "__main__":

    # Create some initial users for our blockchain. Someone has to start with the money!
    create_user("genesis", "password")
    create_user("foo", "bar")

    # Create the first transaction and put some money into the system. Typically this
    # might be called the "genesis" block.
    transaction = {
        "timestamp": str(datetime.datetime.now().isoformat()),
        "from": {
            "username": "genesis",
            "public-key": "genesis",
            "signature": "genesis",
        },
        "to": "foo",
        "amount": 1000,
    }
    # Send this to the blockchain
    requests.post(
        f"http://{_BLOCKCHAIN_IP}:5001/transaction/new",
        headers={"content-type": "application/json"},
        data=json.dumps(transaction, sort_keys=True),
    ).content

    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
