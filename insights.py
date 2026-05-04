"""Generate a structured business-insights brief for a company.

Fast version: scrape the homepage with requests (instant), then ONE Claude
call with web_search to pull external signals and synthesize JSON.
Total runtime ~15-25s instead of multi-minute agentic loops.
"""

import json
import os
import re
from typing import Optional
from urllib.parse import urlparse

import anthropic
import requests
from bs4 import BeautifulSoup

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


def scrape_homepage(url: str, max_chars: int = 8000) -> str:
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


BRIEF_SYSTEM = """You are a B2B sales intelligence analyst. You will be given:
1. The text content of a company's homepage (already scraped)
2. Access to web_search for external signals

Produce a structured insights brief.

EFFICIENCY RULES:
- Use AT MOST 2 web_search calls total
- Then stop and produce the JSON brief

Process:
1. Read the scraped homepage text to understand what they do
2. Run 1-2 targeted web_searches: recent news, leadership hires, funding, events
3. Stop and synthesize

Output: a single JSON object inside one ```json fenced block. NO prose before or after.

Schema:
{
  "company_summary": "2-3 sentence summary of what the company does and who they serve",
  "is_public": true | false,
  "ticker": "TICKER or null if private",
  "insights": [
    {
      "bucket": "news|hires|funding|product|hiring_signals|events|strategic_moves",
      "title": "short headline (under 80 chars)",
      "summary": "1-2 sentence factual summary",
      "why_it_matters": "1 sentence: why a salesperson could anchor outreach on this",
      "source_url": "https://...",
      "date": "YYYY-MM (or YYYY-MM-DD) — REQUIRED, must be within the last 12 months"
    }
  ]
}

HARD RULES:
- DATE FILTER: Only include insights from the last 12 months. Exclude anything older. Each insight MUST include a `date`. If you can't verify a date, skip the insight.
- PUBLIC COMPANY CHECK: Determine if the company is publicly traded. Set `is_public` boolean and `ticker` (or null). If public, INCLUDE recent earnings / 10-K / 10-Q references as insights when relevant.
- 5-10 insights total. Quality over quantity.
- Every insight must be FACTUAL with a source URL.
- Skip buckets with no real signals — don't pad.
- "why_it_matters" is sharp and outreach-focused, not generic.
"""


def generate_brief(website_url: str) -> dict:
    """Scrape homepage + one Claude call with web_search. Returns parsed dict."""
    domain = root_domain(website_url)
    homepage_text = scrape_homepage(domain)

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    user_msg = (
        f"Company website: {domain}\n\n"
        f"Scraped homepage content:\n---\n{homepage_text}\n---\n\n"
        f"Use web_search (max 2 calls) for recent news, hires, funding, events. "
        f"Then produce the JSON brief."
    )

    messages = [{"role": "user", "content": user_msg}]

    response = None
    for _ in range(4):
        response = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            system=BRIEF_SYSTEM,
            output_config={"effort": "medium"},
            tools=[
                {
                    "type": "web_search_20260209",
                    "name": "web_search",
                    "max_uses": 2,
                },
            ],
            messages=messages,
        )
        if response.stop_reason == "end_turn":
            break
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue
        break

    text = "\n".join(b.text for b in (response.content if response else []) if b.type == "text")
    return _parse_brief(text)


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


def insights_by_bucket(brief: dict) -> dict[str, list[dict]]:
    """Group insights by bucket for display."""
    grouped = {b: [] for b in BUCKETS}
    for ins in brief.get("insights", []):
        bucket = ins.get("bucket", "news")
        if bucket not in grouped:
            grouped[bucket] = []
        grouped[bucket].append(ins)
    return {b: items for b, items in grouped.items() if items}
