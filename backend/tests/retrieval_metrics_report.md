# RepoGraphAI — Retrieval Metrics Report

Generated: 2026-07-01 22:32:16

============================================================

## Overall Metrics (All Questions)

| Dataset                      | Top-1  | Top-3  | Top-5  | R@1     | R@3     | R@5     | P@1      | P@3      | P@5      | MRR   |
|------------------------------|--------|--------|--------|---------|---------|---------|----------|----------|----------|-------|
| ALL                          |   66.3% |   84.9% |   94.2% |    66.3% |    84.9% |    94.2% |     66.3% |     28.3% |     18.8% | 0.771 |


## Per-Dataset Metrics

| Dataset                      | Top-1  | Top-3  | Top-5  | R@1     | R@3     | R@5     | P@1      | P@3      | P@5      | MRR   |
|------------------------------|--------|--------|--------|---------|---------|---------|----------|----------|----------|-------|
| Internal (own codebase)      |   47.4% |   73.7% |   94.7% |    47.4% |    73.7% |    94.7% |     47.4% |     24.6% |     18.9% | 0.638 |
| FastAPI                      |   62.5% |   79.2% |   87.5% |    62.5% |    79.2% |    87.5% |     62.5% |     26.4% |     17.5% | 0.720 |
| Typer                        |   71.4% |   95.2% |  100.0% |    71.4% |    95.2% |   100.0% |     71.4% |     31.8% |     20.0% | 0.845 |
| Requests                     |   81.8% |   90.9% |   95.5% |    81.8% |    90.9% |    95.5% |     81.8% |     30.3% |     19.1% | 0.873 |


============================================================

## Mode 1 — Internal Benchmark (Per Question)

============================================================

### How is levenshtein distance represented in the graph?

**Category:** Graph Construction  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0033s

**Expected symbols:**
- `levenshtein_distance`

**Retrieved symbols (top-5):**
1. `levenshtein_distance` [score=43.00] ✓
2. `GraphBuilder.build_graph` [score=27.00]
3. `_is_graph_infrastructure` [score=26.00]
4. `generate_graph` [score=26.00]
5. `GraphService.generate_graph` [score=25.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are levenshtein distance relationships created?

**Category:** Graph Construction  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0024s

**Expected symbols:**
- `levenshtein_distance`

**Retrieved symbols (top-5):**
1. `levenshtein_distance` [score=33.00] ✓
2. `ContextBuilder.build` [score=14.00]
3. `GraphBuilder.build_graph` [score=13.00]
4. `RepositoryRetriever.build_llm_context` [score=13.00]
5. `build_context_builder` [score=13.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### What is the purpose of the llm provider?

**Category:** Graph Construction  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0023s

**Expected symbols:**
- `LLMProvider`

**Retrieved symbols (top-5):**
1. `AnthropicLLMProvider` [score=31.00]
2. `GeminiLLMProvider` [score=31.00]
3. `LLMProvider` [score=31.00] ✓
4. `RetryingLLMProvider` [score=31.00]
5. `CallableLLMProvider` [score=30.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✓ | ✓ | 0.00 | 1.00 | 1.00 | 0.00 | 0.33 | 0.20 | 0.333 |

First hit rank: **3**

------------------------------------------------------------

### What is the purpose of the code parser?

**Category:** Parsing  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0020s

**Expected symbols:**
- `CodeParser`

**Retrieved symbols (top-5):**
1. `CodeParser.extract_function` [score=46.00]
2. `CodeParser._extract_class` [score=43.00]
3. `CodeParser.parse_file` [score=42.00]
4. `CodeParser` [score=41.00] ✓
5. `CodeParser._extract_decorator` [score=41.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✗ | ✓ | 0.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.20 | 0.250 |

First hit rank: **4**

------------------------------------------------------------

### How is code parsed by the CodeParser?

**Category:** Parsing  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0023s

**Expected symbols:**
- `CodeParser`

**Retrieved symbols (top-5):**
1. `CodeParser` [score=51.00] ✓
2. `CodeParser.extract_function` [score=48.00]
3. `CodeParser._extract_class` [score=45.00]
4. `CodeParser.parse_file` [score=44.00]
5. `CodeParser._extract_decorator` [score=43.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is verb noun extraction implemented?

**Category:** Parsing  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0015s

**Expected symbols:**
- `extract_verb_noun`

**Retrieved symbols (top-5):**
1. `extract_verb_noun` [score=39.00] ✓
2. `CodeParser.extract_function` [score=13.00]
3. `QueryResolver.extract_keywords` [score=12.00]
4. `extract_query_keywords` [score=11.00]
5. `CodeParser._extract_class` [score=10.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are verb nouns extracted?

**Category:** Parsing  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0030s

**Expected symbols:**
- `extract_verb_noun`

**Retrieved symbols (top-5):**
1. `extract_verb_noun` [score=61.00] ✓
2. `CodeParser.extract_function` [score=27.00]
3. `QueryResolver.extract_keywords` [score=26.00]
4. `extract_query_keywords` [score=25.00]
5. `CodeParser._extract_class` [score=24.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### What is the purpose of the repository retriever?

**Category:** Retrieval  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0038s

**Expected symbols:**
- `RepositoryRetriever`

**Retrieved symbols (top-5):**
1. `RepositoryRetriever` [score=53.00] ✓
2. `RepositoryRetriever.search_by_label` [score=47.00]
3. `RepositoryRetriever.get_node_context` [score=42.00]
4. `RepositoryRetriever.get_callable_context` [score=39.00]
5. `RepositoryRetriever.get_class_context` [score=39.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is retrieval performed using RepositoryRetriever?

**Category:** Retrieval  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0066s

**Expected symbols:**
- `RepositoryRetriever`

**Retrieved symbols (top-5):**
1. `RepositoryRetriever` [score=63.00] ✓
2. `RepositoryRetriever.search_by_label` [score=49.00]
3. `RepositoryRetriever.get_node_context` [score=44.00]
4. `RepositoryRetriever.get_callable_context` [score=41.00]
5. `RepositoryRetriever.get_class_context` [score=41.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### What is the purpose of the query resolver?

**Category:** Retrieval  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0054s

**Expected symbols:**
- `QueryResolver`

**Retrieved symbols (top-5):**
1. `QueryResolver.resolve_query` [score=52.00]
2. `QueryResolver` [score=45.00] ✓
3. `QueryResolver.resolve_to_node_ids` [score=40.00]
4. `QueryResolver.get_ranking_diagnostics` [score=34.00]
5. `QueryResolver.rank_candidates` [score=34.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✓ | ✓ | 0.00 | 1.00 | 1.00 | 0.00 | 0.33 | 0.20 | 0.500 |

First hit rank: **2**

------------------------------------------------------------

### How is retrieval performed using QueryResolver?

**Category:** Retrieval  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0060s

**Expected symbols:**
- `QueryResolver`

**Retrieved symbols (top-5):**
1. `QueryResolver` [score=49.00] ✓
2. `QueryResolver.resolve_query` [score=48.00]
3. `QueryResolver.resolve_to_node_ids` [score=36.00]
4. `QueryResolver.get_ranking_diagnostics` [score=34.00]
5. `QueryResolver.rank_candidates` [score=34.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### What is the purpose of the retrieval result?

**Category:** Retrieval  
**Repository:** internal  
**Result:** FAIL  
**Retrieval time:** 0.0023s

**Expected symbols:**
- `RetrievalResult`

**Retrieved symbols (top-5):**
1. `ContextBuilder._collect_retrieval_results` [score=38.00]
2. `RetrievalResult.edges_of_type` [score=28.00]
3. `RetrievalResult.neighbour_ids` [score=28.00]
4. `aggregate_results` [score=27.00]
5. `_format_result_line` [score=25.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✗ | ✗ | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 |

First hit rank: **—**

------------------------------------------------------------

### How is retrieval performed using RetrievalResult?

**Category:** Retrieval  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0024s

**Expected symbols:**
- `RetrievalResult`

**Retrieved symbols (top-5):**
1. `RetrievalResult.edges_of_type` [score=28.00]
2. `RetrievalResult.neighbour_ids` [score=28.00]
3. `ContextBuilder._collect_retrieval_results` [score=27.00]
4. `RepositoryRetriever.search_by_label` [score=24.00]
5. `RetrievalResult` [score=24.00] ✓

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✗ | ✓ | 0.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.20 | 0.200 |

First hit rank: **5**

------------------------------------------------------------

### What is the purpose of the query resolution result?

**Category:** Retrieval  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0042s

**Expected symbols:**
- `QueryResolutionResult`

**Retrieved symbols (top-5):**
1. `QueryResolver.resolve_query` [score=37.00]
2. `QueryResolutionResult` [score=36.00] ✓
3. `QueryResolutionResult.top_node_ids` [score=32.00]
4. `QueryResolver.resolve_to_node_ids` [score=28.00]
5. `aggregate_results` [score=27.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✓ | ✓ | 0.00 | 1.00 | 1.00 | 0.00 | 0.33 | 0.20 | 0.500 |

First hit rank: **2**

------------------------------------------------------------

### How is retrieval performed using QueryResolutionResult?

**Category:** Retrieval  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0056s

**Expected symbols:**
- `QueryResolutionResult`

**Retrieved symbols (top-5):**
1. `QueryResolver.resolve_query` [score=37.00]
2. `QueryResolutionResult` [score=34.00] ✓
3. `QueryResolutionResult.top_node_ids` [score=30.00]
4. `QueryResolver.resolve_to_node_ids` [score=28.00]
5. `ContextBuilder._collect_retrieval_results` [score=27.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✓ | ✓ | 0.00 | 1.00 | 1.00 | 0.00 | 0.33 | 0.20 | 0.500 |

First hit rank: **2**

------------------------------------------------------------

### What is the purpose of the query match?

**Category:** Retrieval  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0023s

**Expected symbols:**
- `QueryMatch`

**Retrieved symbols (top-5):**
1. `get_matching_nodes_count` [score=30.00]
2. `QueryResolver.resolve_query` [score=28.00]
3. `extract_query_keywords` [score=25.00]
4. `QueryMatch` [score=23.00] ✓
5. `RepositoryRetriever.search_by_label` [score=22.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✗ | ✓ | 0.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.20 | 0.250 |

First hit rank: **4**

------------------------------------------------------------

### How is retrieval performed using QueryMatch?

**Category:** Retrieval  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0027s

**Expected symbols:**
- `QueryMatch`

**Retrieved symbols (top-5):**
1. `QueryResolver.resolve_query` [score=28.00]
2. `ContextBuilder._collect_retrieval_results` [score=27.00]
3. `QueryMatch` [score=27.00] ✓
4. `extract_query_keywords` [score=25.00]
5. `RepositoryRetriever.search_by_label` [score=24.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✓ | ✓ | 0.00 | 1.00 | 1.00 | 0.00 | 0.33 | 0.20 | 0.333 |

First hit rank: **3**

------------------------------------------------------------

### How does the query match work?

**Category:** Retrieval  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0020s

**Expected symbols:**
- `QueryMatch`

**Retrieved symbols (top-5):**
1. `get_matching_nodes_count` [score=30.00]
2. `QueryResolver.resolve_query` [score=28.00]
3. `extract_query_keywords` [score=25.00]
4. `QueryMatch` [score=23.00] ✓
5. `RepositoryRetriever.search_by_label` [score=22.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✗ | ✓ | 0.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.20 | 0.250 |

First hit rank: **4**

------------------------------------------------------------

### How is rank candidates retrieved?

**Category:** Retrieval  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0028s

**Expected symbols:**
- `QueryResolver.rank_candidates`

**Retrieved symbols (top-5):**
1. `QueryResolver.rank_candidates` [score=59.00] ✓
2. `RepositoryRetriever.search_by_label` [score=26.00]
3. `compute_pagerank` [score=22.00]
4. `QueryResolver.get_ranking_diagnostics` [score=21.00]
5. `RepositoryRetriever.build_llm_context` [score=21.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------


============================================================

## Mode 2 — Cross-Repository Benchmark (Per Question)

============================================================


### Repository: FastAPI

### What is the purpose of the html link attribute?

**Category:** Graph Construction  
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0027s

**Expected symbols:**
- `HTMLLinkAttribute`

**Retrieved symbols (top-5):**
1. `HTMLLinkAttribute` [score=29.00] ✓
2. `extract_html_links` [score=27.00]
3. `_construct_html_link` [score=26.00]
4. `replace_html_links` [score=26.00]
5. `HtmlLinkInfo` [score=22.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How does the html link attribute work?

**Category:** Graph Construction  
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0021s

**Expected symbols:**
- `HTMLLinkAttribute`

**Retrieved symbols (top-5):**
1. `HTMLLinkAttribute` [score=29.00] ✓
2. `extract_html_links` [score=27.00]
3. `_construct_html_link` [score=26.00]
4. `replace_html_links` [score=26.00]
5. `HtmlLinkInfo` [score=22.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is remove header permalinks represented in the graph?

**Category:** Graph Construction  
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0095s

**Expected symbols:**
- `remove_header_permalinks`

**Retrieved symbols (top-5):**
1. `remove_header_permalinks` [score=63.00] ✓
2. `extract_header_permalinks` [score=51.00]
3. `replace_header_permalinks` [score=50.00]
4. `Header` [score=39.00]
5. `HeaderPermalinkInfo` [score=38.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### What is the purpose of the base model with config?

**Category:** Parsing  
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0033s

**Expected symbols:**
- `BaseModelWithConfig`

**Retrieved symbols (top-5):**
1. `BaseModelWithConfig` [score=41.00] ✓
2. `is_union_of_base_models` [score=36.00]
3. `get_en_config` [score=28.00]
4. `create_model_field` [score=27.00]
5. `get_cached_model_fields` [score=27.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How does the base model with config work?

**Category:** Parsing  
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0028s

**Expected symbols:**
- `BaseModelWithConfig`

**Retrieved symbols (top-5):**
1. `BaseModelWithConfig` [score=41.00] ✓
2. `is_union_of_base_models` [score=36.00]
3. `get_en_config` [score=28.00]
4. `create_model_field` [score=27.00]
5. `get_cached_model_fields` [score=27.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is the parsing of lenient issubclass handled?

**Category:** Parsing  
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0065s

**Expected symbols:**
- `lenient_issubclass`

**Retrieved symbols (top-5):**
1. `lenient_issubclass` [score=55.00] ✓
2. `APIRoute.handle` [score=29.00]
3. `get_request_handler` [score=29.00]
4. `APIRoute.get_route_handler` [score=27.00]
5. `APIRouter.handle` [score=27.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is a dependant retrieved?

**Category:** Utilities  
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0065s

**Expected symbols:**
- `get_dependant`

**Retrieved symbols (top-5):**
1. `get_dependant` [score=39.00] ✓
2. `get_flat_dependant` [score=36.00]
3. `get_parameterless_sub_dependant` [score=35.00]
4. `Dependant.is_async_gen_callable` [score=24.00]
5. `Dependant.is_coroutine_callable` [score=24.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are dependants fetched?

**Category:** Utilities  
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0038s

**Expected symbols:**
- `get_dependant`

**Retrieved symbols (top-5):**
1. `get_dependant` [score=39.00] ✓
2. `get_flat_dependant` [score=36.00]
3. `get_parameterless_sub_dependant` [score=35.00]
4. `Dependant.is_async_gen_callable` [score=24.00]
5. `Dependant.is_coroutine_callable` [score=24.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are dependants collected?

**Category:** Utilities  
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0026s

**Expected symbols:**
- `get_dependant`

**Retrieved symbols (top-5):**
1. `get_dependant` [score=20.00] ✓
2. `Dependant` [score=18.00]
3. `get_flat_dependant` [score=17.00]
4. `get_parameterless_sub_dependant` [score=16.00]
5. `Dependant.is_async_gen_callable` [score=9.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is a authorization scheme param retrieved?

**Category:** Utilities  
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0054s

**Expected symbols:**
- `get_authorization_scheme_param`

**Retrieved symbols (top-5):**
1. `get_authorization_scheme_param` [score=68.00] ✓
2. `OAuthFlowAuthorizationCode` [score=36.00]
3. `HTTPAuthorizationCredentials` [score=34.00]
4. `OAuth2AuthorizationCodeBearer` [score=34.00]
5. `get_flat_params` [score=33.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is request response implemented?

**Category:** HTTP  
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0074s

**Expected symbols:**
- `request_response`

**Retrieved symbols (top-5):**
1. `request_response` [score=48.00] ✓
2. `get_graphql_response` [score=32.00]
3. `get_request_handler` [score=32.00]
4. `request_body_to_args` [score=32.00]
5. `request_params_to_args` [score=32.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is request response handled?

**Category:** HTTP  
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0076s

**Expected symbols:**
- `request_response`

**Retrieved symbols (top-5):**
1. `request_response` [score=48.00] ✓
2. `get_request_handler` [score=46.00]
3. `request_validation_exception_handler` [score=40.00]
4. `websocket_request_validation_exception_handler` [score=40.00]
5. `http_exception_handler` [score=36.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are routes registered for effective candidates?

**Category:** Routing  
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0101s

**Expected symbols:**
- `_IncludedRouter.effective_candidates`

**Retrieved symbols (top-5):**
1. `_iter_included_route_candidates` [score=61.00]
2. `_IncludedRouter.effective_candidates` [score=57.00] ✓
3. `_IncludedRouter.effective_route_contexts` [score=52.00]
4. `APIRouter.add_api_route` [score=50.00]
5. `_get_scope_effective_route_context` [score=50.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✓ | ✓ | 0.00 | 1.00 | 1.00 | 0.00 | 0.33 | 0.20 | 0.500 |

First hit rank: **2**

------------------------------------------------------------

### How is the router inclusion context constructed for_include?

**Category:** Routing  
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0096s

**Expected symbols:**
- `_RouterIncludeContext.for_include`

**Retrieved symbols (top-5):**
1. `APIRouter.include_router` [score=65.00]
2. `FastAPI.include_router` [score=63.00]
3. `_RouterIncludeContext.for_include` [score=57.00] ✓
4. `_IncludedRouter.effective_route_contexts` [score=51.00]
5. `_IncludedRouter._build_effective_context` [score=50.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✓ | ✓ | 0.00 | 1.00 | 1.00 | 0.00 | 0.33 | 0.20 | 0.333 |

First hit rank: **3**

------------------------------------------------------------

### How does _RouterIncludeContext combine routing configurations?

**Category:** Routing  
**Repository:** FastAPI  
**Result:** FAIL  
**Retrieval time:** 0.0094s

**Expected symbols:**
- `_RouterIncludeContext.combine`

**Retrieved symbols (top-5):**
1. `APIRouter.include_router` [score=62.00]
2. `FastAPI.include_router` [score=60.00]
3. `_RouterIncludeContext` [score=60.00]
4. `_RouterIncludeContext.for_include` [score=51.00]
5. `_get_scope_effective_route_context` [score=50.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✗ | ✗ | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 |

First hit rank: **—**

------------------------------------------------------------

### How are routes registered for effective route contexts?

**Category:** Routing  
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0152s

**Expected symbols:**
- `_IncludedRouter.effective_route_contexts`

**Retrieved symbols (top-5):**
1. `_IncludedRouter.effective_route_contexts` [score=70.00] ✓
2. `_get_scope_effective_route_context` [score=62.00]
3. `_IncludedRouter._build_effective_context` [score=57.00]
4. `APIRouter.add_api_route` [score=55.00]
5. `APIRoute.get_route_handler` [score=54.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is a websocket route registered?

**Category:** Routing  
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0104s

**Expected symbols:**
- `APIRouter.add_websocket_route`

**Retrieved symbols (top-5):**
1. `APIRouter.add_api_websocket_route` [score=57.00]
2. `APIRouter.add_websocket_route` [score=57.00] ✓
3. `FastAPI.add_api_websocket_route` [score=56.00]
4. `APIRouter.websocket_route` [score=50.00]
5. `FastAPI.websocket_route` [score=50.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✓ | ✓ | 0.00 | 1.00 | 1.00 | 0.00 | 0.33 | 0.20 | 0.500 |

First hit rank: **2**

------------------------------------------------------------

### How are websocket routes registered?

**Category:** Routing  
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0104s

**Expected symbols:**
- `APIRouter.add_websocket_route`

**Retrieved symbols (top-5):**
1. `APIRouter.add_api_websocket_route` [score=63.00]
2. `APIRouter.add_websocket_route` [score=63.00] ✓
3. `FastAPI.add_api_websocket_route` [score=62.00]
4. `APIRouter.websocket_route` [score=56.00]
5. `FastAPI.websocket_route` [score=56.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✓ | ✓ | 0.00 | 1.00 | 1.00 | 0.00 | 0.33 | 0.20 | 0.500 |

First hit rank: **2**

------------------------------------------------------------

### How is a route registered?

**Category:** Routing  
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0111s

**Expected symbols:**
- `APIRouter.add_route`

**Retrieved symbols (top-5):**
1. `APIRouter.add_api_route` [score=36.00]
2. `APIRoute.get_route_handler` [score=35.00]
3. `APIRouter.add_api_websocket_route` [score=35.00]
4. `APIRouter.add_event_handler` [score=35.00]
5. `APIRouter.add_route` [score=35.00] ✓

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✗ | ✓ | 0.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.20 | 0.200 |

First hit rank: **5**

------------------------------------------------------------

### How are routes registered?

**Category:** Routing  
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0119s

**Expected symbols:**
- `APIRouter.add_route`

**Retrieved symbols (top-5):**
1. `APIRouter.add_api_route` [score=50.00]
2. `APIRoute.get_route_handler` [score=49.00]
3. `APIRouter.add_api_websocket_route` [score=49.00]
4. `APIRouter.add_route` [score=49.00] ✓
5. `APIRouter.add_websocket_route` [score=49.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✗ | ✓ | 0.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.20 | 0.250 |

First hit rank: **4**

------------------------------------------------------------

### How does the route decorator register a route in APIRouter?

**Category:** Routing  
**Repository:** FastAPI  
**Result:** FAIL  
**Retrieval time:** 0.0109s

**Expected symbols:**
- `APIRouter.route`

**Retrieved symbols (top-5):**
1. `APIRouter.add_api_route` [score=62.00]
2. `APIRouter.add_api_websocket_route` [score=61.00]
3. `FastAPI.add_api_route` [score=57.00]
4. `FastAPI.add_api_websocket_route` [score=56.00]
5. `APIRouter.api_route` [score=55.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✗ | ✗ | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 |

First hit rank: **—**

------------------------------------------------------------

### How is a route path resolved in _RouterIncludeContext?

**Category:** Routing  
**Repository:** FastAPI  
**Result:** FAIL  
**Retrieval time:** 0.0091s

**Expected symbols:**
- `_RouterIncludeContext.path_for`

**Retrieved symbols (top-5):**
1. `APIRouter.include_router` [score=56.00]
2. `FastAPI.include_router` [score=54.00]
3. `_RouterIncludeContext` [score=48.00]
4. `_RouterIncludeContext.for_include` [score=47.00]
5. `_IncludedRouter.url_path_for` [score=44.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✗ | ✗ | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 |

First hit rank: **—**

------------------------------------------------------------

### How is a event handler registered?

**Category:** Routing  
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0076s

**Expected symbols:**
- `APIRouter.add_event_handler`

**Retrieved symbols (top-5):**
1. `APIRouter.add_event_handler` [score=57.00] ✓
2. `APIRoute.get_route_handler` [score=45.00]
3. `get_request_handler` [score=43.00]
4. `http_exception_handler` [score=41.00]
5. `request_validation_exception_handler` [score=40.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are event handlers registered?

**Category:** Routing  
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0096s

**Expected symbols:**
- `APIRouter.add_event_handler`

**Retrieved symbols (top-5):**
1. `APIRouter.add_event_handler` [score=48.00] ✓
2. `APIRoute.handle` [score=33.00]
3. `APIRouter.on_event` [score=33.00]
4. `FastAPI.on_event` [score=33.00]
5. `APIRoute.get_route_handler` [score=31.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------


### Repository: Typer

### What is the purpose of the context?

**Category:** Graph Construction  
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0038s

**Expected symbols:**
- `Context`

**Retrieved symbols (top-5):**
1. `Command.make_context` [score=18.00]
2. `Context` [score=18.00] ✓
3. `_build_prompt` [score=17.00]
4. `get_current_context` [score=17.00]
5. `pop_context` [score=14.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✓ | ✓ | 0.00 | 1.00 | 1.00 | 0.00 | 0.33 | 0.20 | 0.500 |

First hit rank: **2**

------------------------------------------------------------

### How is default represented in the graph?

**Category:** Graph Construction  
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0055s

**Expected symbols:**
- `Default`

**Retrieved symbols (top-5):**
1. `Default` [score=28.00] ✓
2. `Parameter.get_default` [score=28.00]
3. `resolve_color_default` [score=27.00]
4. `Context.lookup_default` [score=24.00]
5. `make_default_short_help` [score=24.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are default relationships created?

**Category:** Graph Construction  
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0044s

**Expected symbols:**
- `Default`

**Retrieved symbols (top-5):**
1. `Default` [score=18.00] ✓
2. `Parameter.get_default` [score=18.00]
3. `resolve_color_default` [score=17.00]
4. `Context.lookup_default` [score=14.00]
5. `make_default_short_help` [score=14.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is version parsing implemented?

**Category:** Parsing  
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0062s

**Expected symbols:**
- `parse_version`

**Retrieved symbols (top-5):**
1. `parse_version` [score=48.00] ✓
2. `_ParsingState` [score=32.00]
3. `current_version` [score=32.00]
4. `get_current_version` [score=32.00]
5. `update_version_file` [score=31.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are versions parsed?

**Category:** Parsing  
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0044s

**Expected symbols:**
- `parse_version`

**Retrieved symbols (top-5):**
1. `parse_version` [score=48.00] ✓
2. `generate_docs_src_versions_for_file` [score=42.00]
3. `generate_docs_src_versions` [score=41.00]
4. `current_version` [score=32.00]
5. `get_current_version` [score=32.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is a params from function retrieved?

**Category:** Utilities  
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0076s

**Expected symbols:**
- `get_params_from_function`

**Retrieved symbols (top-5):**
1. `get_params_convertors_ctx_param_name_from_function` [score=65.00]
2. `get_params_from_function` [score=65.00] ✓
3. `Command.get_params` [score=47.00]
4. `iter_params_for_processing` [score=40.00]
5. `_install_completion_no_auto_placeholder_function` [score=36.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✓ | ✓ | 0.00 | 1.00 | 1.00 | 0.00 | 0.33 | 0.20 | 0.500 |

First hit rank: **2**

------------------------------------------------------------

### How are params from functions fetched?

**Category:** Utilities  
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0064s

**Expected symbols:**
- `get_params_from_function`

**Retrieved symbols (top-5):**
1. `get_params_convertors_ctx_param_name_from_function` [score=56.00]
2. `get_params_from_function` [score=56.00] ✓
3. `Command.get_params` [score=47.00]
4. `iter_params_for_processing` [score=40.00]
5. `get_click_param` [score=36.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✓ | ✓ | 0.00 | 1.00 | 1.00 | 0.00 | 0.33 | 0.20 | 0.500 |

First hit rank: **2**

------------------------------------------------------------

### How are params from functions collected?

**Category:** Utilities  
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0040s

**Expected symbols:**
- `get_params_from_function`

**Retrieved symbols (top-5):**
1. `get_params_convertors_ctx_param_name_from_function` [score=37.00]
2. `get_params_from_function` [score=37.00] ✓
3. `Command.get_params` [score=28.00]
4. `FuncParamType` [score=25.00]
5. `iter_params_for_processing` [score=25.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✓ | ✓ | 0.00 | 1.00 | 1.00 | 0.00 | 0.33 | 0.20 | 0.500 |

First hit rank: **2**

------------------------------------------------------------

### How is rich format help implemented?

**Category:** Utilities  
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0042s

**Expected symbols:**
- `rich_format_help`

**Retrieved symbols (top-5):**
1. `rich_format_help` [score=62.00] ✓
2. `Command.format_help` [score=53.00]
3. `TyperCommand.format_help` [score=53.00]
4. `TyperGroup.format_help` [score=52.00]
5. `Command.format_help_text` [score=49.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### What is the purpose of the param type?

**Category:** CLI  
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0060s

**Expected symbols:**
- `ParamType`

**Retrieved symbols (top-5):**
1. `_param_type_to_user_string` [score=26.00]
2. `BoolParamType` [score=25.00]
3. `FuncParamType` [score=25.00]
4. `ParamType` [score=25.00] ✓
5. `CompositeParamType` [score=24.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✗ | ✓ | 0.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.20 | 0.250 |

First hit rank: **4**

------------------------------------------------------------

### What is the purpose of the parameter?

**Category:** CLI  
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0027s

**Expected symbols:**
- `Parameter`

**Retrieved symbols (top-5):**
1. `Parameter` [score=39.00] ✓
2. `BadParameter` [score=35.00]
3. `MissingParameter` [score=35.00]
4. `Context.get_parameter_source` [score=34.00]
5. `Context.set_parameter_source` [score=34.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### What is the purpose of the usage error?

**Category:** CLI  
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0024s

**Expected symbols:**
- `UsageError`

**Retrieved symbols (top-5):**
1. `augment_usage_errors` [score=27.00]
2. `UsageError` [score=25.00] ✓
3. `Command.get_usage` [score=19.00]
4. `Context.get_usage` [score=17.00]
5. `UsageError.show` [score=17.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✓ | ✓ | 0.00 | 1.00 | 1.00 | 0.00 | 0.33 | 0.20 | 0.500 |

First hit rank: **2**

------------------------------------------------------------

### What is the purpose of the completion item?

**Category:** CLI  
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0032s

**Expected symbols:**
- `CompletionItem`

**Retrieved symbols (top-5):**
1. `CompletionItem` [score=31.00] ✓
2. `ShellComplete.format_completion` [score=28.00]
3. `ShellComplete.get_completion_args` [score=28.00]
4. `get_completion_script` [score=28.00]
5. `get_param_completion` [score=28.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How does the completion item work?

**Category:** CLI  
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0030s

**Expected symbols:**
- `CompletionItem`

**Retrieved symbols (top-5):**
1. `CompletionItem` [score=31.00] ✓
2. `ShellComplete.format_completion` [score=28.00]
3. `ShellComplete.get_completion_args` [score=28.00]
4. `get_completion_script` [score=28.00]
5. `get_param_completion` [score=28.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How does color default resolution work?

**Category:** CLI  
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0045s

**Expected symbols:**
- `resolve_color_default`

**Retrieved symbols (top-5):**
1. `resolve_color_default` [score=40.00] ✓
2. `Default` [score=18.00]
3. `Parameter.get_default` [score=18.00]
4. `Context.lookup_default` [score=14.00]
5. `make_default_short_help` [score=14.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are color defaults resolved?

**Category:** CLI  
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0031s

**Expected symbols:**
- `resolve_color_default`

**Retrieved symbols (top-5):**
1. `resolve_color_default` [score=40.00] ✓
2. `solve_typer_info_defaults` [score=27.00]
3. `MixedAnnotatedAndDefaultStyleError` [score=24.00]
4. `Default` [score=18.00]
5. `Parameter.get_default` [score=18.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is a current context retrieved?

**Category:** CLI  
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0053s

**Expected symbols:**
- `get_current_context`

**Retrieved symbols (top-5):**
1. `get_current_context` [score=53.00] ✓
2. `get_current_version` [score=36.00]
3. `Context.lookup_default` [score=35.00]
4. `Context.find_object` [score=34.00]
5. `Context.find_root` [score=34.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are current contexts fetched?

**Category:** CLI  
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0066s

**Expected symbols:**
- `get_current_context`

**Retrieved symbols (top-5):**
1. `get_current_context` [score=53.00] ✓
2. `get_current_version` [score=36.00]
3. `Command.make_context` [score=33.00]
4. `current_version` [score=32.00]
5. `_resolve_context` [score=29.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are current contexts collected?

**Category:** CLI  
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0046s

**Expected symbols:**
- `get_current_context`

**Retrieved symbols (top-5):**
1. `get_current_context` [score=34.00] ✓
2. `Command.make_context` [score=18.00]
3. `Context` [score=18.00]
4. `_build_prompt` [score=17.00]
5. `current_version` [score=17.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is a click param retrieved?

**Category:** CLI  
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0071s

**Expected symbols:**
- `get_click_param`

**Retrieved symbols (top-5):**
1. `get_click_param` [score=53.00] ✓
2. `get_click_type` [score=36.00]
3. `get_docs_for_click` [score=36.00]
4. `get_param_callback` [score=36.00]
5. `get_param_completion` [score=36.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are click params fetched?

**Category:** CLI  
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0061s

**Expected symbols:**
- `get_click_param`

**Retrieved symbols (top-5):**
1. `get_click_param` [score=53.00] ✓
2. `get_params_convertors_ctx_param_name_from_function` [score=50.00]
3. `Command.get_params` [score=47.00]
4. `get_params_from_function` [score=47.00]
5. `iter_params_for_processing` [score=40.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------


### Repository: Requests

### What is the purpose of the request exception?

**Category:** Graph Construction  
**Repository:** Requests  
**Result:** FAIL  
**Retrieval time:** 0.0055s

**Expected symbols:**
- `RequestException`

**Retrieved symbols (top-5):**
1. `Session.request` [score=33.00]
2. `request` [score=33.00]
3. `HTTPAdapter.request_url` [score=32.00]
4. `Session.prepare_request` [score=32.00]
5. `HTTPAdapter.send` [score=27.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✗ | ✗ | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 |

First hit rank: **—**

------------------------------------------------------------

### What is the purpose of the session?

**Category:** Graph Construction  
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0042s

**Expected symbols:**
- `Session`

**Retrieved symbols (top-5):**
1. `Session.send` [score=35.00]
2. `SessionRedirectMixin.send` [score=32.00]
3. `HTTPAdapter.build_connection_pool_key_attributes` [score=30.00]
4. `session` [score=30.00]
5. `Session` [score=28.00] ✓

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✗ | ✓ | 0.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.20 | 0.200 |

First hit rank: **5**

------------------------------------------------------------

### How is cookies to jar extraction implemented?

**Category:** Parsing  
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0028s

**Expected symbols:**
- `extract_cookies_to_jar`

**Retrieved symbols (top-5):**
1. `extract_cookies_to_jar` [score=46.00] ✓
2. `merge_cookies` [score=27.00]
3. `PreparedRequest.prepare_cookies` [score=26.00]
4. `RequestsCookieJar` [score=25.00]
5. `cookiejar_from_dict` [score=25.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are cookies to jars extracted?

**Category:** Parsing  
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0032s

**Expected symbols:**
- `extract_cookies_to_jar`

**Retrieved symbols (top-5):**
1. `extract_cookies_to_jar` [score=68.00] ✓
2. `merge_cookies` [score=42.00]
3. `PreparedRequest.prepare_cookies` [score=41.00]
4. `cookiejar_from_dict` [score=40.00]
5. `add_dict_to_cookiejar` [score=37.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is to native string implemented?

**Category:** Utilities  
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0016s

**Expected symbols:**
- `to_native_string`

**Retrieved symbols (top-5):**
1. `to_native_string` [score=40.00] ✓
2. `_basic_auth_str` [score=13.00]
3. `StreamConsumedError` [score=12.00]
4. `SessionRedirectMixin.should_strip_auth` [score=11.00]
5. `stream_decode_response_unicode` [score=11.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is to native string handled?

**Category:** Utilities  
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0022s

**Expected symbols:**
- `to_native_string`

**Retrieved symbols (top-5):**
1. `to_native_string` [score=40.00] ✓
2. `HTTPDigestAuth.handle_401` [score=14.00]
3. `_basic_auth_str` [score=13.00]
4. `StreamConsumedError` [score=12.00]
5. `SessionRedirectMixin.should_strip_auth` [score=11.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is a auth from url retrieved?

**Category:** Utilities  
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0049s

**Expected symbols:**
- `get_auth_from_url`

**Retrieved symbols (top-5):**
1. `get_auth_from_url` [score=53.00] ✓
2. `urldefragauth` [score=37.00]
3. `MockRequest.get_full_url` [score=34.00]
4. `PreparedRequest.prepare_url` [score=32.00]
5. `HTTPAdapter.request_url` [score=30.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are auth from urls fetched?

**Category:** Utilities  
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0029s

**Expected symbols:**
- `get_auth_from_url`

**Retrieved symbols (top-5):**
1. `get_auth_from_url` [score=53.00] ✓
2. `urldefragauth` [score=37.00]
3. `MockRequest.get_full_url` [score=34.00]
4. `PreparedRequest.prepare_url` [score=32.00]
5. `HTTPAdapter.request_url` [score=30.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### What is the purpose of the response?

**Category:** HTTP  
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0020s

**Expected symbols:**
- `Response`

**Retrieved symbols (top-5):**
1. `Response` [score=18.00] ✓
2. `HTTPAdapter.build_response` [score=17.00]
3. `MockResponse` [score=14.00]
4. `get_unicode_from_response` [score=14.00]
5. `stream_decode_response_unicode` [score=14.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### What is the purpose of the http adapter?

**Category:** HTTP  
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0040s

**Expected symbols:**
- `HTTPAdapter`

**Retrieved symbols (top-5):**
1. `HTTPAdapter` [score=31.00] ✓
2. `HTTPAdapter.send` [score=29.00]
3. `Session.get_adapter` [score=29.00]
4. `HTTPAdapter.get_connection` [score=28.00]
5. `HTTPAdapter.get_connection_with_tls_context` [score=28.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### What is the purpose of the http basic auth?

**Category:** HTTP  
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0044s

**Expected symbols:**
- `HTTPBasicAuth`

**Retrieved symbols (top-5):**
1. `_basic_auth_str` [score=46.00]
2. `HTTPBasicAuth` [score=45.00] ✓
3. `HTTPDigestAuth` [score=39.00]
4. `HTTPProxyAuth` [score=37.00]
5. `HTTPAdapter.send` [score=35.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✓ | ✓ | 0.00 | 1.00 | 1.00 | 0.00 | 0.33 | 0.20 | 0.500 |

First hit rank: **2**

------------------------------------------------------------

### How does the http basic auth work?

**Category:** HTTP  
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0044s

**Expected symbols:**
- `HTTPBasicAuth`

**Retrieved symbols (top-5):**
1. `_basic_auth_str` [score=46.00]
2. `HTTPBasicAuth` [score=45.00] ✓
3. `HTTPDigestAuth` [score=39.00]
4. `HTTPProxyAuth` [score=37.00]
5. `HTTPAdapter.send` [score=35.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✓ | ✓ | 0.00 | 1.00 | 1.00 | 0.00 | 0.33 | 0.20 | 0.500 |

First hit rank: **2**

------------------------------------------------------------

### What is the purpose of the http digest auth?

**Category:** HTTP  
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0041s

**Expected symbols:**
- `HTTPDigestAuth`

**Retrieved symbols (top-5):**
1. `HTTPDigestAuth` [score=45.00] ✓
2. `HTTPBasicAuth` [score=39.00]
3. `HTTPDigestAuth.build_digest_header` [score=38.00]
4. `HTTPProxyAuth` [score=37.00]
5. `HTTPAdapter.send` [score=35.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### What is the purpose of the mock response?

**Category:** HTTP  
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0024s

**Expected symbols:**
- `MockResponse`

**Retrieved symbols (top-5):**
1. `MockResponse` [score=25.00] ✓
2. `Response` [score=18.00]
3. `HTTPAdapter.build_response` [score=17.00]
4. `MockRequest` [score=14.00]
5. `MockResponse.getheaders` [score=14.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is handle 401 implemented?

**Category:** HTTP  
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0018s

**Expected symbols:**
- `HTTPDigestAuth.handle_401`

**Retrieved symbols (top-5):**
1. `HTTPDigestAuth.handle_401` [score=34.00] ✓
2. `HTTPDigestAuth.handle_redirect` [score=13.00]
3. `dispatch_hook` [score=11.00]
4. `_implementation` [score=10.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is handle 401 handled?

**Category:** HTTP  
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0018s

**Expected symbols:**
- `HTTPDigestAuth.handle_401`

**Retrieved symbols (top-5):**
1. `HTTPDigestAuth.handle_401` [score=40.00] ✓
2. `HTTPDigestAuth.handle_redirect` [score=24.00]
3. `dispatch_hook` [score=11.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is iter content implemented?

**Category:** HTTP  
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0015s

**Expected symbols:**
- `Response.iter_content`

**Retrieved symbols (top-5):**
1. `Response.iter_content` [score=34.00] ✓
2. `Response.content` [score=16.00]
3. `PreparedRequest.prepare_content_length` [score=15.00]
4. `Response.iter_lines` [score=15.00]
5. `iter_slices` [score=15.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is iter content handled?

**Category:** HTTP  
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0030s

**Expected symbols:**
- `Response.iter_content`

**Retrieved symbols (top-5):**
1. `Response.iter_content` [score=34.00] ✓
2. `Response.content` [score=16.00]
3. `PreparedRequest.prepare_content_length` [score=15.00]
4. `Response.iter_lines` [score=15.00]
5. `iter_slices` [score=15.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is merge environment settings implemented?

**Category:** Configuration  
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0019s

**Expected symbols:**
- `Session.merge_environment_settings`

**Retrieved symbols (top-5):**
1. `Session.merge_environment_settings` [score=59.00] ✓
2. `merge_setting` [score=44.00]
3. `merge_cookies` [score=26.00]
4. `merge_hooks` [score=26.00]
5. `_implementation` [score=20.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is merge environment settings handled?

**Category:** Configuration  
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0024s

**Expected symbols:**
- `Session.merge_environment_settings`

**Retrieved symbols (top-5):**
1. `Session.merge_environment_settings` [score=59.00] ✓
2. `merge_setting` [score=44.00]
3. `merge_cookies` [score=26.00]
4. `merge_hooks` [score=26.00]
5. `HTTPDigestAuth.handle_401` [score=24.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is should strip auth implemented?

**Category:** Authentication  
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0017s

**Expected symbols:**
- `SessionRedirectMixin.should_strip_auth`

**Retrieved symbols (top-5):**
1. `SessionRedirectMixin.should_strip_auth` [score=50.00] ✓
2. `PreparedRequest.prepare_auth` [score=28.00]
3. `get_auth_from_url` [score=28.00]
4. `SessionRedirectMixin.rebuild_auth` [score=27.00]
5. `get_netrc_auth` [score=27.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is should strip auth handled?

**Category:** Authentication  
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0023s

**Expected symbols:**
- `SessionRedirectMixin.should_strip_auth`

**Retrieved symbols (top-5):**
1. `SessionRedirectMixin.should_strip_auth` [score=50.00] ✓
2. `HTTPDigestAuth.handle_401` [score=36.00]
3. `HTTPDigestAuth.handle_redirect` [score=32.00]
4. `PreparedRequest.prepare_auth` [score=28.00]
5. `get_auth_from_url` [score=28.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------
