"""Postgres-backed saved-companies history.

Each successful research call auto-saves the brief (per profile). Users browse
saved companies in the sidebar, search by name, click to reload a brief
without re-researching.

Storage: a single `briefs` table on a Postgres database (Neon free tier
is plenty). One entry per (profile_slug, url) — re-researching replaces.

Graceful fallback: if DATABASE_URL is missing or the DB is unreachable,
every function in this module is a no-op and returns empty / False / None.
The app keeps working without history.
"""
from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, Optional

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover
    psycopg = None  # type: ignore

log = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS briefs (
  id            SERIAL PRIMARY KEY,
  profile_slug  TEXT NOT NULL,
  url           TEXT NOT NULL,
  company_name  TEXT,
  brief_json    JSONB NOT NULL,
  researched_at TIMESTAMP NOT NULL DEFAULT now(),
  UNIQUE (profile_slug, url)
);
CREATE INDEX IF NOT EXISTS idx_briefs_profile_recent
  ON briefs(profile_slug, researched_at DESC);

-- Forward-compatible: add intent fields if they don't exist yet.
ALTER TABLE briefs ADD COLUMN IF NOT EXISTS intent_data TEXT;
ALTER TABLE briefs ADD COLUMN IF NOT EXISTS intent_synthesis TEXT;
"""

_SCHEMA_READY = False  # set once after init_schema() succeeds


@dataclass
class SavedBrief:
    profile_slug: str
    url: str
    company_name: str
    brief: dict
    researched_at: datetime
    intent_data: str = ""
    intent_synthesis: str = ""


def is_enabled() -> bool:
    """True if DATABASE_URL is configured and psycopg is importable."""
    return bool(os.getenv("DATABASE_URL")) and psycopg is not None


@contextmanager
def _conn() -> Iterator["psycopg.Connection"]:
    """Open a short-lived connection. Yields None-safe context."""
    dsn = os.getenv("DATABASE_URL")
    if not dsn or psycopg is None:
        raise RuntimeError("history disabled: DATABASE_URL missing or psycopg unavailable")
    with psycopg.connect(dsn, connect_timeout=5) as c:
        yield c


def init_schema() -> bool:
    """Create the briefs table if it doesn't exist. Returns True on success.

    Safe to call repeatedly. Cached after first success.
    """
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return True
    if not is_enabled():
        return False
    try:
        with _conn() as c, c.cursor() as cur:
            cur.execute(_SCHEMA)
        _SCHEMA_READY = True
        return True
    except Exception as e:
        log.warning("history init_schema failed: %s", e)
        return False


def save_brief(
    profile_slug: str,
    url: str,
    company_name: str,
    brief: dict,
    intent_data: str = "",
    intent_synthesis: str = "",
) -> bool:
    """Upsert a brief for (profile, url). Latest research replaces previous.

    intent_data + intent_synthesis are optional. When provided they overwrite
    whatever was previously stored for this (profile, url).
    """
    if not is_enabled():
        return False
    if not init_schema():
        return False
    if not brief.get("insights"):
        # Don't pollute history with zero-insight failures.
        return False
    try:
        # Strip internal fields the user doesn't need to see later.
        clean = {k: v for k, v in brief.items() if not k.startswith("_")}
        with _conn() as c, c.cursor() as cur:
            cur.execute(
                """
                INSERT INTO briefs (
                    profile_slug, url, company_name, brief_json,
                    intent_data, intent_synthesis, researched_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (profile_slug, url)
                DO UPDATE SET
                  company_name     = EXCLUDED.company_name,
                  brief_json       = EXCLUDED.brief_json,
                  intent_data      = EXCLUDED.intent_data,
                  intent_synthesis = EXCLUDED.intent_synthesis,
                  researched_at    = now()
                """,
                (
                    profile_slug, url, company_name, json.dumps(clean),
                    intent_data or None, intent_synthesis or None,
                ),
            )
        return True
    except Exception as e:
        log.warning("history save_brief failed: %s", e)
        return False


def update_intent(
    profile_slug: str,
    url: str,
    intent_data: str,
    intent_synthesis: str,
) -> bool:
    """Write or replace just the intent fields for an existing brief.

    Used when the user adds/edits intent data on a previously-researched
    company without re-running the research pipeline.
    """
    if not is_enabled() or not init_schema():
        return False
    try:
        with _conn() as c, c.cursor() as cur:
            cur.execute(
                """
                UPDATE briefs
                SET intent_data = %s, intent_synthesis = %s
                WHERE profile_slug = %s AND url = %s
                """,
                (
                    intent_data or None, intent_synthesis or None,
                    profile_slug, url,
                ),
            )
        return True
    except Exception as e:
        log.warning("history update_intent failed: %s", e)
        return False


_SELECT_COLS = (
    "profile_slug, url, company_name, brief_json, "
    "intent_data, intent_synthesis, researched_at"
)


def _row_to_saved(r: dict) -> SavedBrief:
    return SavedBrief(
        profile_slug=r["profile_slug"],
        url=r["url"],
        company_name=r["company_name"] or r["url"],
        brief=r["brief_json"],
        researched_at=r["researched_at"],
        intent_data=r.get("intent_data") or "",
        intent_synthesis=r.get("intent_synthesis") or "",
    )


def list_briefs(profile_slug: str, search: str = "") -> list[SavedBrief]:
    """List all saved briefs for a profile, newest first. Optional case-insensitive search."""
    if not is_enabled() or not init_schema():
        return []
    try:
        with _conn() as c, c.cursor(row_factory=dict_row) as cur:
            if search.strip():
                pattern = f"%{search.strip().lower()}%"
                cur.execute(
                    f"""
                    SELECT {_SELECT_COLS}
                    FROM briefs
                    WHERE profile_slug = %s
                      AND (LOWER(company_name) LIKE %s OR LOWER(url) LIKE %s)
                    ORDER BY researched_at DESC
                    """,
                    (profile_slug, pattern, pattern),
                )
            else:
                cur.execute(
                    f"""
                    SELECT {_SELECT_COLS}
                    FROM briefs
                    WHERE profile_slug = %s
                    ORDER BY researched_at DESC
                    """,
                    (profile_slug,),
                )
            rows = cur.fetchall()
        return [_row_to_saved(r) for r in rows]
    except Exception as e:
        log.warning("history list_briefs failed: %s", e)
        return []


def get_brief(profile_slug: str, url: str) -> Optional[SavedBrief]:
    """Fetch a single saved brief."""
    if not is_enabled() or not init_schema():
        return None
    try:
        with _conn() as c, c.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT {_SELECT_COLS}
                FROM briefs
                WHERE profile_slug = %s AND url = %s
                """,
                (profile_slug, url),
            )
            r = cur.fetchone()
        if not r:
            return None
        return _row_to_saved(r)
    except Exception as e:
        log.warning("history get_brief failed: %s", e)
        return None


def delete_brief(profile_slug: str, url: str) -> bool:
    """Delete one saved brief."""
    if not is_enabled() or not init_schema():
        return False
    try:
        with _conn() as c, c.cursor() as cur:
            cur.execute(
                "DELETE FROM briefs WHERE profile_slug = %s AND url = %s",
                (profile_slug, url),
            )
        return True
    except Exception as e:
        log.warning("history delete_brief failed: %s", e)
        return False


# --- Staleness helpers --------------------------------------------------------

def age_days(saved: SavedBrief) -> int:
    """Days since this brief was researched."""
    delta = datetime.utcnow() - saved.researched_at.replace(tzinfo=None)
    return max(delta.days, 0)


def staleness_class(saved: SavedBrief) -> str:
    """Return 'fresh' | 'aging' | 'stale' for UI tagging.

    - fresh: 0-13 days
    - aging: 14-29 days (amber hint)
    - stale: 30+ days (red, suggest re-research)
    """
    d = age_days(saved)
    if d < 14:
        return "fresh"
    if d < 30:
        return "aging"
    return "stale"
