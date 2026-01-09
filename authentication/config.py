import os
from datetime import timedelta


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


class Config:
    # DB
    SQLALCHEMY_DATABASE_URI = _env("DATABASE_URL", "sqlite:///dev.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT (must match test expectations)
    JWT_SECRET_KEY = _env("JWT_SECRET", "JWT_SECRET_DEV_KEY")
    JWT_ALGORITHM = "HS256"
    JWT_IDENTITY_CLAIM = "sub"
    JWT_DECODE_LEEWAY = 60
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_ENCODE_NBF = True

    # App roles/claims mapping
    ROLES_FIELD = _env("ROLES_FIELD", "roles")
    ROLE_OWNER = _env("ROLE_OWNER", "owner")
    ROLE_CUSTOMER = _env("ROLE_CUSTOMER", "customer")
    ROLE_COURIER = _env("ROLE_COURIER", "courier")

    PORT = int(_env("PORT", "5000"))


