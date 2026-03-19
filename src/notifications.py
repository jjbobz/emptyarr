import requests
from typing import List, Dict


def _post(webhook_url: str, payload: dict):
    if not webhook_url:
        return
    try:
        requests.post(webhook_url, json=payload, timeout=10)
    except Exception:
        pass


def _check_fields(checks: Dict) -> list:
    return [
        {
            "name":   name,
            "value":  ("✅ " if c["pass"] else "❌ ") + c["detail"],
            "inline": False,
        }
        for name, c in checks.items()
    ]


def notify_success(webhook_url: str, instance_name: str, library_name: str,
                   removed_items: List[Dict], checks: Dict):
    if not webhook_url:
        return
    count  = len(removed_items)
    titles = "\n".join(
        f"• {i['title']}" + (f" ({i['year']})" if i.get("year") else "")
        for i in removed_items[:15]
    )
    overflow    = f"\n_…and {count - 15} more_" if count > 15 else ""
    description = (
        f"Emptied **{count}** item(s) from trash.\n\n{titles}{overflow}"
        if count > 0 else "Trash was already empty."
    )
    _post(webhook_url, {"embeds": [{
        "title":       f"✅ emptyarr — {instance_name} / {library_name}",
        "description": description,
        "color":       0x3ecf8e,
        "fields":      _check_fields(checks),
    }]})


def notify_failure(webhook_url: str, instance_name: str, library_name: str,
                   failed_checks: Dict, all_checks: Dict):
    if not webhook_url:
        return
    failed_list = "\n".join(
        f"• **{n}**: {c['detail']}" for n, c in failed_checks.items()
    )
    _post(webhook_url, {"embeds": [{
        "title":       f"⚠️ emptyarr — {instance_name} / {library_name} skipped",
        "description": f"Health checks failed — trash empty skipped.\n\n**Failed:**\n{failed_list}",
        "color":       0xf06565,
        "fields":      _check_fields(all_checks),
    }]})


def notify_skip(webhook_url: str, instance_name: str,
                library_name: str, reason: str):
    if not webhook_url:
        return
    _post(webhook_url, {"embeds": [{
        "title":       f"⏭️ emptyarr — {instance_name} / {library_name} skipped",
        "description": f"**Reason:** {reason}",
        "color":       0xe8a045,
    }]})
