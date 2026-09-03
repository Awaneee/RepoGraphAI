"""
RepoGraphAI — Streamlit Frontend
Run: streamlit run frontend/app.py
"""

import json
import os
from datetime import datetime

import requests
import streamlit as st
from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark", {"linkify": True, "breaks": True}).enable("table")

_DEFAULT_BACKEND = os.getenv("REPOGRAPHAI_BACKEND_URL", "http://localhost:8000")

st.set_page_config(
    page_title="RepoGraphAI — Python repository intelligence",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
  --bg-base:      #0A0E17;
  --bg-panel:     #101725;
  --bg-inset:     #0C1220;
  --bg-elevated:  #131B2B;
  --border-hair:  rgba(255,255,255,0.06);
  --border-lit:   rgba(255,255,255,0.14);
  --mint:         #10B981;
  --mint-soft:    #34D399;
  --mint-glow:    rgba(16,185,129,0.18);
  --user-blue:    #60A5FA;
  --text-hi:      #F1F5F9;
  --text-mid:     #94A3B8;
  --text-low:     #64748B;
  --warn:         #FBBF24;
  --err:          #F87171;
}

html, body, [class*="css"] {
  font-family: 'Inter', system-ui, sans-serif !important;
  -webkit-font-smoothing: antialiased;
}
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

.stApp { background: var(--bg-base); color: var(--text-mid); }
.main .block-container {
  max-width: 1100px;
  padding-top: 1.5rem;
  padding-bottom: 3rem;
}

/* ── Sidebar ────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: var(--bg-inset);
  border-right: 1px solid var(--border-hair);
  width: 260px !important;
}
[data-testid="stSidebar"] > div:first-child { padding-top: 1.2rem; }
[data-testid="stSidebar"] hr { display: none; }

[data-testid="stSidebar"] .stMarkdown h1 {
  font-family: 'Space Grotesk', 'Inter', sans-serif;
  color: var(--text-hi);
  font-size: 1.5rem; font-weight: 700; letter-spacing: -0.02em;
  margin: 0 0 4px 0;
}

.eyebrow {
  font-size: 10px; text-transform: uppercase; letter-spacing: 0.14em;
  color: var(--text-low); font-weight: 700; margin: 0 0 8px 0;
}
.hairline { border: 0; border-top: 1px solid var(--border-hair); margin: 18px 0; }

/* Inputs */
.stTextInput input, .stTextArea textarea {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-hair) !important;
  border-radius: 8px !important;
  color: var(--text-hi) !important;
  font-family: 'Inter', sans-serif !important;
  transition: border-color 150ms ease-out, box-shadow 150ms ease-out !important;
  font-size: 13px !important;
}
.stTextInput input:hover, .stTextArea textarea:hover { border-color: var(--border-lit) !important; }
.stTextInput input:focus, .stTextArea textarea:focus {
  border-color: var(--mint) !important;
  box-shadow: 0 0 0 3px var(--mint-glow) !important;
  outline: none !important;
}
.stTextInput label, .stTextArea label, .stSlider label {
  color: var(--text-mid) !important; font-size: 12px !important; font-weight: 500 !important;
}
[data-testid="stSidebar"] .stTextInput input {
  font-family: 'JetBrains Mono', ui-monospace, monospace !important;
  font-size: 12px !important;
  color: var(--text-hi) !important;
}
[data-testid="stSidebar"] .stTextInput input[type="password"] {
  font-family: 'Inter', sans-serif !important;
}

/* Sliders */
.stSlider [data-baseweb="slider"] > div > div { background: var(--mint) !important; }
.stSlider [role="slider"] {
  background: var(--text-hi) !important;
  box-shadow: 0 0 0 2px var(--bg-base) !important;
}
.stSlider [data-testid="stTickBar"] { display: none !important; }

/* Toggle */
[data-testid="stToggle"] label { color: var(--text-mid) !important; font-size: 13px !important; }

/* Recent-chat rows */
.history-list .stButton > button {
  width: 100% !important;
  background: transparent !important;
  border: none !important;
  border-radius: 6px !important;
  padding: 7px 8px !important;
  color: var(--text-mid) !important;
  font-size: 12.5px !important;
  text-align: left !important;
  justify-content: flex-start !important;
  white-space: nowrap !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  display: block !important;
  font-weight: 400 !important;
}
.history-list .stButton > button:hover {
  background: rgba(16,185,129,0.06) !important;
  color: var(--text-hi) !important;
  border: none !important;
}

/* Default buttons */
.stButton > button, .stFormSubmitButton > button {
  background: var(--bg-elevated) !important;
  color: var(--text-mid) !important;
  border: 1px solid var(--border-hair) !important;
  border-radius: 8px !important;
  font-weight: 500 !important;
  font-family: 'Inter', sans-serif !important;
  font-size: 13px !important;
  transition: all 150ms ease-out !important;
  padding: 0.45rem 0.9rem !important;
  box-shadow: none !important;
}
.stButton > button:hover, .stFormSubmitButton > button:hover {
  border-color: var(--mint) !important;
  color: var(--text-hi) !important;
  transform: none !important;
  background: rgba(16,185,129,0.06) !important;
}

/* Chat input */
[data-testid="stChatInput"] {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border-hair) !important;
  border-radius: 12px !important;
  transition: border-color 150ms ease-out, box-shadow 150ms ease-out;
}
[data-testid="stChatInput"]:focus-within {
  border-color: var(--mint) !important;
  box-shadow: 0 0 0 3px var(--mint-glow) !important;
}
[data-testid="stChatInput"] textarea {
  background: transparent !important;
  color: var(--text-hi) !important;
  font-family: 'Inter', sans-serif !important;
  font-size: 14px !important;
}
[data-testid="stChatInput"] button {
  background: transparent !important;
}
[data-testid="stChatInput"] button svg { fill: var(--mint) !important; color: var(--mint) !important; }

/* Expanders */
[data-testid="stExpander"] {
  background: var(--bg-panel) !important;
  border: 1px solid var(--border-hair) !important;
  border-radius: 10px !important;
}
[data-testid="stExpander"] summary {
  color: var(--text-mid) !important; font-size: 13px !important; font-weight: 500 !important;
}
[data-testid="stExpander"] summary:hover { color: var(--text-hi) !important; }

/* Metrics */
[data-testid="stMetric"] {
  background: var(--bg-inset);
  border: 1px solid var(--border-hair);
  border-radius: 8px;
  padding: 0.7rem 0.9rem;
}
[data-testid="stMetricValue"] {
  color: var(--mint-soft) !important;
  font-weight: 600 !important;
  font-size: 1.05rem !important;
  font-family: 'JetBrains Mono', monospace !important;
}
[data-testid="stMetricLabel"] {
  color: var(--text-low) !important;
  font-size: 10px !important;
  text-transform: uppercase; letter-spacing: 0.12em; font-weight: 700;
}

/* Code */
code {
  font-family: 'JetBrains Mono', ui-monospace, monospace !important;
  background: var(--bg-inset) !important;
  color: var(--mint-soft) !important;
  border: 1px solid var(--border-hair) !important;
  border-radius: 5px !important;
  padding: 1px 6px !important;
  font-size: 0.85em !important;
}

/* Alerts */
.stAlert {
  border-radius: 10px !important;
  border: 1px solid var(--border-hair) !important;
  background: var(--bg-panel) !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #1a2332; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #253247; }

/* ── Session state (loaded) sidebar badge ───────────────────── */
.loaded-pill {
  display: inline-flex; align-items: center; gap: 8px;
  background: rgba(16,185,129,0.08);
  border: 1px solid rgba(16,185,129,0.35);
  border-radius: 8px;
  padding: 8px 12px;
  color: var(--mint-soft);
  font-size: 12.5px; font-weight: 500;
  width: 100%; box-sizing: border-box;
}
.loaded-pill .dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--mint);
  box-shadow: 0 0 6px rgba(16,185,129,0.7);
  animation: pulse 1.8s ease-in-out infinite;
  flex-shrink: 0;
}
@keyframes pulse { 50% { opacity: 0.55; } }

/* Backend health row */
.backend-row {
  display: flex; align-items: center; gap: 8px;
  font-size: 12.5px; color: var(--text-mid);
  margin-top: 4px;
}
.mini-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
.mini-dot.g { background: var(--mint); box-shadow: 0 0 6px rgba(16,185,129,0.6); }
.mini-dot.a { background: var(--warn); box-shadow: 0 0 6px rgba(251,191,36,0.6); }
.mini-dot.r { background: var(--err); box-shadow: 0 0 6px rgba(248,113,113,0.6); }

/* ── Welcome hero card ──────────────────────────────────────── */
.hero-card {
  background:
    radial-gradient(ellipse 90% 60% at 20% 0%, rgba(16,185,129,0.06) 0%, transparent 60%),
    linear-gradient(180deg, #10182A 0%, #0B121F 100%);
  border: 1px solid var(--border-hair);
  border-radius: 16px;
  padding: 40px 44px 36px;
  margin: 0 0 1.5rem;
  position: relative;
  overflow: hidden;
  box-shadow: 0 24px 60px -20px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.03);
}
.hero-card::before {
  content: "";
  position: absolute; inset: 0;
  background-image:
    radial-gradient(circle at 1px 1px, rgba(255,255,255,0.05) 1px, transparent 0);
  background-size: 24px 24px;
  mask-image: radial-gradient(ellipse 60% 60% at 90% 20%, black 20%, transparent 70%);
  pointer-events: none;
}
.hero-card .corner {
  position: absolute; top: 24px; right: 26px;
  color: var(--mint-soft); opacity: 0.55;
}
.hero-top {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 24px; position: relative;
}
.pill-badge {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 5px 12px; border-radius: 999px;
  background: rgba(16,185,129,0.08);
  border: 1px solid rgba(16,185,129,0.35);
  color: var(--mint-soft);
  font-size: 10px; text-transform: uppercase; letter-spacing: 0.18em;
  font-weight: 700;
}
.hero-brand {
  display: flex; align-items: center; gap: 14px;
  margin-bottom: 16px; position: relative;
}
.hero-mark {
  width: 44px; height: 44px; border-radius: 10px;
  background: linear-gradient(135deg, rgba(16,185,129,0.15), rgba(16,185,129,0.05));
  border: 1px solid rgba(16,185,129,0.35);
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--mint-soft);
  box-shadow: 0 0 20px rgba(16,185,129,0.15);
  flex-shrink: 0;
}
.hero-title {
  font-family: 'Space Grotesk', 'Inter', sans-serif;
  font-size: 46px; font-weight: 700; letter-spacing: -0.03em;
  color: var(--text-hi); line-height: 1; margin: 0;
}
.hero-desc {
  color: var(--text-mid); font-size: 14.5px; line-height: 1.7;
  max-width: 640px; margin: 0 0 28px; position: relative;
}
.action-row { display: flex; gap: 10px; flex-wrap: wrap; position: relative; }
.action-pill {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 8px 14px; border-radius: 999px;
  background: rgba(16,185,129,0.06);
  border: 1px solid rgba(16,185,129,0.30);
  color: var(--mint-soft);
  font-size: 12.5px; font-weight: 500;
  transition: all 150ms ease-out;
}
.action-pill:hover {
  background: rgba(16,185,129,0.10);
  border-color: rgba(16,185,129,0.50);
}
.action-pill .num {
  color: var(--mint); font-family: 'JetBrains Mono', monospace;
  font-size: 10.5px; font-weight: 600; opacity: 0.75;
  padding-right: 2px;
}
.hero-footnote {
  color: var(--text-low); font-size: 12px;
  text-align: center; margin-top: 1.5rem;
  padding-top: 1rem;
}
@media (max-width: 768px) { .hero-title { font-size: 32px; } .hero-mark { width: 36px; height: 36px; } }

/* ── Chip rows below hero ──────────────────────────────────── */
.chip-row-label {
  color: var(--text-low); font-size: 12px; font-weight: 500;
  min-width: 110px; padding-top: 6px;
}
.chip-mono {
  font-family: 'JetBrains Mono', monospace !important;
  color: var(--mint-soft) !important;
  font-size: 12px !important;
}

/* ── Session header (chat state) ───────────────────────────── */
.session-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 4px 10px;
  border-bottom: 1px solid var(--border-hair);
  margin-bottom: 20px;
}
.session-header .left {
  color: var(--text-low); font-size: 11px;
  text-transform: uppercase; letter-spacing: 0.14em; font-weight: 600;
}
.session-header .left .repo { color: var(--mint-soft); }
.session-header .right {
  display: inline-flex; align-items: center; gap: 6px;
  color: var(--mint-soft); font-size: 10.5px;
  text-transform: uppercase; letter-spacing: 0.14em; font-weight: 700;
}
.session-header .right .dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--mint);
  box-shadow: 0 0 6px rgba(16,185,129,0.7);
  animation: pulse 1.8s ease-in-out infinite;
}

/* ── Message bubbles (custom, since we right-align user) ───── */
.msg-wrap { display: flex; margin-bottom: 14px; }
.msg-wrap.user  { justify-content: flex-end; }
.msg-wrap.assistant { justify-content: flex-start; }
.bubble {
  max-width: 78%;
  border-radius: 14px;
  padding: 12px 16px;
  border: 1px solid var(--border-hair);
  background: var(--bg-panel);
}
.bubble.user {
  background: rgba(96,165,250,0.06);
  border-color: rgba(96,165,250,0.30);
}
.bubble.assistant {
  background: rgba(16,185,129,0.04);
  border-color: rgba(16,185,129,0.28);
}
.bubble-head {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.14em;
  font-weight: 700; margin-bottom: 8px;
}
.bubble.user .bubble-head .who      { color: var(--user-blue); }
.bubble.assistant .bubble-head .who { color: var(--mint-soft); }
.bubble-head .time { color: var(--text-low); font-weight: 500; }
.bubble-body { color: var(--text-hi); font-size: 14px; line-height: 1.65; }
.bubble-body p { margin: 0 0 10px; }
.bubble-body p:last-child { margin-bottom: 0; }
.bubble-body strong { color: #E2E8F0; font-weight: 600; }
.bubble-body em { color: var(--mint-soft); font-style: normal; }
.bubble-body a { color: var(--mint-soft); text-decoration: underline; text-underline-offset: 2px; }
.bubble-body code { color: var(--mint-soft) !important; font-size: 12.5px !important; }
.bubble-body pre {
  background: var(--bg-inset) !important;
  border: 1px solid var(--border-hair);
  border-left: 2px solid var(--mint);
  border-radius: 8px;
  padding: 10px 12px !important;
  margin: 10px 0 !important;
  overflow-x: auto;
}
.bubble-body pre code {
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
  color: var(--text-hi) !important;
  font-size: 12.5px !important;
  line-height: 1.55;
}
.bubble-body ul, .bubble-body ol { margin: 6px 0 10px; padding-left: 22px; }
.bubble-body li { margin: 3px 0; }
.bubble-body h1, .bubble-body h2, .bubble-body h3, .bubble-body h4 {
  color: var(--text-hi);
  font-family: 'Inter', sans-serif;
  font-weight: 700;
  margin: 12px 0 6px;
  letter-spacing: -0.01em;
}
.bubble-body h1 { font-size: 17px; }
.bubble-body h2 { font-size: 15.5px; }
.bubble-body h3 { font-size: 14.5px; }
.bubble-body h4 { font-size: 13.5px; }
.bubble-body blockquote {
  margin: 8px 0;
  padding: 4px 12px;
  border-left: 2px solid var(--mint);
  color: var(--text-mid);
}
.bubble-body hr {
  border: 0; border-top: 1px solid var(--border-hair);
  margin: 12px 0;
}

/* ── Source-node pills (shown inline under assistant answer) ─ */
.src-row {
  display: flex; flex-wrap: wrap; gap: 6px;
  margin-top: 10px;
}
.src-pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px; border-radius: 999px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px; font-weight: 500;
  border: 1px solid;
}
.src-pill .dot { width: 5px; height: 5px; border-radius: 50%; }
.src-Class    { background: rgba(96,165,250,0.10); border-color: rgba(96,165,250,0.40); color: #60A5FA; }
.src-Class .dot   { background: #60A5FA; }
.src-Method   { background: rgba(16,185,129,0.10); border-color: rgba(16,185,129,0.45); color: #34D399; }
.src-Method .dot  { background: #34D399; }
.src-Function { background: rgba(251,191,36,0.10); border-color: rgba(251,191,36,0.40); color: #FBBF24; }
.src-Function .dot { background: #FBBF24; }
.src-File     { background: rgba(16,185,129,0.10); border-color: rgba(16,185,129,0.45); color: #34D399; }
.src-File .dot    { background: #34D399; }
.src-Module   { background: rgba(248,113,113,0.10); border-color: rgba(248,113,113,0.40); color: #F87171; }
.src-Module .dot  { background: #F87171; }

/* ── Diagnostics expander interior ─────────────────────────── */
.node-grid { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.node-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px; border-radius: 999px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px; font-weight: 500;
  border: 1px solid; white-space: nowrap;
}
.node-Class    { background: rgba(96,165,250,0.10); border-color: rgba(96,165,250,0.40); color: #60A5FA; }
.node-Method   { background: rgba(16,185,129,0.10); border-color: rgba(16,185,129,0.45); color: #34D399; }
.node-Function { background: rgba(251,191,36,0.10); border-color: rgba(251,191,36,0.40); color: #FBBF24; }
.node-File     { background: rgba(148,163,184,0.10); border-color: rgba(148,163,184,0.35); color: #94A3B8; }
.node-Module   { background: rgba(248,113,113,0.10); border-color: rgba(248,113,113,0.40); color: #F87171; }

.stat-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
.stat-chip {
  background: var(--bg-inset); border: 1px solid var(--border-hair);
  border-radius: 6px; padding: 4px 10px;
  font-size: 12px; color: var(--text-mid);
}
.stat-chip strong { color: var(--text-hi); font-weight: 600; }

/* streaming cursor */
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
.cursor {
  display: inline-block; width: 2px; height: 1.05em;
  background: var(--mint);
  animation: blink 0.8s step-end infinite;
  vertical-align: text-bottom; margin-left: 2px; border-radius: 1px;
}
</style>
""", unsafe_allow_html=True)


# ── Session state ──────────────────────────────────────────────
for k, v in {
    "messages":     [],   # each: {role, content, time}
    "session_id":   None,
    "session_info": None,
    "last_repo":    "",
    "health":       None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


def _fetch_health(url: str) -> dict | None:
    try:
        r = requests.get(f"{url}/health", timeout=8)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def _safe_detail(resp) -> str:
    try:
        j = resp.json()
        if isinstance(j, dict):
            return str(j.get("detail", j))
    except Exception:
        pass
    return (resp.text or "")[:300]


def _now_str() -> str:
    return datetime.now().strftime("%I:%M %p").lstrip("0")


# ── SIDEBAR ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("# 🕸️ RepoGraphAI")
    st.markdown(
        "<p style='color:var(--text-low);font-size:12px;margin-top:-6px'>"
        "Ask questions about any Python repo</p>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

    if "_starter_repo" in st.session_state:
        st.session_state["repo_url_input"] = st.session_state.pop("_starter_repo")

    repo_url = st.text_input(
        "GitHub repository",
        placeholder="https://github.com/psf/requests",
        key="repo_url_input",
    )

    if st.session_state.session_id:
        info = st.session_state.session_info or {}
        n = info.get("node_count", "?")
        e = info.get("edge_count", "?")
        n_str = f"{n:,}" if isinstance(n, int) else str(n)
        e_str = f"{e:,}" if isinstance(e, int) else str(e)
        st.markdown(
            f'<div class="loaded-pill"><span class="dot"></span>'
            f'Loaded · <strong style="color:var(--mint-soft)">{n_str}</strong> nodes · '
            f'<strong style="color:var(--mint-soft)">{e_str}</strong> edges</div>',
            unsafe_allow_html=True,
        )
        if st.button("Load a different repo", use_container_width=True):
            st.session_state.session_id   = None
            st.session_state.session_info = None
            st.session_state.last_repo    = ""
            st.session_state.messages     = []
            st.rerun()

    # Backend parameters — sensible defaults, no user-facing controls.
    backend_url    = _DEFAULT_BACKEND.rstrip("/")
    api_key        = ""
    top_k          = 10
    max_hops       = 1
    use_embeddings = False

    st.markdown('<hr class="hairline"/>', unsafe_allow_html=True)

    # Recent chat — past user questions, click to re-run.
    st.markdown('<p class="eyebrow">Recent chat</p>', unsafe_allow_html=True)
    history_qs = [m["content"] for m in st.session_state.messages if m["role"] == "user"]
    if history_qs:
        seen, ordered = set(), []
        for q in reversed(history_qs):
            if q not in seen:
                seen.add(q); ordered.append(q)
        st.markdown('<div class="history-list">', unsafe_allow_html=True)
        for i, q in enumerate(ordered[:12]):
            label = q if len(q) <= 48 else q[:46].rstrip() + "…"
            if st.button(f"↺  {label}", key=f"hist_{i}", use_container_width=True, help=q):
                st.session_state["_prefill"] = q
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<p style="color:var(--text-low);font-size:12px;margin:0">No questions yet.</p>',
            unsafe_allow_html=True,
        )

    st.markdown('<hr class="hairline"/>', unsafe_allow_html=True)

    # Backend health — retry each rerun until success. Single line, no caption.
    if st.session_state.health is None:
        h = _fetch_health(backend_url)
        if h is not None:
            st.session_state.health = h
    else:
        h = st.session_state.health

    if h is None:
        st.markdown(
            '<div class="backend-row"><span class="mini-dot r"></span>Backend unreachable</div>',
            unsafe_allow_html=True,
        )
    else:
        llm_ok = h.get("llm_configured")
        cls   = "g" if llm_ok else "a"
        label = "Ready" if llm_ok else "Ready · retrieval only"
        st.markdown(
            f'<div class="backend-row"><span class="mini-dot {cls}"></span>{label}</div>',
            unsafe_allow_html=True,
        )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("↻ Refresh", use_container_width=True):
            st.session_state.health = _fetch_health(backend_url)
            st.rerun()
    with c2:
        if st.button("⌫ Clear chat", use_container_width=True):
            st.session_state.messages     = []
            st.session_state.session_id   = None
            st.session_state.session_info = None
            st.rerun()


# ── Helpers used by main area ───────────────────────────────────
def _headers():
    h = {"Content-Type": "application/json"}
    if api_key:
        h["X-API-Key"] = api_key
    return h


def _src_pill(node: dict) -> str:
    ntype = node.get("node_type", "")
    label = node.get("label") or node.get("node_id", "")
    fp    = node.get("file_path")
    ln    = node.get("line_number")
    if fp:
        display = f"{fp}:{ln}" if ln else fp
    else:
        display = label
    return (f'<span class="src-pill src-{ntype}"><span class="dot"></span>'
            f'{display}</span>')


def _node_badge(node: dict) -> str:
    ntype = node.get("node_type", "")
    nid   = node.get("node_id", "")
    score = node.get("score", 0)
    icons = {"Class": "□", "Method": "◈", "Function": "◆", "File": "◻", "Module": "○"}
    icon  = icons.get(ntype, "·")
    return (f'<span class="node-badge node-{ntype}" title="{ntype} · score {score:.2f}">'
            f'{icon} {nid}</span>')


def _render_metadata(meta: dict, source_nodes: list):
    with st.expander("⚡  Retrieval diagnostics", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Nodes retrieved", meta.get("resolved_node_count", "—"))
        c2.metric("Subgraph nodes",  meta.get("subgraph_node_count", "—"))
        c3.metric("Subgraph edges",  meta.get("subgraph_edge_count", "—"))
        c4.metric("Strategy",        meta.get("traversal_strategy", "—"))

        chips = ""
        if meta.get("intent_categories"):
            intents = " · ".join(f"<strong>{i}</strong>" for i in meta["intent_categories"])
            chips += f'<span class="stat-chip">Intent: {intents}</span>'
        if meta.get("keywords"):
            kws = ", ".join(meta["keywords"][:8])
            chips += f'<span class="stat-chip">Keywords: <strong>{kws}</strong></span>'
        if chips:
            st.markdown(f'<div class="stat-row">{chips}</div>', unsafe_allow_html=True)

        if source_nodes:
            st.markdown('<p class="eyebrow" style="margin-top:12px">All source nodes</p>', unsafe_allow_html=True)
            badges = "".join(_node_badge(n) for n in source_nodes)
            st.markdown(f'<div class="node-grid">{badges}</div>', unsafe_allow_html=True)


def _create_session(repo: str) -> bool:
    with st.spinner("Building knowledge graph…"):
        try:
            r = requests.post(
                f"{backend_url}/sessions",
                headers=_headers(),
                json={"repo_url": repo, "top_k": top_k, "max_hops": max_hops, "use_embeddings": use_embeddings},
                timeout=300,
            )
        except requests.exceptions.Timeout:
            st.error("Timed out. Repository may be too large.")
            return False
        except Exception as e:
            st.error(f"Error: {e}")
            return False

    if r.status_code == 201:
        d = r.json()
        st.session_state.session_id   = d["session_id"]
        st.session_state.session_info = d
        st.session_state.last_repo    = repo
        return True
    st.error(f"Session failed ({r.status_code}): {_safe_detail(r)}")
    return False


def _ask_streaming(question: str):
    placeholder  = st.empty()
    accumulated  = ""
    source_nodes = []
    meta         = {}

    try:
        requests.get(f"{backend_url}/health", timeout=3)
    except Exception:
        st.error(f"Cannot reach backend at **{backend_url}**. Check the Backend URL in the sidebar and make sure the server is running.")
        return None, [], {}

    try:
        with requests.post(
            f"{backend_url}/qa/stream",
            headers=_headers(),
            json={"repo_url": repo_url, "question": question,
                  "top_k": top_k, "max_hops": max_hops, "use_embeddings": use_embeddings},
            stream=True, timeout=300,
        ) as resp:
            if resp.status_code == 422:
                st.error(f"Validation error: {_safe_detail(resp)}"); return None, [], {}
            if resp.status_code == 401:
                st.error("API key required. Enter it in the sidebar under **API Key**."); return None, [], {}
            if resp.status_code == 429:
                st.error("Rate limit exceeded. Wait a moment and try again."); return None, [], {}
            if resp.status_code != 200:
                st.error(f"Server error {resp.status_code}: {_safe_detail(resp)}"); return None, [], {}

            for raw in resp.iter_lines():
                if not raw: continue
                line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                if not line.startswith("data: "): continue
                try: ev = json.loads(line[6:])
                except json.JSONDecodeError: continue

                t = ev.get("type")
                if t == "metadata":
                    source_nodes = ev.get("source_nodes", [])
                    meta = {
                        "intent_categories":   ev.get("intent_categories", []),
                        "keywords":            ev.get("keywords", []),
                        "resolved_node_count": len(source_nodes),
                        "subgraph_node_count": ev.get("subgraph_node_count", "—"),
                        "subgraph_edge_count": ev.get("subgraph_edge_count", "—"),
                        "traversal_strategy":  ev.get("traversal_strategy", "—"),
                    }
                elif t == "token":
                    accumulated += ev.get("text", "")
                    placeholder.markdown(accumulated + '<span class="cursor"></span>', unsafe_allow_html=True)
                elif t == "done":
                    full = ev.get("full_answer", accumulated)
                    placeholder.markdown(full)
                    return full, source_nodes, meta
                elif t == "error":
                    st.error("Server error: " + ev.get("detail", "Unknown error"))
                    return None, [], {}

    except requests.exceptions.Timeout:
        st.error("Request timed out. Try a smaller repository or simpler question.")
    except requests.exceptions.ConnectionError:
        st.error(f"Connection refused at **{backend_url}**. Is the backend running?")
    except Exception as e:
        st.error(f"Unexpected error: {e}")
    return None, [], {}


def _ask_session(question: str):
    if not st.session_state.session_id:
        return None, [], {}

    with st.spinner("Querying session (no re-clone)…"):
        try:
            r = requests.post(
                f"{backend_url}/sessions/{st.session_state.session_id}/qa",
                headers=_headers(),
                json={"question": question},
                timeout=120,
            )
        except requests.exceptions.ConnectionError:
            st.error(f"Connection refused at **{backend_url}**. The session is still saved — try again.")
            return None, [], {}
        except Exception as e:
            st.error(f"Error: {e}")
            return None, [], {}

    if r.status_code == 404:
        st.toast("Session expired — rebuilding graph…", icon="🔄")
        st.session_state.session_id = None
        return None, [], {}
    if r.status_code == 401:
        st.error("API key required. Enter it in the sidebar under **API Key**.")
        return None, [], {}
    if r.status_code != 200:
        st.error(f"Error {r.status_code}: {_safe_detail(r)}")
        return None, [], {}

    d      = r.json()
    answer = d.get("answer")
    meta   = d.get("retrieval_metadata", {})
    nodes  = d.get("source_nodes", [])

    if not answer:
        st.info("⚡ Offline mode — no LLM key configured. Showing retrieval context.")
        st.code(d.get("llm_context", ""), language=None)
        return "(offline)", nodes, meta
    return answer, nodes, meta


# ── MAIN ────────────────────────────────────────────────────────
def _bubble(role: str, content: str, ts: str, source_nodes: list | None = None):
    who = "You" if role == "user" else "RepoGraphAI"
    src_html = ""
    if source_nodes:
        pills = "".join(_src_pill(n) for n in source_nodes[:6])
        src_html = f'<div class="src-row">{pills}</div>'
    body_html = _md.render(content or "")
    st.markdown(
        f'<div class="msg-wrap {role}">'
        f'  <div class="bubble {role}">'
        f'    <div class="bubble-head"><span class="who">{who}</span><span class="time">{ts}</span></div>'
        f'    <div class="bubble-body">{body_html}{src_html}</div>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# Welcome screen — no messages yet
if not st.session_state.messages:
    def _graph_svg(size: int, sw: float = 1.8) -> str:
        return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
                f'stroke="currentColor" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">'
                '<circle cx="6" cy="6" r="2.2"/><circle cx="18" cy="6" r="2.2"/>'
                '<circle cx="12" cy="18" r="2.2"/><line x1="7.7" y1="7.6" x2="10.5" y2="16"/>'
                '<line x1="16.3" y1="7.6" x2="13.5" y2="16"/><line x1="8.5" y1="6" x2="15.5" y2="6"/></svg>')

    st.markdown(f"""
    <div class="hero-card">
      <div class="hero-top">
        <div class="pill-badge">▸ Code Intelligence</div>
        <div class="corner">{_graph_svg(26, 1.7)}</div>
      </div>
      <div class="hero-brand">
        <div class="hero-mark">{_graph_svg(24, 1.9)}</div>
        <h1 class="hero-title">RepoGraphAI</h1>
      </div>
      <p class="hero-desc">Ask natural-language questions about any Python repository on GitHub. Answers are grounded in a knowledge graph built from the actual code — classes, methods, imports, call sites.</p>
      <div class="action-row">
        <span class="action-pill"><span class="num">1</span>Paste a repo URL in the sidebar</span>
        <span class="action-pill"><span class="num">2</span>Ask a question below</span>
        <span class="action-pill"><span class="num">3</span>Explore with follow-ups</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Try a repo
    label_col, chips_col = st.columns([0.22, 0.78], gap="small")
    with label_col:
        st.markdown('<div class="chip-row-label">▸ Try a repo</div>', unsafe_allow_html=True)
    with chips_col:
        cc = st.columns(3)
        for col, (lbl, url) in zip(cc, [
            ("psf/requests",      "https://github.com/psf/requests"),
            ("tiangolo/typer",    "https://github.com/tiangolo/typer"),
            ("pydantic/pydantic", "https://github.com/pydantic/pydantic"),
        ]):
            with col:
                if st.button(lbl, use_container_width=True, key=f"starter_{lbl}"):
                    st.session_state["_starter_repo"] = url
                    st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Ask a question
    label_col2, chips_col2 = st.columns([0.22, 0.78], gap="small")
    with label_col2:
        st.markdown('<div class="chip-row-label">▸ Ask a question</div>', unsafe_allow_html=True)
    with chips_col2:
        ex_cols = st.columns(3)
        examples = [
            "Where is authentication handled?",
            "How does connection pooling work?",
            "Show me the main entry points",
        ]
        for col, ex in zip(ex_cols, examples):
            with col:
                if st.button(ex, use_container_width=True, key=f"ex_{ex}"):
                    st.session_state["_prefill"] = ex
                    st.rerun()

# Chat state — session header + messages
else:
    repo_label = st.session_state.last_repo or repo_url
    try:
        repo_slug = "/".join(repo_label.rstrip("/").split("/")[-2:])
    except Exception:
        repo_slug = repo_label
    st.markdown(
        f'<div class="session-header">'
        f'  <div class="left">Session / <span class="repo">{repo_slug}</span></div>'
        f'  <div class="right"><span class="dot"></span>Live graph</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    for msg in st.session_state.messages:
        _bubble(
            msg["role"],
            msg["content"],
            msg.get("time", ""),
            msg.get("source_nodes") if msg["role"] == "assistant" else None,
        )

# Chat input
default_q = st.session_state.pop("_prefill", "")
question = st.chat_input(
    "Ask a question about this repository…",
    disabled=not repo_url,
)

if not st.session_state.messages:
    st.markdown(
        '<p class="hero-footnote">Load a repository to unlock deep answers grounded in the graph.</p>',
        unsafe_allow_html=True,
    )
if default_q and not question:
    question = default_q

if question and repo_url:
    ts_user = _now_str()
    st.session_state.messages.append({"role": "user", "content": question, "time": ts_user})
    _bubble("user", question, ts_user)

    # Ensure session
    if not st.session_state.session_id or st.session_state.last_repo != repo_url:
        ok = _create_session(repo_url)
        if not ok:
            st.stop()

    answer, src_nodes, meta = _ask_session(question)

    # Session expired — rebuild once
    if answer is None and not st.session_state.session_id:
        st.info("Rebuilding graph after server restart…")
        ok = _create_session(repo_url)
        if ok:
            answer, src_nodes, meta = _ask_session(question)
        else:
            st.warning("Rebuild failed. Falling back to one-shot mode.")
            answer, src_nodes, meta = _ask_streaming(question)

    if answer:
        ts_a = _now_str()
        display = answer if answer != "(offline)" else "_Offline mode — see retrieval context above._"
        _bubble("assistant", display, ts_a, src_nodes)
        if meta or src_nodes:
            _render_metadata(meta, src_nodes)
        if answer != "(offline)":
            st.session_state.messages.append({
                "role": "assistant",
                "content": display,
                "time": ts_a,
                "source_nodes": src_nodes,
            })
