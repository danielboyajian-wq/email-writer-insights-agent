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
        "WHAT THEY CARE ABOUT: Pipeline contribution, full-funnel attribution, "
        "marketing-sourced revenue, MQL→SQA conversion, audience accuracy at the "
        "account level, cost per opportunity, channel ROI, sales-marketing "
        "alignment around shared revenue goals. Increasingly: shift from MQLs to "
        "Marketing Qualified Accounts (MQAs) because B2B deals involve 10-11 "
        "decision makers, not individuals.\n\n"
        "TOP PAINS:\n"
        "- Anonymous buying: only ~3% of web visitors convert to forms; up to 90% "
        "of identifiable account visitors stay anonymous. Most pipeline activity "
        "is invisible to them.\n"
        "- Resource constraints: 48% of B2B marketing leaders cite budget / "
        "headcount cuts as the #1 challenge. Teams of 2-10 expected to scale "
        "without proportional investment. Mid-market especially.\n"
        "- Attribution gaps: ~90% can't confidently connect marketing activities "
        "to closed-won revenue. Kills credibility in CFO conversations.\n"
        "- Audience targeting inconsistency: 63% struggle to reach the right "
        "buyers across full buying groups. Campaigns scatter.\n"
        "- Sales-marketing misalignment: 44% rank it as a top challenge. Surface-"
        "level collaboration, not operationalized revenue processes.\n"
        "- AI tool sprawl: chaos of adopting AI + fragmented martech. Pressure "
        "without clarity.\n"
        "- Buyers are 69% through their journey before engaging sales. Most "
        "content is gated, blocking early influence.\n"
        "- Momentum loss mid-year: teams reactive instead of strategic past Q1.\n"
        "- Only 5-7% of target accounts are actually in-market at any given time. "
        "Spend wasted on the other 93-95%."
    ),
    six_sense_framing=(
        "6sense gives marketers visibility into real buying activity — which target "
        "accounts are anonymously researching their company, competitors, or "
        "related topics — and lets them act on those signals across every channel.\n\n"
        "Key motions that resonate:\n"
        "- Web de-anonymization + account matching: turn the 90% anonymous traffic "
        "into named target accounts.\n"
        "- Shift from MQL to MQA: focus on the 5-7% of accounts genuinely in-"
        "market right now, not individual form fills.\n"
        "- Full-journey attribution: track impact from anonymous research through "
        "closed-won deals, not just form fills and campaign response.\n"
        "- Single canvas for ads/email/web/sales: dynamic audiences update as "
        "buyer behavior shifts, AI Email Agents trigger on real-time activity, "
        "CRM/MAP sync is automatic.\n"
        "- Ungated content + smart account tracking: stop blocking early-stage "
        "buyers behind forms while still measuring intent.\n"
        "- For lean teams (mid-market): orchestration that compounds, not "
        "tactical optimization that doesn't scale."
    ),
    proof_points=[
        "FireMon: 80% increase in accounts engaged, 3x faster campaign launches, "
        "54% faster opportunity close",
        "OpenText: scaled from 3 to 21 campaigns, 27% new revenue in 30 days",
        "Everbridge: 930+ accounts streamlined via a single intelligent workflow",
        "Coveo: 42 new opportunities in 9 months from ABM after shifting off "
        "lead-based",
        "Bonterra: $6M influenced pipeline (+445% YoY)",
        "Khoros: 42% shorter sales cycle, 16% larger deals, 4x demo conversion "
        "on personalized site experiences (built by a 2-person marketing team)",
        "F12.net: tripled in-market account engagement, hit full-year sales "
        "target by June (small team)",
        "Hexagon: 459% lift in known-account engagement in 3 months",
        "Forrester Wave Q1 2026: Leader in Revenue Marketing Platforms for B2B "
        "(highest possible scores in 14 criteria)",
        "Forrester Wave Q1 2025: Leader in B2B Intent Data Providers (10x "
        "coverage vs. competitors)",
        "Gartner Magic Quadrant for ABM: Leader, 5 years running, highest "
        "positioning for Ability to Execute",
        "Forrester 2026 prediction backdrop: ungoverned GenAI in commercial "
        "apps could cost B2B companies $10B+. AI-powered platforms with "
        "governance and signal quality become the safer bet.",
    ],
    snippet_examples=[
        "Not sure how familiar you are with 6sense, but we show you which target "
        "accounts are anonymously researching {company}, your competitors, or "
        "related topics, and let you use those signals across every channel.",
        "6sense helps marketers connect anonymous buying activity to closed-won "
        "revenue, not just form fills, so attribution actually holds up in CFO "
        "conversations.",
    ],
)


SALES = Persona(
    slug="sales",
    label="Sales",
    priorities=(
        "WHAT THEY CARE ABOUT: Pipeline coverage, win rate, deal velocity, ACV, "
        "rep productivity, quota attainment, ramping new reps, multi-threading "
        "into buying committees, beating competitors to the table.\n\n"
        "TOP PAINS (4 categories):\n\n"
        "1. COMPLEX BUYER DYNAMICS\n"
        "- Bloated buying committees: 5-16 decision makers per B2B deal. Reps "
        "have to arm a champion to sell internally.\n"
        "- Risk-averse buyers, consensus paralysis, internal stakeholder "
        "conflicts.\n"
        "- Information overload: buyers drowning in data, analysis paralysis, "
        "deals stall in late stage.\n"
        "- The 95:5 rule: up to 95% of the target market is NOT in-market at "
        "any given moment. Reps wasting cycles on the other 95%.\n\n"
        "2. PIPELINE & DATA ISSUES\n"
        "- Data decay: poor CRM hygiene stalls pipeline velocity, wastes rep "
        "time on bad records.\n"
        "- Attribution: leaders can't reliably map revenue back to specific "
        "marketing or outbound efforts.\n"
        "- Inconsistent SDR→AE hand-offs: lost momentum, frustrated buyers.\n\n"
        "3. SALES & MARKETING MISALIGNMENT\n"
        "- Wasted leads: no shared qualification criteria → quality leads fall "
        "through the cracks.\n"
        "- Message fragmentation: outbound doesn't match content strategy. "
        "Reps can't deliver a cohesive buyer journey.\n\n"
        "4. TECH SPRAWL & MACRO PRESSURES\n"
        "- AI tool fatigue: rapid AI/sales-tech adoption caused tech sprawl. "
        "Hard to show ROI or streamline workflows.\n"
        "- Budget constraints: do more with less. Higher quotas, tighter "
        "resources, headcount freezes.\n\n"
        "FORRESTER 2026 BACKDROP: B2B buying is shifting toward decentralized "
        "content creation, influencer-driven discovery (75% of enterprises "
        "increasing influencer budgets), and 'AI Inside' product evaluation "
        "compressing the selection phase."
    ),
    six_sense_framing=(
        "6sense gives reps a way out of the 95:5 problem: surface the 5% of "
        "accounts ACTUALLY in-market right now, so reps spend cycles on "
        "winnable deals.\n\n"
        "Mechanisms that resonate:\n"
        "- See which accounts are in-market right now (target outreach → "
        "higher opportunity rate).\n"
        "- See WHAT they're researching (speak to their actual pain → higher "
        "ACV).\n"
        "- See WHEN they're starting research (get in before competitors → "
        "higher win rate, first-on-shortlist wins 77% of the time).\n"
        "- Multi-thread the buying committee: +2 personas per account = ~11pp "
        "higher quota attainment (2026 State of BDR Report).\n"
        "- Sales Copilot inside Salesforce/HubSpot: account-level intel where "
        "reps already live, reducing tech sprawl.\n"
        "- AI Email Agents: equivalent to 3 human SDRs (Vendavo), so reps "
        "focus on real conversations instead of low-intent prospecting."
    ),
    proof_points=[
        "Domo / Tableau / Dell averages: up to 8x lift in opportunity open "
        "rate, 2x win rate, 1.5–2x faster time to close",
        "Cross-customer averages: 2x increase in deal size, 20% better "
        "conversions, 31% more opportunities",
        "Flexera: 82% pipeline lift from high-intent accounts, 85% of target "
        "accounts reached in 2 months",
        "Service Express: 25% sales velocity acceleration via 6sense-driven "
        "SDR strategy",
        "Mission Cloud (CDW): $17M new pipeline, $8.2M launched ARR in 6 "
        "months from timing-based migration campaigns",
        "Clari 'Wake the Dead' closed-lost reactivation: 79% account CTR, "
        "$1.1M pipeline from 5 qualified meetings (2x target)",
        "Vendavo AI Email Agents: output equivalent to 3 human SDRs; full-"
        "year $3.3M pipeline, 3x return vs. human BDRs",
        "2026 State of BDR Report: 99% of BDRs use AI (table stakes, not "
        "an edge); average quota attainment 92%; targeting +2 personas per "
        "account correlates with +11pp quota attainment",
        "First-on-shortlist wins ~77% of deals (Science of B2B)",
    ],
    snippet_examples=[
        "Up to 95% of your target market isn't in-market at any given moment. "
        "6sense surfaces the 5% that is, so your reps spend cycles on "
        "winnable deals instead of low-intent prospecting.",
        "Our customers typically see a 2x increase in deal size, 20% better "
        "conversions, and 31% more opportunities using 6sense.",
        "We help sales teams:\n"
        "- see which accounts are actually in-market (higher opportunity rate)\n"
        "- understand what they're researching (higher ACV deals)\n"
        "- see when they're starting research (get in before competitors, "
        "first-on-shortlist wins ~77% of the time)",
    ],
)


REVOPS = Persona(
    slug="revops",
    label="Revenue Operations",
    priorities=(
        "WHAT THEY CARE ABOUT: Aligning marketing, sales, and customer success "
        "into one predictable revenue engine. A single source of truth for data. "
        "Eliminating operational silos. Automating workflows. Scaling the "
        "customer journey efficiently.\n\n"
        "TOP PRIORITIES (5 categories):\n\n"
        "1. REVENUE ALIGNMENT & CROSS-FUNCTIONAL HARMONY\n"
        "- Shared KPIs across marketing, sales, customer success (e.g. matching "
        "lead quality to close rates). Eliminates finger-pointing.\n"
        "- Seamless handoffs so buyers never feel the seams between departments.\n\n"
        "2. DATA INTEGRITY & SINGLE SOURCE OF TRUTH\n"
        "- Clean data architecture across CRM (Salesforce / HubSpot), MAP, and "
        "intent / enrichment systems. Leaders and frontline teams see the "
        "exact same numbers.\n"
        "- Full-funnel attribution: which specific marketing campaigns and "
        "sales touches generate closed-won.\n\n"
        "3. PIPELINE HEALTH & PREDICTABILITY\n"
        "- Pipeline velocity: time from lead to closed-won, by stage. "
        "Drives forecast accuracy.\n"
        "- Win/loss analysis: where deals stall, why, turn into coaching loops.\n\n"
        "4. REVENUE & GROWTH METRICS THEY OWN\n"
        "- ARR: predictable recurring revenue baseline.\n"
        "- NRR (Net Revenue Retention): the gold-standard SaaS metric. "
        "Renewals + expansion minus churn.\n"
        "- CAC: cost to acquire a dollar of ARR.\n"
        "- CLV / LTV: total customer worth across contract life.\n"
        "- Win rate, sales velocity, ACV, customer retention rate.\n\n"
        "5. TECH STACK OPTIMIZATION\n"
        "- Consolidation: audit overlapping tools, cut platforms that don't "
        "show quantifiable ROI. This is THEIR mandate today.\n"
        "- Automation: replace manual processes with ops software. Frictionless "
        "billing/collections, accurate routing.\n\n"
        "TOP PAINS:\n"
        "- Bad CRM/MAP data, conflicting datasets, manual contact matching "
        "across systems.\n"
        "- Tech sprawl: vendors that overlap, integration debt, ROI hard to "
        "prove.\n"
        "- Attribution that doesn't survive a CFO conversation.\n"
        "- Broken routing because contacts aren't matched across systems."
    ),
    six_sense_framing=(
        "6sense gives RevOps a single platform that REPLACES the stitched-"
        "together stack (visitor ID + intent + enrichment + sequencer + ABM "
        "orchestrator) AND fixes the data hygiene problem at the same time. "
        "This is the consolidation play that maps directly to their mandate.\n\n"
        "Mechanisms that resonate:\n"
        "- Automatic contact matching across CRM/MAP so routing is accurate.\n"
        "- Flags bad / missing data in audience segments before it ruins a "
        "campaign or forecast.\n"
        "- Enriches contacts with technographics and psychographics for "
        "better routing, scoring, and personalization.\n"
        "- Full-funnel attribution: anonymous research → MQA → opportunity → "
        "closed-won, all in one model.\n"
        "- AI / signal quality with governance (vs. the ungoverned AI risk "
        "Forrester is warning about for 2026).\n"
        "- Cuts the tool-consolidation conversation from 'which five vendors' "
        "to 'one platform doing the work of five'."
    ),
    proof_points=[
        "Socure's Treasure Ops: transformational pipeline results",
        "LiveOps: 'fastest turnaround we've ever seen', millions in pipeline",
        "Cross-customer: 2x increase in deal size, 20% better conversions, "
        "31% more opportunities (consistent forecasting input)",
        "Mission Cloud (CDW): timing-based migration campaign generated "
        "$17M new pipeline + $8.2M launched ARR in 6 months — a model for "
        "signal-driven ops",
        "Forrester Wave Q1 2025: Leader in B2B Intent Data Providers (top "
        "scores for identity resolution and noise filtering, both core RevOps "
        "data-quality concerns)",
        "Gartner Magic Quadrant for ABM: Leader, 5 years running, highest "
        "Ability to Execute",
    ],
    snippet_examples=[
        "Bad CRM/MAP data and overlapping vendors are the two biggest "
        "headaches I hear when talking with RevOps leaders. 6sense helps fix "
        "both at once:\n"
        "- Auto-matches contacts across systems so routing is accurate\n"
        "- Flags bad or missing data before it hits a campaign or forecast\n"
        "- Enriches with technographics/psychographics for routing + scoring\n"
        "- Replaces visitor ID + intent + enrichment + sequencer with ONE "
        "platform",
        "Most RevOps leaders I talk to are running consolidation right now. "
        "Worth seeing where 6sense fits if you're auditing the stack at "
        "{company}?",
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
