import requests
from typing import Dict


PROVIDERS = {
    "realdebrid": {
        "url":     "https://api.real-debrid.com/rest/1.0/user",
        "headers": lambda key: {"Authorization": f"Bearer {key}"},
        "parse":   lambda d: f"RD: {d.get('username','?')} (expires {str(d.get('expiration','?'))[:10]})",
    },
    "alldebrid": {
        "url":     "https://api.alldebrid.com/v4/user?agent=emptyarr",
        "headers": lambda key: {"Authorization": f"Bearer {key}"},
        "parse":   lambda d: f"AD: {d.get('data',{}).get('user',{}).get('username','?')}",
    },
    "torbox": {
        "url":     "https://api.torbox.app/v1/api/user/me",
        "headers": lambda key: {"Authorization": f"Bearer {key}"},
        "parse":   lambda d: f"Torbox: {d.get('data',{}).get('email','?')}",
    },
    "debridlink": {
        "url":     "https://debrid-link.com/api/v2/account/infos",
        "headers": lambda key: {"Authorization": f"Bearer {key}"},
        "parse":   lambda d: f"DL: {d.get('value',{}).get('username','?')}",
    },
}


def check_provider(provider_type: str, api_key: str) -> Dict:
    """
    Ping a debrid provider API to confirm connectivity and valid credentials.
    Returns {"pass": bool, "detail": str}.
    Always returns pass=True if api_key is empty (check skipped).
    """
    if not api_key:
        return {"pass": True, "detail": f"{provider_type}: API key not configured — check skipped"}

    spec = PROVIDERS.get(provider_type.lower())
    if not spec:
        return {"pass": True, "detail": f"{provider_type}: unknown provider — check skipped"}

    try:
        r = requests.get(
            spec["url"],
            headers=spec["headers"](api_key),
            timeout=10,
        )
        if r.status_code == 200:
            try:
                detail = spec["parse"](r.json())
            except Exception:
                detail = f"{provider_type}: OK"
            return {"pass": True, "detail": detail}
        elif r.status_code in (401, 403):
            return {"pass": False, "detail": f"{provider_type}: invalid or expired API key"}
        else:
            return {"pass": False, "detail": f"{provider_type}: HTTP {r.status_code}"}
    except requests.exceptions.Timeout:
        return {"pass": False, "detail": f"{provider_type}: request timed out"}
    except Exception as e:
        return {"pass": False, "detail": f"{provider_type}: {e}"}
