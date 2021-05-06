# Simple Blockchain 

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
```
curl 0.0.0.0:5000/user/new -d '{"username": "myname", "password": "password"}' -H 'Content-Type: application/json'
```

* `/user/delete`: 
```
curl 0.0.0.0:5000/user/delete?username=myname'
```

* `/transaction/new`: 
```
curl 0.0.0.0:5000/transaction/new -d '{"from": {"username": "myname", "password": "password"}, "to": "notme", "amount": 100}' -H 'Content-Type: application/json'
```

## Blockchain API


```
curl 0.0.0.0:5001/history
```


```
curl 0.0.0.0:5001/history/nodes
```
