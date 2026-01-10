import time

from flask import Flask, jsonify
from sqlalchemy import text

from config import Config
from extensions import db, jwt


app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
jwt.init_app(app)


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


if __name__ == "__main__":
    _init_db()
    app.run(host="0.0.0.0", port=Config.PORT, debug=False)