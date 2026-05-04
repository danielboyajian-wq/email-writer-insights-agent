"""Persona context: how 6sense helps Marketing, Sales, and RevOps personas.

Each persona has:
- priorities: what they care about / pain points
- six_sense_framing: how 6sense maps to their world (in Daniel's voice)
- proof_points: customer outcomes / stats to optionally cite
- snippet_examples: short value-prop snippets pulled from real outbound

The agent uses these to ground emails in persona-specific language and
outcomes. Personas are picked manually in the UI OR auto-inferred from title
via `infer_persona_from_title`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Persona:
    slug: str
    label: str
    priorities: str
    six_sense_framing: str
    proof_points: list[str]
    snippet_examples: list[str]


MARKETING = Persona(
    slug="marketing",
    label="Marketing",
    priorities=(
        "Pipeline contribution, MQL→SQL conversion, channel performance, "
        "campaign ROI, attribution clarity, audience accuracy, cost per opportunity. "
        "Pain: rebuilding audiences manually, channels in silos, campaigns going stale "
        "as buyer behavior shifts, spending on low-intent traffic, no visibility into "
        "real buying activity."
    ),
    six_sense_framing=(
        "6sense gives marketers visibility into real buying activity — which target "
        "accounts are anonymously researching their company, competitors, or related "
        "topics — and lets them use those signals to power personalized campaigns "
        "across every channel. Outcome: higher ROI by targeting in-market accounts "
        "and cutting spend on low-intent audiences. Mechanisms: dynamic audiences "
        "that update as buyers change, single canvas for ads/email/web, AI email "
        "agents triggered by real-time activity, automatic CRM/MAP sync."
    ),
    proof_points=[
        "FireMon: 80% increase in accounts engaged, 3x faster campaign launches, "
        "54% faster opportunity close time",
        "OpenText: scaled from 3 to 21 campaigns, 27% new revenue in 30 days",
        "Everbridge: streamlined renewal engagement across 930 accounts annually "
        "via a single intelligent workflow",
        "Forrester Wave Q1 2026: 6sense named a Leader in Revenue Marketing "
        "Platforms for B2B",
    ],
    snippet_examples=[
        "Not sure how familiar you are with 6sense, but we show you which target "
        "accounts are anonymously researching {company}, your competitors, or "
        "related topics — and let you use those signals to power personalized "
        "campaigns across every channel.",
        "6sense gives marketers visibility into real buying activity, helping "
        "drive higher ROI by targeting in-market accounts and cutting spend on "
        "low-intent audiences.",
    ],
)


SALES = Persona(
    slug="sales",
    label="Sales",
    priorities=(
        "Pipeline coverage, win rate, deal velocity, ACV, rep productivity, quota "
        "attainment, ramping new reps, beating competitors to the table. "
        "Pain: reps wasting time on accounts that aren't in market, getting to "
        "deals after competitors, low opportunity rate, slow time-to-close, "
        "unpredictable pipeline."
    ),
    six_sense_framing=(
        "6sense surfaces accounts showing real buying signals so reps know exactly "
        "who's in-market and ready to enter a purchase cycle. Mechanisms: see "
        "which accounts are actually in-market (target outreach → higher opportunity "
        "rate), understand what they're researching (speak to their pain → higher "
        "ACV), see when a customer is starting their research (get in before "
        "competitors → higher win rate). Outcome: get into deals sooner, accelerate "
        "deal cycles, increase ACVs, beat competitors."
    ),
    proof_points=[
        "Domo, Tableau, Dell average outcomes: up to 8x lift in opportunity open "
        "rate, 2x improvement in win rate, 1.5–2x faster time to close",
        "Cross-customer averages: 2x increase in deal size, 20% better conversions, "
        "31% more opportunities",
        "Flexera: 82% pipeline lift from high-intent accounts, 85% of target "
        "accounts reached in 2 months",
        "Service Express: accelerated sales velocity by 25% with 6sense-driven "
        "SDR strategy",
        "2026 State of BDR Report: targeting two additional personas correlates "
        "with 11 points higher quota attainment",
    ],
    snippet_examples=[
        "I believe there's an opportunity for 6sense to help your reps get into "
        "deals sooner, accelerate deal cycles, increase ACVs, and beat "
        "{competitor} to the table.",
        "Our customers typically see a 2x increase in deal size, 20% better "
        "conversions, and 31% more opportunities using 6sense.",
        "We help sales teams and reps:\n"
        "- see which accounts are actually in-market (target your outreach → "
        "higher opportunity rate)\n"
        "- understand what they're researching (speak to their pain → higher ACV "
        "deals)\n"
        "- see when a customer is starting their research (get in before "
        "{competitor} → higher win rate)",
    ],
)


REVOPS = Persona(
    slug="revops",
    label="Revenue Operations",
    priorities=(
        "Data hygiene, system integrations, attribution, lead routing, forecasting "
        "accuracy, tooling stack rationalization, contact match rates across "
        "systems. Pain: bad CRM/MAP data, overlapping/conflicting datasets, manual "
        "matching, broken routing, missing technographics."
    ),
    six_sense_framing=(
        "6sense fixes the two biggest revenue-ops headaches: bad CRM/MAP data and "
        "zero visibility into overlapping datasets. It automatically matches "
        "contacts across systems so routing is accurate, flags bad or missing data "
        "in audience segments, and enriches contacts with technographics and "
        "psychographics for better personalization and higher conversions."
    ),
    proof_points=[
        "Socure's Treasure Ops: transformational pipeline results unlocked through "
        "6sense-powered ops",
        "LiveOps: 'fastest turnaround we've ever seen' — generated millions in "
        "pipeline",
    ],
    snippet_examples=[
        "Bad CRM/MAP data and zero visibility into overlapping datasets are the "
        "two biggest headaches I hear when talking with revenue leaders. Here's "
        "how 6sense helps fix that:\n"
        "• Automatically matches contacts across systems so routing is accurate\n"
        "• Flags bad or missing data in your audience segments\n"
        "• Enriches contacts with technographics/psychographics for better "
        "personalization and higher conversions",
    ],
)


PERSONAS: dict[str, Persona] = {
    MARKETING.slug: MARKETING,
    SALES.slug: SALES,
    REVOPS.slug: REVOPS,
}


# Title -> persona slug. Order matters: more specific keywords first.
TITLE_HINTS = [
    # RevOps signals
    ("revops", "revops"),
    ("rev ops", "revops"),
    ("revenue operations", "revops"),
    ("sales operations", "revops"),
    ("sales ops", "revops"),
    ("marketing operations", "revops"),
    ("marketing ops", "revops"),
    ("gtm operations", "revops"),
    # Sales signals
    ("sdr", "sales"),
    ("bdr", "sales"),
    ("account executive", "sales"),
    (" ae ", "sales"),
    ("vp sales", "sales"),
    ("vp of sales", "sales"),
    ("sales director", "sales"),
    ("head of sales", "sales"),
    ("cro", "sales"),
    ("chief revenue", "sales"),
    ("sales enablement", "sales"),
    # Marketing signals
    ("cmo", "marketing"),
    ("chief marketing", "marketing"),
    ("vp marketing", "marketing"),
    ("vp of marketing", "marketing"),
    ("head of marketing", "marketing"),
    ("marketing director", "marketing"),
    ("demand gen", "marketing"),
    ("demand generation", "marketing"),
    ("growth marketing", "marketing"),
    ("abm", "marketing"),
    ("brand", "marketing"),
    ("marketing manager", "marketing"),
    ("digital marketing", "marketing"),
]


def infer_persona_from_title(title: str) -> str | None:
    """Best-effort persona inference. Returns slug or None if no match."""
    if not title:
        return None
    t = f" {title.lower()} "
    for keyword, slug in TITLE_HINTS:
        if keyword in t:
            return slug
    return None


def format_persona_for_prompt(slug: str, company: str = "") -> str:
    """Render a persona block for the LLM system prompt."""
    p = PERSONAS.get(slug)
    if not p:
        return ""
    proof = "\n".join(f"- {pt}" for pt in p.proof_points)
    snippets = "\n\n".join(p.snippet_examples)
    return (
        f"# Persona: {p.label}\n\n"
        f"## What they care about\n{p.priorities}\n\n"
        f"## How 6sense helps them\n{p.six_sense_framing}\n\n"
        f"## Proof points (cite naturally — only if relevant, never as a wall of stats)\n{proof}\n\n"
        f"## Reference snippets (for voice/structure, not literal copy)\n{snippets}"
    )
