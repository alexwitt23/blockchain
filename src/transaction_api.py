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


def create_user(username: str, password: str):

    new_user = {"username": username, "password": password}
    # TODO(shawn): Check if username is in the database and return and error if it is
    if _RD.exists(username) == 1:
        raise Exception('Username {} already exists. Please choose a different username.'.format(username))

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

    return "Account created.", 201



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


@app.route("/user/delete", methods=["GET"])
def delete_user():
    """Delete a user from the account database.
    
    Example: curl 0.0.0.0:5000/user/delete?username=myname
    """
    # TODO(shawn): Remove the user from the database
    user_to_delete = request.args.get('username',type=str)
    if _RD.exists(user_to_delete) == 1:
        _RD.del(user_to_delete)
    else
        raise Exception('User {} does not exist.'.format(user_to_delete)
    return "User deleted."

@app.route("/transaction/new", methods=["POST"])
def create_transaction():
    """Execute a new transaction. There needs to be a 'from' and 'to' keys in the data.
    The 'from' dictionary should have a user name and password.

    Example:
        curl 0.0.0.0:5000/transaction/new \
        -d '{"from": {"username": "genesis", "password": "password"}, "to": "foo", "amount": 10000}' \
        -H 'Content-Type: application/json'
    """
    # Take the from's username and password and extract the private to sign the transaction.
    transaction = request.get_json(force=True)
    from_username = transaction["from"]["username"]
    from_password = transaction["from"]["password"]
    # TODO(shawn): Check that the from user exists and the password is right
    if _RD.exists(from_username) == 1:
        info = pickle.loads(_RD.get(from_username))
        actual_from_password = info['password']
        if from_password != actual_from_password:
            raise Exception('Submitted sender user password {} is incorrect.'.format(from_password))
    else
        raise Exception('Sender user {} does not exist.'.format(from_username))
    # TODO(shawn): Check that the to user exists
    to_username = transaction["to"]["username"]
    to_password = transaction["to"]["password"]
    if _RD.exists(to_username) == 1:
        to_info = pickle.loads(_RD.get(to_username))
        actual_to_password = to_info["password"]
        if to_password != actual_to_passowrd:
            raise Exception('Submitted recipient user password {} is incorrect.'.format(to_password))
    else
        raise Exception('Submitted recipient user {} does not exist.'.format(to_username))

    private_key = rsa.PrivateKey.load_pkcs1(info["private_key"])
    signature = rsa.sign(json.dumps(transaction).encode(), private_key, "SHA-256")
    # Update the transaction with the signed payment and the timestamp
    transaction.update(
        {
            "from": {
                "username": info["public_key"],
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

    # Create the first transaction and put some money into the system.
    ...

    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
