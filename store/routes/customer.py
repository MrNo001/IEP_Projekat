from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from auth import role_required
from blockchain import build_invoice_transaction, emit_owner_transaction, is_valid_address
from config import Config
from extensions import db
from models import Category, Order, OrderItem, Product


bp = Blueprint("customer", __name__)


@bp.get("/search")
@role_required(Config.ROLE_CUSTOMER)
def customer_search():
    name_param = request.args.get("name")
    category_param = request.args.get("category")

    query = Product.query

    if name_param is not None and name_param != "":
        query = query.filter(Product.name.contains(name_param))

    if category_param is not None and category_param != "":
        try:
            category_id = int(category_param)
            category_name = f"Category{category_id}"
            query = query.join(Product.categories).filter(Category.name == category_name)
        except Exception:
            return jsonify({"categories": [], "products": []}), 200

    products = query.all()

    products_payload = []
    categories_set: set[str] = set()
    for product in products:
        category_names = [c.name for c in product.categories.all()]
        for c in category_names:
            categories_set.add(c)
        products_payload.append(
            {
                "categories": category_names,
                "id": int(product.id),
                "name": product.name,
                "price": float(product.price),
            }
        )

    return jsonify({"categories": list(categories_set), "products": products_payload}), 200


@bp.post("/order")
@role_required(Config.ROLE_CUSTOMER)
def customer_order():
    data = request.get_json(silent=True) or {}

    if "requests" not in data:
        return jsonify({"message": "Field requests is missing."}), 400

    requests_list = data.get("requests")
    if not isinstance(requests_list, list):
        return jsonify({"message": "Field requests is missing."}), 400

    if Config.WITH_BLOCKCHAIN:
        address = data.get("address")
        if address is None or str(address).strip() == "":
            return jsonify({"message": "Field address is missing."}), 400
        if not is_valid_address(str(address)):
            return jsonify({"message": "Invalid address."}), 400

    normalized: list[tuple[Product, int]] = []
    for idx, req in enumerate(requests_list):
        if not isinstance(req, dict):
            req = {}

        if "id" not in req:
            return jsonify({"message": f"Product id is missing for request number {idx}."}), 400
        if "quantity" not in req:
            return jsonify({"message": f"Product quantity is missing for request number {idx}."}), 400

        prod_id = req.get("id")
        qty = req.get("quantity")

        if not isinstance(prod_id, int) or prod_id <= 0:
            return jsonify({"message": f"Invalid product id for request number {idx}."}), 400

        if not isinstance(qty, int) or qty <= 0:
            return jsonify({"message": f"Invalid product quantity for request number {idx}."}), 400

        product = Product.query.get(prod_id)
        if product is None:
            return jsonify({"message": f"Invalid product for request number {idx}."}), 400

        normalized.append((product, qty))

    customer_email = get_jwt_identity() if Config.WITH_AUTHENTICATION else "jane@gmail.com"

    total = Decimal("0")
    order = Order(
        customer_email=customer_email,
        total_price=Decimal("0"),
        status="CREATED",
        customer_address=str(data.get("address")) if Config.WITH_BLOCKCHAIN else None,
        payment_complete=False,
    )
    db.session.add(order)
    db.session.flush()

    for product, qty in normalized:
        price = Decimal(str(product.price))
        total += price * qty
        db.session.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=qty,
                price_at_time=price,
            )
        )

    order.total_price = total
    db.session.commit()

    if Config.WITH_BLOCKCHAIN and Config.PROVIDER_URL and Config.OWNER_PRIVATE_KEY:
        emit_owner_transaction(Config.PROVIDER_URL, Config.OWNER_PRIVATE_KEY)

    return jsonify({"id": int(order.id)}), 200


@bp.get("/status")
@role_required(Config.ROLE_CUSTOMER)
def customer_status():
    customer_email = get_jwt_identity() if Config.WITH_AUTHENTICATION else "jane@gmail.com"

    orders = Order.query.filter_by(customer_email=customer_email).order_by(Order.id.asc()).all()

    orders_payload = []
    for order in orders:
        items = (
            db.session.query(OrderItem, Product)
            .join(Product, Product.id == OrderItem.product_id)
            .filter(OrderItem.order_id == order.id)
            .all()
        )

        products_payload = []
        for item, product in items:
            category_names = [c.name for c in product.categories.all()]
            products_payload.append(
                {
                    "categories": category_names,
                    "name": product.name,
                    "price": float(item.price_at_time),
                    "quantity": int(item.quantity),
                }
            )

        orders_payload.append(
            {
                "products": products_payload,
                "price": float(order.total_price),
                "status": order.status,
                "timestamp": order.created_at.isoformat(sep=" ", timespec="seconds"),
            }
        )

    return jsonify({"orders": orders_payload}), 200


@bp.post("/delivered")
@role_required(Config.ROLE_CUSTOMER)
def customer_delivered():
    data = request.get_json(silent=True) or {}

    if "id" not in data:
        return jsonify({"message": "Missing order id."}), 400

    order_id = data.get("id")
    if not isinstance(order_id, int) or order_id <= 0:
        return jsonify({"message": "Invalid order id."}), 400

    order = Order.query.get(order_id)
    if order is None:
        return jsonify({"message": "Invalid order id."}), 400

    if order.status != "PENDING":
        return jsonify({"message": "Delivery not complete."}), 400

    order.status = "COMPLETE"
    db.session.commit()

    if Config.WITH_BLOCKCHAIN and Config.PROVIDER_URL and Config.OWNER_PRIVATE_KEY:
        emit_owner_transaction(Config.PROVIDER_URL, Config.OWNER_PRIVATE_KEY)

    return ("", 200)


@bp.post("/generate_invoice")
@role_required(Config.ROLE_CUSTOMER)
def customer_generate_invoice():
    data = request.get_json(silent=True) or {}

    if "id" not in data:
        return jsonify({"message": "Missing order id."}), 400

    order_id = data.get("id")
    if not isinstance(order_id, int) or order_id <= 0:
        return jsonify({"message": "Invalid order id."}), 400

    order = Order.query.get(order_id)
    if order is None:
        return jsonify({"message": "Invalid order id."}), 400

    address = data.get("address")
    if address is None:
        return jsonify({"message": "Missing address."}), 400

    address_str = str(address)
    if not is_valid_address(address_str):
        return jsonify({"message": "Invalid address."}), 400

    if order.payment_complete:
        return jsonify({"message": "Transfer already complete."}), 400

    order.payment_complete = True
    order.customer_address = address_str
    db.session.commit()

    if not Config.PROVIDER_URL or not Config.OWNER_PRIVATE_KEY:
        return jsonify({"invoice": {}}), 200

    from web3 import Account

    owner_address = Account.from_key(Config.OWNER_PRIVATE_KEY).address
    invoice_tx = build_invoice_transaction(Config.PROVIDER_URL, address_str, owner_address)

    return jsonify({"invoice": invoice_tx}), 200


