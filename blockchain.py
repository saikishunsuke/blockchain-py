from urllib.parse import urlparse
import hashlib
from uuid import uuid4
import json
import time
import requests
from flask import Flask, jsonify, request


class BlockChain:
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()
        self.new_block(previous_hash=1, proof=100)

    def new_transactions(self, sender, recipient, amount):
        """
        新しいトランザクションを発行する。
        :param sender: <str> 送信者のアドレス
        :param recipient: <str> 受信者のアドレス
        :param amount: <int> 送信額
        :return: <int> このトランザクションを含むブロックのアドレス
        """
        self.current_transactions.append({
            "sender": sender,
            "recipient": recipient,
            "amount": amount
        })
        return self.last_block['index'] + 1

    def new_block(self, proof, previous_hash=None):
        """
        ブロックチェーンに新しいブロックを作成する
        :param proof: <int> POFアルゴリズムから得られるproof
        :param previous_hash: <int> (option) 前のブロックのハッシュ
        :return: <dict> 新しいブロック
        """

        block = {
            'index': len(self.chain) + 1,
            'timestamp': time.time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash
        }
        self.current_transactions = []
        self.chain.append(block)
        return block

    @property
    def last_block(self):
        """
        チェーン最後のブロックをリターンする
        """
        return self.chain[-1]

    @staticmethod
    def hash(block):
        """
        ブロックのハッシュを作る
        :param block: <dict> ブロック
        :return: <str> ハッシュ
        """
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def proof_of_work(self, past_proof):
        """
        シンプルなPoFのアルゴリズム
        :param past_proof: <int> 前のブロックのproof
        :return: <int> proof
        """
        proof = 0
        while not self._valid_proof(past_proof, proof):
            proof += 1

        return proof

    @staticmethod
    def _valid_proof(past_proof, proof):
        """
        proofが有効なものかどうかの判定
        :param past_proof: <int> 前のブロックのproof
        :param proof: <int> proofの候補
        :return: <bool> 有効か否か
        """
        guess = f'{past_proof, proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"

    def register_node(self, node_address):
        """
        ノードリストに新しいノードを追加する
        :param node_address: <str> ノードのアドレス
        :return: None
        """
        parsed_url = urlparse(node_address)
        self.nodes.add(node_address)

    def chain_is_valid(self, chain):
        """
        ブロックチェーンが正しいかを判定する
        :param chain: <list> ブロックチェーン
        :return: <bool> ブロックチェーンが正しいか否か
        """
        for last_index, current_block in enumerate(chain):
            last_block = chain[last_index]
            print(f'{last_block}')
            print(f'{current_block}')
            print('\n----------------\n')

            if current_block['previous_hash'] != self.hash(last_block):
                return False

            if not self._valid_proof(last_block['proof'], current_block['proof']):
                return False

        return True

    def resolve_conflicts(self):
        """
        コンフリクトを解消する
        :return: <bool> 自らのチェーンが書き換えられればTrue
        """
        max_length = len(self.chain)
        new_chain = None
        for node in self.nodes:
            response = requests.get(f'http://{node}/chain')
            if response.status_code != 200:
                continue
            length = response.json()['length']
            chain = response.json()['chain']
            if length > max_length and self.chain_is_valid(chain):
                max_length = length
                new_chain = chain
        if new_chain:
            self.chain = new_chain
            return True
        return False


app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
node_identifier = str(uuid4()).replace('-', '')
blockchain = BlockChain()


@app.route('/', methods=['GET'])
def main_page():
    return "Welcome to my BlockChain"


@app.route('/transactions/new', methods=['POST'])
def new_transactions():
    values = request.get_json()
    require = ['sender', 'recipient', 'amount']
    if not all(k in values for k in require):
        return "Missing Values", 400
    index = blockchain.new_transactions(values['sender'], values['recipient'], values['amount'])
    response = {'message': f'トランザクションはブロック {index} に追加されました.'}
    return jsonify(response), 201


@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    blockchain.new_transactions(
        "0",
        node_identifier,
        1
    )
    block = blockchain.new_block(proof)
    response = {
        'message': "新しいブロックを採掘しました",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash']
    }
    return jsonify(response), 200


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain)
    }
    return jsonify(response), 200


@app.route('/nodes/register', methods=['POST'])
def register_node():
    values = request.get_json()
    nodes = values.get('nodes')
    if nodes is None:
        return "Error, 有効でないノードのリストです", 400
    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': '新しいノードが作成されました',
        'total_nodes': list(blockchain.nodes)
    }

    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    if blockchain.resolve_conflicts():
        message = "チェーンが置き換えられました"
    else:
        message = "チェーンが確認されました"
    response = {
        'message': message,
        'chain': blockchain.chain
    }
    return jsonify(response), 200


if __name__ == '__main__':
    app.run(host='localhost', port=5000)