"""Email drafting: takes selected insights + persona + tone, drafts an email.

Single tone, loaded from tones/tone.md. Tone block is prompt-cached.
"""

import json
import os
import re
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

# TOP PRIORITY: TONE

The tone block (further down in this system prompt) is the most important
rule. Every sentence must read like it could appear in one of the example
emails in that block. Match:
- Voice and rhythm (sentence length, transitions, capitalization habits)
- Vocabulary (use the words / phrases that appear in the examples; avoid
  ones that don't)
- Punctuation habits
- Opener structure ("Saw...", "Noticed...", "Tabbed through...", "Was looking
  into..." — past-tense factual hook)
- Sign-off style

If a sentence could plausibly be written in a different voice — rewrite it.
If you find yourself reaching for a phrase that doesn't appear in the
examples, stop and use phrasing from the examples instead. When the tone
rules conflict with anything else in this prompt, the tone wins.

# HARD CONSTRAINTS — NON-NEGOTIABLE

- SHORT. Target 60-90 words for the body. Maximum 110.
- NOT SALESY. Direct, factual, conversational. No hype words, no
  superlatives, no "we'd love to", no "I'd love to", no "would love to",
  no "absolutely", no "incredible", no "powerful".
- NO multi-bullet value-prop lists. At most ONE bullet block of 2-3 lines,
  only if it actually shortens the email.
- ONE specific, persona-anchored CTA (see CTA section below). No double asks.
- No preamble. No "hope this finds you well", "wanted to reach out",
  "circling back".
- Anchor on the selected insights — one or two, referenced naturally,
  not listed.
- Connect insight → why this matters for THIS persona → one specific next
  step.

# LINKEDIN — MANDATORY USE WHEN PROVIDED, AND DEPTH MATTERS

If the user message includes a `RECIPIENT LINKEDIN` block, your opening line
MUST reference a SPECIFIC, PERSONAL, NON-OBVIOUS detail from it.

## What COUNTS as personalization (use these)

Look hard for the personal layer. Examples of strong hooks:
- A specific post they wrote — quote a line, react to a take, agree/disagree
  with a specific point ("Your post on [topic] — the line about [X] stuck with me")
- A personal challenge / endurance event / athletic feat (marathons, Misogi,
  triathlons, climbs, ultramarathons)
- A side project, hobby, or non-work passion (woodworking, photography,
  fly-fishing, podcasting, cooking, music)
- Charity work or causes they personally champion
- A recent personal milestone they shared (a move, a kid, a sabbatical,
  becoming a first-time manager, learning something new)
- A bold opinion they've publicly taken on industry practices
- A book, podcast, or creator they keep recommending
- A distinctive personal philosophy they've articulated in posts
- An unusual career path they took (left tech for sailing, etc.)

The reference should be something that would make the recipient think:
"this person actually read my profile / posts" — not "this is automated."

## What DOES NOT COUNT (forbidden)

These are too generic. They're visible in any prospecting tool. Do not use:
- Their university or where they went to school
- Their current job title or company name
- Their previous job title or company name
- Years of experience or tenure
- Generic skills listed in their profile (e.g. "marketing strategy",
  "leadership", "data analysis")
- Common certifications (PMP, MBA, Salesforce admin)
- Their location / city (unless they recently moved)
- A vague "I see you've been at [Company] for X years"
- "I see you're passionate about [generic topic]"
- "Impressive background in [field]"
- Anything that would be true of 1000 other people in the same role

If the LinkedIn paste only contains generic profile facts (school, titles,
companies, basic skills) and nothing personal, you do NOT get to invent a
personal detail. In that case, lead with the company insight instead and
explain in the email that the personal LinkedIn hook wasn't strong enough.
Better to skip the hook than fake one.

## Where the hook goes

If the LinkedIn detail is strong and personal, lead with it. If the company
insight is stronger, lead with the insight and weave the LinkedIn detail
into the second or third sentence. Either way, the LinkedIn reference must
be specific enough that the recipient would recognize it as theirs.

# CTA — THIS IS WHERE MOST EMAILS FAIL

The CTA is NOT "open to a quick chat?" or "worth a chat?" by default.
Those are weak filler. A strong CTA does TWO things:

(a) Ties back to the specific insight you anchored on (the funding round,
    the new hire, the launch, the 10-K risk, the LinkedIn detail).
(b) States what the recipient gets from the conversation, framed around
    their persona's priorities.

STRONG (match the structure to your tone):
- "Worth a chat to share how we ramp new AEs into pipeline 30% faster?" (anchored on the new-hire insight, sales persona)
- "Open to comparing notes on landing that launch with buying committees already in market?" (anchored on a product launch, marketing persona)
- "Worth 15 min to walk through how we'd cut spend on low-intent traffic before EOY?" (anchored on a 10-K risk, marketing persona)
- "Would it make sense to look at how [Company] could get similar value out of 6sense as y'all do with [Competitor]?" (anchored on a competitor mention)

WEAK (avoid):
- "Open to a quick chat?" (no anchor, no value)
- "Let me know if you're interested." (passive)
- "Happy to share more." (no specific ask)

If you find yourself defaulting to "worth a chat?" with nothing else,
go back and re-anchor it on a specific insight + persona priority.

# STRUCTURE (loose — adapt to the tone)

1. One-line hook: either the LinkedIn detail (if provided) or a past-tense
   factual reference to the strongest insight.
2. One sentence connecting that to what likely matters for the recipient's
   role / persona.
3. One sentence on how 6sense connects (plain, not sales-pitchy).
4. One persona-anchored CTA (see above).

# OUTPUT FORMAT — return ONLY this, no preamble, no commentary, no trailing section:

SUBJECT: <subject line — short, specific, lowercase preferred>

<email body>
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
            # 1h TTL: better cache hit rate for occasional drafters,
            # at the cost of a ~1.6x write premium on the first call.
            # Breaks even after ~3 drafts on the same tone within an hour.
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
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

    # LinkedIn goes early and is marked mandatory when present.
    # The depth bar is high: only PERSONAL details count (posts, hobbies,
    # athletic feats, side projects, opinions). University / job title /
    # company / tenure / generic skills are forbidden — those are too easy
    # to find and signal automation, not personalization.
    if req.linkedin_text:
        parts.append(
            "\nRECIPIENT LINKEDIN — read this carefully.\n"
            "If you find a SPECIFIC, PERSONAL hook (post, athletic challenge, "
            "side project, hobby, opinion, personal milestone), the opening "
            "line MUST use it.\n"
            "If the paste only contains generic profile facts (school, title, "
            "company, tenure, basic skills), DO NOT fake a hook. Skip the "
            "LinkedIn opener and lead with the strongest insight instead.\n"
            f"---\n{req.linkedin_text}\n---"
        )

    persona_block = format_persona_for_prompt(req.persona_slug, req.company)
    if persona_block:
        parts.append(f"\n{persona_block}")

    parts.append(f"\nWHAT I'M PITCHING: {req.your_pitch}")
    parts.append(f"\nINSIGHTS TO ANCHOR ON:\n{_format_insights(req.selected_insights)}")

    if req.extra_notes:
        parts.append(f"\nADDITIONAL CONTEXT:\n{req.extra_notes}")

    parts.append(
        "\nWrite the email now.\n"
        "- TONE first: every sentence must match the tone block.\n"
        "- If LinkedIn provided AND it contains a personal hook, the opening "
        "line MUST use that hook. If LinkedIn only has generic profile facts, "
        "skip the hook and lead with the insight.\n"
        "- CTA must tie back to a specific insight + this persona's priorities. "
        "No generic 'open to a quick chat?'.\n"
        "- Do not invent facts not in the insights / LinkedIn / company context.\n"
        "- Output ONLY the SUBJECT line and the email body. No 'WHY THIS WORKS', "
        "no commentary, no trailing section."
    )
    return "\n".join(parts)


def draft_email(req: DraftRequest) -> tuple[str, dict]:
    """Returns (email_text, usage_stats)."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model=MODEL,
        max_tokens=1200,
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


# ============================================================================
# 6-email cadence
# ============================================================================

CADENCE_INSTRUCTIONS = """You are now writing a 6-EMAIL CADENCE in one go, not a single email.

Same hard constraints as a single email apply to EVERY message: tone, no salesy
phrasing, no preamble fluff, no generic CTAs, all the bans in the base system
prompt. Each message must read like Daniel wrote it.

# Thread structure

The cadence is two threads of three messages each.

- **Thread 1 = emails 1, 2, 3.** Email 1 has a fresh subject line. Emails 2
  and 3 are REPLIES in that same thread — their subject is `Re: <email 1's subject>`.
- **Thread 2 = emails 4, 5, 6.** Email 4 has a FRESH subject line — short,
  factual, lowercase, matches Daniel's style (NOT salesy, NOT a different
  rhetorical register from email 1's subject — same straight-to-the-point
  voice, just different angle). Emails 5 and 6 are REPLIES — their subject
  is `Re: <email 4's subject>`.

# Per-email framework

## Email 1 — Insight-based opener (the existing single-email format)
Same as a one-off cold email: hook on the strongest selected insight (or
LinkedIn personal detail if provided), connect to what likely matters for
this persona, plain explanation of how 6sense connects, persona-anchored CTA.

## Email 2 — Customer story tied back to original pain
Lead with one short framing line (e.g. "Sharing this customer story I thought
you'd find relevant."). Then a customer story from the company_context.md
customer outcomes library, picked to match the prospect's industry / persona
/ situation. Use 2-3 quantified bullet points from that customer's results.
End by tying it back to the SAME pain/insight you opened email 1 with — show
how the story is directly relevant to what they're navigating.

## Email 3 — Short bump
Very short, in-thread reply. 1-3 sentences max. Something like
"Bumping this in case it got buried, any thoughts?" or "Circling back —
totally opposed to grabbing some time in the coming weeks?" Adapt to tone.
NO new pitch, NO new value prop, just a polite nudge.

## Email 4 — Industry observation + tie back to original insights
Opens with what you're hearing from peer leaders in their persona's function
(sales / marketing / revops). Format: "Been hearing {specific issue
relevant to this persona's role} come up a lot in conversations with
{persona} leaders. Curious how you're going about that this year."
Then connect: "I'm sure that on top of {reference the original insights /
changes at their company that we opened with in email 1} has put a lot on
your plate." Close with a CTA on how 6sense could help with both. New
subject line (fresh thread), Daniel-tone — short, factual, lowercase.

## Email 5 — Value-add (your discretion)
Pick what fits best given the prospect: a relevant blog post, another
customer story not used in email 2, a piece of industry research from the
Science of B2B library in company_context.md, OR (if value-add doesn't fit)
a short industry-trend message specific to their persona. Default to value-
add. Whatever you pick, keep it short and useful — not a re-pitch.

## Email 6 — Breakup
Polite close. Acknowledge they may be busy, ask if there's a better time
or another person on the team to connect with. Soft, no guilt-trip.
Example structure (don't copy verbatim):
"Hey {first_name},
Seems like you've been busy — is there a better time to reach out or
someone else on the {company} team I should connect with? Open to
exploring this a bit more? All good if not.
Best,"

# Output format

Return ONLY a single JSON object inside one ```json fenced block, no prose
before or after. Schema:

{
  "emails": [
    {
      "position": 1,
      "thread": 1,
      "purpose": "insight-opener",
      "subject": "<subject line — short, factual, lowercase preferred>",
      "body": "<the email body, including greeting and sign-off>"
    },
    {
      "position": 2,
      "thread": 1,
      "purpose": "customer-story",
      "subject": "Re: <email 1's subject verbatim>",
      "body": "<...>"
    },
    {
      "position": 3,
      "thread": 1,
      "purpose": "bump",
      "subject": "Re: <email 1's subject verbatim>",
      "body": "<...>"
    },
    {
      "position": 4,
      "thread": 2,
      "purpose": "industry-observation",
      "subject": "<fresh subject — Daniel's style, short and factual>",
      "body": "<...>"
    },
    {
      "position": 5,
      "thread": 2,
      "purpose": "value-add",
      "subject": "Re: <email 4's subject verbatim>",
      "body": "<...>"
    },
    {
      "position": 6,
      "thread": 2,
      "purpose": "breakup",
      "subject": "Re: <email 4's subject verbatim>",
      "body": "<...>"
    }
  ]
}

Coherence requirement: when writing email 4, you can reference the same
insight you anchored on in email 1 (re-frame, don't repeat verbatim). When
writing email 2, the customer story must directly support the pain you set
up in email 1. The cadence must read as a coherent sequence, not 6 random
messages stapled together.
"""


def _parse_cadence(text: str) -> dict:
    """Extract the cadence JSON. Forgiving on fenced/unfenced output."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if not raw:
        m = re.search(r"(\{.*\})", text, re.DOTALL)
        raw = m.group(1) if m else None
    if not raw:
        return {"emails": [], "_error": "no JSON found", "_raw": text}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return {"emails": [], "_error": str(e), "_raw": text}
    data.setdefault("emails", [])
    return data


def draft_cadence(req: DraftRequest) -> tuple[dict, dict]:
    """Generate all 6 cadence emails in one Claude call.

    Returns (cadence_dict, usage_stats). cadence_dict has shape:
        {"emails": [{position, thread, purpose, subject, body}, ...]}
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # System = base prompt + cadence appendix + (cached) company context + tone
    base_system_with_cadence = SYSTEM_PROMPT_BASE + "\n\n---\n\n" + CADENCE_INSTRUCTIONS
    system = [
        {"type": "text", "text": base_system_with_cadence},
        {
            "type": "text",
            "text": (
                f"# COMPANY CONTEXT — what we sell, never invent claims outside this\n\n"
                f"{load_company_context()}\n\n---\n\n"
                f"# TONE — match this exactly\n\n{load_tone(req.profile_slug)}"
            ),
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        },
    ]

    user_msg = _build_user_message(req) + (
        "\n\n# CADENCE MODE\n"
        "Generate ALL 6 emails per the framework above. Return JSON only."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=6000,  # 6 emails + JSON overhead
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = next((b.text for b in response.content if b.type == "text"), "")
    cadence = _parse_cadence(text)
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_read": getattr(response.usage, "cache_read_input_tokens", 0),
        "cache_write": getattr(response.usage, "cache_creation_input_tokens", 0),
    }
    return cadence, usage
