from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

from web3 import HTTPProvider, Web3
from web3 import Account

from config import Config
from extensions import db
from models import BlockchainState


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


def get_or_deploy_payment_contract() -> Tuple[Web3, Any]:
    """
    Returns (web3, contract_instance). Contract address is stored in DB (BlockchainState id=1).
    """
    if not Config.WITH_BLOCKCHAIN:
        raise RuntimeError("Blockchain is disabled")

    if not Config.PROVIDER_URL or not Config.OWNER_PRIVATE_KEY:
        raise RuntimeError("Missing PROVIDER_URL / OWNER_PRIVATE_KEY")

    _wait_for_chain()
    w3 = _web3()
    artifact = _load_artifact()

    state = BlockchainState.query.get(1)
    if state is not None and state.contract_address:
        contract = w3.eth.contract(address=state.contract_address, abi=artifact.abi)
        return w3, contract

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

    if state is None:
        state = BlockchainState(id=1, contract_address=address)
        db.session.add(state)
    else:
        state.contract_address = address
    db.session.commit()

    contract = w3.eth.contract(address=address, abi=artifact.abi)
    return w3, contract


def owner_send_contract_tx(function_call) -> None:
    """
    Send a state-changing contract tx signed by owner.
    `function_call` is like contract.functions.createOrder(...)
    """
    w3, _ = get_or_deploy_payment_contract()
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
    w3, contract = get_or_deploy_payment_contract()
    nonce = w3.eth.get_transaction_count(customer_address)
    tx = contract.functions.pay(order_id).build_transaction(
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
    _w3, contract = get_or_deploy_payment_contract()
    return bool(contract.functions.isPaid(order_id).call())


