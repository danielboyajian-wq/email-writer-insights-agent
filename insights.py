"""Generate a structured business-insights brief for a company.

Fast version: scrape the homepage with requests (instant), then ONE Claude
call with web_search to pull external signals and synthesize JSON.
Total runtime ~15-25s instead of multi-minute agentic loops.
"""

import json
import os
import re
from datetime import date, datetime, timedelta
from typing import Optional
from urllib.parse import urlparse

from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic
import requests
from bs4 import BeautifulSoup

try:
    from tavily import TavilyClient
except ImportError:  # pragma: no cover
    TavilyClient = None  # type: ignore

from cache import cache_brief, get_cached_brief
import history

MODEL = "claude-sonnet-4-6"

BUCKETS = [
    "news",
    "hires",
    "funding",
    "product",
    "hiring_signals",
    "events",
    "strategic_moves",
]


def normalize_url(url: str) -> str:
    """Strip tracking params, normalize to scheme://netloc/path."""
    url = url.strip()
    if not url:
        return url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")


def root_domain(url: str) -> str:
    """Return scheme://netloc — the canonical 'company website'."""
    p = urlparse(normalize_url(url))
    return f"{p.scheme}://{p.netloc}"


def scrape_homepage(url: str, max_chars: int = 4000) -> str:
    """Plain HTTP fetch + text extraction. No JS rendering."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        return f"[fetch error: {e}]"

    soup = BeautifulSoup(resp.text, "html.parser")
    # Drop script/style/nav noise
    for tag in soup(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:max_chars]


BRIEF_SYSTEM_TEMPLATE = """You are a GTM (Go-To-Market) sales intelligence analyst. \
You are given pre-filtered, date-restricted search results for a company. \
Your job: synthesize them into a structured insights brief for a salesperson preparing outreach.

WHAT MATTERS for outreach (include if found in the search results):

- New funding rounds
- Strategic partnerships
- New product launches
- Expansion into new markets or verticals
- Earnings calls / 10-Q / 10-K filings (if public)
- New executive hires in Sales, Marketing, Revenue, or GTM roles
- Customer wins or case studies
- Forrester Wave placements, Gartner Magic Quadrant placements, or comparable analyst recognitions
- Public statements about growth priorities or strategic direction

HARD RULES — non-negotiable:

- TODAY IS {today}. THE 6-MONTH CUTOFF IS {cutoff}. \
Anything dated before {cutoff} is OUT. No exceptions.
- DATE HANDLING: For each kept insight, the `date` field comes from this \
priority list:
  1. The DATE line of the source search result, if present (copy verbatim).
  2. An EXPLICIT date in the EXCERPT or TITLE — e.g. "in May 2025", \
"announced March 4, 2026", "Series D in 2025-05". Convert to YYYY-MM.
  3. `null` if neither is available. Vague language like "recent" or \
"this quarter" or "this year" does NOT count — use null.
- If the EXCERPT/TITLE explicitly references an event-date before {cutoff} \
(e.g. "$100M Series D in May 2025", "announced in 2023"), DROP THE INSIGHT \
entirely. The event is outside the window even if the article is fresh.
- The cutoff is enforced both in your output AND by post-filter in code. \
Insights you mark with a pre-cutoff date will be dropped by the post-filter, \
so don't include them.
- Customer wins / case studies count ONLY if the announcement is dated within the 6-month window.
- "Public statements about growth priorities" means earnings calls, investor letters, \
conference keynotes, podcast or press interviews with executives. Not generic blog posts.
- Forrester Wave / Gartner Magic Quadrant / analyst placements count ONLY if the report or \
recognition was published within the 6-month window.
- Do NOT include awards, technical research papers, or engineering benchmarks unless they \
directly signal a GTM motion or business expansion.
- Return 4-6 high-quality insights. Quality beats quantity. Do not pad.

OUTPUT — a single JSON object inside one ```json fenced block. NO prose before or after.

Schema:
{{
  "company_summary": "2-3 sentences on what the company does and who they serve",
  "is_public": true | false,
  "ticker": "TICKER or null if private",
  "insights": [
    {{
      "bucket": "news|hires|funding|product|hiring_signals|events|strategic_moves",
      "title": "short headline (under 80 chars)",
      "summary": "1-2 sentence factual summary",
      "why_it_matters": "1 sentence: the outreach angle a GTM rep could use",
      "source_url": "https://...",
      "date": "YYYY-MM or YYYY-MM-DD, or null if no date can be confirmed"
    }}
  ]
}}

`why_it_matters` should be sharp and outreach-focused. NOT "this shows growth" — \
instead "newly hired CRO is likely re-evaluating the sales tech stack."
"""


def _build_brief_system() -> str:
    """Inject today's date and the 6-month cutoff into the system prompt."""
    today = date.today()
    cutoff = today - timedelta(days=183)
    return BRIEF_SYSTEM_TEMPLATE.format(
        today=today.isoformat(),
        cutoff=cutoff.isoformat(),
    )


def _company_name_from_url(url: str) -> str:
    """Derive a brand-form company name. snorkel.ai -> 'Snorkel AI'."""
    p = urlparse(normalize_url(url))
    host = p.netloc
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) >= 2:
        # snorkel.ai -> "Snorkel AI", acme-corp.io -> "Acme Corp IO"
        base = parts[0].replace("-", " ")
        tld = parts[-1]
        # Treat known marketing TLDs as part of the brand
        if tld in {"ai", "io", "co", "app", "dev", "tech"}:
            return f"{base.title()} {tld.upper()}"
        return base.title()
    return host


def _company_host(url: str) -> str:
    """Bare host without www. for use as a strict search anchor."""
    p = urlparse(normalize_url(url))
    host = p.netloc
    if host.startswith("www."):
        host = host[4:]
    return host


def _tavily_search(
    client: "TavilyClient",
    query: str,
    days: int = 183,
    topic: str = "general",
    max_results: int = 5,
    search_depth: str = "advanced",
) -> list[dict]:
    """One Tavily search call. `topic="news"` returns articles with reliable dates.

    Uses advanced search_depth by default — slower per call (~2-3s vs 1s)
    but much higher result relevance.
    """
    try:
        resp = client.search(
            query=query,
            search_depth=search_depth,
            days=days,
            topic=topic,
            max_results=max_results,
            include_answer=False,
        )
        return resp.get("results", []) or []
    except Exception as e:
        return [{"_error": str(e), "query": query}]


def _gather_search_results(
    company_name: str,
    company_host: str,
) -> dict[str, list[dict]]:
    """Fire 4 Tavily searches in parallel.

    Queries anchor on BOTH the brand name (in quotes for exact match) AND
    the host. Generic single-word brand names (e.g. "Snorkel") otherwise
    match the dictionary word against unrelated companies.
    """
    key = os.getenv("TAVILY_API_KEY")
    if not key or TavilyClient is None:
        raise RuntimeError(
            "TAVILY_API_KEY is missing. Get a free key at https://tavily.com "
            "(1000 searches/month, no credit card) and add it to your .env."
        )
    client = TavilyClient(api_key=key)

    # Quoted brand name + topic="general". The news topic does keyword-relevance
    # ranking which fails on ambiguous brand names ("Snorkel" the noun matches
    # totally unrelated articles). General topic does proper phrase matching.
    brand = f'"{company_name}"'

    queries = {
        "funding_earnings": (
            f"{brand} funding earnings 2026",
            "general",
        ),
        "hires": (
            f"{brand} executive hire 2026",
            "general",
        ),
        "product_partnerships": (
            f"{brand} product launch partnership 2026",
            "general",
        ),
        "analyst_growth": (
            f"{brand} Forrester Wave Gartner Magic Quadrant expansion 2026",
            "general",
        ),
    }

    results: dict[str, list[dict]] = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        future_to_key = {
            ex.submit(_tavily_search, client, q, topic=t): k
            for k, (q, t) in queries.items()
        }
        for fut in as_completed(future_to_key):
            results[future_to_key[fut]] = fut.result()
    return results


def _format_search_results_for_prompt(results: dict[str, list[dict]]) -> str:
    """Compact, model-friendly rendering of the Tavily results."""
    if not results:
        return "(no results)"
    blocks = []
    for category, items in results.items():
        if not items:
            continue
        block = [f"## {category}"]
        for r in items:
            if r.get("_error"):
                block.append(f"  (search error: {r['_error']})")
                continue
            title = r.get("title", "").strip()
            url = r.get("url", "").strip()
            content = (r.get("content") or "").strip()[:500]
            published = r.get("published_date", "") or ""
            block.append(f"- TITLE: {title}")
            if published:
                block.append(f"  DATE: {published}")
            block.append(f"  URL: {url}")
            if content:
                block.append(f"  EXCERPT: {content}")
        blocks.append("\n".join(block))
    return "\n\n".join(blocks)


def generate_brief(
    website_url: str,
    force_refresh: bool = False,
    profile_slug: Optional[str] = None,
) -> dict:
    """Tavily search (parallel) + single Claude synthesis call. ~5-10s total.

    Tavily provides date-filtered, pre-recent search results. Claude only
    synthesizes — no agentic loop, no slow server-side searches. Results
    are cached on disk for 24 hours per normalized domain, and if
    `profile_slug` is set, also persisted to Postgres history.
    """
    domain = root_domain(website_url)

    if not force_refresh:
        cached = get_cached_brief(domain)
        if cached is not None:
            return cached

    company_name = _company_name_from_url(domain)
    company_host = _company_host(domain)
    homepage_text = scrape_homepage(domain)

    # Step 1: fire 4 Tavily searches in parallel. ~2s total.
    try:
        search_results = _gather_search_results(company_name, company_host)
    except RuntimeError as e:
        return {
            "company_summary": "",
            "insights": [],
            "_error": str(e),
            "_raw": "",
        }

    search_text = _format_search_results_for_prompt(search_results)

    # Step 2: single Claude call to synthesize JSON from the pre-filtered
    # search results + homepage. No tools needed — Claude is just doing
    # structured extraction here, which is what it's best at.
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    user_msg = (
        f"Company website: {domain}\n"
        f"Company name (derived): {company_name}\n\n"
        f"HOMEPAGE CONTEXT (scraped):\n---\n{homepage_text}\n---\n\n"
        f"SEARCH RESULTS (from the last 6 months, pre-filtered by Tavily):\n"
        f"---\n{search_text}\n---\n\n"
        "Synthesize the JSON brief per the system prompt's schema. Use the "
        "search results as your primary source. Confirm each insight's date "
        "from the DATE field in the results, and only include things within "
        "the 6-month window. The homepage is just for the company_summary."
    )

    system_prompt = _build_brief_system()
    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=system_prompt,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": user_msg}],
    )

    text = "\n".join(b.text for b in response.content if b.type == "text")
    brief = _parse_brief(text)

    # Hard server-side filter: drop any insight whose parsed date is before
    # the 6-month cutoff. Defensive — the prompt also tells the model to do
    # this, but model decisions on the boundary aren't reliable.
    cutoff = date.today() - timedelta(days=183)
    kept, dropped = [], []
    for ins in brief.get("insights", []):
        d = _parse_insight_date(ins.get("date", "") or "")
        if d is not None and d < cutoff:
            dropped.append(ins)
            continue
        kept.append(ins)
    brief["insights"] = kept
    if dropped:
        brief["_dropped_pre_cutoff"] = [
            {"title": d.get("title"), "date": d.get("date")} for d in dropped
        ]

    if brief.get("insights"):
        cache_brief(domain, brief)
        # Persist to per-profile history (no-op if DB unavailable).
        if profile_slug:
            history.save_brief(profile_slug, domain, company_name, brief)
    else:
        brief["_raw"] = text
        brief["_warning"] = "Model returned 0 insights (after cutoff filter)."
        brief["_search_results"] = search_text[:2000]
    return brief


def _parse_brief(text: str) -> dict:
    """Extract the JSON block from the model output. Forgiving."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        raw = m.group(1)
    else:
        m = re.search(r"(\{.*\})", text, re.DOTALL)
        if not m:
            return {"company_summary": "", "insights": [], "_raw": text, "_error": "no JSON found"}
        raw = m.group(1)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return {"company_summary": "", "insights": [], "_raw": text, "_error": str(e)}

    data.setdefault("company_summary", "")
    data.setdefault("insights", [])
    return data


STALE_AFTER_DAYS = 183  # ~6 months


def _parse_insight_date(raw: str) -> Optional[date]:
    """Parse 'YYYY-MM' or 'YYYY-MM-DD'. Returns None on failure."""
    if not raw or not isinstance(raw, str):
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            d = datetime.strptime(raw, fmt).date()
            return d
        except ValueError:
            continue
    return None


def insight_age_days(insight: dict) -> Optional[int]:
    """Days since the insight's `date`. None if undatable."""
    d = _parse_insight_date(insight.get("date", ""))
    if d is None:
        return None
    return (date.today() - d).days


def is_stale(insight: dict, threshold_days: int = STALE_AFTER_DAYS) -> bool:
    """True if the insight is older than the threshold (default 6 months)."""
    age = insight_age_days(insight)
    return age is not None and age > threshold_days


def _sort_key(ins: dict) -> tuple:
    """Sort by age ascending (freshest first). Undated insights go last."""
    age = insight_age_days(ins)
    if age is None:
        # Push undated insights to the end; among them, preserve original order
        return (1, 10_000_000)
    return (0, age)


def insights_by_bucket(brief: dict, drop_stale: bool = False) -> dict[str, list[dict]]:
    """Group insights by bucket, freshest first inside each bucket.

    drop_stale defaults to False — show everything the model returned with
    amber tags on >6mo entries, so the user can judge. Set True to hide them.
    """
    grouped = {b: [] for b in BUCKETS}
    for ins in brief.get("insights", []):
        if drop_stale and is_stale(ins):
            continue
        bucket = ins.get("bucket", "news")
        if bucket not in grouped:
            grouped[bucket] = []
        grouped[bucket].append(ins)
    return {
        b: sorted(items, key=_sort_key)
        for b, items in grouped.items()
        if items
    }
