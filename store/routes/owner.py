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

    # IMPORTANT (tests): validate CSV structure/price FIRST, and only then check duplicates.
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

    # Only after file format/price validation succeeds, enforce unique product names vs DB.
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


