"""Intent-data synthesis.

Takes a raw paste of 6sense intent data (keywords being researched, pages
visited) and a research brief, and produces a 2-3 sentence hypothesis
about WHY the prospect is in-market right now.

The output is a single piece of text the user can review and edit in the
UI before drafting. It then gets injected into the drafting prompt as
additional context so emails can anchor on the inferred motivation
without dumping the raw signal data into the email body.
"""
from __future__ import annotations

import os

import anthropic

MODEL = "claude-sonnet-4-6"


SYNTHESIS_SYSTEM = """You are a B2B revenue analyst. You will receive:

1. A short brief about a prospect company (what they do, recent news, hires,
   funding, etc.).
2. Raw 6sense intent data the user pasted, which includes the keywords the
   prospect's people are researching online and the pages on the user's own
   website they have visited recently.

Your job: produce a SHORT hypothesis (2-3 sentences, max ~60 words) about
WHY this account appears to be in-market right now. Connect the intent
signals to the recent company changes. Be specific. The hypothesis should
help a salesperson decide how to open their outreach.

Rules:
- 2-3 sentences. No bullet lists.
- No em dashes. Use commas, periods, parentheses.
- Be direct. No filler ("It seems that...", "Based on the data...").
- Tie keyword/page activity to a SPECIFIC company event from the brief
  (a new hire, a recent earnings note, a product launch, etc.) when one
  exists. If no clean tie exists, say so plainly.
- Do not invent insights not present in the brief or intent paste.
- Output the hypothesis text only. No headers, no preamble, no JSON.

Example good output:
"Heavy traffic on the intent-data and pricing pages after the new CMO hire
last month suggests they are scoping vendors for a 2026 revenue-tooling
refresh. The 'ABM platform' and 'account-based marketing' keywords
reinforce this is shortlist-stage research, not casual reading."

Example bad output (DO NOT do this):
"Based on the comprehensive analysis of the intent data provided, it
appears that the prospect organization may potentially be considering..."
"""


def synthesize_intent(
    intent_text: str,
    brief: dict,
    company: str = "",
    persona_label: str = "",
) -> str:
    """Run a single Claude call to synthesize intent data + brief into a
    short hypothesis. Returns plain text (2-3 sentences). Raises on API errors.
    """
    if not intent_text.strip():
        return ""

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Compact the brief for the prompt — only the parts useful for synthesis
    summary = brief.get("company_summary", "")
    insights_lines = []
    for ins in (brief.get("insights") or [])[:10]:
        bucket = ins.get("bucket", "")
        title = ins.get("title", "")
        date = ins.get("date") or "no date"
        insights_lines.append(f"- [{bucket}] {title} ({date})")
    insights_block = "\n".join(insights_lines) if insights_lines else "(none)"

    user_msg = (
        f"COMPANY: {company}\n"
        f"PERSONA WE'RE REACHING OUT TO: {persona_label or 'unspecified'}\n\n"
        f"COMPANY SUMMARY:\n{summary}\n\n"
        f"RECENT INSIGHTS:\n{insights_block}\n\n"
        f"6SENSE INTENT DATA (raw paste from the user — keywords researched, "
        f"pages visited):\n---\n{intent_text.strip()}\n---\n\n"
        f"Produce the 2-3 sentence hypothesis per the rules."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=SYNTHESIS_SYSTEM,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": user_msg}],
    )
    text = next((b.text for b in response.content if b.type == "text"), "")
    # Safety: strip em dashes if any slipped through
    text = (
        text.replace(" — ", ", ").replace("—", ", ")
        .replace(" – ", ", ").replace("–", ", ")
        .replace(" -- ", ", ").replace("--", ", ")
    )
    return text.strip()
