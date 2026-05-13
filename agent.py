"""Email drafting: takes selected insights + persona + tone, drafts an email.

Single tone, loaded from tones/tone.md. Tone block is prompt-cached.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

import anthropic

from personas import format_persona_for_prompt
from profiles import load_tone as load_profile_tone

MODEL = "claude-sonnet-4-6"
COMPANY_CONTEXT_FILE = Path(__file__).parent / "company_context.md"


def load_tone(profile_slug: str = "daniel") -> str:
    """Load tone for the given profile. Falls back to a placeholder."""
    text = load_profile_tone(profile_slug)
    if text:
        return text
    return f"(no tone file found for profile '{profile_slug}' — create one in the Profiles tab)"


def load_company_context() -> str:
    if not COMPANY_CONTEXT_FILE.exists():
        return ""
    return COMPANY_CONTEXT_FILE.read_text()


@dataclass
class DraftRequest:
    company: str
    company_summary: str
    selected_insights: list[dict]   # subset of brief["insights"]
    recipient_name: str
    recipient_title: str
    persona_slug: str               # "marketing" | "sales" | "revops"
    your_pitch: str
    profile_slug: str = "daniel"    # which user profile's tone to use
    linkedin_text: str = ""
    extra_notes: str = ""


SYSTEM_PROMPT_BASE = """You are writing a single cold email for Daniel at 6sense.

HARD CONSTRAINTS — NON-NEGOTIABLE:
- SHORT. Target 60-90 words for the body. Maximum 110.
- NOT SALESY. Direct, factual, conversational. No hype words, no superlatives, no "we'd love to", no "I'd love to", no "would love to", no "absolutely", no "incredible", no "powerful".
- NO multi-bullet value-prop lists. At most ONE bullet block of 2-3 lines, only if it actually shortens the email.
- ONE specific, low-friction CTA. No double asks.
- No preamble. No "hope this finds you well". No "wanted to reach out". No "circling back".
- Match the provided tone EXACTLY (voice, sentence length, punctuation, vocab habits).
- Anchor on the selected insights — one or two, referenced naturally, not listed.
- Connect insight → why this matters for THIS persona → one specific next step.

Structure (loose — adapt to the tone):
1. One-line hook tied to a specific insight (past-tense factual: "Saw...", "Noticed...", "Was looking through...")
2. One sentence on what that likely means for the recipient's role
3. One sentence on how 6sense connects (plain, not sales-pitchy)
4. One soft CTA

Output format — return ONLY this, no preamble:

SUBJECT: <subject line — short, specific, lowercase preferred>

<email body>

---
WHY THIS WORKS:
<2-3 short bullets on which insight you anchored on and why this should land>
"""


def _build_system(tone_text: str, company_context: str) -> list[dict]:
    """System prompt: base rules + company context + tone (cached together).

    Tone + company context change rarely, so caching them together gives
    big savings on repeated drafts.
    """
    cached_block = (
        f"# COMPANY CONTEXT — what we sell, never invent claims outside this\n\n"
        f"{company_context}\n\n"
        f"---\n\n"
        f"# TONE — match this exactly\n\n{tone_text}"
    )
    return [
        {"type": "text", "text": SYSTEM_PROMPT_BASE},
        {
            "type": "text",
            "text": cached_block,
            "cache_control": {"type": "ephemeral"},
        },
    ]


def _format_insights(insights: list[dict]) -> str:
    if not insights:
        return "(none selected)"
    out = []
    for i, ins in enumerate(insights, 1):
        out.append(
            f"{i}. [{ins.get('bucket', '')}] {ins.get('title', '')}\n"
            f"   {ins.get('summary', '')}\n"
            f"   why it matters: {ins.get('why_it_matters', '')}\n"
            f"   source: {ins.get('source_url', '')}"
        )
    return "\n\n".join(out)


def _build_user_message(req: DraftRequest) -> str:
    parts = [
        f"COMPANY: {req.company}",
        f"WHAT THEY DO: {req.company_summary}",
        f"\nRECIPIENT: {req.recipient_name}, {req.recipient_title}",
    ]
    persona_block = format_persona_for_prompt(req.persona_slug, req.company)
    if persona_block:
        parts.append(f"\n{persona_block}")
    parts.append(f"\nWHAT I'M PITCHING: {req.your_pitch}")
    parts.append(f"\nINSIGHTS TO ANCHOR ON:\n{_format_insights(req.selected_insights)}")
    if req.linkedin_text:
        parts.append(
            f"\nRECIPIENT LINKEDIN (raw paste — pull ONE specific, non-generic detail "
            f"if it strengthens the email):\n{req.linkedin_text}"
        )
    if req.extra_notes:
        parts.append(f"\nADDITIONAL CONTEXT:\n{req.extra_notes}")
    parts.append(
        "\nWrite the email now. Match the tone exactly. "
        "Anchor the value prop on how 6sense helps THIS persona specifically. "
        "Do not invent facts not in the insights/LinkedIn text/company context."
    )
    return "\n".join(parts)


def draft_email(req: DraftRequest) -> tuple[str, dict]:
    """Returns (email_text, usage_stats)."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=_build_system(load_tone(req.profile_slug), load_company_context()),
        messages=[{"role": "user", "content": _build_user_message(req)}],
    )
    text = next((b.text for b in response.content if b.type == "text"), "")
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_read": getattr(response.usage, "cache_read_input_tokens", 0),
        "cache_write": getattr(response.usage, "cache_creation_input_tokens", 0),
    }
    return text, usage
