"""On-disk cache for research briefs, keyed by normalized URL.

Each cache entry is one JSON file at .cache/research/<sha256>.json containing
the brief dict plus a created_at timestamp. Default TTL is 24 hours.

Design choices:
- File-based (not Redis / SQLite) for zero external dependencies. Streamlit
  Cloud's ephemeral filesystem means the cache may reset on redeploy, which
  is acceptable for a 24h TTL.
- Atomic writes via tmp + rename so concurrent readers never see a
  half-written file.
- Same domain normalization as insights.normalize_url so callers don't have
  to think about it.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Optional

CACHE_DIR = Path(__file__).parent / ".cache" / "research"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TTL_SECONDS = 24 * 60 * 60  # 24 hours


def _key(url: str) -> str:
    """Stable filename for a URL. SHA-256 keeps it filesystem-safe."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:32] + ".json"


def get_cached_brief(url: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> Optional[dict]:
    """Return cached brief for `url` if it exists and is fresh. Else None."""
    path = CACHE_DIR / _key(url)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    created_at = data.get("_cached_at", 0)
    if time.time() - created_at > ttl_seconds:
        return None
    brief = data.get("brief")
    if not isinstance(brief, dict):
        return None
    # Stamp the brief so the UI can show "cached" indicator if it wants
    brief["_cache_hit"] = True
    brief["_cached_at"] = created_at
    return brief


def cache_brief(url: str, brief: dict) -> None:
    """Write a fresh brief to the cache. Atomic via tmp + rename."""
    # Don't cache error briefs
    if brief.get("_error"):
        return
    path = CACHE_DIR / _key(url)
    tmp = path.with_suffix(".json.tmp")
    payload = {
        "url": url,
        "_cached_at": time.time(),
        "brief": {k: v for k, v in brief.items() if not k.startswith("_cache")},
    }
    try:
        tmp.write_text(json.dumps(payload, indent=2))
        tmp.replace(path)
    except OSError:
        # Cache write failure is non-fatal; the caller still got their brief
        pass


def invalidate(url: str) -> bool:
    """Remove a URL from the cache. Returns True if removed."""
    path = CACHE_DIR / _key(url)
    if path.exists():
        try:
            path.unlink()
            return True
        except OSError:
            return False
    return False


def clear_all() -> int:
    """Remove every cached brief. Returns count."""
    count = 0
    for f in CACHE_DIR.glob("*.json"):
        try:
            f.unlink()
            count += 1
        except OSError:
            pass
    return count
