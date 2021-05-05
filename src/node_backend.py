import requests

NODE_IDX = 0


class FullNode:
    """This is a full node object."""

    def __init__(self):
        self.node_idx = NODE_IDX
        self.ledger_size = 2
        self.ledger = []
        # If both of the above are true, send the transaction to the network
        requests.get(f"http://0.0.0.0:5001/node/new?node_idx={self.node_idx}")

    def update_ledger(self, transaction):
        self.ledger.append(transaction)

    def mine_block(self):
        print("MINING")
