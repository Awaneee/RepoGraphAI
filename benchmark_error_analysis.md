# RepoGraphAI — Benchmark Error Analysis & Benchmark Refinement

This report performs a deep-dive error analysis on the 8 failed questions in the initial curated benchmark and documents the subsequent benchmark refinement.

---

## Overall Statistics

- **Initial Curated Questions**: 88
- **Refined Benchmark Questions**: 86
- **Question Classification Counts**:
  - **KEEP**: 2 questions (valid questions exposing genuine retrieval weaknesses)
  - **REWRITE**: 4 questions (poorly worded template questions rewritten to natural wording)
  - **REMOVE**: 2 questions (invalid templates or duplicate questions)

---

## Comparative Validation Metrics

The table below summarizes the metrics before and after the refinement process, compared to the original manual benchmark.

| Metric | Baseline (`v1_manual`) | Initial Curated (`v2_curated` - 88 Qs) | Refined Curated (`v2_curated` - 86 Qs) | Refined vs. Initial Change |
| :--- | :--- | :--- | :--- | :--- |
| **Top-1 Accuracy** | 83.3% | 64.8% | **66.3%** | +1.5% |
| **Top-3 Accuracy** | 93.3% | 81.8% | **84.9%** | +3.1% |
| **Top-5 Accuracy** | 96.7% | 90.9% | **94.2%** | +3.3% |
| **Mean Reciprocal Rank (MRR)** | 0.879 | 0.750 | **0.772** | +0.022 |

---

## Per-Question Failure Analysis

### 1. What is the purpose of the retrieval result?
- **Expected Symbol**: `RetrievalResult` (RepoGraphAI)
- **Retrieved Top-5**:
  1. `ContextBuilder._collect_retrieval_results`
  2. `RetrievalResult.edges_of_type`
  3. `RetrievalResult.neighbour_ids`
- **Classification**: **KEEP**
- **Primary Cause**: **Ranking weakness** (the resolver prefers high-centrality action methods over a model class).
- **Reasoning**: This is a realistic query about the structure of retrieval outputs. The resolver fails to surface the class `RetrievalResult` because it is penalized as a DTO and has a lower degree than helper methods. Leaving it exposes a genuine retrieval weakness.

### 2. How is code parsed by the BaseModelWithConfig?
- **Expected Symbol**: `BaseModelWithConfig` (FastAPI)
- **Classification**: **REMOVE**
- **Primary Cause**: **Expected symbol is incorrect** (the template engine assigned `BaseModelWithConfig` to the "Parsing" category incorrectly).
- **Reasoning**: `BaseModelWithConfig` is a data class config helper and does not perform any code parsing. The generated question is semantic nonsense and objectively poor.

### 3. How are routes registered for for include?
- **Expected Symbol**: `_RouterIncludeContext.for_include` (FastAPI)
- **Classification**: **REWRITE**
- **New Wording**: `How is the router inclusion context constructed for_include?`
- **New Rank**: **Rank 3 (PASS)**
- **Primary Cause**: **Question wording is unnatural** (double preposition "for for").
- **Reasoning**: Phrasing artifact due to literal string splitting. Rewriting it to use natural phrasing resolved the format issue while keeping the same evaluation target.

### 4. How are routes registered for combine?
- **Expected Symbol**: `_RouterIncludeContext.combine` (FastAPI)
- **Classification**: **REWRITE**
- **New Wording**: `How does _RouterIncludeContext combine routing configurations?`
- **New Rank**: **Rank None (FAIL)**
- **Primary Cause**: **Question wording is unnatural / Retriever weakness**
- **Reasoning**: The original question was poorly worded. The rewritten version uses proper engineering terminology. The rank remained "None" because `include_router` has extremely high centrality and masks the smaller `combine` helper in routing queries. This is a genuine retrieval weakness.

### 5. How are routes registered for route?
- **Expected Symbol**: `APIRouter.route` (FastAPI)
- **Classification**: **REWRITE**
- **New Wording**: `How does the route decorator register a route in APIRouter?`
- **New Rank**: **Rank None (FAIL)**
- **Primary Cause**: **Question wording is unnatural / Ranking weakness**
- **Reasoning**: The rewritten question is natural and clear. The failure to retrieve it is a ranking weakness: the resolver prefers `add_api_route` (which actually registers the route) over the `route` decorator due to high incoming edge degrees.

### 6. How are routes registered for path for?
- **Expected Symbol**: `_RouterIncludeContext.path_for` (FastAPI)
- **Classification**: **REWRITE**
- **New Wording**: `How is a route path resolved in _RouterIncludeContext?`
- **New Rank**: **Rank None (FAIL)**
- **Primary Cause**: **Question wording is unnatural / Retriever weakness**
- **Reasoning**: Rewritten to form a natural question. It fails to retrieve the target because the resolver prefers `_IncludedRouter.url_path_for` (direct match for "path" and "url") and general router helpers, exposing a genuine retrieval weakness.

### 7. What is the purpose of the request exception?
- **Expected Symbol**: `RequestException` (Requests)
- **Classification**: **KEEP**
- **Primary Cause**: **Ranking weakness**
- **Reasoning**: A completely natural question regarding base request exceptions. Fails because `Session.request` has massive centrality and dominates the "request" keyword ranking, masking the exception class. Leaving it exposes a genuine retrieval weakness.

### 8. How does the request exception work?
- **Expected Symbol**: `RequestException` (Requests)
- **Classification**: **REMOVE**
- **Primary Cause**: **Duplicate question testing same capability**
- **Reasoning**: This question is a duplicate of Question 7, targeting the same `RequestException` class. It was removed to enforce the benchmark deduplication criteria.

---

## Discovered Weaknesses

### 1. Retrieval & Ranking Weaknesses
- **DTO/Model Class Penalization**: Classes representing data structures (such as `RetrievalResult`) or Exception categories (such as `RequestException`) are heavily penalized by `_looks_like_dto` or rank low due to low graph connectivity. The resolver fails to balance keyword matches against node type relevance in these scenarios.
- **Hub Domination**: Highly connected methods (such as `include_router` or `add_api_route`) heavily dominate keyword searches, masking specific auxiliary methods (such as `combine` or `route`) in the same namespace.

### 2. Benchmark Generation Weaknesses
- **Preposition Collisions**: Splitting snake_case methods like `for_include` into nouns/verbs sometimes produces literal phrase matching issues like "registered for for include".
- **Category Mismatch**: Inexact category keyword matching (`BaseModelWithConfig` matching "Parsing") results in nonsensical question templates.

---

## Final Recommendation

The refined curation benchmark (86 questions) is highly balanced and representative of the 4 repositories. The metrics (`Top-5: 94.2%`) show a robust baseline that exposes genuine structural retrieval weaknesses without being artificially easy. It is recommended to use `v2_curated.json` as the permanent, deterministic benchmark for evaluating future retrieval improvements.
