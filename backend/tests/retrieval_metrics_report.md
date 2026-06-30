# RepoGraphAI — Retrieval Metrics Report

Generated: 2026-06-30 23:45:08

============================================================

## Overall Metrics (All Questions)

| Dataset                      | Top-1  | Top-3  | Top-5  | R@1     | R@3     | R@5     | P@1      | P@3      | P@5      | MRR   |
|------------------------------|--------|--------|--------|---------|---------|---------|----------|----------|----------|-------|
| ALL                          |   83.3% |   93.3% |   96.7% |    52.2% |    75.6% |    90.0% |     83.3% |     46.7% |     35.3% | 0.879 |


## Per-Dataset Metrics

| Dataset                      | Top-1  | Top-3  | Top-5  | R@1     | R@3     | R@5     | P@1      | P@3      | P@5      | MRR   |
|------------------------------|--------|--------|--------|---------|---------|---------|----------|----------|----------|-------|
| Internal (own codebase)      |   73.3% |   86.7% |   93.3% |    73.3% |    86.7% |    93.3% |     73.3% |     28.9% |     18.7% | 0.802 |
| FastAPI                      |  100.0% |  100.0% |  100.0% |    33.3% |    60.0% |    93.3% |    100.0% |     60.0% |     56.0% | 1.000 |
| Typer                        |  100.0% |  100.0% |  100.0% |    33.3% |    73.3% |    86.7% |    100.0% |     73.3% |     52.0% | 1.000 |
| Requests                     |   80.0% |  100.0% |  100.0% |    26.7% |    60.0% |    80.0% |     80.0% |     60.0% |     48.0% | 0.867 |


============================================================

## Mode 1 — Internal Benchmark (Per Question)

============================================================

### How are files parsed?

**Category:** Parsing  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0049s

**Expected symbols:**
- `CodeParser.parse_file`

**Retrieved symbols (top-5):**
1. `CodeParser.parse_file` [score=47.00] ✓
2. `CodeParser.extract_function` [score=29.00]
3. `CodeParser._extract_class` [score=26.00]
4. `_file_id` [score=25.00]
5. `CodeParser._extract_decorator` [score=24.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are imports extracted?

**Category:** Parsing  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0022s

**Expected symbols:**
- `CodeParser._extract_imports`

**Retrieved symbols (top-5):**
1. `CodeParser._extract_imports` [score=52.00] ✓
2. `CodeParser.extract_function` [score=27.00]
3. `QueryResolver.extract_keywords` [score=26.00]
4. `GraphBuilder.build_import_graph` [score=25.00]
5. `CodeParser._extract_class` [score=24.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are classes extracted?

**Category:** Parsing  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0024s

**Expected symbols:**
- `CodeParser._extract_class`

**Retrieved symbols (top-5):**
1. `CodeParser._extract_class` [score=49.00] ✓
2. `RepositoryService.classify_repository_type` [score=34.00]
3. `RepositoryRetriever.get_class_context` [score=31.00]
4. `GraphVisualizer.save_class_graph` [score=30.00]
5. `GraphBuilder.build_class_graph` [score=29.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is the graph generated?

**Category:** Graph Construction  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0026s

**Expected symbols:**
- `GraphBuilder.build_graph`

**Retrieved symbols (top-5):**
1. `generate_graph` [score=56.00]
2. `GraphService.generate_graph` [score=55.00]
3. `GraphBuilder.build_graph` [score=39.00] ✓
4. `GraphBuilder.generate_statistics` [score=38.00]
5. `build_graphrag_engine` [score=34.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✓ | ✓ | 0.00 | 1.00 | 1.00 | 0.00 | 0.33 | 0.20 | 0.333 |

First hit rank: **3**

------------------------------------------------------------

### How are graph nodes created?

**Category:** Graph Construction  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0034s

**Expected symbols:**
- `GraphBuilder.build_graph`

**Retrieved symbols (top-5):**
1. `GraphBuilder.build_graph` [score=48.00] ✓
2. `GraphRAGEngine._build_source_nodes` [score=48.00]
3. `ContextBuilder._build_resolved_nodes` [score=47.00]
4. `build_graphrag_engine` [score=43.00]
5. `_emit_nodes` [score=40.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are graph edges created?

**Category:** Graph Construction  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0055s

**Expected symbols:**
- `GraphBuilder.build_graph`

**Retrieved symbols (top-5):**
1. `GraphBuilder.build_graph` [score=48.00] ✓
2. `build_graphrag_engine` [score=43.00]
3. `RetrievalResult.edges_of_type` [score=39.00]
4. `GraphBuilder.build_architecture_graph` [score=38.00]
5. `GraphBuilder.build_call_graph` [score=38.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is inheritance represented?

**Category:** Graph Construction  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0022s

**Expected symbols:**
- `GraphBuilder.build_class_graph`

**Retrieved symbols (top-5):**
1. `GraphVisualizer.save_class_graph` [score=33.00]
2. `GraphBuilder.build_class_graph` [score=32.00] ✓
3. `_SymbolRegistry.parent_defines_method` [score=16.00]
4. `C:\Users\awane\RepoGraphAI\backend\app\models\pydantic_models.py` [score=-5.00]
5. `app.models.pydantic_models` [score=-5.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✓ | ✓ | 0.00 | 1.00 | 1.00 | 0.00 | 0.33 | 0.20 | 0.500 |

First hit rank: **2**

------------------------------------------------------------

### How are hotspots calculated?

**Category:** Analytics  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0019s

**Expected symbols:**
- `GraphBuilder.generate_statistics`

**Retrieved symbols (top-5):**
1. `GraphBuilder.generate_statistics` [score=35.00] ✓
2. `RepositoryCache.compute_fingerprint` [score=21.00]
3. `GraphStatistics` [score=19.00]
4. `NodeDegree` [score=13.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are graph statistics generated?

**Category:** Analytics  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0037s

**Expected symbols:**
- `GraphBuilder.generate_statistics`

**Retrieved symbols (top-5):**
1. `GraphBuilder.generate_statistics` [score=62.00] ✓
2. `GraphStatistics` [score=51.00]
3. `generate_graph` [score=49.00]
4. `GraphService.generate_graph` [score=48.00]
5. `GraphBuilder.build_graph` [score=32.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How does retrieval work?

**Category:** Retrieval  
**Repository:** internal  
**Result:** FAIL  
**Retrieval time:** 0.0016s

**Expected symbols:**
- `RepositoryRetriever.get_node_context`

**Retrieved symbols (top-5):**
1. `ContextBuilder._collect_retrieval_results` [score=27.00]
2. `RepositoryRetriever.search_by_label` [score=24.00]
3. `RepositoryRetriever` [score=22.00]
4. `RetrievalMetadata` [score=21.00]
5. `RetrievalResult.edges_of_type` [score=21.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✗ | ✗ | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.000 |

First hit rank: **—**

------------------------------------------------------------

### How are neighbours retrieved?

**Category:** Retrieval  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0021s

**Expected symbols:**
- `RepositoryRetriever._collect_neighbours`

**Retrieved symbols (top-5):**
1. `RepositoryRetriever._collect_neighbours` [score=37.00] ✓
2. `RetrievalResult.neighbour_ids` [score=35.00]
3. `RepositoryRetriever.search_by_label` [score=26.00]
4. `RepositoryRetriever.build_llm_context` [score=21.00]
5. `RepositoryRetriever.get_node_context` [score=21.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is a subgraph extracted?

**Category:** Retrieval  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0039s

**Expected symbols:**
- `RepositoryRetriever.get_subgraph`

**Retrieved symbols (top-5):**
1. `RepositoryRetriever.get_subgraph` [score=50.00] ✓
2. `RepositoryRetriever.get_subgraph_for_intent` [score=47.00]
3. `_build_subgraph_summary` [score=42.00]
4. `CodeParser.extract_function` [score=27.00]
5. `QueryResolver.extract_keywords` [score=26.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How does query resolution work?

**Category:** Query Resolution  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0031s

**Expected symbols:**
- `QueryResolver.resolve_query`

**Retrieved symbols (top-5):**
1. `QueryResolver.resolve_query` [score=37.00] ✓
2. `QueryResolutionResult` [score=30.00]
3. `QueryResolutionResult.top_node_ids` [score=30.00]
4. `QueryResolver.resolve_to_node_ids` [score=28.00]
5. `QueryResolver` [score=26.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are symbols ranked?

**Category:** Query Resolution  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0020s

**Expected symbols:**
- `QueryResolver.rank_candidates`

**Retrieved symbols (top-5):**
1. `QueryResolver.rank_candidates` [score=34.00] ✓
2. `_SymbolRegistry.is_repo_symbol` [score=27.00]
3. `_SymbolRegistry` [score=23.00]
4. `QueryResolver.get_ranking_diagnostics` [score=21.00]
5. `ContextPackage.top_node_ids` [score=20.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.20 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is LLM context built?

**Category:** Context Building  
**Repository:** internal  
**Result:** PASS  
**Retrieval time:** 0.0026s

**Expected symbols:**
- `ContextBuilder.build`

**Retrieved symbols (top-5):**
1. `RepositoryRetriever.build_llm_context` [score=69.00]
2. `ContextBuilder._build_llm_context_text` [score=65.00]
3. `build_context_builder` [score=48.00]
4. `RepositoryRetriever.get_node_context` [score=36.00]
5. `ContextBuilder.build` [score=35.00] ✓

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✗ | ✓ | 0.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.20 | 0.200 |

First hit rank: **5**

------------------------------------------------------------


============================================================

## Mode 2 — Cross-Repository Benchmark (Per Question)

============================================================


### Repository: FastAPI

### How are routes registered?

**Category:**   
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0109s

**Expected symbols:**
- `APIRouter.add_api_route`
- `APIRouter.add_route`
- `APIRouter.add_api_websocket_route`

**Retrieved symbols (top-5):**
1. `APIRouter.add_api_route` [score=50.00] ✓
2. `APIRoute.get_route_handler` [score=49.00]
3. `APIRouter.add_api_websocket_route` [score=49.00] ✓
4. `APIRouter.add_route` [score=49.00] ✓
5. `APIRouter.add_websocket_route` [score=49.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 0.33 | 0.67 | 1.00 | 1.00 | 0.67 | 0.60 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How does dependency injection work?

**Category:**   
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0053s

**Expected symbols:**
- `get_dependant`
- `solve_dependencies`
- `add_non_field_param_to_dependency`

**Retrieved symbols (top-5):**
1. `add_non_field_param_to_dependency` [score=36.00] ✓
2. `DependencyScopeError` [score=28.00]
3. `get_dependant` [score=21.00] ✓
4. `get_flat_dependant` [score=21.00]
5. `solve_dependencies` [score=21.00] ✓

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 0.33 | 0.67 | 1.00 | 1.00 | 0.67 | 0.60 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are requests handled?

**Category:**   
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0064s

**Expected symbols:**
- `get_request_handler`
- `APIRoute.handle`
- `request_validation_exception_handler`

**Retrieved symbols (top-5):**
1. `get_request_handler` [score=46.00] ✓
2. `request_validation_exception_handler` [score=40.00] ✓
3. `websocket_request_validation_exception_handler` [score=40.00]
4. `http_exception_handler` [score=36.00]
5. `APIRoute.handle` [score=33.00] ✓

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 0.33 | 0.67 | 1.00 | 1.00 | 0.67 | 0.60 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are responses generated?

**Category:**   
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0046s

**Expected symbols:**
- `ORJSONResponse.render`
- `UJSONResponse.render`
- `serialize_response`

**Retrieved symbols (top-5):**
1. `serialize_response` [score=33.00] ✓
2. `get_graphql_response` [score=29.00]
3. `request_response` [score=28.00]
4. `ORJSONResponse.render` [score=26.00] ✓
5. `UJSONResponse.render` [score=26.00] ✓

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 0.33 | 0.33 | 1.00 | 1.00 | 0.33 | 0.60 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are middleware components registered?

**Category:**   
**Repository:** FastAPI  
**Result:** PASS  
**Retrieval time:** 0.0081s

**Expected symbols:**
- `FastAPI.middleware`
- `FastAPI.build_middleware_stack`
- `AsyncExitStackMiddleware.__call__`

**Retrieved symbols (top-5):**
1. `FastAPI.middleware` [score=29.00] ✓
2. `FastAPI.build_middleware_stack` [score=28.00] ✓
3. `APIRouter.include_router` [score=24.00]
4. `add_missing` [score=24.00]
5. `add_permalinks_page` [score=24.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 0.33 | 0.67 | 0.67 | 1.00 | 0.67 | 0.40 | 1.000 |

First hit rank: **1**

------------------------------------------------------------


### Repository: Typer

### How are CLI commands registered?

**Category:**   
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0071s

**Expected symbols:**
- `TyperCLIGroup.list_commands`
- `TyperGroup.format_commands`
- `TyperGroup._click_resolve_command`

**Retrieved symbols (top-5):**
1. `TyperCLIGroup.list_commands` [score=44.00] ✓
2. `TyperGroup.format_commands` [score=43.00] ✓
3. `TyperCLIGroup.get_command` [score=41.00]
4. `TyperGroup.list_commands` [score=40.00]
5. `maybe_add_run_to_cli` [score=40.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 0.33 | 0.67 | 0.67 | 1.00 | 0.67 | 0.40 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are command arguments parsed?

**Category:**   
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0106s

**Expected symbols:**
- `Command.parse_args`
- `TyperArgument._parse_decls`
- `_OptionParser.add_argument`

**Retrieved symbols (top-5):**
1. `Command.parse_args` [score=55.00] ✓
2. `get_install_completion_arguments` [score=48.00]
3. `_OptionParser._process_args_for_options` [score=44.00]
4. `_OptionParser.add_argument` [score=40.00] ✓
5. `Argument` [score=39.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 0.33 | 0.33 | 0.67 | 1.00 | 0.33 | 0.40 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are options defined?

**Category:**   
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0084s

**Expected symbols:**
- `Command.format_options`
- `TyperCommand.format_options`
- `TyperGroup.format_options`

**Retrieved symbols (top-5):**
1. `Command.format_options` [score=37.00] ✓
2. `TyperGroup.format_options` [score=37.00] ✓
3. `TyperCommand.format_options` [score=36.00] ✓
4. `join_options` [score=36.00]
5. `_print_options_panel` [score=32.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 0.33 | 1.00 | 1.00 | 1.00 | 1.00 | 0.60 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How is help text generated?

**Category:**   
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0051s

**Expected symbols:**
- `Command.format_help_text`
- `_get_help_text`
- `_sanitize_help_text`

**Retrieved symbols (top-5):**
1. `Command.format_help_text` [score=49.00] ✓
2. `_get_help_text` [score=44.00] ✓
3. `_sanitize_help_text` [score=42.00] ✓
4. `Context.get_help` [score=39.00]
5. `HelpFormatter.write_text` [score=37.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 0.33 | 1.00 | 1.00 | 1.00 | 1.00 | 0.60 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are callbacks executed?

**Category:**   
**Repository:** Typer  
**Result:** PASS  
**Retrieval time:** 0.0054s

**Expected symbols:**
- `get_callback`
- `Typer.callback`
- `get_param_callback`

**Retrieved symbols (top-5):**
1. `get_callback` [score=41.00] ✓
2. `callback` [score=39.00]
3. `Typer.callback` [score=38.00] ✓
4. `get_param_callback` [score=38.00] ✓
5. `install_callback` [score=37.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 0.33 | 0.67 | 1.00 | 1.00 | 0.67 | 0.60 | 1.000 |

First hit rank: **1**

------------------------------------------------------------


### Repository: Requests

### How are HTTP requests executed?

**Category:**   
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0054s

**Expected symbols:**
- `HTTPAdapter.send`
- `Session.send`
- `HTTPAdapter.request_url`

**Retrieved symbols (top-5):**
1. `HTTPAdapter.send` [score=39.00] ✓
2. `HTTPAdapter.request_url` [score=37.00] ✓
3. `RequestsCookieJar` [score=35.00]
4. `HTTPAdapter.get_connection` [score=34.00]
5. `HTTPAdapter.get_connection_with_tls_context` [score=34.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 0.33 | 0.67 | 0.67 | 1.00 | 0.67 | 0.40 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are sessions managed?

**Category:**   
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0030s

**Expected symbols:**
- `Session.send`
- `Session.__init__`
- `session`

**Retrieved symbols (top-5):**
1. `Session.send` [score=35.00] ✓
2. `SessionRedirectMixin.send` [score=32.00]
3. `HTTPAdapter.init_poolmanager` [score=31.00]
4. `HTTPAdapter.build_connection_pool_key_attributes` [score=30.00]
5. `session` [score=30.00] ✓

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 0.33 | 0.33 | 0.67 | 1.00 | 0.33 | 0.40 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are adapters used?

**Category:**   
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0014s

**Expected symbols:**
- `HTTPAdapter`
- `BaseAdapter`
- `Session.get_adapter`

**Retrieved symbols (top-5):**
1. `Session.get_adapter` [score=15.00] ✓
2. `BaseAdapter` [score=14.00] ✓
3. `HTTPAdapter` [score=14.00] ✓
4. `C:\Users\awane\RepoGraphAI\backend\repos\requests\src\requests\adapters.py` [score=10.00]
5. `HTTPAdapter.build_response` [score=10.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 0.33 | 1.00 | 1.00 | 1.00 | 1.00 | 0.60 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are redirects handled?

**Category:**   
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0037s

**Expected symbols:**
- `SessionRedirectMixin.resolve_redirects`
- `HTTPDigestAuth.handle_redirect`
- `Response.is_redirect`

**Retrieved symbols (top-5):**
1. `SessionRedirectMixin.resolve_redirects` [score=28.00] ✓
2. `HTTPDigestAuth.handle_redirect` [score=27.00] ✓
3. `TooManyRedirects` [score=23.00]
4. `Response.is_redirect` [score=17.00] ✓
5. `HTTPDigestAuth.handle_401` [score=14.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✓ | ✓ | ✓ | 0.33 | 0.67 | 1.00 | 1.00 | 0.67 | 0.60 | 1.000 |

First hit rank: **1**

------------------------------------------------------------

### How are responses processed?

**Category:**   
**Repository:** Requests  
**Result:** PASS  
**Retrieval time:** 0.0053s

**Expected symbols:**
- `Response.iter_content`
- `Response.content`
- `stream_decode_response_unicode`

**Retrieved symbols (top-5):**
1. `HTTPAdapter.build_response` [score=29.00]
2. `get_unicode_from_response` [score=26.00]
3. `stream_decode_response_unicode` [score=26.00] ✓
4. `Response.iter_content` [score=25.00] ✓
5. `Response.links` [score=24.00]

| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |
|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|
| Value | ✗ | ✓ | ✓ | 0.00 | 0.33 | 0.67 | 0.00 | 0.33 | 0.40 | 0.333 |

First hit rank: **3**

------------------------------------------------------------
