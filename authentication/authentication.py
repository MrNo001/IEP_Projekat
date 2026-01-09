import re
import time

from flask import Flask, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from sqlalchemy import text
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from extensions import db, jwt
from models import User

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def _missing(data: dict, field: str) -> bool:
    return (field not in data) or (data[field] == "")


def _is_valid_email(email: str) -> bool:
    email = email.strip()
    if not email:
        return False
    if " " in email:
        return False
    return EMAIL_RE.match(email) is not None


def _is_valid_password(password: str) -> bool:
    password = password.strip()
    if len(password) < 8:
        return False
    if re.search(r"\s", password):
        return False
    if re.search(r"[a-z]", password) is None:
        return False
    if re.search(r"[A-Z]", password) is None:
        return False
    if re.search(r"\d", password) is None:
        return False
    return True


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


def _seed_owner() -> None:
    existing = User.query.filter_by(email="onlymoney@gmail.com").first()
    if existing is not None:
        return

    owner = User(
        email="onlymoney@gmail.com",
        password_hash=generate_password_hash("evenmoremoney"),
        forename="Scrooge",
        surname="McDuck",
        role=Config.ROLE_OWNER,
    )
    db.session.add(owner)
    db.session.commit()


def _init_db() -> None:
    # Needs an app context for Flask-SQLAlchemy
    with app.app_context():
        _wait_for_db()
        db.create_all()
        _seed_owner()


@app.get("/")
def health():
    return jsonify({"message": "Authentication service is healthy"}), 200


def _register(role: str):
    data = request.get_json(silent=True) or {}

    if _missing(data, "forename"):
        return jsonify({"message": "Field forename is missing."}), 400
    if _missing(data, "surname"):
        return jsonify({"message": "Field surname is missing."}), 400
    if _missing(data, "email"):
        return jsonify({"message": "Field email is missing."}), 400
    if _missing(data, "password"):
        return jsonify({"message": "Field password is missing."}), 400

    forename = str(data["forename"])
    surname = str(data["surname"])
    email_raw = str(data["email"])
    password_raw = str(data["password"])

    if not _is_valid_email(email_raw):
        return jsonify({"message": "Invalid email."}), 400

    if not _is_valid_password(password_raw):
        return jsonify({"message": "Invalid password."}), 400

    email = email_raw.strip()

    existing = User.query.filter_by(email=email).first()
    if existing is not None:
        return jsonify({"message": "Email already exists."}), 400

    user = User(
        email=email,
        password_hash=generate_password_hash(password_raw),
        forename=forename,
        surname=surname,
        role=role,
    )
    db.session.add(user)
    db.session.commit()

    return ("", 200)


@app.post("/register_customer")
def register_customer():
    return _register(Config.ROLE_CUSTOMER)


@app.post("/register_courier")
def register_courier():
    return _register(Config.ROLE_COURIER)


@app.post("/login")
def login():
    data = request.get_json(silent=True) or {}

    if _missing(data, "email"):
        return jsonify({"message": "Field email is missing."}), 400
    if _missing(data, "password"):
        return jsonify({"message": "Field password is missing."}), 400

    email_raw = str(data["email"])
    password_raw = str(data["password"])

    if not _is_valid_email(email_raw):
        return jsonify({"message": "Invalid email."}), 400

    email = email_raw.strip()

    user = User.query.filter_by(email=email).first()
    if user is None:
        return jsonify({"message": "Invalid credentials."}), 400
    if not check_password_hash(user.password_hash, password_raw):
        return jsonify({"message": "Invalid credentials."}), 400

    additional_claims = {
        "forename": user.forename,
        "surname": user.surname,
        Config.ROLES_FIELD: [user.role],
    }
    token = create_access_token(identity=user.email, additional_claims=additional_claims)

    return jsonify({"accessToken": token}), 200


@app.post("/delete")
@jwt_required()
def delete():
    email = get_jwt_identity()

    user = User.query.filter_by(email=email).first()
    if user is None:
        return jsonify({"message": "Unknown user."}), 400

    db.session.delete(user)
    db.session.commit()

    return ("", 200)


if __name__ == "__main__":
    _init_db()
    app.run(host="0.0.0.0", port=Config.PORT, debug=False)
