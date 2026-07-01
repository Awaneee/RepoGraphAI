# RepoGraphAI — Benchmark Generation Report

This report summarizes the creation, curation, and validation of the new automated, graph-native benchmark version.

## Benchmark Summary

- **Total Candidate Question Templates**: 88 candidates
- **Total Curated / Accepted Questions**: 86 questions
- **Benchmark Version**: `v2_curated`

### Repository Distribution
- **FastAPI**: 24 questions
- **RepoGraphAI**: 19 questions
- **Requests**: 22 questions
- **Typer**: 21 questions

### Category Distribution
- **Authentication**: 2 questions
- **CLI**: 12 questions
- **Configuration**: 2 questions
- **Graph Construction**: 11 questions
- **HTTP**: 12 questions
- **Parsing**: 11 questions
- **Retrieval**: 12 questions
- **Routing**: 12 questions
- **Utilities**: 12 questions

---

## Validation Metrics

The table below compares the retrieval metrics of the new curated benchmark (`v2_curated`) against the baseline manual benchmark (`v1_manual`).

| Metric | Baseline (`v1_manual`) | New Curated (`v2_curated`) | Status / Change |
| :--- | :--- | :--- | :--- |
| **Top-1 Accuracy** | 83.3% | 66.3% | 66.3% (-17.1%) |
| **Top-3 Accuracy** | 93.3% | 84.9% | 84.9% (-8.5%) |
| **Top-5 Accuracy** | 96.7% | 94.2% | 94.2% (-2.5%) |
| **Mean Reciprocal Rank (MRR)** | 0.879 | 0.771 | 0.771 (-0.108) |

> [!NOTE]
> Lower retrieval metrics on a larger, more balanced dataset are expected if it exposes genuine architectural retrieval limits (e.g. broad coverage of 4 repositories rather than a small subset). This is part of the Quality-First validation philosophy.

---


### Regressed / Failing Questions Analysis

The following questions failed to retrieve the expected symbol in the top 5 results:

#### 1. What is the purpose of the retrieval result?
- **Repository**: internal
- **Expected Symbol**: `RetrievalResult`
- **First Hit Rank**: Not Found
- **Top Retrieved Symbols**:
  - `ContextBuilder._collect_retrieval_results`
  - `RetrievalResult.edges_of_type`
  - `RetrievalResult.neighbour_ids`
- **Analysis**: Expected symbol not in top 5 retrieval. The query wording might need to be refined to better match the symbol label, or the symbol holds low centrality/importance in the graph.

#### 2. How does _RouterIncludeContext combine routing configurations?
- **Repository**: FastAPI
- **Expected Symbol**: `_RouterIncludeContext.combine`
- **First Hit Rank**: Not Found
- **Top Retrieved Symbols**:
  - `APIRouter.include_router`
  - `FastAPI.include_router`
  - `_RouterIncludeContext`
- **Analysis**: Expected symbol not in top 5 retrieval. The query wording might need to be refined to better match the symbol label, or the symbol holds low centrality/importance in the graph.

#### 3. How does the route decorator register a route in APIRouter?
- **Repository**: FastAPI
- **Expected Symbol**: `APIRouter.route`
- **First Hit Rank**: Not Found
- **Top Retrieved Symbols**:
  - `APIRouter.add_api_route`
  - `APIRouter.add_api_websocket_route`
  - `FastAPI.add_api_route`
- **Analysis**: Expected symbol not in top 5 retrieval. The query wording might need to be refined to better match the symbol label, or the symbol holds low centrality/importance in the graph.

#### 4. How is a route path resolved in _RouterIncludeContext?
- **Repository**: FastAPI
- **Expected Symbol**: `_RouterIncludeContext.path_for`
- **First Hit Rank**: Not Found
- **Top Retrieved Symbols**:
  - `APIRouter.include_router`
  - `FastAPI.include_router`
  - `_RouterIncludeContext`
- **Analysis**: Expected symbol not in top 5 retrieval. The query wording might need to be refined to better match the symbol label, or the symbol holds low centrality/importance in the graph.

#### 5. What is the purpose of the request exception?
- **Repository**: Requests
- **Expected Symbol**: `RequestException`
- **First Hit Rank**: Not Found
- **Top Retrieved Symbols**:
  - `Session.request`
  - `request`
  - `HTTPAdapter.request_url`
- **Analysis**: Expected symbol not in top 5 retrieval. The query wording might need to be refined to better match the symbol label, or the symbol holds low centrality/importance in the graph.



## Known Limitations & Dataset Evolution

1. **Static Templates**: Questions are generated using structured templates mapping verbs/nouns from public API symbols. Future iterations could integrate paraphrasing tools to enhance natural language variety.
2. **Deterministic matching**: Expected symbols are strictly verified via graph-native path IDs. Any refactoring of symbol names in subsequent repository updates requires regenerations.
