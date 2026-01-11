import os


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


class Config:
    # DB
    SQLALCHEMY_DATABASE_URI = _env("DATABASE_URL", "sqlite:///store-dev.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT (must match authentication service)
    JWT_SECRET_KEY = _env("JWT_SECRET", "JWT_SECRET_DEV_KEY")
    JWT_ALGORITHM = "HS256"
    JWT_IDENTITY_CLAIM = "sub"
    JWT_DECODE_LEEWAY = 60

    # App roles/claims mapping (must match authentication service)
    ROLES_FIELD = _env("ROLES_FIELD", "roles")
    ROLE_OWNER = _env("ROLE_OWNER", "owner")
    ROLE_CUSTOMER = _env("ROLE_CUSTOMER", "customer")
    ROLE_COURIER = _env("ROLE_COURIER", "courier")

    # Modes
    SERVICE_MODE = _env("SERVICE_MODE", "customer")  # owner|customer|courier

    # Ports (set per container)
    PORT = int(_env("PORT", "5002"))

    # Feature flags
    WITH_AUTHENTICATION = _env("WITH_AUTHENTICATION", "1") == "1"
    WITH_BLOCKCHAIN = _env("WITH_BLOCKCHAIN", "0") == "1"

    # Dev/test helpers
    ALLOW_RESET = _env("ALLOW_RESET", "0") == "1"
    RESET_TOKEN = _env("RESET_TOKEN", "")

    # Blockchain settings (used when WITH_BLOCKCHAIN=1)
    PROVIDER_URL = _env("PROVIDER_URL", "")
    OWNER_PRIVATE_KEY = _env("OWNER_PRIVATE_KEY", "")


