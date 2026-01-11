from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar, cast

from flask import jsonify
from flask_jwt_extended import get_jwt, verify_jwt_in_request

from config import Config

F = TypeVar("F", bound=Callable[..., Any])


def unauthorized_response():
    # Tests expect this exact payload for missing header AND for wrong role.
    return jsonify({"msg": "Missing Authorization Header"}), 401


def register_jwt_error_handlers(jwt_manager) -> None:

    @jwt_manager.unauthorized_loader
    def _jwt_missing_header(_reason: str):
        return unauthorized_response()

    @jwt_manager.invalid_token_loader
    def _jwt_invalid_token(_reason: str):
        return unauthorized_response()

    @jwt_manager.expired_token_loader
    def _jwt_expired_token(_jwt_header, _jwt_payload):
        return unauthorized_response()

    @jwt_manager.revoked_token_loader
    def _jwt_revoked_token(_jwt_header, _jwt_payload):
        return unauthorized_response()


def role_required(required_role: str) -> Callable[[F], F]:
    """
    Enforce:
    - If WITH_AUTHENTICATION=0 -> no-op (allow).
    - Otherwise require a valid JWT and required_role in token claim Config.ROLES_FIELD.
    For any failure, respond with 401 + {"msg":"Missing Authorization Header"} (test expectation).
    """

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            if not Config.WITH_AUTHENTICATION:
                return fn(*args, **kwargs)

            try:
                verify_jwt_in_request()
                claims = get_jwt() or {}
                roles_field = Config.ROLES_FIELD
                roles_val = claims.get(roles_field, [])
                if isinstance(roles_val, str):
                    roles = [roles_val]
                elif isinstance(roles_val, list):
                    roles = roles_val
                else:
                    roles = []

                if required_role not in roles:
                    return unauthorized_response()
            except Exception:
                # Includes missing header / invalid token / decode failures.
                return unauthorized_response()

            return fn(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


