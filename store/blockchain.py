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
