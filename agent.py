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
    # 6sense intent data: raw user paste (keywords + pages visited) and the
    # 2-3 sentence hypothesis produced by intent.synthesize_intent(). Both
    # optional. When present, they get woven into the draft as additional
    # context — anchors a more specific "why now" hook.
    intent_data: str = ""
    intent_synthesis: str = ""


SYSTEM_PROMPT_BASE = """You are writing a single cold email for Daniel at 6sense.

# ABSOLUTE FORMATTING RULES

- NEVER USE EM DASHES. Not the character "—", not double-hyphens "--", not
  the en dash "–". Use commas, periods, colons, semicolons, or parentheses
  instead. This is non-negotiable.
- SHORT. Target 45-75 words for the email body. Maximum 95. The email must
  be scannable in 5 seconds and easily readable on a phone screen.
- CONVERSATIONAL, not salesy. Direct, factual, plain. Sound like a peer
  texting a quick note, not a vendor pitching.
- NO bullet lists in single emails unless the value prop genuinely needs 2
  short bullets. Default to flowing sentences.
- PARAGRAPH BREAKS: never write more than 2 sentences in a single paragraph.
  The opener (insight reference + immediate "so what") goes on its own line,
  then a blank line, then the next thought on a new paragraph. Walls of text
  are unreadable on a phone. Aim for 3 to 4 short paragraphs in a body.

# DO NOT SOUND LIKE AI

The biggest tell that an email was written by an LLM is overly formal,
overly complete phrasing. Daniel writes the way a human BDR talks:

- USE ABBREVIATIONS for role titles. Write "AEs", "VPs", "CRO", "CMO",
  "AE", "BDR", "SDR", "RevOps". NOT "Account Executives", "Vice Presidents",
  "Chief Revenue Officer", "Director-level positions".
- DROP "around your X offering" / "around your Y product line" / "to support
  the Z initiative" qualifiers. They're padding. Replace with shorter forms:
  - BAD: "hiring Account Executives and Director-level roles around your
    Data-as-a-Service offering"
  - GOOD: "hiring for AEs and Director level roles for your data offering"
- SHORTEN proper nouns when natural. "Data-as-a-Service" → "data offering"
  or "DaaS motion". "Account-Based Marketing platform" → "ABM platform".
- LOWERCASE the company name mid-sentence sometimes (matches Daniel's
  lowercase-subject habit and overall casual register). "saw snorkel is
  hiring..." reads more human than "Saw Snorkel is actively hiring...".
- DROP "actively" and "currently" qualifiers in front of verbs. They're
  filler. "actively hiring" → "hiring". "currently looking" → "looking".
- DROP "I noticed that" / "I can see that" / "It appears that". Start
  with the verb. "Saw snorkel is hiring..." not "I noticed that snorkel
  is actively hiring..."

If you find yourself writing a sentence that's grammatically perfect and
fully spelled out, ask: would a salesperson typing this on their phone in
30 seconds say it this way? Usually they'd shorten it.

# DO NOT RE-QUOTE INSIGHT NOUNS VERBATIM

When you reference an insight, name it ONCE in the opener. After that,
PARAPHRASE. "Career Networks and My Clinical Exchange" becomes "new
markets" or "those growth investments". "Q1 2026 earnings call" becomes
"the Q1 earnings" or "the recent announcement". This applies within a
single email AND across the cadence: if the email opens with the specific
product names, every subsequent reference uses a paraphrase.

Speak directly to the insight as if you understand what it means for them.
Avoid 6sense-jargon connectors ("who filled out a form", "anonymous research
signals", "buyer intent data") that sound like reused marketing copy and
don't connect to the actual signal you're referencing. Connect insight to
plain-English business consequence.

# FORBIDDEN PHRASES (the model keeps reaching for these)

Do NOT use any variant of:
- "happens before anyone fills out a form"
- "before they ever fill out a form"
- "who filled out a form"
- "who fills out a form"
- "most of that buying activity happens before"
- "anonymous research signals"
- "buyer intent data"

These are 6sense marketing taglines. They sound like robotic vendor copy.
If you're tempted to write one, REWRITE the sentence to say what the
insight actually means for THIS prospect's business in plain English.

# IMPORTANCE CLAIMS MUST CARRY CONTEXT

Phrases like "matters a lot", "is important", "is critical", "is key",
"becomes the main lever", "is the difference", "is what wins" are NOT
banned. They're useful as setups. But on their own they carry no
authority and read as filler.

Rule: when you use one of these phrases, the SAME sentence (or the very
next clause) must give the concrete reason. Don't claim importance and
stop. Say WHY in the same breath, in as few words as possible.

Examples:

- WEAK: "getting campaigns in front of the right accounts early matters a lot."
- BETTER: "matters because competitors are running the same plays."
- BETTER: "is what separates the deals you win from the ones competitors take."
- ALSO FINE: cut the importance claim entirely and let the next sentence
  about 6sense carry the weight.

Quick concrete stakes you can lean on when relevant (pick the one that
fits, paraphrase, don't list multiple):
- competitors getting to in-market accounts first
- spend leaking to low-intent traffic
- pipeline contribution unclear at QBR
- new hires ramping slower than plan
- the launch missing its number
- the renewal book leaking
- data too dirty for routing
- forecast accuracy slipping

The shorter the better. "Matters because competitors will get there first"
works. "Matters a lot" alone does not.

# CUT FILLER AGGRESSIVELY (final-pass rule)

Before finalizing each email, do a filler pass. Every word must earn its
place. Common cuts:

- "before competitors do" → "before competitors"
- "this year" / "right now" / "going forward" → cut unless load-bearing
- "I just wanted to" / "I figured I'd" → cut, start the sentence with the verb
- "It looks like" / "It seems like" → cut, just state the thing
- "from a {persona} perspective" → cut, the audience knows their own role
- Trailing softeners like "or so", "in some way", "kind of" → cut
- Doubled-up adjectives ("clean clear visibility") → pick one

If a sentence reads fine without a word, the word doesn't belong. Read
each email out loud in your head, cut anything that adds syllables without
adding meaning.

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

- NOT SALESY. Direct, factual, conversational. No hype words, no
  superlatives, no "we'd love to", no "I'd love to", no "would love to",
  no "absolutely", no "incredible", no "powerful".
- ONE specific, persona-anchored CTA (see CTA section below). No double asks.
- No preamble. No "hope this finds you well", "wanted to reach out",
  "circling back".
- Anchor on the selected insights, one or two, referenced naturally, not
  listed.
- Connect insight, why this matters for THIS persona, one specific next
  step. Keep each step to a sentence.

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

    # 6sense intent data: SECONDARY, additive context. Insights stay the
    # primary anchor of the email. Intent shows up as a short "noticed some
    # research" line that adds evidence the timing is right. Do NOT inflate
    # length to accommodate it.
    if req.intent_synthesis or req.intent_data:
        parts.append("\nINTENT CONTEXT (6sense data) — SECONDARY ANCHOR:")
        if req.intent_synthesis:
            parts.append(f"WHY-NOW HYPOTHESIS: {req.intent_synthesis}")
        if req.intent_data:
            parts.append(
                f"RAW PASTE (keywords + pages visited):\n"
                f"---\n{req.intent_data.strip()}\n---"
            )
        parts.append(
            "HARD RULES for intent context:\n"
            "- The PRIMARY anchor of email 1 is still the selected insight. "
            "Do NOT lead with intent.\n"
            "- Intent shows up as ONE short additional sentence after the "
            "insight hook. FORMAT: 'Noticed some research from the {company} "
            "team around {top keyword 1} and {top keyword 2}.' Pull the "
            "1-2 most prominent KEYWORDS from the raw paste, not the pages "
            "on our website. Do NOT say 'your team has been looking at our "
            "intent-data page' — that is too loose and reads like surveillance. "
            "Reference what THEY are researching by topic.\n"
            "- This ADDITIONAL sentence does NOT extend the email's word "
            "budget. Keep total length within the per-email range. Trim the "
            "rest if needed.\n"
            "- If the keywords don't meaningfully connect to the selected "
            "insight, skip the intent line entirely. Don't force it in.\n"
            "- The recipient should never feel surveilled. One subtle "
            "reference to their research topics, not a forensic readout."
        )

    if req.extra_notes:
        parts.append(f"\nADDITIONAL CONTEXT:\n{req.extra_notes}")

    parts.append(
        "\nWrite the email now.\n"
        "- SHORT, punchy, conversational. Mobile-readable at a glance.\n"
        "- NO EM DASHES. Not the character, not double-hyphens. Use commas, "
        "periods, colons, parentheses.\n"
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
    text = _strip_em_dashes(text)  # safety net
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

# UNIVERSAL RULES FOR ALL 6 EMAILS

- ABSOLUTELY NO EM DASHES. Not "—", not "--", not "–". Ever. Anywhere.
  Use commas, periods, colons, semicolons, or parentheses.
- SHORT, PUNCHY, MOBILE-READABLE. The whole email should be scannable in
  5 seconds on a phone. Short sentences. Short paragraphs (often one
  sentence each).
- CONVERSATIONAL, not salesy. Sound like a peer dropping a quick note.
- Match Daniel's tone exactly. Every email must read like he wrote it.
- PARAGRAPH BREAKS: never write more than 2 sentences in a single
  paragraph. Insert a blank line between thoughts. Wall-of-text is
  unreadable on a phone. Each email body should look like 2-4 short
  paragraphs (one to two sentences each).
- HYPERLINK CUSTOMERS: in email 2 (and email 5 if you reference a
  customer), wrap the customer name in a markdown link using the URL
  from the "Customer story URL map" section of company_context.md.
  Example: `[Mission Cloud](https://6sense.com/customer-stories/...)`
  ran a timing-based campaign and saw $17M in new pipeline...
  Use the link form ONCE per email, on the first mention of the customer.

# PARAPHRASE RULE — VERY IMPORTANT

- DO NOT re-quote the original insight verbatim across emails. Especially
  do not list specific product names, initiative names, or earnings-call
  product references (e.g. "Career Networks and My Clinical Exchange",
  "Project Opera", "Castlight Health rollout") more than ONCE across the
  cadence, and even then only if absolutely necessary.
- Use light paraphrases instead: "the new markets they're investing in",
  "the Q1 earnings update", "the recent expansion", "the build-out you
  mentioned on the call". The reader knows what you mean.
- After email 1 establishes the specific signal, every subsequent email
  refers to it in SHORTHAND, not in full.

# DON'T DROP 6SENSE JARGON ON SIGNALS WHERE IT DOESN'T LAND

- Do not paste generic 6sense talking points that don't connect to the
  prospect's actual situation. Bad example: prospect is scaling into new
  product lines and the email says "your campaigns need to keep up with
  buyers, not just who filled out a form." Form-fills have nothing to do
  with product expansion. That reads like a robot.
- Connect the SPECIFIC signal to the SPECIFIC pain. If they're scaling
  into new markets, the relevant 6sense angle is "knowing which accounts
  in those new markets are actually researching the category." Not forms.
- If 6sense's standard angle doesn't fit the signal cleanly, REPHRASE the
  6sense pitch so it does. Plain language about THEIR situation, not
  template phrases.

# Thread structure

THREE threads now (not two):

- **Thread 1 = emails 1, 2, 3.** Email 1 has a fresh subject. Emails 2 and
  3 are REPLIES, subject = `Re: <email 1's subject>` (verbatim).
- **Thread 2 = emails 4, 5.** Email 4 has a fresh subject (Daniel-tone,
  short, factual, lowercase, different angle from email 1 but same voice).
  Email 5 is a REPLY, subject = `Re: <email 4's subject>` (verbatim).
- **Thread 3 = email 6 ONLY.** Standalone breakup with its own fresh
  subject. The subject MUST be exactly: `bad timing / should I move on?`

# INTENT DATA — SECONDARY, ADDITIVE context across the cadence

If a "WHY-NOW HYPOTHESIS" and / or "RAW PASTE" appear in the user message,
treat them as SUPPORTING evidence, never the primary anchor. Insights from
section "INSIGHTS TO ANCHOR ON" remain the primary hook of every email.

CRITICAL: intent shows up as ONE short additional sentence, not as a
new opener or a length extension. Same word budget per email. If intent
doesn't naturally fit, skip it entirely.

- **Email 1**: anchor opens on the selected INSIGHT (unchanged). Then ONE
  short follow-up sentence in the form: "Noticed some research from the
  {company} team around {top keyword 1} and {top keyword 2}." Pull the
  1-2 most prominent KEYWORDS from the raw paste, NOT the 6sense pages
  they visited. Reference what they're researching by TOPIC. Do NOT say
  "your team has been looking at our intent-data page" — that reads
  surveilly and weak. Total word count stays within the 45-75 range.
  Trim other lines to make room.
- **Email 2**: when picking the customer story, prefer one whose topic
  aligns with the keyword themes if there's a clean match. No additional
  intent reference in the body. Customer choice is the only effect.
- **Email 4**: the "what we're hearing from peer leaders" line may
  loosely echo the keyword themes (e.g. if they're researching attribution
  and intent, mention attribution clarity as a topic peers are raising).
  No raw quotes from the paste. Same word budget.
- **Email 5**: the value-add should match what they have been researching
  if a clean match exists. Otherwise default to your normal choice.
- **Emails 3 and 6**: unchanged. Never reference intent.

If the hypothesis or paste doesn't meaningfully connect to a chosen
insight or persona, SKIP the intent line in email 1. Forcing it in
weakens the email.

The reader should never feel surveilled. One subtle reference at most,
in one email, paraphrased. Never list raw keywords or page URLs.

# Per-email framework + word budgets

## Email 1 — Insight-based opener (45-75 words body)
Hook on the strongest insight (or LinkedIn personal detail if provided).
Name the specific signal ONCE (the actual filing, the actual product
launch, the actual hire). Then translate into plain-English business
consequence in YOUR words, not 6sense marketing copy. Avoid robotic
connectors like "not just who filled out a form" or "anonymous research
signals". Connect insight, what it likely means for them, one persona-
anchored CTA.

## Email 2 — Customer story tied back to email 1's pain (40-60 words body)
Open by NAMING the artifact: "Thought this customer story was relevant
given what {company} is navigating right now." (Not "thought this one
was relevant", which is unclear.)

Format the customer outcomes as a SINGLE FLOWING SENTENCE, not bullets.
Bullets read as chunky and awkward in a short email. Inline reads like
a person talking.

Pattern (vary wording, keep the shape):
"FireMon, after using 6sense, saw 80% more accounts engaged, 3x faster
campaign launches, and 54% faster opportunity close times."

NEVER use bullet points in email 2. Numbers and percentages stay inline.

Do NOT add a separate sentence re-explaining why that customer is
relevant. You already said it's relevant in the opener. Pick the right
customer story and let the numbers do the work.

Then ONE tie-back sentence that PARAPHRASES the original pain in
plain language (e.g. "Based off the new markets {company} is investing
in, getting campaigns in front of in-market accounts faster is exactly
where this kind of motion pays off."). NO re-quoting the specific
product names from email 1.

ONE CTA.

Pick the customer from company_context.md whose industry / persona /
situation best matches this prospect.

## Email 3 — Short bump (15-30 words body)
Two lines max. Just a polite nudge. No new pitch.
Examples (don't copy verbatim):
- "Bumping this in case it got buried, any thoughts?"
- "Circling back, totally opposed to grabbing 15 min in the coming weeks?"

## Email 4 — Industry observation + tie back (50-70 words body)
THIS OPENING PATTERN IS THE WIN, keep it:
"Been hearing {specific issue relevant to this persona's role} come up
a lot in conversations with {persona} leaders at {their industry}
companies. Curious how you're thinking about that heading into {timeframe}."

Then ONE sentence tying it back to email 1's signal, but PARAPHRASE.
Do NOT re-state the specific product names or filing name from email 1.
Use generic shorthand: "new markets", "those growth investments", "the
recent announcement", "what {company} is navigating".

ONE CTA.

## Email 5 — Value-add or industry note (40-60 words body)
Frame it as relevant TO THEM, not interesting TO YOU. Avoid "stuck with
me", "I found this interesting", "I love this stat". The framing is
about THEIR situation.

Good frame: "One stat from 6sense's Science of B2B research that's
relevant given {their situation, paraphrased}: {stat}."

Then ONE tie-back sentence in plain language. Then ONE soft CTA.

Pick from: a Science of B2B stat, a relevant blog post, a different
customer story (not the one used in email 2), or a short industry-trend
note specific to their persona. Default to a stat that lands hard for
their function.

## Email 6 — Breakup with ONE situation-driven reason (35-55 words body)
NOT a multiple-choice quiz. NO bullet points. NO list of three options.

Read the prospect's actual situation (the company changes, the new role,
the expansion, the launch). Pick ONE plausible reason they might be
heads-down right now. Write it as a single conversational sentence.

Format (adapt wording, don't copy verbatim):

"Hi {first_name},

Totally understand if {specific situation-driven reason in plain prose,
e.g. 'getting the new product lines launched is taking priority right
now' / 'ramping the new hires is taking the floor this quarter' /
'closing out the fiscal year has the floor for now'}.

Would a placeholder for {time horizon, e.g. 'a month from now' / 'after
the launch settles'} make more sense?

Best,"

Subject MUST be exactly: `bad timing / should I move on?`

Personal. Situation-aware. Not formulaic. The placeholder offer is the
soft re-engagement hook.

# Output format

Return ONLY a single JSON object inside one ```json fenced block, no prose
before or after. Schema:

{
  "emails": [
    {
      "position": 1,
      "thread": 1,
      "purpose": "insight-opener",
      "subject": "<fresh subject, Daniel-tone, short and factual>",
      "body": "<email body with greeting and sign-off>"
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
      "subject": "<fresh subject, Daniel-tone, short and factual>",
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
      "thread": 3,
      "purpose": "breakup",
      "subject": "bad timing / should I move on?",
      "body": "<breakup body with ONE situation-driven reason + placeholder offer. NO bullet list.>"
    }
  ]
}

Coherence requirement: email 2's customer story must directly support
email 1's pain. Email 4 must reference the same insight from email 1
(reframed, not repeated). The cadence must read as a coherent sequence.

Re-read every email before finalizing. Three self-checks:

1. EM DASHES: if you see "—", "--", or "–" anywhere, rewrite that sentence
   with a comma or period.

2. PARAPHRASE: if a specific product name, initiative, or filing name from
   email 1 appears in emails 2 through 6, rewrite using shorthand ("new
   markets", "the Q1 update", "the recent expansion", "what you mentioned
   on the call"). The reader knows what you mean.

3. JARGON-DISCONNECT: if any email pastes a 6sense talking point that
   doesn't actually connect to the prospect's specific signal (e.g. talking
   about "form fills" when the signal is product expansion), rewrite the
   pitch so it speaks to the actual situation in plain language.

4. EMAIL 2 BULLETS: if email 2 contains bullet points, rewrite as a single
   flowing sentence.

5. EMAIL 6: must not contain bullet points or a list of three reasons.
   Plain prose, ONE situation-driven reason, placeholder offer.
"""


def _strip_em_dashes(s: str) -> str:
    """Remove em / en dashes / double-hyphens. Belt-and-suspenders.

    Replaces with a comma + space when in the middle of a sentence, else a
    space. Cheap heuristic but kills the most common offender if the model
    sneaks one through.
    """
    if not s:
        return s
    # Replace em (—), en (–), and double-hyphens with a comma + space
    out = s.replace(" — ", ", ").replace("—", ", ")
    out = out.replace(" – ", ", ").replace("–", ", ")
    out = out.replace(" -- ", ", ").replace("--", ", ")
    return out


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
    # Safety net: strip em / en dashes from every email body + subject.
    for em in cadence.get("emails", []):
        em["body"] = _strip_em_dashes(em.get("body", ""))
        em["subject"] = _strip_em_dashes(em.get("subject", ""))
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_read": getattr(response.usage, "cache_read_input_tokens", 0),
        "cache_write": getattr(response.usage, "cache_creation_input_tokens", 0),
    }
    return cadence, usage
