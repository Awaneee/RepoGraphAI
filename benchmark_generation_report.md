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
| **Top-1 Accuracy** | 83.3% | 82.6% | 82.6% (-0.8%) |
| **Top-3 Accuracy** | 93.3% | 94.2% | 94.2% (+0.9%) |
| **Top-5 Accuracy** | 96.7% | 98.8% | 98.8% (+2.2%) |
| **Mean Reciprocal Rank (MRR)** | 0.879 | 0.890 | 0.890 (+0.011) |

> [!NOTE]
> Lower retrieval metrics on a larger, more balanced dataset are expected if it exposes genuine architectural retrieval limits (e.g. broad coverage of 4 repositories rather than a small subset). This is part of the Quality-First validation philosophy.

---


### Regressed / Failing Questions Analysis

The following questions failed to retrieve the expected symbol in the top 5 results:

#### 1. How does the route decorator register a route in APIRouter?
- **Repository**: FastAPI
- **Expected Symbol**: `APIRouter.route`
- **First Hit Rank**: Not Found
- **Top Retrieved Symbols**:
  - `APIRouter.add_api_route`
  - `APIRouter.add_api_websocket_route`
  - `APIRouter.api_route`
- **Analysis**: Expected symbol not in top 5 retrieval. The query wording might need to be refined to better match the symbol label, or the symbol holds low centrality/importance in the graph.



## Known Limitations & Dataset Evolution

1. **Static Templates**: Questions are generated using structured templates mapping verbs/nouns from public API symbols. Future iterations could integrate paraphrasing tools to enhance natural language variety.
2. **Deterministic matching**: Expected symbols are strictly verified via graph-native path IDs. Any refactoring of symbol names in subsequent repository updates requires regenerations.
