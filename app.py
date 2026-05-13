"""Streamlit UI: profile-aware insights brief + email draft."""

import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

from agent import DraftRequest, draft_email
from insights import BUCKETS, generate_brief, insights_by_bucket
from personas import PERSONAS, infer_persona_from_title
from profiles import (
    delete_profile,
    list_profiles,
    save_profile,
    transcribe_image,
)

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

# ============================================================================
# SIDEBAR: API key + profile switcher
# ============================================================================
with st.sidebar:
    st.subheader("API key")
    st.write("Anthropic:", "✅" if os.getenv("ANTHROPIC_API_KEY") else "❌ missing")
    st.caption("Set in `.env` (see `.env.example`)")

    st.divider()
    st.subheader("Profile")
    profiles = list_profiles()
    if not profiles:
        st.warning("No profiles yet — create one in the **Profiles** tab.")
        active_profile = None
    else:
        slugs = [p.slug for p in profiles]
        names = {p.slug: p.name for p in profiles}
        default_idx = 0
        if "active_profile" in st.session_state and st.session_state["active_profile"] in slugs:
            default_idx = slugs.index(st.session_state["active_profile"])
        active_profile = st.selectbox(
            "Active profile",
            options=slugs,
            index=default_idx,
            format_func=lambda s: names[s],
        )
        st.session_state["active_profile"] = active_profile

    st.divider()
    if st.button("🔄 Reset session"):
        for k in list(st.session_state.keys()):
            if k != "active_profile":
                del st.session_state[k]
        st.rerun()

# ============================================================================
# TABS: Draft  |  Profiles
# ============================================================================
draft_tab, profiles_tab = st.tabs(["✍️ Draft", "👤 Profiles"])

# ----------------------------------------------------------------------------
# TAB 1: DRAFT
# ----------------------------------------------------------------------------
with draft_tab:
    if not active_profile:
        st.info("Create a profile in the **Profiles** tab to get started.")
    else:
        # === STEP 1: Insights ===
        st.header("1. Generate insights brief")
        website = st.text_input("Company website", placeholder="https://acme.com")

        if st.button("🔎 Run research", type="primary", disabled=not website):
            with st.spinner("Researching... (~15–25s)"):
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

            st.subheader("Insights — check the ones to use in the email")
            grouped = insights_by_bucket(brief)

            selected = []
            for bucket, items in grouped.items():
                st.markdown(f"### {BUCKET_LABELS.get(bucket, bucket)}")
                for i, ins in enumerate(items):
                    key = f"ins_{bucket}_{i}"
                    checked = st.checkbox(f"**{ins.get('title', '')}**", key=key)
                    with st.container():
                        st.caption(ins.get("summary", ""))
                        st.caption(f"💡 *{ins.get('why_it_matters', '')}*")
                        if ins.get("date"):
                            st.caption(f"🗓️ {ins['date']}")
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
                req = DraftRequest(
                    company=website,
                    company_summary=brief.get("company_summary", ""),
                    selected_insights=selected,
                    recipient_name=recipient_name,
                    recipient_title=recipient_title,
                    persona_slug=persona_slug,
                    your_pitch=your_pitch,
                    profile_slug=active_profile,
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

# ----------------------------------------------------------------------------
# TAB 2: PROFILES (onboarding + management)
# ----------------------------------------------------------------------------
with profiles_tab:
    st.header("Profiles")
    st.caption(
        "Each profile holds one user's tone — a voice description plus example emails. "
        "Add a profile so the agent can write in your voice."
    )

    # --- existing profiles list ---
    if profiles:
        st.subheader("Existing profiles")
        for p in profiles:
            cols = st.columns([4, 1, 1])
            cols[0].markdown(f"**{p.name}** &nbsp; `{p.slug}`")
            cols[0].caption(f"Created: {p.created_at[:10] if p.created_at else '—'}")
            if cols[1].button("✏️ Edit", key=f"edit_{p.slug}"):
                st.session_state["editing_profile"] = p.slug
                st.rerun()
            if cols[2].button("🗑️ Delete", key=f"del_{p.slug}"):
                delete_profile(p.slug)
                if st.session_state.get("active_profile") == p.slug:
                    del st.session_state["active_profile"]
                st.rerun()
        st.divider()

    # --- create / edit form ---
    editing_slug = st.session_state.get("editing_profile")
    if editing_slug:
        from profiles import get_profile, load_tone as load_profile_tone

        existing = get_profile(editing_slug)
        existing_tone_md = load_profile_tone(editing_slug)
        st.subheader(f"Edit profile: {existing.name if existing else editing_slug}")
        if st.button("← Cancel edit"):
            del st.session_state["editing_profile"]
            st.rerun()
    else:
        existing = None
        existing_tone_md = ""
        st.subheader("Create a new profile")

    # Pre-fill if editing
    if existing:
        default_name = existing.name
        default_pitch = existing.default_pitch
        # try to extract existing description + examples from tone.md
        default_description = ""
        default_examples_text = ""
        if existing_tone_md:
            # crude split — works with our save_profile format
            import re as _re
            m = _re.search(r"## Voice description\s*\n+(.*?)\n+---", existing_tone_md, _re.DOTALL)
            if m:
                default_description = m.group(1).strip()
            m2 = _re.search(r"## Examples\s*(.*)$", existing_tone_md, _re.DOTALL)
            if m2:
                default_examples_text = m2.group(1).strip()
    else:
        default_name = ""
        default_pitch = ""
        default_description = ""
        default_examples_text = ""

    name = st.text_input("Display name", default_name, placeholder="e.g. Daniel, Sarah, Marcus")

    description = st.text_area(
        "Tone description",
        default_description,
        height=200,
        placeholder=(
            "Describe your voice. Examples:\n"
            "- Sentence length, capitalization habits\n"
            "- Vocabulary you use / avoid\n"
            "- Punctuation style (em-dashes, lowercase subjects, etc.)\n"
            "- CTA style\n"
            "- Phrases to NEVER use"
        ),
    )

    default_pitch_input = st.text_input(
        "Default pitch (optional — pre-fills the draft form for this profile)",
        default_pitch,
        placeholder="Quick chat to see if 6sense could help your team.",
    )

    st.divider()
    st.markdown("**Email examples** — paste text below or upload screenshots.")

    # Image upload with auto-transcribe
    uploads = st.file_uploader(
        "Upload screenshot(s) — auto-transcribed with Claude vision",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
    )

    transcribed_examples: list[str] = []
    if uploads:
        if st.button(f"🔍 Transcribe {len(uploads)} image(s)"):
            progress = st.progress(0.0, text="Transcribing...")
            for i, f in enumerate(uploads):
                media_type = f"image/{f.type.split('/')[-1]}" if f.type else "image/png"
                try:
                    text = transcribe_image(f.read(), media_type=media_type)
                    transcribed_examples.append(text)
                except Exception as e:
                    st.error(f"Failed to transcribe {f.name}: {e}")
                progress.progress((i + 1) / len(uploads), text=f"Transcribed {i+1}/{len(uploads)}")
            progress.empty()
            # Append transcribed to the paste box via session state
            st.session_state["_transcribed"] = "\n\n---\n\n".join(transcribed_examples)
            st.success(f"Transcribed {len(transcribed_examples)} email(s). Review below.")

    transcribed_block = st.session_state.get("_transcribed", "")
    examples_text = st.text_area(
        "Examples (paste your emails — separate multiple with `---` on its own line)",
        value=(transcribed_block + ("\n\n---\n\n" + default_examples_text if default_examples_text else "")
               if transcribed_block else default_examples_text),
        height=400,
        placeholder=(
            "Paste 5–25 real emails. Separate them with `---` on its own line.\n\n"
            "Example:\n\n"
            "Subject: quick q about your stack\n\n"
            "Hi Jane,\n\n"
            "Saw the new self-serve tier launch ...\n\n"
            "Worth 15 min next week?\n\n"
            "— Dan\n\n"
            "---\n\n"
            "Subject: next email here\n..."
        ),
    )

    save_label = "💾 Update profile" if existing else "💾 Save profile"
    if st.button(save_label, type="primary", disabled=not (name and description and examples_text)):
        # Split on "---" separators
        examples = [e.strip() for e in examples_text.split("\n---\n") if e.strip()]
        if not examples:
            examples = [examples_text.strip()]
        saved = save_profile(
            name=name,
            tone_description=description,
            examples=examples,
            default_pitch=default_pitch_input,
            slug=editing_slug if editing_slug else None,
        )
        st.session_state["active_profile"] = saved.slug
        if "editing_profile" in st.session_state:
            del st.session_state["editing_profile"]
        if "_transcribed" in st.session_state:
            del st.session_state["_transcribed"]
        st.success(f"Saved profile **{saved.name}** with {len(examples)} examples.")
        st.rerun()
