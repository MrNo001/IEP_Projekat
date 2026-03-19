from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

from web3 import HTTPProvider, Web3
from web3 import Account

from config import Config
from models import Order


@dataclass(frozen=True)
class ContractArtifact:
    abi: Any
    bytecode: str


def _load_artifact() -> ContractArtifact:
    artifact_path = Path(__file__).parent / "contracts" / "Payment.artifact.json"
    data = json.loads(artifact_path.read_text(encoding="utf-8"))
    return ContractArtifact(abi=data["abi"], bytecode=data["bin"])


def _web3() -> Web3:
    return Web3(HTTPProvider(Config.PROVIDER_URL))


def _wait_for_chain(max_attempts: int = 60, sleep_seconds: float = 1.0) -> None:
    last_err: Exception | None = None
    for _ in range(max_attempts):
        try:
            w3 = _web3()
            _ = w3.eth.chain_id
            return
        except Exception as e:
            last_err = e
            time.sleep(sleep_seconds)
    raise RuntimeError("Blockchain not reachable") from last_err


def _get_owner_address() -> str:
    return Account.from_key(Config.OWNER_PRIVATE_KEY).address


def _ensure_blockchain() -> None:
    if not Config.WITH_BLOCKCHAIN:
        raise RuntimeError("Blockchain is disabled")
    if not Config.PROVIDER_URL or not Config.OWNER_PRIVATE_KEY:
        raise RuntimeError("Missing PROVIDER_URL / OWNER_PRIVATE_KEY")


def deploy_contract_for_order(order_id: int, price_wei: int, customer_address: str) -> str:
    """
    Deploy a new Payment contract for this order, call initialize(price_wei, customer_address).
    Price in wei must be order_total_price * 100 (per spec). Returns contract address.
    """
    _ensure_blockchain()
    _wait_for_chain()
    w3 = _web3()
    artifact = _load_artifact()
    owner_address = _get_owner_address()
    nonce = w3.eth.get_transaction_count(owner_address)
    contract_factory = w3.eth.contract(abi=artifact.abi, bytecode=artifact.bytecode)
    tx = contract_factory.constructor().build_transaction(
        {
            "from": owner_address,
            "nonce": nonce,
            "gas": 5_000_000,
            "gasPrice": 1,
            "chainId": w3.eth.chain_id,
        }
    )
    signed = w3.eth.account.sign_transaction(tx, Config.OWNER_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    address = receipt.contractAddress
    contract = w3.eth.contract(address=address, abi=artifact.abi)
    owner_send_contract_tx(contract.functions.initialize(price_wei, customer_address))
    return address


def get_contract_at_address(contract_address: str) -> Tuple[Web3, Any]:
    """Return (web3, contract_instance) for an already-deployed contract."""
    _ensure_blockchain()
    _wait_for_chain()
    w3 = _web3()
    artifact = _load_artifact()
    contract = w3.eth.contract(address=contract_address, abi=artifact.abi)
    return w3, contract


def owner_send_contract_tx(function_call) -> None:
    """
    Send a state-changing contract tx signed by owner.
    `function_call` is like contract.functions.initialize(...) or .pickUp(...) or .deliver(...)
    """
    _ensure_blockchain()
    _wait_for_chain()
    w3 = _web3()
    owner_address = _get_owner_address()
    nonce = w3.eth.get_transaction_count(owner_address)
    tx = function_call.build_transaction(
        {
            "from": owner_address,
            "nonce": nonce,
            "gas": 500_000,
            "gasPrice": 1,
            "chainId": w3.eth.chain_id,
        }
    )
    signed = w3.eth.account.sign_transaction(tx, Config.OWNER_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash)


def build_customer_pay_tx(order_id: int, customer_address: str, value_wei: int) -> Dict[str, Any]:
    order = Order.query.get(order_id)
    if not order or not order.contract_address:
        raise RuntimeError("Order or contract address not found")
    w3, contract = get_contract_at_address(order.contract_address)
    nonce = w3.eth.get_transaction_count(customer_address)
    tx = contract.functions.pay().build_transaction(
        {
            "from": customer_address,
            "nonce": nonce,
            "value": value_wei,
            "gas": 200_000,
            "gasPrice": 1,
            "chainId": w3.eth.chain_id,
        }
    )
    return tx


def is_order_paid_onchain(order_id: int) -> bool:
    order = Order.query.get(order_id)
    if not order or not order.contract_address:
        return False
    _w3, contract = get_contract_at_address(order.contract_address)
    return bool(contract.functions.isPaid().call())
