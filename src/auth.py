import os
import hashlib
import secrets
from functools import wraps
from flask import request, session, redirect, url_for, jsonify


def _get_credentials():
    username = os.environ.get("EMPTYARR_USERNAME", "")
    password = os.environ.get("EMPTYARR_PASSWORD", "")
    if username and password:
        return username, password
    return None, None


def auth_enabled() -> bool:
    u, _ = _get_credentials()
    return bool(u)


def check_credentials(username: str, password: str) -> bool:
    u, p = _get_credentials()
    if not u:
        return True
    # Use constant-time comparison to prevent timing attacks
    return secrets.compare_digest(username, u) and secrets.compare_digest(password, p)


def is_authenticated() -> bool:
    if not auth_enabled():
        return True
    return session.get("authenticated") is True


def require_auth(f):
    """Redirect to login page for HTML requests, 401 for API requests."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not auth_enabled():
            return f(*args, **kwargs)
        if not is_authenticated():
            # API requests get 401, page requests get redirect
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated