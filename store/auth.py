from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import jsonify
from flask_jwt_extended import get_jwt, verify_jwt_in_request

from config import Config



def unauthorized_response():
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


def role_required(required_role: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
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
                return unauthorized_response()
            return fn(*args, **kwargs)
        return wrapper
    return decorator


