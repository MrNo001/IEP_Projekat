from __future__ import annotations

from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from sqlalchemy import case, func

from auth import role_required
from config import Config
from extensions import db
from models import Category, Order, OrderItem, Product, product_categories

bp = Blueprint("owner", __name__)


@bp.post("/update")
@role_required(Config.ROLE_OWNER)
def owner_update():
    if "file" not in request.files:
        return jsonify({"message": "Field file is missing."}), 400

    file = request.files["file"]
    content = file.read().decode("utf-8", errors="replace")
    lines = [line for line in content.splitlines() if line != ""]

    parsed_rows: list[tuple[int, list[str], str, Decimal]] = []

    # IMPORTANT: Validate CSV structure/price FIRST, and only then check duplicates.
    for idx, line in enumerate(lines):
        parts = line.split(",")
        if len(parts) != 3:
            return jsonify({"message": f"Incorrect number of values on line {idx}."}), 400

        categories_raw, product_name, price_raw = parts[0].strip(), parts[1].strip(), parts[2].strip()

        try:
            price = Decimal(price_raw)
        except (InvalidOperation, ValueError):
            return jsonify({"message": f"Incorrect price on line {idx}."}), 400

        if price <= 0:
            return jsonify({"message": f"Incorrect price on line {idx}."}), 400

        category_names = [c.strip() for c in categories_raw.split("|") if c.strip()]
        parsed_rows.append((idx, category_names, product_name, price))


    for _idx, _category_names, product_name, _price in parsed_rows:
        existing = Product.query.filter_by(name=product_name).first()
        if existing is not None:
            return jsonify({"message": f"Product {product_name} already exists."}), 400

    for _idx, category_names, product_name, price in parsed_rows:
        product = Product(name=product_name, price=price)

        for category_name in category_names:
            category = Category.query.filter_by(name=category_name).first()
            if category is None:
                category = Category(name=category_name)
                db.session.add(category)
                db.session.flush()
            product.categories.append(category)

        db.session.add(product)

    db.session.commit()
    return ("", 200)




@bp.get("/product_statistics")
@role_required(Config.ROLE_OWNER)
def product_statistics():
    sold_expr = func.coalesce(
        func.sum(case((Order.status == "COMPLETE", OrderItem.quantity), else_=0)), 0
    )
    waiting_expr = func.coalesce(
        func.sum(case((Order.status != "COMPLETE", OrderItem.quantity), else_=0)), 0
    )

    rows = (
        db.session.query(
            Product.name.label("name"),
            sold_expr.label("sold"),
            waiting_expr.label("waiting"),
        )
        .select_from(Product)
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, OrderItem.order_id == Order.id)
        .group_by(Product.id)
        .all()
    )

    return (
        jsonify(
            {
                "statistics": [
                    {"name": name, "sold": int(sold), "waiting": int(waiting)}
                    for (name, sold, waiting) in rows
                ]
            }
        ),
        200,
    )


@bp.get("/category_statistics")
@role_required(Config.ROLE_OWNER)
def category_statistics():
    sold_expr = func.coalesce(
        func.sum(case((Order.status == "COMPLETE", OrderItem.quantity), else_=0)), 0
    )

    rows = (
        db.session.query(Category.name.label("name"), sold_expr.label("sold"))
        .select_from(Category)
        .outerjoin(product_categories, product_categories.c.category_id == Category.id)
        .outerjoin(Product, product_categories.c.product_id == Product.id)
        .outerjoin(OrderItem, OrderItem.product_id == Product.id)
        .outerjoin(Order, OrderItem.order_id == Order.id)
        .group_by(Category.id)
        .all()
    )

    sorted_names = [name for (name, _sold) in sorted(rows, key=lambda r: (-int(r[1]), r[0]))]

    return jsonify({"statistics": sorted_names}), 200



# @bp.get("/product_statistics")
# @role_required(Config.ROLE_OWNER)
# def product_statistics():
#     # Fetch order rows with product name, status, and quantity.
#     rows = (
#         db.session.query(Product.name, Order.status, OrderItem.quantity)
#         .join(OrderItem, OrderItem.product_id == Product.id)
#         .join(Order, OrderItem.order_id == Order.id)
#         .all()
#     )

#     # Build per-product counters.
#     by_product: dict[str, dict[str, int]] = {}
#     for name, status, quantity in rows:
#         if name not in by_product:
#             by_product[name] = {"sold": 0, "waiting": 0}

#         if status == "COMPLETE":
#             by_product[name]["sold"] += int(quantity)
#         else:
#             by_product[name]["waiting"] += int(quantity)

#     # Convert counters into response format.
#     statistics = []
#     for name, counters in by_product.items():
#         statistics.append(
#             {"name": name, "sold": counters["sold"], "waiting": counters["waiting"]}
#         )

#     return jsonify({"statistics": statistics}), 200


# @bp.get("/category_statistics")
# @role_required(Config.ROLE_OWNER)
# def category_statistics():
#     # Load all categories so empty categories are still included.
#     categories = Category.query.all()
#     sold_by_category: dict[str, int] = {category.name: 0 for category in categories}

#     # Load only sold order items (from COMPLETE orders).
#     sold_items = (
#         OrderItem.query.join(Order, OrderItem.order_id == Order.id)
#         .filter(Order.status == "COMPLETE")
#         .all()
#     )

#     # Add sold quantity to every category of each sold product.
#     for item in sold_items:
#         for category in item.product.categories.all():
#             sold_by_category[category.name] += int(item.quantity)

#     # Sort by sold desc, then category name asc.
#     sorted_names = [
#         name
#         for name, _sold in sorted(
#             sold_by_category.items(), key=lambda row: (-row[1], row[0])
#         )
#     ]

#     return jsonify({"statistics": sorted_names}), 200


