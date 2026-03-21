import hashlib
import os
import secrets
import time
from functools import wraps
from flask import request, session, redirect, url_for, jsonify


def _hash_password(password: str) -> str:
    return hashlib.sha256(f"emptyarr:{password}".encode()).hexdigest()


def _get_credentials(config=None):
    env_user = os.environ.get("EMPTYARR_USERNAME", "")
    env_pass = os.environ.get("EMPTYARR_PASSWORD", "")
    if env_user and env_pass:
        return env_user, _hash_password(env_pass)
    if config and getattr(config, "auth_username", "") and getattr(config, "auth_password_hash", ""):
        return config.auth_username, config.auth_password_hash
    return None, None


def auth_enabled(config=None) -> bool:
    u, _ = _get_credentials(config)
    return bool(u)


# ── Brute force protection ────────────────────────────────────────────────────
# Simple in-memory tracker: {ip: [timestamp, ...]}
_login_attempts: dict = {}
_MAX_ATTEMPTS  = 10    # max failures in window
_WINDOW_SECS   = 300   # 5 minute window
_LOCKOUT_SECS  = 600   # 10 minute lockout after max attempts


def _record_attempt(ip: str, success: bool):
    now = time.time()
    attempts = _login_attempts.get(ip, [])
    # Prune old attempts
    attempts = [t for t in attempts if now - t < _WINDOW_SECS]
    if not success:
        attempts.append(now)
    else:
        attempts = []  # clear on success
    _login_attempts[ip] = attempts


def _is_locked_out(ip: str) -> bool:
    now      = time.time()
    attempts = _login_attempts.get(ip, [])
    recent   = [t for t in attempts if now - t < _WINDOW_SECS]
    if len(recent) >= _MAX_ATTEMPTS:
        # Locked out if most recent attempt is within lockout window
        return (now - max(recent)) < _LOCKOUT_SECS
    return False


def check_credentials(username: str, password: str, config=None, ip: str = "") -> bool:
    u, ph = _get_credentials(config)
    if not u:
        return True
    if ip and _is_locked_out(ip):
        return False
    ok = (secrets.compare_digest(username, u) and
          secrets.compare_digest(_hash_password(password), ph))
    if ip:
        _record_attempt(ip, ok)
    return ok


def is_locked_out(ip: str) -> bool:
    return _is_locked_out(ip)


def hash_password(password: str) -> str:
    return _hash_password(password)


def is_authenticated() -> bool:
    return session.get("authenticated") is True


def require_auth(f):
    """
    Redirect to login for page requests, 401 for API requests.
    API requests can authenticate via session cookie OR X-API-Token header.
    The API token is the SHA-256 hash of the password (same as stored hash).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        from app import config as _config
        if not auth_enabled(_config):
            return f(*args, **kwargs)
        # Check session first
        if is_authenticated():
            return f(*args, **kwargs)
        # Check X-API-Token header for API requests
        if request.path.startswith("/api/"):
            api_token = request.headers.get("X-API-Token", "")
            if api_token:
                _, ph = _get_credentials(_config)
                if ph and secrets.compare_digest(api_token, ph):
                    return f(*args, **kwargs)
            return jsonify({"error": "Unauthorized — set credentials or provide X-API-Token header"}), 401
        return redirect(url_for("login"))
    return decorated