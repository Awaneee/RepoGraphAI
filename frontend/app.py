"""
RepoGraphAI — Streamlit Frontend

Connects to the FastAPI backend at BACKEND_URL (default: http://localhost:8000).
Supports streaming answers, multi-turn sessions, and retrieval diagnostics.

Run:
    streamlit run frontend/app.py
"""

import json
import time
from typing import Optional

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="RepoGraphAI",
    page_icon="🕸️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------

def _init_state():
    defaults = {
        "messages":     [],      # list of {role, content, metadata}
        "session_id":   None,    # active /sessions ID
        "session_info": None,    # {node_count, edge_count}
        "last_repo":    "",      # repo URL used to create current session
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ---------------------------------------------------------------------------
# Sidebar — settings
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🕸️ RepoGraphAI")
    st.caption("Graph-native RAG for codebase Q&A")
    st.divider()

    backend_url = st.text_input(
        "Backend URL",
        value="http://localhost:8000",
        help="URL of the FastAPI backend server",
    ).rstrip("/")

    repo_url = st.text_input(
        "Repository URL",
        placeholder="https://github.com/psf/requests",
        help="Any public GitHub, GitLab, or Bitbucket repository",
    )

    api_key = st.text_input(
        "API Key (optional)",
        type="password",
        help="Set in backend via API_KEY env var. Leave blank for open access.",
    )

    st.divider()
    st.subheader("Retrieval settings")

    top_k = st.slider("Top-K nodes", min_value=1, max_value=30, value=10,
                      help="How many graph nodes to retrieve per question")
    max_hops = st.slider("Max hops", min_value=0, max_value=3, value=1,
                         help="Neighbourhood expansion depth in the graph")
    use_embeddings = st.toggle("Hybrid retrieval",
                               help="Combine keyword + semantic (sentence-transformers). "
                                    "Slower but better on ambiguous questions.")

    st.divider()
    st.subheader("Mode")

    use_session = st.toggle(
        "Session mode",
        help="Build graph once, reuse for follow-up questions. Much faster for multi-turn Q&A.",
    )
    use_stream = st.toggle("Stream tokens", value=True,
                           help="Show answer word-by-word as the LLM generates it.")

    st.divider()

    # Health check
    if st.button("🔍 Check server health", use_container_width=True):
        try:
            r = requests.get(f"{backend_url}/health", timeout=5)
            h = r.json()
            if h.get("status") == "ok":
                st.success("Server is healthy")
            else:
                st.warning("Server degraded")
            col1, col2 = st.columns(2)
            col1.metric("LLM", "✓" if h.get("llm_configured") else "✗")
            col2.metric("Embeddings", "✓" if h.get("embedding_available") else "✗")
        except Exception as e:
            st.error(f"Cannot reach server: {e}")

    # Session management
    if st.session_state.session_id:
        st.success(f"Session active")
        info = st.session_state.session_info or {}
        st.caption(
            f"📊 {info.get('node_count', '?')} nodes · "
            f"{info.get('edge_count', '?')} edges"
        )
        if st.button("End session", use_container_width=True):
            st.session_state.session_id   = None
            st.session_state.session_info = None
            st.session_state.last_repo    = ""
            st.rerun()

    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.messages   = []
        st.session_state.session_id = None
        st.session_state.session_info = None
        st.rerun()

# ---------------------------------------------------------------------------
# Helper: common request headers
# ---------------------------------------------------------------------------

def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if api_key:
        h["X-API-Key"] = api_key
    return h

# ---------------------------------------------------------------------------
# Helper: create session
# ---------------------------------------------------------------------------

def _create_session(repo: str) -> bool:
    """POST /sessions and store session_id. Returns True on success."""
    try:
        with st.spinner("Building knowledge graph (first time only)…"):
            r = requests.post(
                f"{backend_url}/sessions",
                headers=_headers(),
                json={
                    "repo_url":       repo,
                    "top_k":          top_k,
                    "max_hops":       max_hops,
                    "use_embeddings": use_embeddings,
                },
                timeout=300,
            )
        if r.status_code == 201:
            data = r.json()
            st.session_state.session_id   = data["session_id"]
            st.session_state.session_info = data
            st.session_state.last_repo    = repo
            return True
        st.error(f"Session creation failed ({r.status_code}): {r.json().get('detail', r.text)}")
        return False
    except requests.exceptions.Timeout:
        st.error("Timed out creating session. The repository may be too large.")
        return False
    except Exception as e:
        st.error(f"Error: {e}")
        return False

# ---------------------------------------------------------------------------
# Helper: render source nodes
# ---------------------------------------------------------------------------

def _render_metadata(meta: dict, source_nodes: list):
    """Show retrieval metadata and source nodes in an expander."""
    with st.expander("📊 Retrieval details", expanded=False):
        col1, col2, col3 = st.columns(3)
        col1.metric("Nodes retrieved", meta.get("resolved_node_count", "—"))
        col2.metric("Subgraph nodes",  meta.get("subgraph_node_count", "—"))
        col3.metric("Strategy",        meta.get("traversal_strategy",  "—"))

        if meta.get("intent_categories"):
            st.caption("**Intent detected:** " + ", ".join(meta["intent_categories"]))
        if meta.get("keywords"):
            st.caption("**Keywords:** " + ", ".join(meta["keywords"]))

        if source_nodes:
            st.caption("**Source nodes:**")
            cols = st.columns(min(len(source_nodes), 4))
            type_colors = {
                "Class":    "🟦",
                "Method":   "🟩",
                "Function": "🟨",
                "File":     "⬜",
                "Module":   "🟫",
            }
            for i, node in enumerate(source_nodes):
                icon = type_colors.get(node.get("node_type", ""), "⚪")
                col = cols[i % len(cols)]
                col.markdown(
                    f"{icon} `{node['node_id']}`  \n"
                    f"<small>score: {node.get('score', 0):.2f}</small>",
                    unsafe_allow_html=True,
                )

# ---------------------------------------------------------------------------
# Core: ask via streaming SSE
# ---------------------------------------------------------------------------

def _ask_streaming(question: str) -> Optional[str]:
    """
    Call POST /qa/stream and render tokens live.
    Returns the final answer string, or None on error.
    """
    placeholder   = st.empty()
    accumulated   = ""
    source_nodes  = []
    meta          = {}

    try:
        with requests.post(
            f"{backend_url}/qa/stream",
            headers=_headers(),
            json={
                "repo_url":       repo_url,
                "question":       question,
                "top_k":          top_k,
                "max_hops":       max_hops,
                "use_embeddings": use_embeddings,
            },
            stream=True,
            timeout=300,
        ) as resp:
            if resp.status_code != 200:
                detail = resp.json().get("detail", resp.text)
                st.error(f"Error {resp.status_code}: {detail}")
                return None

            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                if not line.startswith("data: "):
                    continue

                try:
                    event = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue

                etype = event.get("type")

                if etype == "metadata":
                    source_nodes = event.get("source_nodes", [])
                    meta = {
                        "intent_categories":   event.get("intent_categories", []),
                        "keywords":            event.get("keywords", []),
                        "resolved_node_count": len(source_nodes),
                        "subgraph_node_count": event.get("subgraph_node_count", "—"),
                        "traversal_strategy":  event.get("traversal_strategy", "—"),
                    }

                elif etype == "token":
                    accumulated += event.get("text", "")
                    placeholder.markdown(accumulated + "▌")

                elif etype == "done":
                    full = event.get("full_answer", accumulated)
                    placeholder.markdown(full)
                    if meta or source_nodes:
                        _render_metadata(meta, source_nodes)
                    return full

                elif etype == "error":
                    st.error("Server error: " + event.get("detail", "Unknown"))
                    return None

    except requests.exceptions.Timeout:
        st.error("Request timed out. Try a smaller repository or simpler question.")
    except Exception as e:
        st.error(f"Connection error: {e}")
    return None

# ---------------------------------------------------------------------------
# Core: ask via sync endpoint (no streaming)
# ---------------------------------------------------------------------------

def _ask_sync(question: str) -> Optional[str]:
    """Call POST /qa and render the full response at once."""
    with st.spinner("Thinking…"):
        try:
            r = requests.post(
                f"{backend_url}/qa",
                headers=_headers(),
                json={
                    "repo_url":       repo_url,
                    "question":       question,
                    "top_k":          top_k,
                    "max_hops":       max_hops,
                    "use_embeddings": use_embeddings,
                },
                timeout=300,
            )
        except requests.exceptions.Timeout:
            st.error("Request timed out.")
            return None
        except Exception as e:
            st.error(f"Connection error: {e}")
            return None

    if r.status_code != 200:
        st.error(f"Error {r.status_code}: {r.json().get('detail', r.text)}")
        return None

    data   = r.json()
    answer = data.get("answer")
    meta   = data.get("retrieval_metadata", {})
    nodes  = data.get("source_nodes", [])

    if answer:
        st.markdown(answer)
    else:
        # Offline mode — no LLM key configured
        ctx = data.get("llm_context", "")
        st.info("No LLM key configured — showing raw retrieval context.")
        st.code(ctx, language=None)

    if meta or nodes:
        _render_metadata(meta, nodes)

    return answer or "(offline mode)"

# ---------------------------------------------------------------------------
# Core: ask via session endpoint (multi-turn)
# ---------------------------------------------------------------------------

def _ask_session(question: str) -> Optional[str]:
    """Call POST /sessions/{id}/qa for a multi-turn session question."""
    with st.spinner("Querying session (no re-clone)…"):
        try:
            r = requests.post(
                f"{backend_url}/sessions/{st.session_state.session_id}/qa",
                headers=_headers(),
                json={"question": question},
                timeout=120,
            )
        except Exception as e:
            st.error(f"Connection error: {e}")
            return None

    if r.status_code == 404:
        st.warning("Session expired. Creating a new one…")
        st.session_state.session_id = None
        return None
    if r.status_code != 200:
        st.error(f"Error {r.status_code}: {r.json().get('detail', r.text)}")
        return None

    data   = r.json()
    answer = data.get("answer")
    meta   = data.get("retrieval_metadata", {})
    nodes  = data.get("source_nodes", [])

    if answer:
        st.markdown(answer)
    else:
        ctx = data.get("llm_context", "")
        st.info("Offline mode — showing retrieval context.")
        st.code(ctx, language=None)

    if meta or nodes:
        _render_metadata(meta, nodes)

    return answer or "(offline mode)"

# ---------------------------------------------------------------------------
# Main chat UI
# ---------------------------------------------------------------------------

st.title("🕸️ RepoGraphAI")
st.caption("Ask questions about any GitHub repository using graph-native RAG.")

# Render existing chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
question = st.chat_input(
    "Ask about the repository…  (e.g. How does Session.send work?)",
    disabled=not repo_url,
)

if not repo_url:
    st.info("👈 Enter a repository URL in the sidebar to get started.")

if question and repo_url:
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # Get answer
    with st.chat_message("assistant"):

        answer = None

        # ── Session mode ──────────────────────────────────────────────────
        if use_session:
            # Create session if needed (or repo changed)
            if (
                not st.session_state.session_id
                or st.session_state.last_repo != repo_url
            ):
                ok = _create_session(repo_url)
                if not ok:
                    st.stop()

            answer = _ask_session(question)

            # If session expired, retry once with a fresh session
            if answer is None and not st.session_state.session_id:
                ok = _create_session(repo_url)
                if ok:
                    answer = _ask_session(question)

        # ── Streaming mode ────────────────────────────────────────────────
        elif use_stream:
            answer = _ask_streaming(question)

        # ── Sync mode ─────────────────────────────────────────────────────
        else:
            answer = _ask_sync(question)

    # Save assistant reply to history
    if answer:
        st.session_state.messages.append({"role": "assistant", "content": answer})
