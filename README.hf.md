---
title: RepoGraphAI
emoji: 🕸️
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Ask natural-language questions about any Python/TS repo.
---

# RepoGraphAI

Ask natural-language questions about any Python or TypeScript/JavaScript
repository on GitHub. Answers are grounded in a typed knowledge graph built
from the actual code — classes, methods, imports, call sites — not just file
search.

- **Backend**: FastAPI + tree-sitter/AST parsers + graph-native retrieval.
- **Frontend**: Streamlit chat UI.
- **LLM**: Google Gemini (default) or Anthropic Claude.

## How it works on this Space

Both processes run inside one Docker container. Streamlit binds to the
public port (`7860`). FastAPI runs on `127.0.0.1:8000` internally.

## Environment (set as Space secrets)

| Key | Required | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` | at least one | Gemini API key |
| `ANTHROPIC_API_KEY` | at least one | Claude API key |
| `DEFAULT_LLM_PROVIDER` | no | `gemini` (default) or `anthropic` |
| `MAX_REPO_SIZE_MB` | no | Hard cap on clone size (default 500) |
| `API_KEY` | no | If set, requests must include `X-API-Key: <value>` |

Without any LLM key the app still runs in retrieval-only mode (returns
graph context instead of a generated answer).

## Notes

- First cold start after a deploy is ~3–4 min (Docker build + model download).
- Free Spaces sleep after 48 hrs of inactivity; the first request after sleep
  triggers a fast restart.
- Cloned repos live on ephemeral disk. They re-clone on restart, but the
  shallow clone (`--depth=1`) keeps this under a minute for most repos.
- Source: [github.com/Awaneee/RepoGraphAI](https://github.com/Awaneee/RepoGraphAI)
