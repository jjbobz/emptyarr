import os
import yaml
from dataclasses import dataclass, field
from typing import List, Optional, Dict


# ── Provider check ────────────────────────────────────────────────────────────

@dataclass
class ProviderCheck:
    type: str          # realdebrid | alldebrid | torbox | debridlink | usenet (future)
    api_key: str = ""


# ── Path config ───────────────────────────────────────────────────────────────

@dataclass
class PathConfig:
    path: str
    type: str                                    # physical | debrid | usenet
    min_files: int = 50
    min_threshold: float = 0.90
    provider_checks: List[ProviderCheck] = field(default_factory=list)


# ── Library config ────────────────────────────────────────────────────────────

@dataclass
class LibraryConfig:
    name: str
    type: str                                    # physical | debrid | usenet | mixed
    paths: List[PathConfig]
    cron: str = "0 * * * *"
    section_id: Optional[str] = None            # auto-discovered if not set


# ── Plex instance config ──────────────────────────────────────────────────────

@dataclass
class PlexInstanceConfig:
    name: str
    url: str
    token: str
    libraries: List[LibraryConfig]


# ── Notification config ───────────────────────────────────────────────────────

@dataclass
class NotifyConfig:
    on_success: bool = False
    on_failure: bool = True
    on_skip: bool = True


# ── Top-level app config ──────────────────────────────────────────────────────

@dataclass
class AppConfig:
    instances: List[PlexInstanceConfig]
    discord_webhook: str = ""
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    log_level: str = "INFO"


# ── Loader ────────────────────────────────────────────────────────────────────

def _load_provider_checks(raw: list) -> List[ProviderCheck]:
    checks = []
    for pc in (raw or []):
        checks.append(ProviderCheck(
            type    = pc.get("type", ""),
            api_key = pc.get("api_key", ""),
        ))
    return checks


def _load_path(raw: dict, lib_type: str,
               lib_min_files: int, lib_min_threshold: float) -> PathConfig:
    """
    Parse a single path entry. Falls back to library-level min_files/threshold
    if not specified on the path itself.
    """
    # provider_checks can be a list (plural) or single dict (singular)
    pc_raw = raw.get("provider_checks", raw.get("provider_check", None))
    if isinstance(pc_raw, dict):
        pc_raw = [pc_raw]

    return PathConfig(
        path             = raw["path"],
        type             = raw.get("type", lib_type),
        min_files        = int(raw.get("min_files", lib_min_files)),
        min_threshold    = float(raw.get("min_threshold", lib_min_threshold * 100)) / 100.0,
        provider_checks  = _load_provider_checks(pc_raw or []),
    )


def _load_library(raw: dict) -> LibraryConfig:
    lib_type          = raw.get("type", "physical")
    lib_min_files     = int(raw.get("min_files", 50))
    lib_min_threshold = float(raw.get("min_threshold", 90)) / 100.0
    cron              = raw.get("cron", "0 * * * *")

    raw_paths = raw.get("paths", [])

    # Support shorthand: paths as list of strings instead of dicts
    # e.g. paths: ["/media/movies"] instead of paths: [{path: "/media/movies"}]
    parsed_paths = []
    for p in raw_paths:
        if isinstance(p, str):
            parsed_paths.append(PathConfig(
                path          = p,
                type          = lib_type if lib_type != "mixed" else "physical",
                min_files     = lib_min_files,
                min_threshold = lib_min_threshold,
            ))
        elif isinstance(p, dict):
            parsed_paths.append(_load_path(p, lib_type, lib_min_files, lib_min_threshold))

    # Shorthand: single path string at library level
    if not parsed_paths and raw.get("path"):
        single = raw["path"]
        paths_list = single if isinstance(single, list) else [single]
        for p in paths_list:
            parsed_paths.append(PathConfig(
                path          = p,
                type          = lib_type,
                min_files     = lib_min_files,
                min_threshold = lib_min_threshold,
            ))

    return LibraryConfig(
        name       = raw["name"],
        type       = lib_type,
        paths      = parsed_paths,
        cron       = cron,
        section_id = raw.get("section_id", None),
    )


def _load_instance(raw: dict) -> PlexInstanceConfig:
    return PlexInstanceConfig(
        name      = raw["name"],
        url       = raw.get("url", ""),
        token     = raw.get("token", ""),
        libraries = [_load_library(lib) for lib in raw.get("libraries", [])],
    )


def load_config(path: str = "data/config.yml") -> AppConfig:
    with open(path, "r") as f:
        raw = yaml.safe_load(f)

    discord = os.environ.get("DISCORD_WEBHOOK", raw.get("discord_webhook", ""))

    notify_raw = raw.get("notify", {})
    notify = NotifyConfig(
        on_success = notify_raw.get("on_success", False),
        on_failure = notify_raw.get("on_failure", True),
        on_skip    = notify_raw.get("on_skip", True),
    )

    instances = []
    for inst in raw.get("plex_instances", []):
        # Allow env var overrides per instance via name-based vars
        # e.g. PLEX_TOKEN_STREAMSTEAD, PLEX_TOKEN_STREAMSTEAD_UNLIMITED
        safe_name = inst["name"].upper().replace(" ", "_").replace("-", "_")
        inst["url"]   = os.environ.get(f"PLEX_URL_{safe_name}",
                        os.environ.get("PLEX_URL", inst.get("url", "")))
        inst["token"] = os.environ.get(f"PLEX_TOKEN_{safe_name}",
                        os.environ.get("PLEX_TOKEN", inst.get("token", "")))

        # Inject RD/AD/TB api keys from env into provider_checks on paths
        env_keys = {
            "realdebrid": os.environ.get("RD_API_KEY", ""),
            "alldebrid":  os.environ.get("AD_API_KEY", ""),
            "torbox":     os.environ.get("TB_API_KEY", ""),
            "debridlink": os.environ.get("DL_API_KEY", ""),
        }
        for lib in inst.get("libraries", []):
            for p in lib.get("paths", []):
                if isinstance(p, dict):
                    for pc in p.get("provider_checks", []):
                        if not pc.get("api_key") and env_keys.get(pc.get("type", "")):
                            pc["api_key"] = env_keys[pc["type"]]

        instances.append(_load_instance(inst))

    return AppConfig(
        instances       = instances,
        discord_webhook = discord,
        notify          = notify,
        log_level       = os.environ.get("LOG_LEVEL", raw.get("log_level", "INFO")),
    )
