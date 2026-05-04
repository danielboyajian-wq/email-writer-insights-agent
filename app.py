"""Streamlit UI: website -> insights brief -> optional email draft."""

import hmac
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

from agent import DraftRequest, draft_email
from insights import BUCKETS, generate_brief, insights_by_bucket
from personas import PERSONAS, infer_persona_from_title


def _check_password() -> bool:
    """Return True if user has entered the right password.

    Reads APP_PASSWORD from env (local .env) or st.secrets (Streamlit Cloud).
    If no password is configured, the app is open (useful for local dev).
    """
    expected = os.getenv("APP_PASSWORD") or st.secrets.get("APP_PASSWORD", "") if hasattr(st, "secrets") else os.getenv("APP_PASSWORD", "")
    if not expected:
        return True  # no password configured -> open access (local only)

    if st.session_state.get("auth_ok"):
        return True

    st.title("🔒 Email Insights Agent")
    pw = st.text_input("Password", type="password")
    if st.button("Unlock"):
        if hmac.compare_digest(pw, expected):
            st.session_state["auth_ok"] = True
            st.rerun()
        else:
            st.error("Wrong password.")
    return False


if not _check_password():
    st.stop()

BUCKET_LABELS = {
    "news": "📰 News",
    "hires": "👥 Hires",
    "funding": "💰 Funding",
    "product": "🚀 Product",
    "hiring_signals": "🔍 Hiring signals",
    "events": "🎤 Events / Webinars",
    "strategic_moves": "♟️ Strategic moves",
}

st.set_page_config(page_title="Email Insights Agent", layout="wide")
st.title("Email Insights Agent")

with st.sidebar:
    st.subheader("API key")
    st.write("Anthropic:", "✅" if os.getenv("ANTHROPIC_API_KEY") else "❌ missing")
    st.caption("Set in `.env` (see `.env.example`)")
    if st.button("🔄 Reset session"):
        st.session_state.clear()
        st.rerun()

# === STEP 1: Insights ===
st.header("1. Generate insights brief")
website = st.text_input("Company website", placeholder="https://acme.com")

if st.button("🔎 Run research", type="primary", disabled=not website):
    with st.spinner("Researching... (this can take 30-60s — Claude is fetching the site and searching the web)"):
        try:
            brief = generate_brief(website)
            st.session_state["brief"] = brief
        except Exception as e:
            st.error(f"Research failed: {e}")
            st.stop()

if "brief" in st.session_state:
    brief = st.session_state["brief"]

    if brief.get("_error"):
        st.warning(f"Could not parse structured output: {brief['_error']}")
        with st.expander("Raw model output"):
            st.text(brief.get("_raw", ""))
        st.stop()

    st.success("Brief generated.")
    st.markdown(f"**What they do:** {brief.get('company_summary', '—')}")
    is_public = brief.get("is_public")
    ticker = brief.get("ticker")
    if is_public is True:
        st.markdown(f"📈 **Publicly traded** — `{ticker or 'ticker unknown'}`")
    elif is_public is False:
        st.markdown("🔒 **Private company**")

    st.subheader("Insights — check the ones to use in the email")
    grouped = insights_by_bucket(brief)

    selected = []
    for bucket, items in grouped.items():
        st.markdown(f"### {BUCKET_LABELS.get(bucket, bucket)}")
        for i, ins in enumerate(items):
            key = f"ins_{bucket}_{i}"
            date_label = f" · 📅 {ins['date']}" if ins.get("date") else ""
            checked = st.checkbox(
                f"**{ins.get('title', '')}**{date_label}",
                key=key,
            )
            with st.container():
                st.caption(ins.get("summary", ""))
                st.caption(f"💡 *{ins.get('why_it_matters', '')}*")
                if ins.get("source_url"):
                    st.caption(f"🔗 [source]({ins['source_url']})")
            if checked:
                selected.append(ins)

    st.session_state["selected_insights"] = selected

    st.divider()

    # === STEP 2: Draft email ===
    st.header("2. Draft email")

    c1, c2 = st.columns(2)
    recipient_name = c1.text_input("Recipient name", "")
    recipient_title = c2.text_input("Recipient title", "")

    # Persona — auto-suggest from title, allow override
    persona_options = list(PERSONAS.keys())
    auto_persona = infer_persona_from_title(recipient_title)
    default_idx = persona_options.index(auto_persona) if auto_persona in persona_options else 0
    persona_slug = st.selectbox(
        "Persona (auto-detected from title — override if needed)",
        options=persona_options,
        index=default_idx,
        format_func=lambda s: PERSONAS[s].label,
    )
    st.caption(PERSONAS[persona_slug].priorities)

    your_pitch = st.text_area(
        "Your pitch (one line — what specifically you want this email to drive toward)",
        "Quick chat to see if 6sense could help your team.",
    )

    with st.expander("➕ Optional: paste LinkedIn for hyper-personalization"):
        linkedin_text = st.text_area(
            "Paste recipient's LinkedIn About / Experience / recent posts",
            height=180,
            label_visibility="collapsed",
        )

    extra_notes = st.text_area("Extra notes (optional)", "", height=60)

    if st.button("✍️ Draft email", type="primary", disabled=not selected):
        if not selected:
            st.warning("Select at least one insight first.")
            st.stop()

        req = DraftRequest(
            company=website,
            company_summary=brief.get("company_summary", ""),
            selected_insights=selected,
            recipient_name=recipient_name,
            recipient_title=recipient_title,
            persona_slug=persona_slug,
            your_pitch=your_pitch,
            linkedin_text=linkedin_text,
            extra_notes=extra_notes,
        )
        with st.spinner("Drafting..."):
            try:
                text, usage = draft_email(req)
            except Exception as e:
                st.error(f"Draft failed: {e}")
                st.stop()

        st.subheader("Draft")
        st.text_area("Email", text, height=450, label_visibility="collapsed")
        st.caption(
            f"Tokens — in: {usage['input_tokens']} | out: {usage['output_tokens']} "
            f"| cache read: {usage['cache_read']} | cache write: {usage['cache_write']}"
        )
