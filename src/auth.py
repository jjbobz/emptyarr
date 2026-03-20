import os
import base64
from functools import wraps
from flask import request, Response


def _get_credentials():
    """Get configured credentials from environment. Returns (username, password) or (None, None) if auth disabled."""
    username = os.environ.get("EMPTYARR_USERNAME", "")
    password = os.environ.get("EMPTYARR_PASSWORD", "")
    if username and password:
        return username, password
    return None, None


def auth_enabled() -> bool:
    u, p = _get_credentials()
    return u is not None


def check_auth(username: str, password: str) -> bool:
    u, p = _get_credentials()
    if u is None:
        return True  # auth disabled
    return username == u and password == p


def unauthorized():
    return Response(
        "Unauthorized — please provide valid credentials.",
        401,
        {"WWW-Authenticate": 'Basic realm="emptyarr"'}
    )


def require_auth(f):
    """Decorator that enforces basic auth if credentials are configured."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not auth_enabled():
            return f(*args, **kwargs)
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return unauthorized()
        return f(*args, **kwargs)
    return decorated