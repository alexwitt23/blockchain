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

To run the services locally, please install docker compose. You can scale how many
miners you'd like. This will default to 2 nodes since anything less would be boring.

```
NODES=5 make up
```
All mining logs are written to the `logging` folder. The files are named by node
id.

## Kubernetes

To get started, run:
```
kubectl apply -f deploy/blockchain_api && \
  kubectl apply -f deploy/db && \
  kubectl apply -f deploy/transaction_api && \
  kubectl apply -f deploy/node && \
  kubectl apply -f deploy/debug
```

There are multiple REST APIs in this project, so we'll need to get the Kubernetes
service IPs and add them to the different deployment files.

```
$ kubectl get service
NAME                          TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)          AGE
blockchain-redis-service      ClusterIP   10.101.248.127   <none>        6379/TCP         55m
blockchain-service            ClusterIP   10.110.183.205   <none>        5001/TCP         55m
transaction-service           ClusterIP   10.99.107.3      <none>        5000/TCP         55m
```

* In `deploy/blockchain_api/deployment.yml`, add the `blockchain-redis-service` CLUSTER-IP.
```
env:
- name: "REDIS_IP"
  value: "10.101.248.127"
```

* In `deploy/node/deployment.yml`, add the `blockchain-redis-service` CLUSTER-IP.
```
env:
- name: "REDIS_IP"
  value: "10.101.248.127"
```

* In `deploy/transaction_api/deployment.yml`, add the `blockchain-redis-service` CLUSTER-IP
and the `blockchain-service` CLUSTER-IP.
```
env:
- name: "REDIS_IP"
  value: "10.101.248.127"
- name: "BLOCKCHAIN_IP"
  value: "10.110.183.205"
```

Finally, reapply these services with:

```
kubectl apply -f deploy/blockchain_api && \
  kubectl apply -f deploy/transaction_api && \
  kubectl apply -f deploy/node 
```

NOTE, in real blockchains, each node keeps an isolated copy of the blockchain.
We keep things simple here.


### Kubernetes Usage

Find the debug pod that was created:

```
kubectl get pods
NAME                                                 READY   STATUS             RESTARTS   AGE
blockchain-debug-5cc8cdd65f-j6kqc                    1/1     Running            0          7s
```

Exec into this pod to interact with the APIs:

```
kubectl exec -ti blockchain-debug-5cc8cdd65f-j6kqc -- /bin/bash
```

Now you can follow the API examples below using the right IP for the transaction and
blockchain APIs.

#### Cleanup
```
kubectl delete -f deploy/blockchain_api && \
  kubectl delete -f deploy/db && \
  kubectl delete -f deploy/transaction_api && \
  kubectl delete -f deploy/node && \
  kubectl delete -f deploy/debug
```

## Transaction API

* `/user/new`: 
Create a new user:
```
curl 0.0.0.0:5000/user/new \
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
Send a transaction! The account you need the username and password of your account. You
also need the username of an account that exists.
```
curl 0.0.0.0:5000/transaction/new \
  -d '{"from": {"username": "myname", "password": "password"}, "to": "notme", "amount": 100}' \
  -H 'Content-Type: application/json'

"Transaction added to ledger."
```

Once you execute a transaction, there is no going back. This transaction is sent to the
blockchain network and miners will begin validating it.

## Blockchain API

Query the blockchain history. This will extract shortest chain which is the most
verified chain. 

```
curl 0.0.0.0:5001/history

[
  {
    "hash": "00308d327e99fafbb90f8e9072627d9e3bb708ff805f4abaf5986019a94fd28b", 
    "mined-by": "23822524.065c.4234.8cff.2076a28772b3", 
    "nonce": 108, 
    "previous_hash": "0000000000000000000000000000000000000000000000000000000000000000", 
    "transactions": {
      "b'transaction:2021-05-07T01:20:11.135929'": {
        "amount": 1000, 
        "from": {
          "public-key": "genesis", 
          "signature": "genesis", 
          "username": "genesis"
        }, 
        "timestamp": "2021-05-07T01:20:11.135929", 
        "to": "foo"
      }
    }
  }, 
  {
    "hash": "00011b76cfff4c5c8aaff2e94996fba3a2679cced10c12028b07b22f43a78945", 
    "mined-by": "23822524.065c.4234.8cff.2076a28772b3", 
    "nonce": 430, 
    "previous_hash": "00308d327e99fafbb90f8e9072627d9e3bb708ff805f4abaf5986019a94fd28b", 
    "transactions": {
      "b'transaction:2021-05-07T01:20:30.322384'": {
        "amount": 100, 
        "from": {
          "public-key": "-----BEGIN RSA PUBLIC KEY-----\nMEgCQQDPyFwxRyerCll7BIrbevqQ86zdnfqc5pA0tow/+W3oNbDBbcGlzHdqGZV0\n/On8HLl54ccpl/eFLacXmRNfyJgZAgMBAAE=\n-----END RSA PUBLIC KEY-----\n", 
          "signature": "c\u0012X\u000f\u0004g6<4\u0007)`OB\u0002-b ~jC}R\"#\u0017\u0017S<dr\u00010]io", 
          "username": "myname"
        }, 
        "timestamp": "2021-05-07T01:20:30.322384", 
        "to": "myname"
      }
    }
  }
]
```


This command will get all the blockchain histories from all the mining nodes. Note,
since it takes a bit of time for all the nodes to agree on the blockchain state, the
return of the endpoint might not give chains of equal length. However, all the blocks
that are present across each node should be 100% identical. 

```
curl 0.0.0.0:5001/history/nodes
{
  "61217525.e8c4.405b.9813.dee50079cf15": {
    "block-0": {
      "hash": "00308d327e99fafbb90f8e9072627d9e3bb708ff805f4abaf5986019a94fd28b", 
      "mined-by": "23822524.065c.4234.8cff.2076a28772b3", 
      "nonce": 108, 
      "previous_hash": "0000000000000000000000000000000000000000000000000000000000000000", 
      "transactions": {
        "b'transaction:2021-05-07T01:20:11.135929'": {
          "amount": 1000, 
          "from": {
            "public-key": "genesis", 
            "signature": "genesis", 
            "username": "genesis"
          }, 
          "timestamp": "2021-05-07T01:20:11.135929", 
          "to": "foo"
        }
      }
    }, 
    "block-1": {
      "hash": "00011b76cfff4c5c8aaff2e94996fba3a2679cced10c12028b07b22f43a78945", 
      "mined-by": "23822524.065c.4234.8cff.2076a28772b3", 
      "nonce": 430, 
      "previous_hash": "00308d327e99fafbb90f8e9072627d9e3bb708ff805f4abaf5986019a94fd28b", 
      "transactions": {
        "b'transaction:2021-05-07T01:20:30.322384'": {
          "amount": 100, 
          "from": {
            "public-key": "-----BEGIN RSA PUBLIC KEY-----\nMEgCQQDPyFwxRyerCll7BIrbevqQ86zdnfqc5pA0tow/+W3oNbDBbcGlzHdqGZV0\n/On8HLl54ccpl/eFLacXmRNfyJgZAgMBAAE=\n-----END RSA PUBLIC KEY-----\n", 
            "signature": "c\u0012X\u000f\u0004g6<4\u0007)`OB\u0002-b ~jC}R\"#\u0017\u0017S<dr\u00010]io", 
            "username": "myname"
          }, 
          "timestamp": "2021-05-07T01:20:30.322384", 
          "to": "myname"
        }
      }
    }
  }, 
  "23822524.065c.4234.8cff.2076a28772b3": {
    "block-0": {
      "hash": "00308d327e99fafbb90f8e9072627d9e3bb708ff805f4abaf5986019a94fd28b", 
      "mined-by": "23822524.065c.4234.8cff.2076a28772b3", 
      "nonce": 108, 
      "previous_hash": "0000000000000000000000000000000000000000000000000000000000000000", 
      "transactions": {
        "b'transaction:2021-05-07T01:20:11.135929'": {
          "amount": 1000, 
          "from": {
            "public-key": "genesis", 
            "signature": "genesis", 
            "username": "genesis"
          }, 
          "timestamp": "2021-05-07T01:20:11.135929", 
          "to": "foo"
        }
      }
    }, 
    "block-1": {
      "hash": "00011b76cfff4c5c8aaff2e94996fba3a2679cced10c12028b07b22f43a78945", 
      "mined-by": "23822524.065c.4234.8cff.2076a28772b3", 
      "nonce": 430, 
      "previous_hash": "00308d327e99fafbb90f8e9072627d9e3bb708ff805f4abaf5986019a94fd28b", 
      "transactions": {
        "b'transaction:2021-05-07T01:20:30.322384'": {
          "amount": 100, 
          "from": {
            "public-key": "-----BEGIN RSA PUBLIC KEY-----\nMEgCQQDPyFwxRyerCll7BIrbevqQ86zdnfqc5pA0tow/+W3oNbDBbcGlzHdqGZV0\n/On8HLl54ccpl/eFLacXmRNfyJgZAgMBAAE=\n-----END RSA PUBLIC KEY-----\n", 
            "signature": "c\u0012X\u000f\u0004g6<4\u0007)`OB\u0002-b ~jC}R\"#\u0017\u0017S<dr\u00010]io", 
            "username": "myname"
          }, 
          "timestamp": "2021-05-07T01:20:30.322384", 
          "to": "myname"
        }
      }
    }
  }, 
  "34b61774.c418.4fca.a80a.2616c1163689": {
    "block-0": {
      "hash": "00308d327e99fafbb90f8e9072627d9e3bb708ff805f4abaf5986019a94fd28b", 
      "mined-by": "23822524.065c.4234.8cff.2076a28772b3", 
      "nonce": 108, 
      "previous_hash": "0000000000000000000000000000000000000000000000000000000000000000", 
      "transactions": {
        "b'transaction:2021-05-07T01:20:11.135929'": {
          "amount": 1000, 
          "from": {
            "public-key": "genesis", 
            "signature": "genesis", 
            "username": "genesis"
          }, 
          "timestamp": "2021-05-07T01:20:11.135929", 
          "to": "foo"
        }
      }
    }, 
    "block-1": {
      "hash": "00011b76cfff4c5c8aaff2e94996fba3a2679cced10c12028b07b22f43a78945", 
      "mined-by": "23822524.065c.4234.8cff.2076a28772b3", 
      "nonce": 430, 
      "previous_hash": "00308d327e99fafbb90f8e9072627d9e3bb708ff805f4abaf5986019a94fd28b", 
      "transactions": {
        "b'transaction:2021-05-07T01:20:30.322384'": {
          "amount": 100, 
          "from": {
            "public-key": "-----BEGIN RSA PUBLIC KEY-----\nMEgCQQDPyFwxRyerCll7BIrbevqQ86zdnfqc5pA0tow/+W3oNbDBbcGlzHdqGZV0\n/On8HLl54ccpl/eFLacXmRNfyJgZAgMBAAE=\n-----END RSA PUBLIC KEY-----\n", 
            "signature": "c\u0012X\u000f\u0004g6<4\u0007)`OB\u0002-b ~jC}R\"#\u0017\u0017S<dr\u00010]io", 
            "username": "myname"
          }, 
          "timestamp": "2021-05-07T01:20:30.322384", 
          "to": "myname"
        }
      }
    }
  }
}
```
