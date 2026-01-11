import time

from decimal import Decimal, InvalidOperation

from flask import Flask, jsonify, request
from sqlalchemy import case, func, text

from config import Config
from auth import register_jwt_error_handlers, role_required
from extensions import db, jwt
from models import Category, Product, Order, OrderItem  


app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
jwt.init_app(app)
register_jwt_error_handlers(jwt)


def _wait_for_db(max_attempts: int = 60, sleep_seconds: float = 1.0) -> None:
    last_err: Exception | None = None
    for _ in range(max_attempts):
        try:
            db.session.execute(text("SELECT 1"))
            return
        except Exception as e:
            last_err = e
            time.sleep(sleep_seconds)
    raise RuntimeError("Database not reachable") from last_err


def _init_db() -> None:
    # Needs an app context for Flask-SQLAlchemy
    with app.app_context():
        _wait_for_db()
        db.create_all()


@app.get("/")
def health():
    return (
        jsonify(
            {
                "message": "Store service is healthy",
                "mode": Config.SERVICE_MODE,
            }
        ),
        200,
    )


@app.post("/update")
@role_required(Config.ROLE_OWNER)
def owner_update():
    if "file" not in request.files:
        return jsonify({"message": "Field file is missing."}), 400

    file = request.files["file"]
    content = file.read().decode("utf-8", errors="replace")
    # Splitlines handles trailing newline nicely.
    lines = [line for line in content.splitlines() if line != ""]

    parsed_rows: list[tuple[int, list[str], str, Decimal]] = []

    # First pass: validate syntax/price + duplicates against DB (atomic-ish behavior for tests)
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

        existing = Product.query.filter_by(name=product_name).first()
        if existing is not None:
            return jsonify({"message": f"Product {product_name} already exists."}), 400

        category_names = [c.strip() for c in categories_raw.split("|") if c.strip()]
        parsed_rows.append((idx, category_names, product_name, price))

    # Second pass: insert
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


@app.get("/product_statistics")
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


@app.get("/category_statistics")
@role_required(Config.ROLE_OWNER)
def category_statistics():
    from models import product_categories  # avoid circular at import time

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

    # Tests expect ordering by sold desc, then name asc.
    sorted_names = [name for (name, _sold) in sorted(rows, key=lambda r: (-int(r[1]), r[0]))]

    return jsonify({"statistics": sorted_names}), 200


if __name__ == "__main__":
    _init_db()
    app.run(host="0.0.0.0", port=Config.PORT, debug=False)