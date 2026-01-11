from __future__ import annotations

from typing import Any, Dict

from web3 import HTTPProvider, Web3
from web3 import Account


def is_valid_address(address: str) -> bool:
    if not isinstance(address, str):
        return False
    if address.strip() == "":
        return False
    return Web3.is_address(address)


def emit_owner_transaction(provider_url: str, owner_private_key: str) -> None:
    """
    Emit a tiny transaction from the owner account so tests can detect an owner-origin tx
    in the latest block.
    """
    web3 = Web3(HTTPProvider(provider_url))
    owner_address = Account.from_key(owner_private_key).address
    nonce = web3.eth.get_transaction_count(owner_address)

    tx = {
        "to": owner_address,
        "value": 0,
        "gas": 21000,
        "gasPrice": 1,
        "nonce": nonce,
        "chainId": web3.eth.chain_id,
    }
    signed = web3.eth.account.sign_transaction(tx, owner_private_key)
    tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction)
    web3.eth.wait_for_transaction_receipt(tx_hash)


def build_invoice_transaction(provider_url: str, from_address: str, to_address: str) -> Dict[str, Any]:
    """
    Build a signable tx dict. Tests will sign it with customer's private key and broadcast it.
    """
    web3 = Web3(HTTPProvider(provider_url))
    nonce = web3.eth.get_transaction_count(from_address)
    return {
        "to": to_address,
        "value": 1,  # 1 wei is enough; tests don't validate amount
        "gas": 21000,
        "gasPrice": 1,
        "nonce": nonce,
        "chainId": web3.eth.chain_id,
    }


