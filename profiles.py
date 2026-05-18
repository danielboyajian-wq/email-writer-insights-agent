"""User profile management.

Each profile lives in profiles/<slug>/ with:
- tone.md   : tone description + email examples (loaded into the system prompt)
- meta.json : { "name": "...", "created_at": "...", "default_pitch": "..." }

Profiles are local files — no auth, no database. Designed for a small team
to share one running instance, each picking their own profile.
"""
from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic
from filelock import FileLock, Timeout

PROFILES_DIR = Path(__file__).parent / "profiles"
PROFILES_DIR.mkdir(exist_ok=True)

# Single global write lock for profile mutations. Reads are not locked
# (they're safe since file writes are atomic via os.replace under the hood
# and worst case a reader gets a stale-by-milliseconds view).
_LOCK_PATH = PROFILES_DIR / ".write.lock"
_LOCK_TIMEOUT = 10  # seconds — if a write is held longer than this, something is wrong


def _write_lock() -> FileLock:
    """Returns the global profile write lock. Use as a context manager."""
    return FileLock(str(_LOCK_PATH), timeout=_LOCK_TIMEOUT)


@dataclass
class Profile:
    slug: str
    name: str
    created_at: str
    default_pitch: str = ""


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "profile"


def list_profiles() -> list[Profile]:
    profiles = []
    for d in sorted(PROFILES_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta_path = d / "meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text())
        except Exception:
            continue
        profiles.append(
            Profile(
                slug=d.name,
                name=meta.get("name", d.name),
                created_at=meta.get("created_at", ""),
                default_pitch=meta.get("default_pitch", ""),
            )
        )
    return profiles


def get_profile(slug: str) -> Optional[Profile]:
    for p in list_profiles():
        if p.slug == slug:
            return p
    return None


def load_tone(slug: str) -> str:
    """Read tone.md for the given profile. Returns empty string if missing."""
    tone_path = PROFILES_DIR / slug / "tone.md"
    if not tone_path.exists():
        return ""
    return tone_path.read_text()


def save_profile(
    name: str,
    tone_description: str,
    examples: list[str],
    default_pitch: str = "",
    slug: Optional[str] = None,
) -> Profile:
    """Create or overwrite a profile atomically. Returns the saved Profile.

    Acquires a global write lock so concurrent saves (e.g. two users editing
    different profiles at the same time, or the same profile from two tabs)
    can't interleave their writes and leave a half-written meta.json.
    """
    if not slug:
        slug = slugify(name)

    try:
        with _write_lock():
            pdir = PROFILES_DIR / slug
            pdir.mkdir(parents=True, exist_ok=True)

            # Build tone.md
            examples_block = ""
            for i, ex in enumerate(examples, 1):
                examples_block += f"\n### Example {i}\n\n{ex.strip()}\n\n---\n"

            tone_md = (
                f"# {name} — outbound tone\n\n"
                f"## Voice description\n\n"
                f"{tone_description.strip()}\n\n"
                f"---\n\n"
                f"## Examples\n{examples_block}"
            )

            # Atomic write: stage to .tmp, then rename. Rename is atomic on POSIX.
            tone_path = pdir / "tone.md"
            tone_tmp = pdir / "tone.md.tmp"
            tone_tmp.write_text(tone_md)
            tone_tmp.replace(tone_path)

            existing = get_profile(slug)
            meta = {
                "name": name,
                "created_at": existing.created_at if existing else datetime.utcnow().isoformat(),
                "default_pitch": default_pitch,
            }
            meta_path = pdir / "meta.json"
            meta_tmp = pdir / "meta.json.tmp"
            meta_tmp.write_text(json.dumps(meta, indent=2))
            meta_tmp.replace(meta_path)

            return Profile(
                slug=slug,
                name=name,
                created_at=meta["created_at"],
                default_pitch=default_pitch,
            )
    except Timeout:
        raise RuntimeError(
            "Could not acquire profile write lock within 10s. "
            "Another process may be stuck. Try again."
        )


def delete_profile(slug: str) -> bool:
    """Delete a profile directory atomically. Returns True if removed."""
    pdir = PROFILES_DIR / slug
    if not pdir.exists():
        return False
    try:
        with _write_lock():
            if not pdir.exists():  # re-check inside lock
                return False
            import shutil
            shutil.rmtree(pdir)
            return True
    except Timeout:
        raise RuntimeError(
            "Could not acquire profile write lock within 10s. "
            "Another process may be stuck. Try again."
        )


# --- Claude vision: transcribe email screenshots -----------------------------

VISION_MODEL = "claude-sonnet-4-6"

_TRANSCRIBE_PROMPT = """Transcribe the email visible in this screenshot.

Output ONLY the email text, exactly as written. Preserve:
- Subject line if visible (as `Subject: ...` on the first line)
- Greeting and sign-off
- Paragraph breaks
- Bullet points
- Punctuation, capitalization, contractions

Do NOT add commentary, explanations, or formatting. Just the email body.
If multiple emails are visible, separate them with `\\n\\n---\\n\\n`.
"""


def transcribe_image(image_bytes: bytes, media_type: str = "image/png") -> str:
    """Use Claude vision to OCR an email screenshot."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    response = client.messages.create(
        model=VISION_MODEL,
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64},
                    },
                    {"type": "text", "text": _TRANSCRIBE_PROMPT},
                ],
            }
        ],
    )
    return next((b.text for b in response.content if b.type == "text"), "").strip()
