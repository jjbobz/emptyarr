import bcrypt
import hashlib
import os
import secrets
import time
from functools import wraps
from flask import request, session, redirect, url_for, jsonify

_BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    """Generate a bcrypt hash for storage in config.yml."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode()


def _legacy_hash(password: str) -> str:
    """SHA-256 hash used for env-var auth path (deterministic — needed for stable X-API-Token)."""
    return hashlib.sha256(f"emptyarr:{password}".encode()).hexdigest()


def _verify_password(plain: str, stored: str) -> bool:
    """Verify plain password against stored hash.
    Supports bcrypt (new) and SHA-256 (legacy config.yml hashes).
    """
    if stored.startswith(("$2b$", "$2a$", "$2y$")):
        try:
            return bcrypt.checkpw(plain.encode(), stored.encode())
        except Exception:
            return False
    # Legacy SHA-256 fallback for configs created before bcrypt was introduced
    return secrets.compare_digest(_legacy_hash(plain), stored)


def _get_credentials(config=None):
    env_user = os.environ.get("EMPTYARR_USERNAME", "")
    env_pass = os.environ.get("EMPTYARR_PASSWORD", "")
    if env_user and env_pass:
        # Keep SHA-256 for env-var path — deterministic hash keeps X-API-Token stable
        return env_user, _legacy_hash(env_pass)
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
    ok = secrets.compare_digest(username, u) and _verify_password(password, ph)
    if ip:
        _record_attempt(ip, ok)
    return ok


def is_locked_out(ip: str) -> bool:
    return _is_locked_out(ip)


def is_authenticated() -> bool:
    return session.get("authenticated") is True


def require_auth(f):
    """
    Redirect to login for page requests, 401 for API requests.
    API requests can authenticate via session cookie OR X-API-Token header.
    The API token is the stored password hash (from /api/auth/token).
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
