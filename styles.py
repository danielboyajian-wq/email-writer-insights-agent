"""Design system. Warm minimal product UI with one confident accent.

Principles:
  - Single typeface (Geist), hierarchy by weight not theatre
  - Warm-tinted near-white background, cool near-black foreground (gives the
    page a subtle dimensional feel without glass or gradients)
  - One coral accent. Used for focus rings, links, selection states, and the
    section bullet. Reserved, never decorative.
  - 1px borders, 8px radii, fast easeOutQuart transitions
  - No shadow theatrics, no gradient text, no glassmorphism, no side stripes

Call inject_styles() once at the top of app.py.
"""
import streamlit as st

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500&display=swap');

:root {
  /* Surfaces — warm-tinted (hue 40, low chroma) */
  --bg:          oklch(98.8% 0.005 40);
  --bg-2:        oklch(97% 0.008 40);
  --surface:     oklch(99.5% 0.003 40);
  --surface-2:   oklch(96.5% 0.008 40);
  --surface-hi:  oklch(94% 0.012 40);

  /* Borders */
  --border:      oklch(91% 0.01 40);
  --border-2:    oklch(85% 0.012 40);
  --border-hi:   oklch(70% 0.015 40);

  /* Foreground — cool near-black, gives warm/cool contrast against the bg */
  --fg:          oklch(22% 0.012 270);
  --fg-1:        oklch(38% 0.01 270);
  --fg-2:        oklch(55% 0.008 270);
  --fg-3:        oklch(72% 0.006 270);
  --fg-on-accent: oklch(99% 0.002 40);

  /* Accent — coral, used for focus / links / selection / bullets only */
  --accent:      oklch(68% 0.17 32);
  --accent-hi:   oklch(62% 0.19 30);
  --accent-deep: oklch(54% 0.2 28);
  --accent-bg:   oklch(96% 0.035 32);
  --accent-ring: oklch(85% 0.08 32);

  /* Secondary signals */
  --success:     oklch(62% 0.13 160);
  --danger:      oklch(58% 0.18 25);

  --font:  'Geist', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --mono:  'Geist Mono', ui-monospace, 'SF Mono', Menlo, monospace;

  --radius:    8px;
  --radius-sm: 5px;
  --radius-lg: 12px;

  --ease: cubic-bezier(0.2, 0.8, 0.2, 1); /* easeOutQuart-ish */
}

/* ---- Foundation ---- */
html, body, .stApp {
  font-family: var(--font);
  color: var(--fg);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  font-feature-settings: 'cv11', 'ss01', 'ss03';
}

.stApp {
  background:
    radial-gradient(ellipse 60% 40% at 15% 0%, oklch(96% 0.025 32 / 0.55), transparent 60%),
    radial-gradient(ellipse 50% 35% at 100% 100%, oklch(96% 0.02 200 / 0.4), transparent 60%),
    var(--bg);
  background-attachment: fixed;
}

#MainMenu, header[data-testid="stHeader"], .stDeployButton,
[data-testid="stToolbar"], footer { display: none !important; }

.main .block-container {
  padding-top: 1.5rem !important;
  padding-bottom: 5rem !important;
  max-width: 880px;
}

/* Subtle page-load fade for the main container */
.main .block-container > div:first-child {
  animation: eia-fade-in 360ms var(--ease);
}
@keyframes eia-fade-in {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ---- Typography ---- */
h1, h2, h3, h4 {
  font-family: var(--font);
  color: var(--fg);
  letter-spacing: -0.012em;
}
h1 { font-size: 1.55rem; font-weight: 600; line-height: 1.25; margin: 0.25rem 0 0.25rem; }
h2 { font-size: 1.1rem;  font-weight: 600; line-height: 1.3;  margin: 1.5rem 0 0.5rem; }
h3 { font-size: 0.95rem; font-weight: 600; line-height: 1.35; margin: 1.1rem 0 0.4rem; }

.main p, [data-testid="stMarkdownContainer"] p, .main li {
  font-family: var(--font);
  font-size: 0.875rem;
  line-height: 1.55;
  color: var(--fg-1);
  max-width: 68ch;
}

[data-testid="stCaptionContainer"], .stCaption, small {
  font-family: var(--font) !important;
  font-size: 0.78rem !important;
  color: var(--fg-2) !important;
  letter-spacing: 0 !important;
  text-transform: none !important;
}

/* ---- Header ---- */
.eia-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.25rem 0 1rem;
  border-bottom: 1px solid var(--border);
  margin-bottom: 1.5rem;
}
.eia-header-title {
  display: flex; align-items: center; gap: 0.6rem;
}
.eia-mark {
  width: 22px; height: 22px;
  border-radius: 6px;
  background: linear-gradient(135deg, var(--accent), var(--accent-deep));
  position: relative;
  box-shadow: 0 0 0 1px oklch(50% 0.18 30 / 0.2);
}
.eia-mark::after {
  content: '';
  position: absolute; inset: 6px;
  border-radius: 2px;
  background: var(--fg-on-accent);
  opacity: 0.95;
}
.eia-header-title h1 {
  font-size: 0.98rem;
  font-weight: 600;
  margin: 0;
}
.eia-header-sub {
  font-size: 0.78rem;
  color: var(--fg-2);
}

/* ---- Section heads (bullet + title) ---- */
.eia-section-head {
  margin: 1.75rem 0 0.6rem;
  display: flex; align-items: center; gap: 0.55rem;
}
.eia-section-head::before {
  content: '';
  width: 7px; height: 7px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-bg);
}
.eia-section-head .title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--fg);
}
.eia-section-head .note {
  font-size: 0.78rem;
  color: var(--fg-2);
  margin-left: 0.25rem;
}

/* ---- Buttons (bulletproof contrast) ---- */
/* Base / secondary */
.stButton > button,
[data-testid="stBaseButton-secondary"],
[data-testid="baseButton-secondary"] {
  background: var(--surface) !important;
  color: var(--fg) !important;
  border: 1px solid var(--border-2) !important;
  border-radius: var(--radius) !important;
  font-family: var(--font) !important;
  font-size: 0.83rem !important;
  font-weight: 500 !important;
  letter-spacing: -0.005em !important;
  text-transform: none !important;
  padding: 0.45rem 0.9rem !important;
  min-height: 34px;
  height: auto !important;
  box-shadow: none !important;
  transition:
    background 180ms var(--ease),
    border-color 180ms var(--ease),
    color 180ms var(--ease),
    transform 180ms var(--ease);
}
.stButton > button:hover,
[data-testid="stBaseButton-secondary"]:hover,
[data-testid="baseButton-secondary"]:hover {
  background: var(--accent-bg) !important;
  color: var(--accent-deep) !important;
  border-color: var(--accent) !important;
}
.stButton > button:active,
[data-testid="stBaseButton-secondary"]:active {
  background: var(--accent-ring) !important;
  color: var(--accent-deep) !important;
  transform: translateY(1px);
}
.stButton > button:disabled,
.stButton > button[disabled] {
  background: var(--surface-2) !important;
  color: var(--fg-3) !important;
  border-color: var(--border) !important;
  cursor: not-allowed;
}
.stButton > button:focus-visible {
  outline: none !important;
  box-shadow: 0 0 0 3px var(--accent-ring) !important;
}

/* Primary — coral fill, white text, contrast-preserving hover */
button[kind="primary"],
button[data-testid="stBaseButton-primary"],
button[data-testid="baseButton-primary"],
.stButton > button[kind="primary"] {
  background: var(--accent) !important;
  color: var(--fg-on-accent) !important;
  border: 1px solid var(--accent) !important;
  font-weight: 600 !important;
}
button[kind="primary"]:hover,
button[data-testid="stBaseButton-primary"]:hover,
button[data-testid="baseButton-primary"]:hover {
  background: var(--accent-hi) !important;
  border-color: var(--accent-hi) !important;
  color: var(--fg-on-accent) !important;
}
button[kind="primary"]:active,
button[data-testid="stBaseButton-primary"]:active {
  background: var(--accent-deep) !important;
  border-color: var(--accent-deep) !important;
  color: var(--fg-on-accent) !important;
  transform: translateY(1px);
}
button[kind="primary"]:disabled,
button[data-testid="stBaseButton-primary"]:disabled {
  background: var(--surface-2) !important;
  color: var(--fg-3) !important;
  border-color: var(--border) !important;
}

/* ---- Inputs ---- */
.stTextInput input,
.stTextArea textarea,
.stNumberInput input {
  background: var(--surface) !important;
  border: 1px solid var(--border-2) !important;
  border-radius: var(--radius) !important;
  padding: 0.55rem 0.75rem !important;
  font-family: var(--font) !important;
  font-size: 0.88rem !important;
  color: var(--fg) !important;
  box-shadow: none !important;
  transition: border-color 180ms var(--ease), box-shadow 180ms var(--ease);
}
.stTextInput input:focus,
.stTextArea textarea:focus,
.stNumberInput input:focus {
  border-color: var(--accent) !important;
  outline: none !important;
  box-shadow: 0 0 0 3px var(--accent-ring) !important;
}
.stTextInput input::placeholder,
.stTextArea textarea::placeholder { color: var(--fg-3) !important; }

/* Labels */
.stTextInput label, .stTextArea label, .stSelectbox label,
.stFileUploader label, .stCheckbox label,
[data-testid="stWidgetLabel"] label, label {
  font-family: var(--font) !important;
  font-size: 0.78rem !important;
  font-weight: 500 !important;
  letter-spacing: 0 !important;
  text-transform: none !important;
  color: var(--fg-1) !important;
  margin-bottom: 0.25rem !important;
}

/* Selectbox */
[data-baseweb="select"] > div {
  background: var(--surface) !important;
  border: 1px solid var(--border-2) !important;
  border-radius: var(--radius) !important;
  font-family: var(--font) !important;
  font-size: 0.88rem !important;
  min-height: 36px !important;
  box-shadow: none !important;
  transition: border-color 180ms var(--ease), box-shadow 180ms var(--ease);
}
[data-baseweb="select"] > div:hover { border-color: var(--border-hi) !important; }
[data-baseweb="select"] > div:focus-within {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px var(--accent-ring) !important;
}

/* File uploader */
[data-testid="stFileUploader"] section {
  background: var(--surface-2) !important;
  border: 1px dashed var(--border-2) !important;
  border-radius: var(--radius) !important;
  padding: 1rem !important;
  transition: border-color 180ms var(--ease), background 180ms var(--ease);
}
[data-testid="stFileUploader"] section:hover {
  border-color: var(--accent) !important;
  background: var(--accent-bg) !important;
}
[data-testid="stFileUploader"] button {
  background: var(--surface) !important;
  color: var(--fg) !important;
  border: 1px solid var(--border-2) !important;
}
[data-testid="stFileUploader"] button:hover {
  background: var(--accent-bg) !important;
  color: var(--accent-deep) !important;
  border-color: var(--accent) !important;
}

/* Checkbox */
.stCheckbox > label {
  font-family: var(--font) !important;
  font-size: 0.88rem !important;
  color: var(--fg) !important;
  text-transform: none !important;
  letter-spacing: 0 !important;
}
.stCheckbox [data-baseweb="checkbox"] [data-checked="true"] {
  background-color: var(--accent) !important;
  border-color: var(--accent) !important;
}

/* ---- Tabs ---- */
.stTabs [data-baseweb="tab-list"] {
  border-bottom: 1px solid var(--border);
  gap: 1.5rem;
  background: transparent;
  padding: 0;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important;
  font-family: var(--font) !important;
  font-size: 0.84rem !important;
  font-weight: 500 !important;
  letter-spacing: 0 !important;
  text-transform: none !important;
  padding: 0.55rem 0 !important;
  color: var(--fg-2) !important;
  border-radius: 0 !important;
  border: none !important;
  transition: color 180ms var(--ease);
}
.stTabs [data-baseweb="tab"]:hover { color: var(--fg) !important; }
.stTabs [aria-selected="true"] {
  color: var(--fg) !important;
  border-bottom: 2px solid var(--accent) !important;
  margin-bottom: -1px;
}
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }

/* ---- Sidebar ---- */
[data-testid="stSidebar"] {
  background: var(--bg-2);
  border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] .block-container { padding-top: 1.25rem; }
[data-testid="stSidebar"] h3 {
  font-family: var(--font);
  font-size: 0.72rem !important;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--fg-2);
  margin: 1.1rem 0 0.45rem;
}
[data-testid="stSidebar"] .stButton > button { width: 100%; }

/* ---- Alerts ---- */
[data-testid="stAlert"] {
  border-radius: var(--radius) !important;
  border: 1px solid var(--border) !important;
  background: var(--surface) !important;
  font-family: var(--font);
  font-size: 0.85rem !important;
  padding: 0.7rem 0.9rem !important;
  box-shadow: none !important;
}

/* ---- Insight row ---- */
.eia-insight {
  border: 1px solid var(--border);
  background: var(--surface);
  border-radius: var(--radius);
  padding: 0.85rem 1rem;
  margin-bottom: 0.4rem;
  transition:
    border-color 180ms var(--ease),
    background 180ms var(--ease);
}
.eia-insight:hover {
  border-color: var(--border-hi);
}
.eia-bucket-head {
  display: flex; align-items: center; gap: 0.5rem;
  margin: 1.25rem 0 0.5rem;
}
.eia-bucket-head .label {
  font-family: var(--font);
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--fg-2);
}
.eia-bucket-head .rule {
  flex: 1; height: 1px;
  background: linear-gradient(to right, var(--border), transparent);
}

/* ---- Spinner: skeleton shimmer bar ---- */
.stSpinner {
  padding: 0.5rem 0;
}
.stSpinner > div {
  display: flex !important;
  align-items: center !important;
  gap: 0.75rem !important;
  font-family: var(--font) !important;
  font-size: 0.84rem !important;
  color: var(--fg-2) !important;
}
/* Replace Streamlit's circular SVG spinner with a sleek shimmer bar */
.stSpinner i, .stSpinner svg { display: none !important; }
.stSpinner > div::before {
  content: '';
  display: inline-block;
  width: 140px;
  height: 4px;
  border-radius: 2px;
  background:
    linear-gradient(
      90deg,
      transparent 0%,
      var(--surface-hi) 20%,
      var(--accent) 50%,
      var(--surface-hi) 80%,
      transparent 100%
    );
  background-size: 200% 100%;
  animation: eia-shimmer 1.5s cubic-bezier(0.4, 0, 0.2, 1) infinite;
}
@keyframes eia-shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Reusable skeleton class for placeholder blocks */
.eia-skeleton {
  border-radius: var(--radius-sm);
  background:
    linear-gradient(
      90deg,
      var(--surface-2) 0%,
      var(--surface-hi) 50%,
      var(--surface-2) 100%
    );
  background-size: 200% 100%;
  animation: eia-shimmer 1.4s cubic-bezier(0.4, 0, 0.2, 1) infinite;
}

/* ---- Expander ---- */
[data-testid="stExpander"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  background: var(--surface);
  box-shadow: none !important;
  overflow: hidden;
}
[data-testid="stExpander"] summary {
  font-family: var(--font);
  font-size: 0.84rem;
  font-weight: 500;
  color: var(--fg);
  padding: 0.65rem 0.9rem;
  transition: background 180ms var(--ease);
}
[data-testid="stExpander"] summary:hover { background: var(--surface-2); }

/* ---- Code / mono ---- */
code, pre {
  font-family: var(--mono) !important;
  background: var(--surface-hi) !important;
  border-radius: var(--radius-sm) !important;
  font-size: 0.82em !important;
  padding: 0.05em 0.35em;
  color: var(--accent-deep);
}

/* ---- Links ---- */
.main a {
  color: var(--accent-deep);
  text-decoration: none;
  border-bottom: 1px solid var(--accent-ring);
  transition: color 180ms var(--ease), border-color 180ms var(--ease);
}
.main a:hover {
  color: var(--accent-hi);
  border-bottom-color: var(--accent);
}

/* ---- Age pill (fresh / stale) ---- */
.eia-age-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.32rem;
  font-family: var(--font);
  font-size: 0.68rem;
  font-weight: 500;
  letter-spacing: 0.02em;
  padding: 0.12rem 0.45rem;
  border-radius: 999px;
  vertical-align: middle;
  margin-left: 0.4rem;
  line-height: 1.2;
}
.eia-age-tag::before {
  content: '';
  width: 5px;
  height: 5px;
  border-radius: 50%;
}

/* Fresh: green */
.eia-age-tag.is-fresh {
  background: oklch(95% 0.04 155);
  color: oklch(38% 0.1 155);
  border: 1px solid oklch(86% 0.06 155);
}
.eia-age-tag.is-fresh::before {
  background: oklch(62% 0.14 155);
}

/* Stale: amber/orange */
.eia-age-tag.is-stale {
  background: oklch(94% 0.04 75);
  color: oklch(42% 0.11 65);
  border: 1px solid oklch(86% 0.06 75);
}
.eia-age-tag.is-stale::before {
  background: oklch(68% 0.16 65);
}

/* Unknown date: neutral gray */
.eia-age-tag.is-unknown {
  background: oklch(95% 0.005 270);
  color: oklch(48% 0.008 270);
  border: 1px solid oklch(88% 0.006 270);
}
.eia-age-tag.is-unknown::before {
  background: oklch(65% 0.01 270);
}

/* Backwards-compat alias kept for any older code paths */
.eia-stale-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.32rem;
  font-family: var(--font);
  font-size: 0.68rem;
  font-weight: 500;
  padding: 0.12rem 0.45rem;
  border-radius: 999px;
  background: oklch(94% 0.04 75);
  color: oklch(42% 0.11 65);
  border: 1px solid oklch(86% 0.06 75);
  vertical-align: middle;
  margin-left: 0.4rem;
  line-height: 1.2;
}
.eia-stale-tag::before {
  content: '';
  width: 5px; height: 5px; border-radius: 50%;
  background: oklch(68% 0.16 65);
}

/* ---- Status pip ---- */
.eia-pip {
  display: inline-flex; align-items: center; gap: 0.5rem;
  font-family: var(--font);
  font-size: 0.78rem;
  color: var(--fg-1);
}
.eia-pip::before {
  content: ''; width: 7px; height: 7px; border-radius: 50%;
  background: var(--success);
  box-shadow: 0 0 0 3px oklch(62% 0.13 160 / 0.18);
}
.eia-pip.is-off::before {
  background: var(--danger);
  box-shadow: 0 0 0 3px oklch(58% 0.18 25 / 0.18);
}

/* ---- Email output ---- */
.eia-output {
  background: var(--surface);
  border: 1px solid var(--border-2);
  border-radius: var(--radius-lg);
  padding: 1.2rem 1.4rem;
  font-family: var(--font);
  font-size: 0.93rem;
  line-height: 1.6;
  color: var(--fg);
  white-space: pre-wrap;
  margin: 0.75rem 0;
  position: relative;
  overflow: hidden;
}
.eia-output::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: linear-gradient(
    90deg,
    transparent 0%,
    var(--accent) 20%,
    var(--accent-deep) 45%,
    var(--accent) 70%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: eia-sweep 4.2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
}
@keyframes eia-sweep {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ---- Scrollbar ---- */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--fg-3); }

/* Tighter vertical block gaps */
[data-testid="stVerticalBlock"] > div { gap: 0.55rem; }

/* Smooth scrolling on the whole page */
html { scroll-behavior: smooth; }
</style>
"""


def inject_styles() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def render_hero(subtitle: str = "") -> None:
    """Compact app header. Replaces st.title()."""
    sub = subtitle or "Company research, persona context, your voice."
    st.markdown(
        f"""
        <div class="eia-header">
          <div class="eia-header-title">
            <div class="eia-mark"></div>
            <h1>Email Insights</h1>
          </div>
          <div class="eia-header-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_head(_number: str, title: str, note: str = "") -> None:
    """Section heading with coral bullet."""
    note_html = f'<span class="note">{note}</span>' if note else ""
    st.markdown(
        f"""
        <div class="eia-section-head">
          <span class="title">{title}</span>
          {note_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def bucket_head(label: str) -> None:
    st.markdown(
        f"""
        <div class="eia-bucket-head">
          <span class="label">{label}</span>
          <span class="rule"></span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_pip(label: str, ok: bool = True) -> None:
    cls = "eia-pip" + ("" if ok else " is-off")
    st.markdown(f'<span class="{cls}">{label}</span>', unsafe_allow_html=True)


def render_email_output(text: str) -> None:
    """Render an email body. Escapes HTML, neutralises Streamlit's LaTeX
    rendering of `$...$`, and converts markdown-style links `[text](url)`
    into clickable anchors. Preserves whitespace via CSS `pre-wrap`.
    """
    import html as _html
    import re as _re

    safe = _html.escape(text)
    # Streamlit's markdown processor parses `$...$` as KaTeX, which turns
    # numbers like "$475M" into serif/italic math glyphs. Use the HTML
    # entity so the dollar sign renders as a plain character.
    safe = safe.replace("$", "&#36;")

    # Convert `[label](https://...)` to a real anchor. html.escape leaves
    # brackets and parens intact, so the pattern still matches post-escape.
    link_re = _re.compile(r'\[([^\]]+)\]\((https?://[^)\s]+)\)')
    safe = link_re.sub(
        r'<a href="\2" target="_blank" rel="noopener">\1</a>',
        safe,
    )

    st.markdown(f'<div class="eia-output">{safe}</div>', unsafe_allow_html=True)
