from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import case, func

from auth import role_required
from config import Config
from extensions import db
from models import Order, OrderItem, Product

bp = Blueprint("product_stats", __name__, url_prefix="/product_stats")


def _parse_limit(default: int = 5, max_limit: int = 50) -> int | None:
    raw = request.args.get("limit", None)
    if raw is None:
        return default
    try:
        limit = int(raw)
        if limit <= 0:
            return None
        return min(limit, max_limit)
    except Exception:
        return None


@bp.get("/summary")
@role_required(Config.ROLE_OWNER)
def summary():
    """
    GET /product_stats/summary
    Returns per-product sold/waiting quantities and simple revenue stats.
    "Sold" = Order.status == "COMPLETE".
    """
    sold_qty_expr = func.coalesce(
        func.sum(case((Order.status == "COMPLETE", OrderItem.quantity), else_=0)),
        0,
    )
    waiting_qty_expr = func.coalesce(
        func.sum(case((Order.status != "COMPLETE", OrderItem.quantity), else_=0)),
        0,
    )
    revenue_expr = func.coalesce(
        func.sum(
            case(
                (
                    Order.status == "COMPLETE",
                    OrderItem.quantity * OrderItem.price_at_time,
                ),
                else_=0,
            )
        ),
        0,
    )
    avg_price_expr = func.coalesce(
        revenue_expr / func.nullif(sold_qty_expr, 0),
        0,
    )

    rows = (
        db.session.query(
            Product.id.label("id"),
            Product.name.label("name"),
            sold_qty_expr.label("sold_quantity"),
            waiting_qty_expr.label("waiting_quantity"),
            revenue_expr.label("revenue"),
            avg_price_expr.label("avg_unit_price"),
        )
        .outerjoin(OrderItem, OrderItem.product_id == Product.id)
        .outerjoin(Order, Order.id == OrderItem.order_id)
        .group_by(Product.id, Product.name)
        .order_by(Product.id.asc())
        .all()
    )

    products_payload = []
    for r in rows:
        products_payload.append(
            {
                "id": int(r.id),
                "name": r.name,
                "sold_quantity": int(r.sold_quantity),
                "waiting_quantity": int(r.waiting_quantity),
                "revenue": float(r.revenue),
                "avg_unit_price": float(r.avg_unit_price),
            }
        )

    return jsonify({"products": products_payload, "count": len(products_payload)}), 200


@bp.get("/top_sold")
@role_required(Config.ROLE_OWNER)
def top_sold():
    """
    GET /product_stats/top_sold?limit=5
    Top products by sold quantity.
    """
    limit = _parse_limit()
    if limit is None:
        return jsonify({"error": "Invalid query param: limit"}), 400

    sold_qty_expr = func.coalesce(
        func.sum(case((Order.status == "COMPLETE", OrderItem.quantity), else_=0)),
        0,
    )

    rows = (
        db.session.query(Product.id, Product.name, sold_qty_expr.label("sold_quantity"))
        .outerjoin(OrderItem, OrderItem.product_id == Product.id)
        .outerjoin(Order, Order.id == OrderItem.order_id)
        .group_by(Product.id, Product.name)
        .order_by(sold_qty_expr.desc(), Product.id.asc())
        .limit(limit)
        .all()
    )

    return jsonify(
        {
            "products": [
                {
                    "id": int(r.id),
                    "name": r.name,
                    "sold_quantity": int(r.sold_quantity),
                }
                for r in rows
            ],
            "count": len(rows),
        }
    ), 200


@bp.get("/top_revenue")
@role_required(Config.ROLE_OWNER)
def top_revenue():
    """
    GET /product_stats/top_revenue?limit=5
    Top products by revenue from COMPLETE orders.
    """
    limit = _parse_limit()
    if limit is None:
        return jsonify({"error": "Invalid query param: limit"}), 400

    revenue_expr = func.coalesce(
        func.sum(
            case(
                (
                    Order.status == "COMPLETE",
                    OrderItem.quantity * OrderItem.price_at_time,
                ),
                else_=0,
            )
        ),
        0,
    )

    rows = (
        db.session.query(Product.id, Product.name, revenue_expr.label("revenue"))
        .outerjoin(OrderItem, OrderItem.product_id == Product.id)
        .outerjoin(Order, Order.id == OrderItem.order_id)
        .group_by(Product.id, Product.name)
        .order_by(revenue_expr.desc(), Product.id.asc())
        .limit(limit)
        .all()
    )

    return jsonify(
        {
            "products": [
                {
                    "id": int(r.id),
                    "name": r.name,
                    "revenue": float(r.revenue),
                }
                for r in rows
            ],
            "count": len(rows),
        }
    ), 200

