import requests
from typing import List, Dict


def _post(webhook_url: str, payload: dict):
    if not webhook_url:
        return
    # Validate it's actually a Discord webhook URL to prevent SSRF
    if not webhook_url.startswith("https://discord.com/api/webhooks/") and \
       not webhook_url.startswith("https://discordapp.com/api/webhooks/"):
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


def _format_tv_tree(items: List[Dict]) -> str:
    """
    Build a hierarchical show → season → episode listing for Discord.
    Episodes are grouped under their show and season.
    Seasons and shows without episodes are listed beneath the tree.
    """
    episodes = [i for i in items if i.get("type") == "episode"]
    seasons  = [i for i in items if i.get("type") == "season"]
    shows    = [i for i in items if i.get("type") == "show"]

    # Build tree: {show_name: {season_label: [ep_labels]}}
    tree: dict = {}
    for ep in episodes:
        show   = ep.get("grandparent_title") or ep.get("parent_title") or "Unknown Show"
        s_num  = ep.get("parent_index", "")
        season = f"Season {s_num}" if s_num else (ep.get("parent_title") or "Unknown Season")
        ep_num = ep.get("index", "")
        label  = f"Ep {ep_num} \u2013 {ep['title']}" if ep_num else ep["title"]
        tree.setdefault(show, {}).setdefault(season, []).append((int(ep_num) if str(ep_num).isdigit() else 999, label))

    # Sort episodes within each season
    for show in tree:
        for season in tree[show]:
            tree[show][season].sort(key=lambda x: x[0])
            tree[show][season] = [label for _, label in tree[show][season]]

    # Seasons without episodes
    for s in seasons:
        show   = s.get("parent_title") or s.get("grandparent_title") or "Unknown Show"
        s_num  = s.get("index", "") or s.get("parent_index", "")
        season = f"Season {s_num}" if s_num else s["title"]
        tree.setdefault(show, {}).setdefault(season, [])

    # Shows without seasons/episodes
    for sh in shows:
        tree.setdefault(sh["title"], {})

    def _season_num(s: str) -> int:
        parts = s.split()
        return int(parts[-1]) if parts and parts[-1].isdigit() else 999

    lines = []
    for show_name in sorted(tree):
        lines.append(f"**{show_name}**")
        for season in sorted(tree[show_name], key=_season_num):
            lines.append(f"\u00a0\u00a0{season}")
            for ep in tree[show_name][season]:
                lines.append(f"\u00a0\u00a0\u00a0\u00a0\u2022 {ep}")

    return "\n".join(lines)


def notify_emptied(webhook_url: str, instance_name: str, library_name: str,
                   removed_items: List[Dict], checks: Dict, breakdown: str = ""):
    """Fired when trash was actually emptied (items removed)."""
    if not webhook_url:
        return

    count       = len(removed_items)
    description = f"Emptied **{breakdown or f'{count} item(s)'}** from trash."

    has_tv     = any(i.get("type") in ("episode", "season", "show") for i in removed_items)
    has_movies = any(i.get("type") == "movie" for i in removed_items)

    body_lines = []

    if has_tv:
        tv_items = [i for i in removed_items if i.get("type") in ("episode", "season", "show")]
        body_lines.append(_format_tv_tree(tv_items))

    if has_movies:
        movies = [i for i in removed_items if i.get("type") == "movie"]
        if body_lines:
            body_lines.append("")  # blank line between TV and movies
        for m in movies[:20]:
            year = f" ({m['year']})" if m.get("year") else ""
            body_lines.append(f"• {m['title']}{year}")
        if len(movies) > 20:
            body_lines.append(f"_…and {len(movies) - 20} more movies_")

    if not has_tv and not has_movies and removed_items:
        for i in removed_items[:15]:
            year = f" ({i['year']})" if i.get("year") else ""
            body_lines.append(f"• {i['title']}{year}")
        if count > 15:
            body_lines.append(f"_…and {count - 15} more_")

    if body_lines:
        body = "\n".join(body_lines)
        # Discord embed description cap is 4096 chars — truncate cleanly if needed
        if len(description) + len(body) + 2 > 4000:
            body = body[:4000 - len(description) - 20] + "\n_…(truncated)_"
        description += f"\n\n{body}"

    _post(webhook_url, {"embeds": [{
        "title":       f"✅ emptyarr — {instance_name} / {library_name}",
        "description": description,
        "color":       0x3ecf8e,
        "fields":      _check_fields(checks),
    }]})


def notify_clean(webhook_url: str, instance_name: str, library_name: str,
                 checks: Dict):
    """Fired when run succeeded but trash was already empty."""
    if not webhook_url:
        return
    _post(webhook_url, {"embeds": [{
        "title":       f"✅ emptyarr — {instance_name} / {library_name}",
        "description": "Trash was already empty — nothing to remove.",
        "color":       0x3ecf8e,
        "fields":      _check_fields(checks),
    }]})


def notify_health_fail(webhook_url: str, instance_name: str, library_name: str,
                       failed_checks: Dict, all_checks: Dict):
    """Fired when health checks failed — trash empty was skipped."""
    if not webhook_url:
        return
    failed_list = "\n".join(
        f"• **{n}**: {c['detail']}" for n, c in failed_checks.items()
    )
    _post(webhook_url, {"embeds": [{
        "title":       f"⚠️ emptyarr — {instance_name} / {library_name}",
        "description": f"Health checks failed — trash empty skipped.\n\n**Failed:**\n{failed_list}",
        "color":       0xf06565,
        "fields":      _check_fields(all_checks),
    }]})


def notify_error(webhook_url: str, instance_name: str, library_name: str,
                 error: str, checks: Dict):
    """Fired when emptyTrash API call failed."""
    if not webhook_url:
        return
    _post(webhook_url, {"embeds": [{
        "title":       f"🔴 emptyarr — {instance_name} / {library_name} error",
        "description": f"emptyTrash failed:\n```{error}```",
        "color":       0xe74c3c,
        "fields":      _check_fields(checks),
    }]})


def notify_skip(webhook_url: str, instance_name: str,
                library_name: str, reason: str):
    """Fired when run was skipped (scheduling paused, config error, etc)."""
    if not webhook_url:
        return
    _post(webhook_url, {"embeds": [{
        "title":       f"⏭️ emptyarr — {instance_name} / {library_name} skipped",
        "description": f"**Reason:** {reason}",
        "color":       0xe8a045,
    }]})