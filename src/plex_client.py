import requests
from typing import Optional, List, Dict


class PlexClient:
    def __init__(self, url: str, token: str):
        self.url   = url.rstrip("/")
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "X-Plex-Token": token,
            "Accept":       "application/json",
        })

    def _get(self, path: str, params: dict = None, timeout: int = 15):
        return self.session.get(f"{self.url}{path}", params=params, timeout=timeout)

    def check_reachable(self) -> Dict:
        try:
            r = self._get("/identity")
            if r.status_code == 200:
                version = r.json().get("MediaContainer", {}).get("version", "?")
                return {"pass": True, "detail": f"Plex reachable (v{version}) at {self.url}"}
            return {"pass": False, "detail": f"Plex returned HTTP {r.status_code}"}
        except requests.exceptions.Timeout:
            return {"pass": False, "detail": f"Plex timed out: {self.url}"}
        except Exception as e:
            return {"pass": False, "detail": f"Plex unreachable ({self.url}): {e}"}

    def get_sections(self) -> List[Dict]:
        r = self._get("/library/sections")
        r.raise_for_status()
        return [
            {"id": str(s["key"]), "title": s["title"], "type": s["type"]}
            for s in r.json().get("MediaContainer", {}).get("Directory", [])
        ]

    def find_section_id(self, library_name: str) -> Optional[str]:
        try:
            for s in self.get_sections():
                if s["title"].lower() == library_name.lower():
                    return s["id"]
        except Exception:
            pass
        return None

    def get_library_item_count(self, section_id: str) -> int:
        try:
            r = self._get(f"/library/sections/{section_id}/all",
                          params={"X-Plex-Container-Start": 0,
                                  "X-Plex-Container-Size": 0})
            r.raise_for_status()
            return int(r.json().get("MediaContainer", {}).get("totalSize", 0))
        except Exception:
            return 0

    def get_trash_items(self, section_id: str) -> List[Dict]:
        try:
            r = self._get(f"/library/sections/{section_id}/all",
                          params={"trash": 1})
            r.raise_for_status()
            items = r.json().get("MediaContainer", {}).get("Metadata", [])
            return [
                {
                    "title": item.get("title", "Unknown"),
                    "year":  item.get("year", ""),
                    "type":  item.get("type", ""),
                }
                for item in items
            ]
        except Exception:
            return []

    def empty_trash(self, section_id: str) -> Dict:
        try:
            r = self.session.put(
                f"{self.url}/library/sections/{section_id}/emptyTrash",
                timeout=30
            )
            if r.status_code in (200, 204):
                return {"ok": True,  "http": r.status_code}
            return {"ok": False, "http": r.status_code, "error": r.text[:200]}
        except Exception as e:
            return {"ok": False, "http": None, "error": str(e)}
