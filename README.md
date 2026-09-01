# RepoGraphAI

A Python FastAPI backend that builds a typed knowledge graph from any Python **or TypeScript / JavaScript** repository and answers natural-language questions about it using graph-native retrieval (no embeddings, no vector databases). A Streamlit frontend is included.

**Live demo:** [repographai.onrender.com](https://repographai.onrender.com)

> Free-tier hosting: the service sleeps after 15 min of inactivity, so the first
> request after a nap takes ~30 s to wake up. Paste any public Python or TS/JS
> repo URL in the sidebar and ask a question — no signup required.

---

## Problem Statement

Reading unfamiliar codebases is expensive. Developers spend hours navigating file trees, tracing call chains, and piecing together class hierarchies before they can reason about a change or answer a question. RepoGraphAI automates this by converting a repository into a queryable knowledge graph and answering questions like:

- "How does authentication work?"
- "What methods does GraphBuilder expose?"
- "Which classes inherit from RepositoryRetriever?"
- "How is the graph cache invalidated?"

---

## Architecture

```
User Question
     |
     v
+-------------------------------------------------------+
|                     FastAPI                           |
|  POST /analyze  |  POST /graph  |  POST /qa          |
+-------------------------------------------------------+
        |                   |               |
        v                   v               v
RepositoryService    GraphService      GraphService
(clone + summary)   (build graph)   + ContextBuilder
        |                   |         + GraphRAGEngine
        v                   |               |
  git clone                 |               v
  (GitPython)               |         LLMProvider
                            |        (Anthropic or Gemini)
                            v
               +------------------------+
               |   CodeParser (Python)  |
               |   TypeScriptParser     |
               |   (tree-sitter, TS/JS) |
               +----------+-------------+
                          |
                          v
               +------------------------+
               |      GraphBuilder      |
               |  3-pass typed graph    |
               +----------+-------------+
                          |
                          v
               +------------------------+
               |    RepositoryGraph     |<-- RepositoryCache
               |  (nodes + edges)       |    (disk pickle)
               +----------+-------------+
                          |
               +----------+-----------+
               v                      v
     QueryResolver            RepositoryRetriever
     (15-signal keyword       (graph traversal,
      + intent ranking)        subgraph extraction)
               |                      |
               +-----------+----------+
                           v
                    ContextBuilder
               (intent-aware traversal
                + LLM context assembly)
                           |
                           v
                    ContextPackage
              (structured retrieval result)
                           |
                           v
                   GraphRAGEngine
              (prompt construction + LLM call)
                           |
                           v
                   GraphRAGResponse
            {answer, source_nodes, metadata}
```

---

## Graph Schema

### Node Types

| Type | Description |
|------|-------------|
| File | A source file (`.py` or `.ts` / `.tsx` / `.js` / `.jsx` / `.mjs` / `.cjs`). ID = file path. |
| Module | A dotted import path, e.g. fastapi, os.path. Classified as stdlib / third_party / internal. |
| Class | A class definition. Hub for INHERITS, CONTAINS, INSTANTIATES edges. |
| Function | A module-level (top-level) function. |
| Method | A function defined inside a class body. Kept separate so OVERRIDES can be expressed. |

### Node Fields

All nodes: `id`, `type`, `label`, `file_path`, `line_number`, `line_end`, `docstring`

Function / Method only: `source_code` (actual def block, truncated at 50 lines to first 30 + last 5)

Module only: `module_origin` (stdlib | third_party | internal | unknown)

### Edge Types

| Type | Direction | Description |
|------|-----------|-------------|
| CONTAINS | File -> Class, File -> Function, Class -> Method | Structural containment |
| IMPORTS | File -> Module | Import dependency |
| CALLS | Function/Method -> Function/Method | Call site in function body |
| INHERITS | Class -> Class | Inheritance relationship |
| INSTANTIATES | Function/Method -> Class | Direct object construction |
| DECORATES | decorator_ref -> Function/Method/Class | Decorator application |
| OVERRIDES | Method -> Method | Method override in subclass |

---

## Retrieval Approach

**No embeddings. No vector databases.**

QueryResolver uses 15 weighted signals to rank graph nodes against a natural-language question:

| Signal | Weight | Description |
|--------|--------|-------------|
| EXACT_LABEL | +10.0 | node.label == keyword (case-insensitive) |
| EXACT_ID | +8.0 | node.id == keyword |
| PHRASE_MATCH | +7.0 | node matches a recognised multi-word SE phrase |
| INTENT_TYPE | +6.0 | node type matches the intent's preferred types |
| MULTI_KW_BONUS | +5.0 | node matches 2+ distinct base keywords |
| CALLABLE_SUPREMACY | +5.0 | METHOD/FUNCTION in implementation queries |
| PARTIAL_LABEL | +4.0 | keyword in node.label |
| VERB_LABEL_BOOST | +4.0 | node label verb component matches intent |
| NODE_TYPE_BASE | +3.0 | CLASS/FUNCTION/METHOD over FILE/MODULE |
| SNAKE_EXPANSION | +3.0 | snake_case component match |
| LABEL_COVERAGE | +3.0 | >= 67% of node parts match query keywords |
| PARTIAL_ID | +2.0 | keyword in node.id |
| HOTSPOT_BOOST | +1.0/edge, cap +5.0 | proportional to graph degree |
| DTO_PENALTY | -15.0 | node looks like a data container |
| GENERIC_PENALTY | -4.0 | node only matches via expansion, not base keywords |

### Intent Detection

16 intent categories detected from query keywords and multi-word phrases:

PARSING, GENERATION, RETRIEVAL, LOADING, SAVING, VISUALIZATION, STATISTICS,
ANALYSIS, AUTHENTICATION, ROUTING, VALIDATION, EXECUTION, CONFIGURATION,
TRANSFORMATION, GRAPH_TRAVERSAL, AGGREGATION, UNKNOWN

### Intent-Aware Traversal Policies

Each intent has a per-edge-type hop budget for subgraph expansion:

- **ROUTING**: CALLS=2, DECORATES=2 -- follow call and decorator chains
- **EXECUTION**: CALLS=2, INSTANTIATES=2 -- follow runtime flow
- **ANALYSIS**: INHERITS=2, OVERRIDES=2 -- follow class hierarchy
- **LOADING**: IMPORTS=2 -- follow transitive import dependencies

CONTAINS is excluded (0 hops) by default to prevent noise from structural containers.

---

## Evaluation Results

Measured on the RepoGraphAI codebase (cross-repo benchmark, v2_curated benchmark set):

| Metric | Score |
|--------|-------|
| Top-1 Accuracy | **82.6%** |
| MRR (Mean Reciprocal Rank) | **0.890** |
| Top-5 Accuracy | ~96% |

These are retrieval metrics -- they measure whether the correct graph node appears in the top-K results, not whether the final LLM answer is correct.

---

## Setup

### Prerequisites

- Python 3.10+
- Git

### Installation

```bash
cd backend
pip install fastapi uvicorn pydantic pydantic-settings gitpython python-dotenv networkx

# Optional: for LLM answers
pip install anthropic       # Anthropic Claude
pip install google-genai    # Google Gemini

# Optional: for TypeScript / JavaScript support
pip install tree-sitter tree-sitter-typescript
```

### Frontend (Streamlit)

```bash
pip install -r frontend/requirements.txt
streamlit run frontend/app.py
```

The frontend defaults to `http://localhost:8000` for the backend; override with
`REPOGRAPHAI_BACKEND_URL` or the sidebar's Advanced settings.

### Configuration

```bash
cp backend/.env.example backend/.env
# Edit .env and add your LLM API key
```

Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| ANTHROPIC_API_KEY | (none) | Anthropic Claude API key |
| GOOGLE_API_KEY | (none) | Google Gemini API key |
| DEFAULT_LLM_PROVIDER | anthropic | Which provider to prefer |
| MAX_REPO_SIZE_MB | 500 | Clone size limit |
| CLONE_TIMEOUT_SECONDS | 60 | Clone timeout (Unix only) |

### Running

```bash
cd backend
uvicorn app.main:app --reload
```

API docs at http://localhost:8000/docs

---

## API

### POST /analyze

Clone a repository and return a filesystem summary.

```json
{"repo_url": "https://github.com/psf/requests"}
```

Returns: language distribution, framework detection, file counts, largest files.

---

### POST /graph

Build and cache the typed knowledge graph.

```json
{"repo_url": "https://github.com/psf/requests"}
```

Returns: nodes and typed edges. Subsequent calls for the same unchanged repository load from cache.

---

### POST /qa

Answer a natural-language question about a repository.

```json
{
  "repo_url": "https://github.com/psf/requests",
  "question": "How does session management work?",
  "top_k": 10,
  "max_hops": 1
}
```

Returns:
```json
{
  "question": "How does session management work?",
  "answer": "...",
  "source_nodes": [{"node_id": "...", "score": 18.5, ...}],
  "retrieval_metadata": {"intent_categories": [...], "traversal_strategy": "authentication"},
  "intent_categories": ["authentication"]
}
```

If no LLM key is configured: `answer` is null, `llm_context` is populated (useful for offline testing).

**Security:** Only https://github.com, https://gitlab.com, https://bitbucket.org URLs are accepted.

---

## Security Measures

| Risk | Mitigation |
|------|------------|
| SSRF | URL allowlist: github.com, gitlab.com, bitbucket.org only |
| Path traversal | Repo name regex + realpath guard |
| Concurrent clone race | Per-repo threading.Lock |
| Hung clone | 60s SIGALRM timeout (Unix, main thread only) |
| Disk exhaustion | 500 MB post-clone size limit |
| Cache safety | Pickle used only for internal state; external input sanitized before any path derivation |

---

## Technologies Actually Present

- FastAPI -- web framework
- Streamlit -- frontend chat UI
- Pydantic + pydantic-settings -- data validation and settings
- GitPython -- repository cloning (shallow, `--depth=1`)
- Python `ast` module -- purely syntactic Python analysis (no runtime imports)
- tree-sitter + tree-sitter-typescript -- syntactic TS/JS analysis (optional)
- NetworkX -- graph analysis utilities
- anthropic SDK -- Claude LLM provider (optional)
- google-genai -- Gemini LLM provider (optional)
- sentence-transformers -- opt-in embedding re-ranker (optional)
- pickle -- internal graph cache
- threading.Lock -- concurrent clone safety

## Technologies NOT Present

This project does NOT use:
- Redis
- Kubernetes or Docker
- Kafka or message queues
- Neo4j or any graph database
- Vector databases (Chroma, Qdrant, pgvector, etc.) -- embeddings, when enabled, are computed on-the-fly and re-rank the keyword-ranked candidates; no persistent vector store
- Celery

---

## Known Limitations

1. **Python and TypeScript/JavaScript only** -- other languages (Go, Rust, Java, C++, Ruby, …) are not parsed; the graph for such repos will be effectively empty.
2. **Keyword-based retrieval** -- No embeddings by default; questions with no keyword overlap may return poor results. Optional semantic re-ranking is available via the sidebar's "Semantic search" toggle.
3. **Synchronous** -- All operations are synchronous; requests queue under load.
4. **No authentication** -- Suitable for local use only.
5. **Clone timeout** -- SIGALRM only works in the Unix main thread; test/worker threads have no timeout.
6. **Source code truncation** -- Functions > 50 lines are truncated to first 30 + last 5 lines.
7. **Shallow-clone tradeoff** -- Repos are cloned with `--depth=1 --single-branch --no-tags` for speed; historical `git blame` / commit-diff features are not available inside the graph.

---

## Future Work

- Async clone and graph build (asyncio subprocess or BackgroundTasks)
- Additional language parsers (Java, Go, Rust)
- Deeper hybrid retrieval (embedding re-ranker is present as an opt-in toggle)
- Incremental graph update (diff-based re-parse on file change)
- Authentication / rate limiting layer
