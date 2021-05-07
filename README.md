# Simple Blockchain 

![CI](https://github.com/alexwitt23/blockchain/workflows/CI/badge.svg)


This project was created for a final in COE 332 at UT Austin. It is an attempt at
implementing some of the basic operations of a blockchain for validating transactions.

## Requirements

* A: We created a Flask REST API.

* B: Backend Node runners that mine

* C: Redis database to save users, transaction, blockchain

* D: Strong code organization


## Local Development

To run the services locally, please install docker compose. Then run:

```
make up
```

```
docker-compose up -d --scale node_api=2
```

## Transaction API

* `/user/new`: 
Create a new user:
```
$ curl 0.0.0.0:5000/user/new \
  -d '{"username": "myname", "password": "password"}' \
  -H 'Content-Type: application/json'

"Account created for 'myname'."
```

You will recieve an error if you try to create an account with a taken username.

* `/user/delete`:
Remove an account:
```
curl 0.0.0.0:5000/user/delete \
  -d '{"username": "myname", "password": "password"}' \
  -H 'Content-Type: application/json'

"User 'myname' deleted."
```
You must have the right username and password to delete the account.

* `/transaction/new`: 
```
curl 0.0.0.0:5000/transaction/new -d '{"from": {"username": "myname", "password": "password"}, "to": "notme", "amount": 100}' -H 'Content-Type: application/json'
```

## Blockchain API


```
curl 0.0.0.0:5001/history
```


This command will get all the blockchain histories from all the mining nodes. Note,
since it takes a bit of time for all the nodes to agree on the blockchain state, the
return of the endpoint might not give chains of equal length. However, all the blocks
that are present across each node should be 100% identical. 

```
curl 0.0.0.0:5001/history/nodes
```


## Kubernetes

```
kubectl apply -f deploy/blockchain_api && \
  kubectl apply -f deploy/db && \
  kubectl apply -f deploy/transaction_api && \
  kubectl apply -f deploy/node
```

```
kubectl delete -f deploy/blockchain_api && \
  kubectl delete -f deploy/db && \
  kubectl delete -f deploy/transaction_api && \
  kubectl delete -f deploy/node
```