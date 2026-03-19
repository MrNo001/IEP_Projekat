"""
Blockchain interface routes for personal/testing use: check balances,
create accounts, send wei. Use to verify that wei was successfully
transmitted via the Payment contract (e.g. after pay() or owner withdrawals).

Account indexes: The chain does not assign indexes to accounts. The "index"
(reflected in fund_from_account_index and in GET /blockchain/accounts) is
the position in the list returned by the RPC eth_accounts. Dev nodes
(Ganache, Hardhat, etc.) pre-create a fixed set of accounts and expose them
via eth_accounts; index 0 is the first, index 1 the second, etc. On
mainnet or nodes that don't manage keys, eth_accounts is often empty.
"""
from __future__ import annotations

import secrets

from flask import Blueprint, jsonify, request
from web3 import Account, HTTPProvider, Web3

from config import Config

from models import Order

bp = Blueprint("blockchain_interface", __name__, url_prefix="/blockchain")


def _web3() -> Web3:
    if not Config.PROVIDER_URL:
        raise RuntimeError("PROVIDER_URL not configured")
    return Web3(HTTPProvider(Config.PROVIDER_URL))


@bp.get("/owner")
def get_owner_address():
    """
    GET /blockchain/owner
    Returns the owner address derived from Config.OWNER_PRIVATE_KEY.
    Useful when you have the key but don't know the corresponding address.
    """
    if not Config.OWNER_PRIVATE_KEY:
        return jsonify({"error": "OWNER_PRIVATE_KEY not configured"}), 400
    pk = Config.OWNER_PRIVATE_KEY.strip()
    if not pk.startswith("0x"):
        pk = "0x" + pk
    try:
        address = Account.from_key(pk).address
        return jsonify({"address": address, "address_checksum": Web3.to_checksum_address(address)}), 200
    except Exception as e:
        return jsonify({"error": f"Invalid OWNER_PRIVATE_KEY: {e}"}), 400


@bp.get("/test-accounts")
def list_test_accounts_and_balances():
    """
    GET /blockchain/test-accounts
    Returns addresses + balances for the accounts used in blockchain tests:
      - Ganache dev/faucet account: w3.eth.accounts[0] (if present)
      - Owner account: derived from Config.OWNER_PRIVATE_KEY
      - Customer + courier addresses currently stored in Order rows

    This is intended for dev/personal testing, not production usage.
    """
    try:
        w3 = _web3()

        addresses: dict[str, dict] = {}

        # 1) Ganache dev/faucet account (index 0)
        eth_accounts = w3.eth.accounts or []
        if len(eth_accounts) > 0 and Web3.is_address(eth_accounts[0]):
            faucet_addr = Web3.to_checksum_address(eth_accounts[0])
            addresses[faucet_addr] = {"source": "ganache_accounts[0]", "index": 0}

        # 2) Owner address
        if not Config.OWNER_PRIVATE_KEY:
            return jsonify({"error": "OWNER_PRIVATE_KEY not configured"}), 400

        owner_pk = Config.OWNER_PRIVATE_KEY.strip()
        if not owner_pk.startswith("0x"):
            owner_pk = "0x" + owner_pk
        owner_addr = Web3.to_checksum_address(Account.from_key(owner_pk).address)
        addresses[owner_addr] = {"source": "owner_private_key"}

        # 3) Customer + courier addresses stored on backend
        # Orders persist the addresses that tests send (customer_address/courier_address).
        for order in Order.query.all():
            customer_address = getattr(order, "customer_address", None)
            if customer_address is not None and str(customer_address).strip() != "" and Web3.is_address(str(customer_address)):
                ca = Web3.to_checksum_address(str(customer_address))
                addresses.setdefault(ca, {"source": "customer_address_on_orders"})

            courier_address = getattr(order, "courier_address", None)
            if courier_address is not None and str(courier_address).strip() != "" and Web3.is_address(str(courier_address)):
                qa = Web3.to_checksum_address(str(courier_address))
                addresses.setdefault(qa, {"source": "courier_address_on_orders"})

        # Fetch balances
        result = []
        for addr, meta in addresses.items():
            balance_wei = w3.eth.get_balance(addr)
            result.append({
                "address": addr,
                "balance_wei": balance_wei,
                "balance_ether": str(w3.from_wei(balance_wei, "ether")),
                **meta,
            })

        return jsonify({"accounts": result, "count": len(result)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.get("/accounts")
def list_accounts():
    """
    GET /blockchain/accounts
    Returns all addresses known to the node (eth_accounts) and their wei
    balance. Only dev nodes (Ganache, Hardhat, etc.) typically expose a
    non-empty list; production nodes often return [].
    """
    try:
        w3 = _web3()
        addresses = w3.eth.accounts
        result = []
        for index, address in enumerate(addresses):
            balance_wei = w3.eth.get_balance(address)
            result.append({
                "index": index,
                "address": address,
                "balance_wei": balance_wei,
                "balance_ether": str(w3.from_wei(balance_wei, "ether")),
            })
        return jsonify({"accounts": result, "count": len(result)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.get("/balance")
def get_balance():
    """
    GET /blockchain/balance?address=0x...
    Returns wei balance for the given address.
    """
    address = request.args.get("address")
    if not address:
        return jsonify({"error": "Missing query parameter: address"}), 400
    if not Web3.is_address(address):
        return jsonify({"error": "Invalid address"}), 400
    try:
        w3 = _web3()
        balance_wei = w3.eth.get_balance(Web3.to_checksum_address(address))
        return jsonify({
            "address": address,
            "balance_wei": balance_wei,
            "balance_ether": str(w3.from_wei(balance_wei, "ether")),
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.post("/account")
def create_account():
    """
    POST /blockchain/account
    Creates a new account (address + private_key). For testing only.
    Optionally pass JSON { "fund_from_account_index": 0, "fund_wei": 1000000 }
    to fund the new account from the provider's accounts[0] (e.g. dev chain).
    """
    body = request.get_json(silent=True) or {}
    fund_index = body.get("fund_from_account_index")
    fund_wei = body.get("fund_wei")

    private_key = "0x" + secrets.token_hex(32)
    account = Account.from_key(private_key)
    address = account.address

    out = {"address": address, "private_key": private_key}

    if fund_wei is not None and fund_index is not None:
        try:
            w3 = _web3()
            accounts = w3.eth.accounts
            if fund_index < 0 or fund_index >= len(accounts):
                return jsonify({"error": f"Account index {fund_index} out of range (0..{len(accounts)-1})"}), 400
            tx = {
                "from": accounts[fund_index],
                "to": address,
                "value": int(fund_wei),
                "gas": 21000,
                "gasPrice": 1,
            }
            tx_hash = w3.eth.send_transaction(tx)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
            out["fund_tx_hash"] = tx_hash.hex()
            out["fund_receipt_status"] = receipt.get("status")
        except Exception as e:
            return jsonify({"error": f"Fund failed: {e}", "account": out}), 500

    return jsonify(out), 200


@bp.post("/send")
def send_wei():
    """
    POST /blockchain/send
    JSON: { "from_private_key": "0x...", "to_address": "0x...", "value_wei": 123 }
    Sends value_wei from the account derived from from_private_key to to_address.
    Returns tx hash and receipt status.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    pk = data.get("from_private_key")
    to_addr = data.get("to_address")
    value_wei = data.get("value_wei")

    if not pk or not to_addr or value_wei is None:
        return jsonify({"error": "Missing from_private_key, to_address, or value_wei"}), 400
    if not Web3.is_address(to_addr):
        return jsonify({"error": "Invalid to_address"}), 400

    try:
        w3 = _web3()
        account = Account.from_key(pk)
        to_checksum = Web3.to_checksum_address(to_addr)
        nonce = w3.eth.get_transaction_count(account.address)
        tx = {
            "from": account.address,
            "to": to_checksum,
            "value": int(value_wei),
            "gas": 21000,
            "gasPrice": 1,
            "nonce": nonce,
            "chainId": w3.eth.chain_id,
        }
        signed = w3.eth.account.sign_transaction(tx, pk)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        return jsonify({
            "tx_hash": tx_hash.hex(),
            "from_address": account.address,
            "to_address": to_addr,
            "value_wei": int(value_wei),
            "status": receipt.get("status"),
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.get("/transaction/<tx_hash>")
def get_transaction(tx_hash: str):
    """
    GET /blockchain/transaction/<tx_hash>
    Returns transaction and receipt for the given hash (for debugging).
    """
    if not tx_hash or not tx_hash.startswith("0x"):
        return jsonify({"error": "Invalid tx hash"}), 400
    try:
        w3 = _web3()
        tx = w3.eth.get_transaction(tx_hash)
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        if not tx or not receipt:
            return jsonify({"error": "Transaction not found"}), 404
        return jsonify({
            "transaction": {
                "from": tx.get("from"),
                "to": tx.get("to"),
                "value": tx.get("value"),
                "gas": tx.get("gas"),
                "blockNumber": tx.get("blockNumber"),
            },
            "receipt": {
                "status": receipt.get("status"),
                "blockNumber": receipt.get("blockNumber"),
                "gasUsed": receipt.get("gasUsed"),
            },
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
