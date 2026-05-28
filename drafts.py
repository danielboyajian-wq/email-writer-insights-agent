"""Postgres-backed drafted-email history.

Every successful draft (single email or 6-email cadence) auto-saves to
the `drafts` table, scoped by profile + URL. The BDR can look up previous
drafts for a prospect to remember what email 1 said when writing email 2,
or compare cadence variants over time.

Multiple drafts per (profile, URL) are kept — no overwrite. Newer drafts
sort first when listed. Graceful no-op if DATABASE_URL is missing.
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
CREATE TABLE IF NOT EXISTS drafts (
  id           SERIAL PRIMARY KEY,
  profile_slug TEXT NOT NULL,
  url          TEXT NOT NULL,
  company_name TEXT,
  draft_type   TEXT NOT NULL,
  draft_json   JSONB NOT NULL,
  recipient    TEXT,
  drafted_at   TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_drafts_profile_url_recent
  ON drafts(profile_slug, url, drafted_at DESC);
CREATE INDEX IF NOT EXISTS idx_drafts_profile_recent
  ON drafts(profile_slug, drafted_at DESC);

-- Forward-compatible: add persona column to existing tables.
ALTER TABLE drafts ADD COLUMN IF NOT EXISTS persona TEXT;
"""

_SCHEMA_READY = False


@dataclass
class SavedDraft:
    id: int
    profile_slug: str
    url: str
    company_name: str
    draft_type: str        # 'single' or 'cadence'
    draft: dict            # for single: {"text": ...}
                           # for cadence: {"emails": [...]}
    recipient: str
    drafted_at: datetime
    persona: str = ""      # 'marketing' | 'sales' | 'revops' (optional)


def is_enabled() -> bool:
    return bool(os.getenv("DATABASE_URL")) and psycopg is not None


@contextmanager
def _conn() -> Iterator["psycopg.Connection"]:
    dsn = os.getenv("DATABASE_URL")
    if not dsn or psycopg is None:
        raise RuntimeError("drafts disabled: DATABASE_URL missing or psycopg unavailable")
    with psycopg.connect(dsn, connect_timeout=5) as c:
        yield c


def init_schema() -> bool:
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
        log.warning("drafts init_schema failed: %s", e)
        return False


def save_draft(
    profile_slug: str,
    url: str,
    company_name: str,
    draft_type: str,
    draft: dict,
    recipient: str = "",
    persona: str = "",
) -> Optional[int]:
    """Insert a new draft row. Returns the new row's id, or None on failure."""
    if not is_enabled() or not init_schema():
        return None
    if draft_type not in ("single", "cadence"):
        return None
    try:
        with _conn() as c, c.cursor() as cur:
            cur.execute(
                """
                INSERT INTO drafts (
                    profile_slug, url, company_name, draft_type,
                    draft_json, recipient, persona
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    profile_slug, url, company_name, draft_type,
                    json.dumps(draft), recipient or None, persona or None,
                ),
            )
            row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        log.warning("drafts save_draft failed: %s", e)
        return None


_DRAFT_COLS = (
    "id, profile_slug, url, company_name, draft_type, "
    "draft_json, recipient, drafted_at, persona"
)


def _row_to_saved(r: dict) -> SavedDraft:
    return SavedDraft(
        id=r["id"],
        profile_slug=r["profile_slug"],
        url=r["url"],
        company_name=r["company_name"] or r["url"],
        draft_type=r["draft_type"],
        draft=r["draft_json"],
        recipient=r["recipient"] or "",
        drafted_at=r["drafted_at"],
        persona=r.get("persona") or "",
    )


def list_drafts_for_prospect(profile_slug: str, url: str) -> list[SavedDraft]:
    """All drafts for a specific (profile, url), newest first."""
    if not is_enabled() or not init_schema():
        return []
    try:
        with _conn() as c, c.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT {_DRAFT_COLS}
                FROM drafts
                WHERE profile_slug = %s AND url = %s
                ORDER BY drafted_at DESC
                """,
                (profile_slug, url),
            )
            rows = cur.fetchall()
        return [_row_to_saved(r) for r in rows]
    except Exception as e:
        log.warning("drafts list_for_prospect failed: %s", e)
        return []


def list_recent_drafts(profile_slug: str, limit: int = 200) -> list[SavedDraft]:
    """Recent activity across all prospects for a profile."""
    if not is_enabled() or not init_schema():
        return []
    try:
        with _conn() as c, c.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT {_DRAFT_COLS}
                FROM drafts
                WHERE profile_slug = %s
                ORDER BY drafted_at DESC
                LIMIT %s
                """,
                (profile_slug, limit),
            )
            rows = cur.fetchall()
        return [_row_to_saved(r) for r in rows]
    except Exception as e:
        log.warning("drafts list_recent failed: %s", e)
        return []


def delete_draft(draft_id: int) -> bool:
    if not is_enabled() or not init_schema():
        return False
    try:
        with _conn() as c, c.cursor() as cur:
            cur.execute("DELETE FROM drafts WHERE id = %s", (draft_id,))
        return True
    except Exception as e:
        log.warning("drafts delete failed: %s", e)
        return False
