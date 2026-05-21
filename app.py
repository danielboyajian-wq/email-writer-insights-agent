"""Email Insights — editorial intelligence terminal."""

import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

from agent import DraftRequest, draft_cadence, draft_email
import history
from insights import (
    BUCKETS,
    generate_brief,
    insight_age_days,
    insights_by_bucket,
    is_stale,
)
from personas import PERSONAS, infer_persona_from_title
from profiles import (
    delete_profile,
    list_profiles,
    save_profile,
    transcribe_image,
)
from styles import (
    bucket_head,
    inject_styles,
    render_email_output,
    render_hero,
    section_head,
    status_pip,
)

BUCKET_LABELS = {
    "news":              "News",
    "hires":             "Hires",
    "funding":           "Funding",
    "product":           "Product",
    "hiring_signals":    "Hiring signals",
    "events":            "Events / Webinars",
    "strategic_moves":   "Strategic moves",
}

st.set_page_config(page_title="Email Insights", page_icon="✦", layout="wide")
inject_styles()

# ============================================================================
# SIDEBAR
# ============================================================================
with st.sidebar:
    st.markdown("### Signal")
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
    status_pip("Anthropic — connected" if has_anthropic else "Anthropic — missing", ok=has_anthropic)
    has_tavily = bool(os.getenv("TAVILY_API_KEY"))
    status_pip("Tavily — connected" if has_tavily else "Tavily — missing", ok=has_tavily)
    if not has_tavily:
        st.caption(
            "Get a free Tavily key at tavily.com — 1000 searches/mo, "
            "no card. Required for research."
        )
    has_db = history.is_enabled()
    status_pip("History — connected" if has_db else "History — disabled", ok=has_db)
    if not has_db:
        st.caption(
            "Set DATABASE_URL (Neon free tier works) to save and "
            "browse past research."
        )

    st.markdown("### Profile")
    profiles = list_profiles()
    if not profiles:
        st.warning("No profiles. Create one in the **Profiles** tab.")
        active_profile = None
    else:
        slugs = [p.slug for p in profiles]
        names = {p.slug: p.name for p in profiles}
        default_idx = 0
        if "active_profile" in st.session_state and st.session_state["active_profile"] in slugs:
            default_idx = slugs.index(st.session_state["active_profile"])
        active_profile = st.selectbox(
            "Active voice",
            options=slugs,
            index=default_idx,
            format_func=lambda s: names[s],
            label_visibility="collapsed",
        )
        st.session_state["active_profile"] = active_profile

    st.markdown("### Session")
    if st.button("Reset state", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k != "active_profile":
                del st.session_state[k]
        st.rerun()

    # --- Saved companies (per-profile history) ---
    if active_profile and history.is_enabled():
        st.markdown("### Saved companies")
        profile_label = names.get(active_profile, active_profile)
        with st.expander(f"📁 {profile_label}'s history", expanded=False):
            search_q = st.text_input(
                "Search",
                key="history_search",
                placeholder="Filter by name or domain",
                label_visibility="collapsed",
            )
            saved = history.list_briefs(active_profile, search=search_q or "")
            if not saved:
                st.caption("No saved research yet." if not search_q else "No matches.")
            else:
                st.caption(f"{len(saved)} saved")
                for sb in saved[:50]:
                    age = history.age_days(sb)
                    cls = history.staleness_class(sb)
                    age_color = {
                        "fresh": "var(--success, oklch(62% 0.13 160))",
                        "aging": "oklch(68% 0.13 75)",
                        "stale": "oklch(58% 0.18 25)",
                    }[cls]
                    age_label = f"{age}d" if age < 14 else (f"{age}d" if age < 30 else "stale")

                    cols = st.columns([0.78, 0.22])
                    if cols[0].button(
                        sb.company_name,
                        key=f"load_{sb.url}",
                        use_container_width=True,
                        help=f"Researched {sb.researched_at.date().isoformat()}",
                    ):
                        # Restore brief + URL into session so the Draft tab
                        # renders as if we just researched.
                        st.session_state["brief"] = sb.brief
                        st.session_state["website"] = sb.url
                        st.session_state["loaded_from_history"] = True
                        st.rerun()
                    if cols[1].button("×", key=f"del_{sb.url}", help="Delete"):
                        history.delete_brief(active_profile, sb.url)
                        st.rerun()
                    # Age indicator
                    st.markdown(
                        f"<div style='margin:-0.4rem 0 0.3rem 0.2rem;'>"
                        f"<span style='font-family:var(--font); font-size:0.7rem; "
                        f"color:{age_color};'>● {age_label}</span></div>",
                        unsafe_allow_html=True,
                    )

# ============================================================================
# MAIN
# ============================================================================
render_hero()

draft_tab, profiles_tab = st.tabs(["Draft", "Profiles"])

# ----------------------------------------------------------------------------
# DRAFT TAB
# ----------------------------------------------------------------------------
with draft_tab:
    if not active_profile:
        st.info("Create a profile in the **Profiles** tab to begin.")
    else:
        # --- §01 Research ---
        section_head("01", "Research")
        st.caption("Paste a company URL. We read the homepage and the open web.")

        website = st.text_input(
            "Company website",
            value=st.session_state.get("website", ""),
            placeholder="acme.com",
            label_visibility="collapsed",
            key="website_input",
        )
        # Keep session_state["website"] in sync with whatever's typed
        st.session_state["website"] = website

        run_col, reload_col = st.columns([1, 4])
        with run_col:
            run = st.button(
                "Run research", type="primary",
                disabled=not website, use_container_width=True,
            )
        if run:
            with st.spinner("Reading homepage, searching news, synthesizing (~15s)"):
                try:
                    brief = generate_brief(website, profile_slug=active_profile)
                    st.session_state["brief"] = brief
                    st.session_state.pop("loaded_from_history", None)
                except Exception as e:
                    st.error(f"Research failed: {e}")
                    st.stop()

        if "brief" in st.session_state:
            brief = st.session_state["brief"]

            if brief.get("_error"):
                st.warning(f"Could not parse structured output — {brief['_error']}")
                with st.expander("Raw model output"):
                    st.text(brief.get("_raw", ""))
                st.stop()

            # Insights
            section_head("", "Insights")
            summary = brief.get("company_summary", "")
            is_public = brief.get("is_public")
            ticker = brief.get("ticker")
            tag = ""
            if is_public and ticker:
                tag = f" · public · {ticker}"
            elif is_public is False:
                tag = " · private"
            st.markdown(
                f"<p style='font-size:0.92rem; line-height:1.55; color:var(--fg-1); "
                f"max-width:68ch; margin:0.15rem 0 0.4rem;'>{summary}"
                f"<span style='color:var(--fg-2);'>{tag}</span></p>",
                unsafe_allow_html=True,
            )

            # Surface a clear warning when the model returned 0 insights, with
            # the raw output for debugging. Also offer a re-research button.
            if not brief.get("insights"):
                st.warning(
                    "The model returned 0 insights. This is usually a prompt-restriction "
                    "issue, not a 'no recent activity' reality. Try re-researching, or "
                    "expand the raw output below to see what the model actually said."
                )
                cols = st.columns([1, 4])
                if cols[0].button("Re-research", use_container_width=True):
                    with st.spinner("Re-researching with cache bypassed"):
                        try:
                            brief = generate_brief(
                                website,
                                force_refresh=True,
                                profile_slug=active_profile,
                            )
                            st.session_state["brief"] = brief
                            st.rerun()
                        except Exception as e:
                            st.error(f"Re-research failed: {e}")
                            st.stop()
                with st.expander("Raw model output"):
                    st.text(brief.get("_raw", "(no raw output captured)"))
                st.stop()

            st.caption("Select the insights to anchor the email on.")

            grouped = insights_by_bucket(brief)
            selected = []
            for bucket, items in grouped.items():
                bucket_head(BUCKET_LABELS.get(bucket, bucket))
                for i, ins in enumerate(items):
                    key = f"ins_{bucket}_{i}"
                    with st.container():
                        c_check, c_body = st.columns([0.05, 0.95])
                        with c_check:
                            checked = st.checkbox(
                                " ",
                                key=key,
                                label_visibility="collapsed",
                            )
                        with c_body:
                            age = insight_age_days(ins)
                            age_html = ""
                            if age is not None:
                                if age < 30:
                                    label = f"{age}d"
                                else:
                                    months = age // 30
                                    label = f"{months}mo"
                                if is_stale(ins):
                                    age_html = (
                                        f'<span class="eia-age-tag is-stale" '
                                        f'title="Older than 6 months. Verify before referencing.">'
                                        f'{label}</span>'
                                    )
                                else:
                                    age_html = (
                                        f'<span class="eia-age-tag is-fresh" '
                                        f'title="Within the last 6 months.">'
                                        f'{label}</span>'
                                    )
                            else:
                                age_html = (
                                    '<span class="eia-age-tag is-unknown" '
                                    'title="Source date could not be confirmed. '
                                    'Verify recency before referencing.">'
                                    'no date found</span>'
                                )
                            st.markdown(
                                f"<div style='font-size:0.9rem; font-weight:500; "
                                f"line-height:1.4; color:var(--fg); margin-bottom:0.15rem;'>"
                                f"{ins.get('title','')}{age_html}</div>",
                                unsafe_allow_html=True,
                            )
                            st.markdown(
                                f"<div style='font-size:0.84rem; line-height:1.5; "
                                f"color:var(--fg-1); margin-bottom:0.3rem;'>"
                                f"{ins.get('summary','')}</div>",
                                unsafe_allow_html=True,
                            )
                            meta_bits = []
                            why = ins.get('why_it_matters', '')
                            if why:
                                meta_bits.append(f"<span style='color:var(--fg-1);'>{why}</span>")
                            if ins.get("date"):
                                meta_bits.append(f"<span style='color:var(--fg-2);'>{ins['date']}</span>")
                            if ins.get("source_url"):
                                meta_bits.append(f"<a href='{ins['source_url']}' target='_blank'>source</a>")
                            meta_html = " · ".join(meta_bits)
                            st.markdown(
                                f"<div style='font-size:0.78rem; line-height:1.5; "
                                f"margin-bottom:0.2rem;'>{meta_html}</div>",
                                unsafe_allow_html=True,
                            )
                    if checked:
                        selected.append(ins)

            st.session_state["selected_insights"] = selected

            # --- §03 Draft ---
            section_head("03", "Compose")

            c1, c2 = st.columns(2)
            recipient_name = c1.text_input("Recipient name", "", placeholder="Jane Doe")
            recipient_title = c2.text_input("Recipient title", "", placeholder="VP Marketing")

            persona_options = list(PERSONAS.keys())
            auto = infer_persona_from_title(recipient_title)
            default_idx = persona_options.index(auto) if auto in persona_options else 0
            persona_slug = st.selectbox(
                "Persona",
                options=persona_options,
                index=default_idx,
                format_func=lambda s: PERSONAS[s].label,
            )
            st.caption(PERSONAS[persona_slug].priorities)

            your_pitch = st.text_area(
                "Your angle",
                "Quick chat to see if 6sense could help your team.",
                height=70,
            )

            with st.expander("Hyper-personalize with LinkedIn"):
                linkedin_text = st.text_area(
                    "Paste profile TEXT (About, Activity / Posts, Featured) "
                    "— URLs alone won't work, LinkedIn blocks scraping",
                    height=180,
                    label_visibility="collapsed",
                )
                # Warn if user pasted just a URL — that does nothing.
                _stripped = linkedin_text.strip()
                if _stripped and len(_stripped) < 200 and (
                    _stripped.startswith("http") or "linkedin.com/" in _stripped
                ):
                    st.warning(
                        "That looks like just a LinkedIn URL. The drafter can't fetch "
                        "the page (LinkedIn blocks scraping). Open the profile in your "
                        "browser, copy the **About** section, then the **Activity / Posts** "
                        "tab content (especially recent posts), and paste that text here. "
                        "Without text content, the LinkedIn hook will be skipped."
                    )
                    # Don't pass the URL through — the model will ignore it anyway,
                    # and clearing it removes the false "mandatory LinkedIn use" signal.
                    linkedin_text = ""

            extra_notes = st.text_area("Notes (optional)", "", height=70)

            # Output mode toggle — single email vs full 6-email cadence
            mode = st.radio(
                "Output",
                options=["Single email", "6-email cadence"],
                horizontal=True,
                key="output_mode",
            )

            draft_col, _ = st.columns([1, 4])
            with draft_col:
                go_label = "Draft email" if mode == "Single email" else "Draft cadence"
                go = st.button(
                    go_label,
                    type="primary",
                    disabled=not selected,
                    use_container_width=True,
                )
            if go:
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

                if mode == "Single email":
                    with st.spinner("Drafting in your voice."):
                        try:
                            text, usage = draft_email(req)
                        except Exception as e:
                            st.error(f"Draft failed: {e}")
                            st.stop()
                    section_head("04", "Output")
                    render_email_output(text)
                    st.caption(
                        f"in {usage['input_tokens']}  ·  out {usage['output_tokens']}  ·  "
                        f"cache read {usage['cache_read']}  ·  cache write {usage['cache_write']}"
                    )
                else:
                    with st.spinner("Drafting all 6 emails in your voice (~30s)."):
                        try:
                            cadence, usage = draft_cadence(req)
                        except Exception as e:
                            st.error(f"Cadence failed: {e}")
                            st.stop()

                    section_head("04", "Cadence")

                    if cadence.get("_error"):
                        st.warning(f"Could not parse cadence JSON: {cadence['_error']}")
                        with st.expander("Raw model output"):
                            st.text(cadence.get("_raw", ""))
                        st.stop()

                    emails = sorted(
                        cadence.get("emails", []),
                        key=lambda e: e.get("position", 0),
                    )
                    if not emails:
                        st.warning("No emails returned.")
                        st.stop()

                    # Render emails grouped by thread
                    current_thread = None
                    for em in emails:
                        thr = em.get("thread", 1)
                        if thr != current_thread:
                            st.markdown(
                                f"<div style='font-family:var(--font); font-size:0.72rem; "
                                f"font-weight:600; letter-spacing:0.06em; text-transform:uppercase; "
                                f"color:var(--fg-2); margin:1.4rem 0 0.5rem;'>"
                                f"Thread {thr}</div>",
                                unsafe_allow_html=True,
                            )
                            current_thread = thr
                        # Header strip for each email
                        st.markdown(
                            f"<div style='display:flex; align-items:baseline; gap:0.6rem; "
                            f"margin:0.5rem 0 0.25rem;'>"
                            f"<span style='font-family:var(--font); font-size:0.78rem; "
                            f"font-weight:600; color:var(--fg);'>Email {em.get('position')}</span>"
                            f"<span style='font-family:var(--font); font-size:0.72rem; "
                            f"color:var(--fg-2);'>· {em.get('purpose', '').replace('-', ' ')}</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                        # Subject line
                        st.markdown(
                            f"<div style='font-family:var(--font); font-size:0.82rem; "
                            f"color:var(--fg-1); margin-bottom:0.35rem;'>"
                            f"<span style='color:var(--fg-2);'>Subject:</span> "
                            f"<span style='font-weight:500;'>{em.get('subject', '')}</span></div>",
                            unsafe_allow_html=True,
                        )
                        render_email_output(em.get("body", ""))

                    st.caption(
                        f"in {usage['input_tokens']}  ·  out {usage['output_tokens']}  ·  "
                        f"cache read {usage['cache_read']}  ·  cache write {usage['cache_write']}"
                    )

# ----------------------------------------------------------------------------
# PROFILES TAB
# ----------------------------------------------------------------------------
with profiles_tab:
    section_head("§", "Profiles")
    st.caption(
        "Each profile is one writer's voice — a tone description plus example emails. "
        "Add yours and the agent will draft accordingly."
    )

    # --- existing ---
    if profiles:
        st.markdown(
            "<div style='font-size:0.72rem; font-weight:500; letter-spacing:0.04em; "
            "text-transform:uppercase; color:var(--fg-2); margin:1.25rem 0 0.5rem;'>"
            "On file</div>",
            unsafe_allow_html=True,
        )
        for p in profiles:
            cols = st.columns([5, 1, 1])
            cols[0].markdown(
                f"<div style='padding:0.55rem 0; border-bottom:1px solid var(--border);'>"
                f"<span style='font-size:0.92rem; font-weight:500;'>{p.name}</span>"
                f" &middot; <span style='font-size:0.78rem; color:var(--fg-2);'>{p.slug}</span>"
                f"<div style='font-size:0.76rem; color:var(--fg-2); margin-top:0.1rem;'>"
                f"{p.created_at[:10] if p.created_at else ''}</div></div>",
                unsafe_allow_html=True,
            )
            if cols[1].button("Edit", key=f"edit_{p.slug}", use_container_width=True):
                st.session_state["editing_profile"] = p.slug
                st.rerun()
            if cols[2].button("Delete", key=f"del_{p.slug}", use_container_width=True):
                delete_profile(p.slug)
                if st.session_state.get("active_profile") == p.slug:
                    del st.session_state["active_profile"]
                st.rerun()

    # --- create / edit ---
    editing_slug = st.session_state.get("editing_profile")
    if editing_slug:
        from profiles import get_profile, load_tone as load_profile_tone

        existing = get_profile(editing_slug)
        existing_tone_md = load_profile_tone(editing_slug)
        section_head("Edit", existing.name if existing else editing_slug)
        if st.button("← Cancel"):
            del st.session_state["editing_profile"]
            st.rerun()
    else:
        existing = None
        existing_tone_md = ""
        section_head("New", "Create a profile")

    if existing:
        default_name = existing.name
        default_pitch = existing.default_pitch
        default_description = ""
        default_examples_text = ""
        if existing_tone_md:
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

    name = st.text_input("Name", default_name, placeholder="Daniel, Sarah, Marcus")

    description = st.text_area(
        "Tone description",
        default_description,
        height=200,
        placeholder=(
            "Describe your voice — sentence length, capitalization, vocabulary, "
            "CTA style, phrases to avoid."
        ),
    )

    default_pitch_input = st.text_input(
        "Default angle (optional)",
        default_pitch,
        placeholder="Quick chat to see if 6sense could help your team.",
    )

    bucket_head("Examples")
    st.caption("Paste below, or upload screenshots and we'll transcribe.")

    uploads = st.file_uploader(
        "Screenshots (.png, .jpg)",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
    )

    if uploads and st.button(f"Transcribe {len(uploads)} image(s)"):
        progress = st.progress(0.0, text="Transcribing.")
        transcribed = []
        for i, f in enumerate(uploads):
            media_type = f"image/{f.type.split('/')[-1]}" if f.type else "image/png"
            try:
                text = transcribe_image(f.read(), media_type=media_type)
                transcribed.append(text)
            except Exception as e:
                st.error(f"Failed on {f.name}: {e}")
            progress.progress((i + 1) / len(uploads), text=f"{i+1} / {len(uploads)}")
        progress.empty()
        st.session_state["_transcribed"] = "\n\n---\n\n".join(transcribed)
        st.success(f"Transcribed {len(transcribed)} email(s).")

    transcribed_block = st.session_state.get("_transcribed", "")
    examples_text = st.text_area(
        "Examples — separate with `---` on its own line",
        value=(transcribed_block + ("\n\n---\n\n" + default_examples_text if default_examples_text else "")
               if transcribed_block else default_examples_text),
        height=400,
        placeholder=(
            "Subject: quick q about your stack\n\n"
            "Hi Jane,\n\nSaw the new self-serve tier launch — nice.\n\n"
            "Worth 15 min next week?\n\n— Dan\n\n---\n\nSubject: next email\n..."
        ),
    )

    save_label = "Update profile" if existing else "Save profile"
    save_col, _ = st.columns([1, 4])
    with save_col:
        save = st.button(
            save_label,
            type="primary",
            disabled=not (name and description and examples_text),
            use_container_width=True,
        )
    if save:
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
        st.success(f"Saved **{saved.name}** with {len(examples)} examples.")
        st.rerun()
