"""
RepoGraphAI — Streamlit Frontend
Run: streamlit run frontend/app.py
"""

import json
import requests
import streamlit as st

# ── Page config (must be first) ───────────────────────────────────────────────
st.set_page_config(
    page_title="RepoGraphAI",
    page_icon="🕸️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Global ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Hide Streamlit default chrome */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* ── App background ── */
.stApp {
    background: linear-gradient(135deg, #0d1117 0%, #0f1923 100%);
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #0d1117;
    border-right: 1px solid #21262d;
}
[data-testid="stSidebar"] .stMarkdown h1 {
    background: linear-gradient(90deg, #388bfd, #58a6ff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 1.6rem;
    font-weight: 700;
    letter-spacing: -0.5px;
}

/* ── Inputs ── */
.stTextInput input, .stTextArea textarea {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
    color: #e6edf3 !important;
    font-family: 'Inter', sans-serif !important;
    transition: border-color 0.2s !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: #388bfd !important;
    box-shadow: 0 0 0 3px rgba(56,139,253,0.15) !important;
}

/* ── Sliders ── */
.stSlider [data-testid="stSlider"] > div > div > div {
    background: #388bfd;
}

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #1f6feb, #388bfd) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-family: 'Inter', sans-serif !important;
    transition: all 0.2s !important;
    padding: 0.5rem 1rem !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(56,139,253,0.4) !important;
}
.stButton > button:active { transform: translateY(0) !important; }

/* ── Chat messages ── */
[data-testid="stChatMessage"] {
    background: #161b22 !important;
    border: 1px solid #21262d !important;
    border-radius: 12px !important;
    padding: 1rem !important;
    margin-bottom: 0.75rem !important;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background: #1c2434 !important;
    border-color: #1f3a5f !important;
}

/* ── Chat input ── */
[data-testid="stChatInput"] {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 12px !important;
}
[data-testid="stChatInput"]:focus-within {
    border-color: #388bfd !important;
    box-shadow: 0 0 0 3px rgba(56,139,253,0.15) !important;
}
[data-testid="stChatInput"] textarea {
    background: transparent !important;
    color: #e6edf3 !important;
    font-family: 'Inter', sans-serif !important;
}

/* ── Expanders ── */
[data-testid="stExpander"] {
    background: #0d1117 !important;
    border: 1px solid #21262d !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"] summary {
    color: #8b949e !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
}
[data-testid="stExpander"] summary:hover { color: #e6edf3 !important; }

/* ── Metrics ── */
[data-testid="stMetric"] {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 0.75rem 1rem;
}
[data-testid="stMetricValue"] { color: #58a6ff !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { color: #8b949e !important; font-size: 0.75rem !important; }

/* ── Dividers ── */
hr { border-color: #21262d !important; }

/* ── Code blocks ── */
code {
    font-family: 'JetBrains Mono', monospace !important;
    background: #161b22 !important;
    color: #79c0ff !important;
    border-radius: 4px !important;
    padding: 2px 6px !important;
    font-size: 0.85em !important;
}

/* ── Success / Info / Error ── */
.stAlert {
    border-radius: 10px !important;
    border: none !important;
}

/* ── Toggle / Checkbox ── */
.stCheckbox label, [data-testid="stToggle"] label {
    color: #c9d1d9 !important;
    font-size: 0.9rem !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #484f58; }

/* ── Custom node badge ── */
.node-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 8px;
}
.node-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 20px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    font-weight: 500;
    border: 1px solid;
    white-space: nowrap;
}
.node-Class    { background:#1f3a5f22; border-color:#388bfd66; color:#58a6ff; }
.node-Method   { background:#1a3a2222; border-color:#3fb95066; color:#3fb950; }
.node-Function { background:#3a2d1022; border-color:#d2992266; color:#d29922; }
.node-File     { background:#2a2a2a22; border-color:#8b949e66; color:#8b949e; }
.node-Module   { background:#3a1f1f22; border-color:#f8514966; color:#f85149; }

/* ── Stat chips ── */
.stat-row {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin: 6px 0;
}
.stat-chip {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 0.78rem;
    color: #8b949e;
}
.stat-chip strong { color: #c9d1d9; }

/* ── Welcome card ── */
.welcome-card {
    background: linear-gradient(135deg, #161b22, #1c2434);
    border: 1px solid #21262d;
    border-radius: 16px;
    padding: 2.5rem;
    text-align: center;
    margin: 2rem auto;
    max-width: 600px;
}
.welcome-card h2 {
    background: linear-gradient(90deg, #388bfd, #79c0ff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 1.8rem;
    font-weight: 700;
    margin-bottom: 0.5rem;
}
.welcome-card p { color: #8b949e; font-size: 0.95rem; line-height: 1.6; }
.welcome-steps {
    display: flex;
    justify-content: center;
    gap: 1.5rem;
    margin-top: 1.5rem;
    flex-wrap: wrap;
}
.welcome-step {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 0.75rem 1.25rem;
    font-size: 0.85rem;
    color: #c9d1d9;
}
.welcome-step .step-num {
    display: block;
    color: #388bfd;
    font-weight: 700;
    font-size: 1.1rem;
    margin-bottom: 4px;
}

/* ── Streaming cursor ── */
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
.cursor {
    display: inline-block;
    width: 2px;
    height: 1.1em;
    background: #388bfd;
    animation: blink 0.8s step-end infinite;
    vertical-align: text-bottom;
    margin-left: 2px;
    border-radius: 1px;
}

/* ── Session badge ── */
.session-active {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #1a3a22;
    border: 1px solid #3fb95066;
    border-radius: 20px;
    padding: 4px 12px;
    color: #3fb950;
    font-size: 0.8rem;
    font-weight: 600;
}
.session-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #3fb950;
    animation: blink 1.5s ease-in-out infinite;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
for k, v in {
    "messages":     [],
    "session_id":   None,
    "session_info": None,
    "last_repo":    "",
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("# 🕸️ RepoGraphAI")
    st.markdown("<p style='color:#8b949e;font-size:0.85rem;margin-top:-10px'>Graph-native RAG for codebase Q&A</p>", unsafe_allow_html=True)
    st.divider()

    backend_url = st.text_input(
        "🔗 Backend URL",
        value="http://localhost:8000",
    ).rstrip("/")

    repo_url = st.text_input(
        "📦 Repository URL",
        placeholder="https://github.com/psf/requests",
    )

    api_key = st.text_input("🔑 API Key", type="password", placeholder="Optional")

    st.divider()
    st.markdown("<p style='color:#8b949e;font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em'>Retrieval</p>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        top_k = st.slider("Top-K", 1, 30, 10, help="Nodes retrieved per query")
    with col2:
        max_hops = st.slider("Hops", 0, 3, 1, help="Graph expansion depth")

    use_embeddings = st.toggle("🔀 Hybrid retrieval", help="Keyword + semantic (sentence-transformers)")

    st.divider()
    st.markdown("<p style='color:#8b949e;font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em'>Mode</p>", unsafe_allow_html=True)

    use_session = st.toggle("💬 Session mode", help="Build graph once, reuse for follow-ups")
    use_stream  = st.toggle("⚡ Stream tokens", value=True, help="Live word-by-word output")

    st.divider()

    # Session status
    if st.session_state.session_id:
        info = st.session_state.session_info or {}
        st.markdown(
            f'<div class="session-active"><div class="session-dot"></div>'
            f'Session active &nbsp;·&nbsp; {info.get("node_count","?")} nodes</div>',
            unsafe_allow_html=True,
        )
        st.caption(f'↳ {info.get("edge_count","?")} edges in graph')
        if st.button("✕ End session", use_container_width=True):
            st.session_state.session_id   = None
            st.session_state.session_info = None
            st.session_state.last_repo    = ""
            st.rerun()

    # Health check
    if st.button("🔍 Server health", use_container_width=True):
        try:
            r = requests.get(f"{backend_url}/health", timeout=5)
            h = r.json()
            if h.get("status") == "ok":
                st.success("✓ Server healthy")
            else:
                st.warning("⚠ Server degraded")
            c1, c2 = st.columns(2)
            c1.metric("LLM", "✓" if h.get("llm_configured") else "✗")
            c2.metric("Embeddings", "✓" if h.get("embedding_available") else "✗")
        except Exception as e:
            st.error(f"Cannot reach server: {e}")

    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.messages   = []
        st.session_state.session_id = None
        st.session_state.session_info = None
        st.rerun()


# ── Header ────────────────────────────────────────────────────────────────────
def _headers():
    h = {"Content-Type": "application/json"}
    if api_key:
        h["X-API-Key"] = api_key
    return h


def _node_badge(node: dict) -> str:
    ntype = node.get("node_type", "")
    nid   = node.get("node_id", "")
    score = node.get("score", 0)
    icons = {"Class": "□", "Method": "◈", "Function": "◆", "File": "◻", "Module": "○"}
    icon  = icons.get(ntype, "·")
    return (
        f'<span class="node-badge node-{ntype}" title="{ntype} · score {score:.2f}">'
        f'{icon} {nid}</span>'
    )


def _render_metadata(meta: dict, source_nodes: list):
    with st.expander("📊 Retrieval diagnostics", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Nodes retrieved",  meta.get("resolved_node_count", "—"))
        c2.metric("Subgraph nodes",   meta.get("subgraph_node_count", "—"))
        c3.metric("Subgraph edges",   meta.get("subgraph_edge_count", "—"))
        c4.metric("Strategy",         meta.get("traversal_strategy", "—"))

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
            st.markdown("<p style='color:#8b949e;font-size:0.8rem;margin:12px 0 6px'>Source nodes</p>", unsafe_allow_html=True)
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
    st.error(f"Session failed ({r.status_code}): {r.json().get('detail', r.text)}")
    return False


def _ask_streaming(question: str):
    placeholder  = st.empty()
    accumulated  = ""
    source_nodes = []
    meta         = {}

    try:
        with requests.post(
            f"{backend_url}/qa/stream",
            headers=_headers(),
            json={"repo_url": repo_url, "question": question,
                  "top_k": top_k, "max_hops": max_hops, "use_embeddings": use_embeddings},
            stream=True, timeout=300,
        ) as resp:
            if resp.status_code != 200:
                st.error(f"Error {resp.status_code}: {resp.json().get('detail', resp.text)}")
                return None

            for raw in resp.iter_lines():
                if not raw:
                    continue
                line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                if not line.startswith("data: "):
                    continue
                try:
                    ev = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue

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
                    if meta or source_nodes:
                        _render_metadata(meta, source_nodes)
                    return full
                elif t == "error":
                    st.error("Server: " + ev.get("detail", "Unknown error"))
                    return None

    except requests.exceptions.Timeout:
        st.error("Request timed out.")
    except Exception as e:
        st.error(f"Connection error: {e}")
    return None


def _ask_sync(question: str):
    with st.spinner("Thinking…"):
        try:
            r = requests.post(
                f"{backend_url}/qa",
                headers=_headers(),
                json={"repo_url": repo_url, "question": question,
                      "top_k": top_k, "max_hops": max_hops, "use_embeddings": use_embeddings},
                timeout=300,
            )
        except Exception as e:
            st.error(f"Error: {e}")
            return None

    if r.status_code != 200:
        st.error(f"Error {r.status_code}: {r.json().get('detail', r.text)}")
        return None

    d      = r.json()
    answer = d.get("answer")
    meta   = d.get("retrieval_metadata", {})
    nodes  = d.get("source_nodes", [])

    if answer:
        st.markdown(answer)
    else:
        st.info("⚡ Offline mode — no LLM key configured. Showing retrieval context.")
        st.code(d.get("llm_context", ""), language=None)

    if meta or nodes:
        _render_metadata(meta, nodes)
    return answer or "(offline)"


def _ask_session(question: str):
    with st.spinner("Querying session…"):
        try:
            r = requests.post(
                f"{backend_url}/sessions/{st.session_state.session_id}/qa",
                headers=_headers(),
                json={"question": question},
                timeout=120,
            )
        except Exception as e:
            st.error(f"Error: {e}")
            return None

    if r.status_code == 404:
        st.warning("Session expired — creating a new one…")
        st.session_state.session_id = None
        return None
    if r.status_code != 200:
        st.error(f"Error {r.status_code}: {r.json().get('detail', r.text)}")
        return None

    d      = r.json()
    answer = d.get("answer")
    meta   = d.get("retrieval_metadata", {})
    nodes  = d.get("source_nodes", [])

    if answer:
        st.markdown(answer)
    else:
        st.info("⚡ Offline mode.")
        st.code(d.get("llm_context", ""), language=None)

    if meta or nodes:
        _render_metadata(meta, nodes)
    return answer or "(offline)"


# ── Main ──────────────────────────────────────────────────────────────────────

# Welcome screen
if not st.session_state.messages:
    st.markdown("""
    <div class="welcome-card">
        <h2>🕸️ RepoGraphAI</h2>
        <p>Ask natural-language questions about any GitHub repository.<br>
        The answer is grounded in a typed knowledge graph built from the code — not just file search.</p>
        <div class="welcome-steps">
            <div class="welcome-step"><span class="step-num">1</span>Paste a GitHub URL in the sidebar</div>
            <div class="welcome-step"><span class="step-num">2</span>Type a question below</div>
            <div class="welcome-step"><span class="step-num">3</span>Watch the answer stream</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Example questions
    st.markdown("<p style='text-align:center;color:#8b949e;font-size:0.85rem;margin-top:1rem'>Try these with <code>https://github.com/psf/requests</code></p>", unsafe_allow_html=True)
    ex_cols = st.columns(3)
    examples = [
        "How does Session.send work?",
        "What does HTTPAdapter do?",
        "How are redirects handled?",
    ]
    for col, ex in zip(ex_cols, examples):
        with col:
            if st.button(f'"{ex}"', use_container_width=True):
                st.session_state["_prefill"] = ex
                st.rerun()

# Render existing messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="👤" if msg["role"] == "user" else "🕸️"):
        st.markdown(msg["content"])

# Pre-fill from example buttons
default_q = st.session_state.pop("_prefill", "")

# Chat input
question = st.chat_input(
    "Ask anything about the repository…",
    disabled=not repo_url,
)
if default_q and not question:
    question = default_q

if not repo_url and not st.session_state.messages:
    pass  # welcome screen already shown

if question and repo_url:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user", avatar="👤"):
        st.markdown(question)

    with st.chat_message("assistant", avatar="🕸️"):
        answer = None

        if use_session:
            if not st.session_state.session_id or st.session_state.last_repo != repo_url:
                ok = _create_session(repo_url)
                if not ok:
                    st.stop()
            answer = _ask_session(question)
            if answer is None and not st.session_state.session_id:
                if _create_session(repo_url):
                    answer = _ask_session(question)
        elif use_stream:
            answer = _ask_streaming(question)
        else:
            answer = _ask_sync(question)

    if answer:
        st.session_state.messages.append({"role": "assistant", "content": answer})
