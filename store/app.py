import time

from flask import Flask, jsonify, request
from sqlalchemy import text

from config import Config
from auth import register_jwt_error_handlers
from extensions import db, jwt
from models import BlockchainState, Category, Order, OrderItem, Product  
from routes.blockchain_interface import bp as blockchain_interface_bp
from routes.courier import bp as courier_bp
from routes.customer import bp as customer_bp
from routes.product_stats import bp as product_stats_bp
from routes.owner import bp as owner_bp


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

@app.post("/__reset")
def reset_store_db():
    """
    Dev-only helper: drop and recreate all store tables.
    Enabled only when ALLOW_RESET=1. Optional RESET_TOKEN via X-Reset-Token header.
    """
    if not Config.ALLOW_RESET:
        return ("", 404)

    if Config.RESET_TOKEN:
        if request.headers.get("X-Reset-Token", "") != Config.RESET_TOKEN:
            return ("", 403)

    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()

    return ("", 200)


def _register_blueprints(app: Flask) -> None:
    mode = Config.SERVICE_MODE.lower().strip()

    # Blockchain interface for personal/testing (balance, create account, send wei)
    app.register_blueprint(blockchain_interface_bp)

    if mode == "owner":
        app.register_blueprint(owner_bp)
    elif mode == "courier":
        app.register_blueprint(courier_bp)
    elif mode == "all":
        app.register_blueprint(owner_bp)
        app.register_blueprint(customer_bp)
        app.register_blueprint(courier_bp)
    elif mode == "stats":
        app.register_blueprint(product_stats_bp)
    else:
        # default: customer
        app.register_blueprint(customer_bp)


_register_blueprints(app)


if __name__ == "__main__":
    _init_db()
    app.run(host="0.0.0.0", port=Config.PORT, debug=False)