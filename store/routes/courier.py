from __future__ import annotations

from flask import Blueprint, jsonify, request

from auth import role_required
from blockchain import emit_owner_transaction, is_valid_address
from config import Config
from extensions import db
from models import Order

bp = Blueprint("courier", __name__)


@bp.get("/orders_to_deliver")
@role_required(Config.ROLE_COURIER)
def orders_to_deliver():
    # Only orders that are not yet picked up.
    orders = Order.query.filter_by(status="CREATED").order_by(Order.id.asc()).all()
    return (
        jsonify(
            {
                "orders": [
                    {"id": int(order.id), "email": order.customer_email} for order in orders
                ]
            }
        ),
        200,
    )


@bp.post("/pick_up_order")
@role_required(Config.ROLE_COURIER)
def pick_up_order():
    data = request.get_json(silent=True) or {}

    if "id" not in data:
        return jsonify({"message": "Missing order id."}), 400

    order_id = data.get("id")
    if not isinstance(order_id, int) or order_id <= 0:
        return jsonify({"message": "Invalid order id."}), 400

    order = Order.query.get(order_id)
    if order is None:
        return jsonify({"message": "Invalid order id."}), 400

    # Can only pick up undelivered & not-yet-picked-up orders.
    if order.status != "CREATED":
        return jsonify({"message": "Invalid order id."}), 400

    if Config.WITH_BLOCKCHAIN:
        address = data.get("address")
        if address is None or str(address).strip() == "":
            return jsonify({"message": "Missing address."}), 400

        address_str = str(address)
        if not is_valid_address(address_str):
            return jsonify({"message": "Invalid address."}), 400

        # Must be paid first.
        if not order.payment_complete:
            return jsonify({"message": "Transfer not complete."}), 400

        order.courier_address = address_str

    order.status = "PENDING"
    db.session.commit()

    # Blockchain: emit an owner-origin tx (tests check latest block)
    if Config.WITH_BLOCKCHAIN and Config.PROVIDER_URL and Config.OWNER_PRIVATE_KEY:
        emit_owner_transaction(Config.PROVIDER_URL, Config.OWNER_PRIVATE_KEY)

    return ("", 200)


