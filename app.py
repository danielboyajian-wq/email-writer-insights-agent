"""Email Insights — editorial intelligence terminal."""

import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

from agent import (
    DraftRequest,
    draft_cadence,
    draft_email,
    load_company_context,
    load_tone,
    parse_single_email,
    refine_email,
)
import drafts
import history
from intent import synthesize_intent
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

st.set_page_config(
    page_title="Email Insights",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)
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
                        # Restore brief + URL + any saved intent context so
                        # the Research tab renders as if we just researched.
                        # Write to the same keys the widgets use so the
                        # text fields actually pre-fill on rerender. The
                        # URL field is bound to "website_input"; writing
                        # only to "website" leaves the input stale.
                        st.session_state["brief"] = sb.brief
                        st.session_state["website"] = sb.url
                        st.session_state["website_input"] = sb.url
                        st.session_state["intent_data_input"] = sb.intent_data
                        st.session_state["intent_synthesis_input"] = sb.intent_synthesis
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

draft_tab, drafts_tab, profiles_tab = st.tabs(["Research", "Drafts", "Profiles"])

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

        # Canonical lookup URL: use the same normalization the research
        # pipeline + history modules use so saves and lookups always match.
        from insights import root_domain as _root_domain
        try:
            website_key = _root_domain(website) if website else ""
        except Exception:
            website_key = website

        run_col, opt_col = st.columns([1, 4])
        with run_col:
            run = st.button(
                "Run research", type="primary",
                disabled=not website, use_container_width=True,
            )
        with opt_col:
            extend_window = st.checkbox(
                "Search beyond 6 months",
                value=st.session_state.get("extend_window", False),
                key="extend_window",
                help=(
                    "By default we only surface insights from the last 6 "
                    "months. Toggle this to broaden the search up to ~2 years "
                    "— useful when a company has had nothing fresh to report."
                ),
            )
        if run:
            with st.spinner("Reading homepage, searching news, synthesizing (~15s)"):
                try:
                    brief = generate_brief(
                        website,
                        profile_slug=active_profile,
                        extend_window=extend_window,
                    )
                    st.session_state["brief"] = brief
                    st.session_state.pop("loaded_from_history", None)
                    # Fresh research = clear stale intent context from prior prospect.
                    st.session_state["intent_data_input"] = ""
                    st.session_state["intent_synthesis_input"] = ""
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
                    brief.get("_warning")
                    or "The model returned 0 insights."
                )
                diag = brief.get("_search_diagnostics")
                if diag:
                    st.caption(
                        "Tavily per-query result counts: "
                        + ", ".join(f"{k}={v}" for k, v in diag.items())
                    )
                cols = st.columns([1, 1, 3])
                if cols[0].button("Re-research", use_container_width=True):
                    with st.spinner("Re-researching with cache bypassed"):
                        try:
                            brief = generate_brief(
                                website,
                                force_refresh=True,
                                profile_slug=active_profile,
                                extend_window=extend_window,
                            )
                            st.session_state["brief"] = brief
                            st.rerun()
                        except Exception as e:
                            st.error(f"Re-research failed: {e}")
                            st.stop()
                if cols[1].button(
                    "Retry · extended window",
                    use_container_width=True,
                    help="Bypass the 6-month limit and search up to ~2 years.",
                ):
                    with st.spinner("Re-researching with extended window"):
                        try:
                            brief = generate_brief(
                                website,
                                force_refresh=True,
                                profile_slug=active_profile,
                                extend_window=True,
                            )
                            st.session_state["brief"] = brief
                            st.session_state["extend_window"] = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"Extended re-research failed: {e}")
                            st.stop()
                with st.expander("Raw model output"):
                    st.text(brief.get("_raw", "(no raw output captured)"))
                with st.expander("Raw search results (Tavily)"):
                    st.text(brief.get("_search_results", "(none)"))
                st.stop()

            # Banner when we had to reach beyond the 6-month window to fill 6
            if brief.get("_fallback_to_older"):
                in_w = brief.get("_in_window_count", 0)
                out_w = brief.get("_out_window_used", 0)
                st.info(
                    f"Only {in_w} insight(s) found within the 6-month window. "
                    f"Padded with {out_w} older insight(s) — check the date "
                    "tags before referencing."
                )

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

            # --- §03 Intent signals (optional, additive supporting context) ---
            section_head("03", "Intent signals", note="optional")
            st.caption(
                "Paste 6sense intent data (keywords and pages visited). The drafter "
                "uses this as a secondary 'also noticed' line, NOT the main anchor "
                "of the email. Insights stay the primary hook."
            )

            intent_data = st.text_area(
                "Paste intent data",
                placeholder=(
                    "Keywords: ABM platform, intent data providers, account-based "
                    "marketing tools\nPages visited: /platform/intent-data/, "
                    "/customer-stories/firemon, /pricing\n..."
                ),
                height=140,
                label_visibility="collapsed",
                key="intent_data_input",
            )

            ai_col, _ = st.columns([1, 4])
            with ai_col:
                analyze = st.button(
                    "Analyze",
                    disabled=not intent_data.strip(),
                    use_container_width=True,
                )
            if analyze:
                with st.spinner("Synthesizing intent context"):
                    try:
                        synth = synthesize_intent(
                            intent_text=intent_data,
                            brief=brief,
                            company=website,
                            persona_label="",
                        )
                    except Exception as e:
                        st.error(f"Synthesis failed: {e}")
                        synth = None
                if synth:
                    # Write to the SAME key the widget uses, then rerun so the
                    # text area re-renders with the new initial value. This is
                    # the only reliable Streamlit pattern for programmatically
                    # populating a keyed widget after the fact.
                    st.session_state["intent_synthesis_input"] = synth
                    st.rerun()

            intent_synthesis = st.text_area(
                "Intent context (edit before drafting)",
                height=110,
                placeholder=(
                    "Click Analyze to generate, or write your own. The drafter "
                    "uses this as a SECONDARY 'also noticed' line, not the lead."
                ),
                key="intent_synthesis_input",
            )

            # Persist intent + synthesis to history when populated. Best-effort;
            # silent on DB errors so the draft flow is never blocked.
            if active_profile and (intent_data or intent_synthesis):
                try:
                    history.update_intent(
                        profile_slug=active_profile,
                        url=website_key,
                        intent_data=intent_data,
                        intent_synthesis=intent_synthesis,
                    )
                except Exception:
                    pass

            # --- Previous drafts for this prospect (read-only reference) ---
            past = []
            if active_profile and drafts.is_enabled() and website_key:
                try:
                    past = drafts.list_drafts_for_prospect(
                        active_profile, website_key,
                    )
                except Exception:
                    past = []
                if past:
                    with st.expander(f"📝 Previous drafts for this company ({len(past)})", expanded=False):
                        for d in past:
                            ts = d.drafted_at.strftime("%Y-%m-%d %H:%M")
                            label_type = "Cadence" if d.draft_type == "cadence" else "Single"
                            recip = f" · {d.recipient}" if d.recipient else ""
                            cols = st.columns([7, 1])
                            cols[0].markdown(
                                f"<div style='font-size:0.82rem; font-weight:500; color:var(--fg);'>"
                                f"{label_type} · {ts}{recip}</div>",
                                unsafe_allow_html=True,
                            )
                            if cols[1].button("×", key=f"del_draft_{d.id}", help="Delete this draft"):
                                drafts.delete_draft(d.id)
                                st.rerun()
                            # Render body
                            if d.draft_type == "single":
                                render_email_output(d.draft.get("text", ""))
                            else:
                                for em in d.draft.get("emails", []):
                                    st.markdown(
                                        f"<div style='font-size:0.74rem; color:var(--fg-2); "
                                        f"margin:0.4rem 0 0.1rem;'>"
                                        f"Email {em.get('position')} · {em.get('purpose','').replace('-', ' ')} "
                                        f"· <span style='color:var(--fg-1);'>{em.get('subject','')}</span>"
                                        f"</div>",
                                        unsafe_allow_html=True,
                                    )
                                    render_email_output(em.get("body", ""))
                            st.markdown(
                                "<hr style='border:none; border-top:1px solid var(--border); "
                                "margin:0.5rem 0;'>",
                                unsafe_allow_html=True,
                            )

            # --- §04 Draft ---
            section_head("04", "Compose")

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

            # The "Your angle" pitch, LinkedIn paste, and extra notes were
            # removed to keep the UI focused. The drafter relies on the
            # selected insights + persona + (optional) intent context.
            your_pitch = ""
            linkedin_text = ""
            extra_notes = ""

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
                    intent_data=intent_data,
                    intent_synthesis=intent_synthesis,
                )

                if mode == "Single email":
                    with st.spinner("Drafting in your voice."):
                        try:
                            text, usage = draft_email(req)
                        except Exception as e:
                            st.error(f"Draft failed: {e}")
                            st.stop()
                    # Auto-save to drafts history (best-effort, silent on failure)
                    try:
                        drafts.save_draft(
                            profile_slug=active_profile,
                            url=website_key,
                            company_name=website_key,
                            draft_type="single",
                            draft={"text": text},
                            recipient=(
                                f"{recipient_name}, {recipient_title}".strip(", ")
                                if recipient_name or recipient_title else ""
                            ),
                            persona=persona_slug,
                        )
                    except Exception:
                        pass
                    st.session_state["draft_result"] = parse_single_email(text)
                    st.session_state["draft_usage"] = usage
                    st.session_state["last_draft_mode"] = "single"
                    st.session_state.pop("original_draft", None)
                else:
                    with st.spinner("Drafting all 6 emails in your voice (~30s)."):
                        try:
                            cadence, usage = draft_cadence(req)
                        except Exception as e:
                            st.error(f"Cadence failed: {e}")
                            st.stop()

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

                    # Auto-save the full cadence to drafts history (best-effort)
                    try:
                        drafts.save_draft(
                            profile_slug=active_profile,
                            url=website_key,
                            company_name=website_key,
                            draft_type="cadence",
                            draft={"emails": emails},
                            recipient=(
                                f"{recipient_name}, {recipient_title}".strip(", ")
                                if recipient_name or recipient_title else ""
                            ),
                            persona=persona_slug,
                        )
                    except Exception:
                        pass

                    st.session_state["cadence_result"] = emails
                    st.session_state["cadence_usage"] = usage
                    st.session_state["last_draft_mode"] = "cadence"
                    for _i in range(6):
                        st.session_state.pop(f"original_email_{_i}", None)
                        st.session_state.pop(f"refine_attempt_{_i}", None)

            # --- Output + Refine (rendered from session state, survives reruns) ---
            _last_mode = st.session_state.get("last_draft_mode")

            if _last_mode == "single" and "draft_result" in st.session_state:
                _email = st.session_state["draft_result"]
                section_head("05", "Output")
                render_email_output(f"SUBJECT: {_email['subject']}\n\n{_email['body']}")
                _usage = st.session_state.get("draft_usage", {})
                st.caption(
                    f"in {_usage.get('input_tokens', '?')}  ·  "
                    f"out {_usage.get('output_tokens', '?')}  ·  "
                    f"cache read {_usage.get('cache_read', '?')}  ·  "
                    f"cache write {_usage.get('cache_write', '?')}"
                )

                st.markdown("---")
                _attempt = st.session_state.get("refine_attempt_single", 0)
                _refine_text = st.text_area(
                    "Refine this email",
                    placeholder="e.g. 'make this shorter', 'less formal', 'mention our 2026 report'",
                    key=f"refine_single_{_attempt}",
                    height=80,
                )
                _rc1, _rc2 = st.columns([1, 5])
                with _rc1:
                    if st.button(
                        "Refine",
                        key="refine_single_btn",
                        disabled=not _refine_text.strip(),
                    ):
                        with st.spinner("Refining…"):
                            try:
                                _refined = refine_email(
                                    current_email=_email,
                                    refine_instruction=_refine_text,
                                    is_cadence=False,
                                    company_context=load_company_context(),
                                    tone=load_tone(active_profile),
                                    selected_insights=st.session_state.get(
                                        "selected_insights", []
                                    ),
                                )
                                if "original_draft" not in st.session_state:
                                    st.session_state["original_draft"] = dict(_email)
                                st.session_state["draft_result"] = _refined
                                st.session_state["refine_attempt_single"] = _attempt + 1
                                st.rerun()
                            except Exception as _e:
                                st.error(f"Refine failed: {_e}")
                with _rc2:
                    if st.session_state.get("original_draft"):
                        if st.button("Revert to original", key="revert_single"):
                            st.session_state["draft_result"] = st.session_state.pop(
                                "original_draft"
                            )
                            st.session_state["refine_attempt_single"] = _attempt + 1
                            st.rerun()

            elif _last_mode == "cadence" and "cadence_result" in st.session_state:
                section_head("05", "Cadence")
                _emails = st.session_state["cadence_result"]

                _current_thread = None
                for _i, _em in enumerate(_emails):
                    _thr = _em.get("thread", 1)
                    if _thr != _current_thread:
                        st.markdown(
                            f"<div style='font-family:var(--font); font-size:0.72rem; "
                            f"font-weight:600; letter-spacing:0.06em; text-transform:uppercase; "
                            f"color:var(--fg-2); margin:1.4rem 0 0.5rem;'>"
                            f"Thread {_thr}</div>",
                            unsafe_allow_html=True,
                        )
                        _current_thread = _thr
                    st.markdown(
                        f"<div style='display:flex; align-items:baseline; gap:0.6rem; "
                        f"margin:0.5rem 0 0.25rem;'>"
                        f"<span style='font-family:var(--font); font-size:0.78rem; "
                        f"font-weight:600; color:var(--fg);'>Email {_em.get('position')}</span>"
                        f"<span style='font-family:var(--font); font-size:0.72rem; "
                        f"color:var(--fg-2);'>· {_em.get('purpose', '').replace('-', ' ')}"
                        f"</span></div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"<div style='font-family:var(--font); font-size:0.82rem; "
                        f"color:var(--fg-1); margin-bottom:0.35rem;'>"
                        f"<span style='color:var(--fg-2);'>Subject:</span> "
                        f"<span style='font-weight:500;'>{_em.get('subject', '')}</span></div>",
                        unsafe_allow_html=True,
                    )
                    render_email_output(_em.get("body", ""))

                    st.markdown("---")
                    _attempt_i = st.session_state.get(f"refine_attempt_{_i}", 0)
                    _refine_text_i = st.text_area(
                        f"Refine email {_i + 1}",
                        placeholder="e.g. 'make this shorter', 'less formal'",
                        key=f"refine_email_{_i}_{_attempt_i}",
                        height=80,
                    )
                    _bc1, _bc2, _ = st.columns([1, 1, 4])
                    with _bc1:
                        if st.button(
                            "Refine",
                            key=f"refine_btn_{_i}",
                            disabled=not _refine_text_i.strip(),
                        ):
                            with st.spinner(f"Refining email {_i + 1}…"):
                                try:
                                    _refined_i = refine_email(
                                        current_email={
                                            "subject": _em.get("subject", ""),
                                            "body": _em.get("body", ""),
                                        },
                                        refine_instruction=_refine_text_i,
                                        is_cadence=True,
                                        email_position=_em.get("position", _i + 1),
                                        company_context=load_company_context(),
                                        tone=load_tone(active_profile),
                                        selected_insights=st.session_state.get(
                                            "selected_insights", []
                                        ),
                                    )
                                    if f"original_email_{_i}" not in st.session_state:
                                        st.session_state[f"original_email_{_i}"] = {
                                            "subject": _em.get("subject", ""),
                                            "body": _em.get("body", ""),
                                        }
                                    _updated = list(st.session_state["cadence_result"])
                                    _updated[_i] = {
                                        **_em,
                                        "subject": _refined_i["subject"],
                                        "body": _refined_i["body"],
                                    }
                                    st.session_state["cadence_result"] = _updated
                                    st.session_state[f"refine_attempt_{_i}"] = _attempt_i + 1
                                    st.rerun()
                                except Exception as _e:
                                    st.error(f"Refine failed: {_e}")
                    with _bc2:
                        if st.session_state.get(f"original_email_{_i}"):
                            if st.button("Revert", key=f"revert_email_{_i}"):
                                _orig = st.session_state.pop(f"original_email_{_i}")
                                _updated = list(st.session_state["cadence_result"])
                                _updated[_i] = {
                                    **_em,
                                    "subject": _orig["subject"],
                                    "body": _orig["body"],
                                }
                                st.session_state["cadence_result"] = _updated
                                st.session_state[f"refine_attempt_{_i}"] = _attempt_i + 1
                                st.rerun()

                _usage_c = st.session_state.get("cadence_usage", {})
                st.caption(
                    f"in {_usage_c.get('input_tokens', '?')}  ·  "
                    f"out {_usage_c.get('output_tokens', '?')}  ·  "
                    f"cache read {_usage_c.get('cache_read', '?')}  ·  "
                    f"cache write {_usage_c.get('cache_write', '?')}"
                )

# ----------------------------------------------------------------------------
# DRAFTS TAB — browse every past draft for the active profile
# ----------------------------------------------------------------------------
with drafts_tab:
    section_head("", "Drafts history")
    if not active_profile:
        st.info("Pick a profile in the sidebar to see your drafts.")
    elif not drafts.is_enabled():
        st.warning(
            "Drafts history needs a Postgres connection. Set `DATABASE_URL` "
            "in the environment and restart."
        )
    else:
        st.caption(
            "Every email and cadence you've drafted, grouped by company. "
            "Search filters across company, recipient, and persona."
        )

        # Search + persona filter row
        col_search, col_persona, col_sort = st.columns([3, 1.5, 1.5])
        with col_search:
            search_q = st.text_input(
                "Search",
                placeholder="Filter by company, recipient, or URL",
                label_visibility="collapsed",
                key="drafts_search",
            ).strip().lower()
        with col_persona:
            persona_filter = st.selectbox(
                "Persona",
                options=["All personas"] + [PERSONAS[s].label for s in PERSONAS],
                index=0,
                label_visibility="collapsed",
                key="drafts_persona_filter",
            )
        with col_sort:
            sort_mode = st.selectbox(
                "Sort",
                options=["Company (A-Z)", "Most recent"],
                index=0,
                label_visibility="collapsed",
                key="drafts_sort",
            )

        all_drafts = drafts.list_recent_drafts(active_profile, limit=500)

        # Apply filters
        if search_q:
            all_drafts = [
                d for d in all_drafts
                if search_q in (d.url or "").lower()
                or search_q in (d.recipient or "").lower()
                or search_q in (d.company_name or "").lower()
                or search_q in (d.persona or "").lower()
            ]
        if persona_filter != "All personas":
            wanted_slug = next(
                (s for s in PERSONAS if PERSONAS[s].label == persona_filter),
                None,
            )
            if wanted_slug:
                all_drafts = [d for d in all_drafts if d.persona == wanted_slug]

        if not all_drafts:
            st.markdown(
                "<div style='padding:2.5rem 1rem; text-align:center; "
                "color:var(--fg-2); font-size:0.92rem;'>"
                "<div style='font-size:2rem; margin-bottom:0.5rem;'>📭</div>"
                "No drafts match. Generate one from the Draft tab and it'll "
                "show up here automatically.</div>",
                unsafe_allow_html=True,
            )
        else:
            # Group drafts by company NAME (derived from URL), not raw URL.
            # Raw URLs can vary (https://acme.com, acme.com, acme.com/about),
            # which splits the same company across multiple groups. Mapping
            # every URL through the same _company_name_from_url helper that
            # the research pipeline uses makes the grouping bulletproof.
            from collections import defaultdict
            from insights import _company_name_from_url as _name_from_url

            def _company_name(d) -> str:
                name = (_name_from_url(d.url) or "").strip()
                return name or (d.company_name or d.url or "Unknown")

            groups: dict[str, list] = defaultdict(list)
            for d in all_drafts:
                groups[_company_name(d)].append(d)

            # Sort group keys
            if sort_mode == "Company (A-Z)":
                ordered_names = sorted(
                    groups.keys(), key=lambda n: n.lower()
                )
            else:
                ordered_names = sorted(
                    groups.keys(),
                    key=lambda n: max(d.drafted_at for d in groups[n]),
                    reverse=True,
                )

            total = len(all_drafts)
            st.caption(
                f"{total} draft{'s' if total != 1 else ''} across "
                f"{len(groups)} compan{'y' if len(groups) == 1 else 'ies'}"
            )

            for company in ordered_names:
                group = sorted(groups[company], key=lambda d: d.drafted_at, reverse=True)
                # Personas represented in this group, as chips
                persona_chips = sorted({
                    PERSONAS[d.persona].label if d.persona in PERSONAS else "Other"
                    for d in group if d.persona
                })
                chip_html = ""
                if persona_chips:
                    chip_html = " &nbsp;" + " ".join(
                        f"<span style='display:inline-block; "
                        f"font-family:var(--font); font-size:0.65rem; "
                        f"font-weight:600; letter-spacing:0.03em; "
                        f"text-transform:uppercase; padding:0.12rem 0.45rem; "
                        f"border-radius:999px; background:var(--accent-bg); "
                        f"color:var(--accent-deep);'>{p}</span>"
                        for p in persona_chips
                    )
                # Company header (brand-form name, no URL)
                st.markdown(
                    f"<div style='margin:1.5rem 0 0.4rem;'>"
                    f"<span style='font-family:var(--font); font-size:1.05rem; "
                    f"font-weight:600; color:var(--fg);'>{company}</span> "
                    f"<span style='font-family:var(--font); font-size:0.78rem; "
                    f"color:var(--fg-2);'>· {len(group)} "
                    f"draft{'s' if len(group) != 1 else ''}</span>"
                    f"{chip_html}</div>",
                    unsafe_allow_html=True,
                )

                for d in group:
                    ts = d.drafted_at.strftime("%b %d, %Y · %H:%M")
                    label_type = "📋 Cadence" if d.draft_type == "cadence" else "✉ Single"
                    persona_label = (
                        PERSONAS[d.persona].label if d.persona in PERSONAS else ""
                    )
                    persona_bit = f" · {persona_label}" if persona_label else ""
                    recip_bit = f" · {d.recipient}" if d.recipient else ""
                    summary = f"{label_type}{persona_bit}{recip_bit} · {ts}"
                    with st.expander(summary, expanded=False):
                        cols = st.columns([7, 1])
                        cols[0].caption(f"Saved {ts}")
                        if cols[1].button("Delete", key=f"del_draft_tab_{d.id}"):
                            drafts.delete_draft(d.id)
                            st.rerun()

                        if d.draft_type == "single":
                            render_email_output(d.draft.get("text", ""))
                        else:
                            for em in d.draft.get("emails", []):
                                st.markdown(
                                    f"<div style='margin:0.6rem 0 0.1rem;'>"
                                    f"<span style='font-family:var(--font); font-size:0.78rem; "
                                    f"font-weight:600; color:var(--fg);'>Email {em.get('position')}</span> "
                                    f"<span style='font-family:var(--font); font-size:0.72rem; "
                                    f"color:var(--fg-2);'>· {em.get('purpose','').replace('-', ' ')}</span><br>"
                                    f"<span style='font-family:var(--font); font-size:0.76rem; "
                                    f"color:var(--fg-1);'>Subject: <strong>{em.get('subject','')}</strong></span>"
                                    f"</div>",
                                    unsafe_allow_html=True,
                                )
                                render_email_output(em.get("body", ""))


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
