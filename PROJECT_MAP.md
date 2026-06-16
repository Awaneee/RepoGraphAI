# PROJECT_MAP.md - RepoGraphAI

## 1. Overall Goal of the Project
RepoGraphAI is a GraphRAG-based Repository Architecture Analysis Platform. Its primary goal is to clone Git repositories, analyze their structure, and generate insights, including comprehensive summaries and knowledge graphs, to facilitate understanding of codebase architecture.

## 2. Current Architecture
The backend is a FastAPI application serving as the core of RepoGraphAI. The overall architecture for processing and querying repositories follows this flow:

Repository
→ Parser
→ Knowledge Graph
→ Analytics
→ RepositoryRetriever
→ QueryResolver
→ ContextBuilder
→ GraphRAG (planned)

The architecture is modular, separating concerns into distinct layers for repository operations, code parsing, graph building, retrieval, and data modeling.

## 3. Major Layers
*   **API Layer (`app/api`)**: Exposes RESTful endpoints for external interaction, built with FastAPI.
*   **Services Layer (`app/services`)**: Contains the primary business logic, orchestrating repository management and graph generation.
*   **Parsers Layer (`app/parsers`)**: Responsible for syntactically analyzing source code (currently Python) to extract structural information.
*   **Graph Layer (`app/graph`)**: Handles the construction and filtering of repository knowledge graphs based on parsed data.
*   **Models Layer (`app/models`)**: Defines data structures using Pydantic for request validation, response serialization, and internal graph representation.
*   **RAG Layer (`app/rag`)**: Intended for Retrieval Augmented Generation, to build context from graphs and answer queries.
*   **Retrievers Layer (`app/retrievers`)**: Components for retrieving specific code or graph information.
*   **Embeddings Layer (`app/embeddings`)**: Manages the generation of vector embeddings for code or graph elements.
*   **Core Layer (`app/core`)**: Contains application-wide configurations.
*   **Evaluation Layer (`app/evaluation`)**: Provides tools and logic for evaluating the system's performance and output quality.

## 4. Python File Summaries (in `backend/app`)

*   **`main.py`**
    *   Purpose: Initializes the FastAPI application and includes the API router.
    *   Key classes/functions: `app = FastAPI(...)`
*   **`api/endpoints.py`**
    *   Purpose: Defines the primary API routes for repository analysis and graph generation.
    *   Key classes/functions: `@router.post("/analyze") def analyze_repository(...)`, `@router.post("/graph") def generate_graph(...)`
*   **`services/repository_service.py`**
    *   Purpose: Manages Git repository cloning, scanning for file statistics, and generating repository summaries.
    *   Key classes/functions: `class RepositoryService`, `clone_repository(repo_url: str)`, `detect_framework(repo_path: str)`, `scan_repository(repo_path: str)`, `generate_summary(repo_path: str)`
*   **`services/graph_services.py`**
    *   Purpose: Orchestrates the parsing of repository code and the subsequent building of the knowledge graph.
    *   Key classes/functions: `class GraphService`, `generate_graph(repository_path: str)`
*   **`parsers/code_parser.py`**
    *   Purpose: Parses Python source files using AST to extract structured information like classes, functions, imports, and decorators.
    *   Key classes/functions: `class CodeParser`, `parse_file(file_path: str)`, `parse_repository(repository_path: str)`
*   **`graph/graph_builder.py`**
    *   Purpose: Constructs a comprehensive repository knowledge graph from parsed data and provides methods to generate filtered graph views (architecture, class, call graphs) and statistics.
    *   Key classes/functions: `class GraphBuilder`, `build_graph(repository: ParsedRepository)`, `build_architecture_graph(...)`, `build_class_graph(...)`, `build_call_graph(...)`, `generate_statistics(...)`
*   **`rag/context_builder.py`**
    *   Purpose: Orchestrates the retrieval pipeline to construct a cohesive context for LLMs by expanding subgraphs.
    *   Key classes/functions: `class ContextBuilder`, `build_context(...)`
*   **`rag/rag_pipeline.py`**
    *   Purpose: (Inferred) Implements the overall Retrieval Augmented Generation pipeline.
    *   Key classes/functions: `RAGPipeline` (class/function inferred from name)
*   **`retrievers/code_retriever.py`**
    *   Purpose: Retrieves specific code elements, graph components, and extracts relevant subgraphs from the knowledge graph.
    *   Key classes/functions: `class RepositoryRetriever`, `retrieve_nodes(...)`, `retrieve_classes(...)`, `retrieve_callables(...)`, `extract_subgraph(...)`, `generate_llm_context(...)`
*   **`retrievers/query_resolver.py`**
    *   Purpose: Interprets natural language queries, detects user intent, extracts keywords, ranks retrieval results, and resolves top-k relevant graph elements.
    *   Key classes/functions: `class QueryResolver`, `resolve_query(...)`, `detect_intent(...)`, `extract_keywords(...)`, `rank_results(...)`
*   **`models/pydantic_models.py`**
    *   Purpose: Defines all Pydantic models used for data validation, serialization, and structured representation across the application.
    *   Key classes/functions: `RepositoryRequest`, `RepositorySummary`, `RepositoryGraph`, `GraphNode`, `GraphEdge`, `ParsedFile`, `ParsedClass`, `ParsedFunction`
*   **`core/config.py`**
    *   Purpose: (Inferred) Manages application settings and configuration.
    *   Key classes/functions: `Settings` (class inferred from common patterns)
*   **`embeddings/embedding_model.py`**
    *   Purpose: (Inferred) Provides an interface for generating numerical vector embeddings from text or code.
    *   Key classes/functions: `EmbeddingModel` (class/function inferred from name)
*   **`evaluation/evaluator.py`**
    *   Purpose: (Inferred) Contains logic and tools for evaluating the performance and accuracy of the RepoGraphAI system.
    *   Key classes/functions: `Evaluator` (class/function inferred from name)

### 1. RepositoryRetriever
The `RepositoryRetriever` is responsible for fetching specific components and subgraphs from the knowledge graph.
*   **Node Retrieval**: Retrieves individual graph nodes based on various criteria (e.g., node type, name, attributes).
*   **Class Retrieval**: Specifically targets and retrieves class nodes and their associated properties.
*   **Callable Retrieval**: Retrieves function and method nodes, including their arguments and return types.
*   **Subgraph Extraction**: Extracts relevant subgraphs around specified nodes, expanding to include connected elements up to a certain depth or relationship type.
*   **LLM Context Generation**: Formats retrieved graph data into a structured context suitable for consumption by an LLM.

### 2. QueryResolver
The `QueryResolver` acts as the natural language interface to the retrieval pipeline, translating user questions into actionable graph queries.
*   **Intent Detection**: Analyzes the user's natural language query to determine the underlying intent (e.g., "find class definition", "show call hierarchy", "explain module dependencies").
*   **Keyword Extraction**: Identifies key terms and entities within the query that can be mapped to graph elements (e.g., class names, function names, file paths).
*   **Ranking**: Ranks potential retrieval results based on their relevance to the extracted keywords and detected intent.
*   **Top-K Resolution**: Selects the most relevant `k` results to pass to the `RepositoryRetriever` for detailed fetching.

### 3. ContextBuilder
The `ContextBuilder` orchestrates the retrieval process and prepares the final context for the LLM.
*   **Retrieval Orchestration**: Manages calls to the `QueryResolver` and `RepositoryRetriever` to fetch initial relevant graph elements.
*   **Subgraph Expansion**: Expands the initial retrieved subgraphs to include additional, related context (e.g., parent classes, callers, callees, importing files) to provide a more complete picture.
*   **Context Packaging**: Packages the expanded graph context, along with any relevant code snippets or documentation, into a structured format that an LLM can effectively use to generate an answer.

## 7. Missing Capabilities
*   **Comprehensive RAG Integration**: While foundational components for RAG exist (`app/rag`, `app/retrievers`, `app/embeddings`), a direct, user-facing API endpoint or workflow that leverages the knowledge graph for advanced natural language architectural query answering is not yet exposed. The current outputs are raw data (summaries, graphs) rather than LLM-generated insights from the graph.
*   **Interactive Graph Visualization**: Although `graph_visualizer.py` is present, the capability to visualize the generated knowledge graphs directly through the API or an integrated interface is not evident in the main API endpoints. This would greatly enhance usability for architectural analysis.
*   **Knowledge Persistence and Management**: The system processes repositories on-demand. There's no explicit mechanism for persisting, indexing, or managing generated graphs and summaries for multiple repositories or historical analysis over time.
*   **Cross-language Support**: Code parsing and graph building are currently focused exclusively on Python. Support for other programming languages would broaden the platform's utility.
*   **User Interface**: As a backend service, RepoGraphAI lacks a frontend application for intuitive user interaction, query input, and visualization of results.
*   **Advanced Graph Querying**: While basic statistics are available, a flexible query language or interface to perform complex graph traversals and answer detailed architectural questions (e.g., "find all files affected by changes in `X` class") programmatically is missing.

## 8. Recommended Next Milestone
The next critical milestone for RepoGraphAI should be to **implement a dedicated GraphRAG query endpoint**. This endpoint would accept natural language architectural questions about an analyzed repository, leverage the existing graph, embeddings, and retrieval components (`app/rag`, `app/retrievers`, `app/embeddings`) to retrieve relevant graph context, and then utilize an LLM to generate a coherent, natural language answer based on the retrieved information. This will directly fulfill the "GraphRAG-based" promise and move beyond raw data outputs to provide actionable architectural intelligence.
## Current Maturity

Completed:
✅ Parser
✅ Knowledge Graph
✅ Analytics
✅ Graph Views
✅ RepositoryRetriever
✅ QueryResolver
✅ ContextBuilder

In Progress:
⏳ Retrieval Quality Improvements

Planned:
🔜 GraphRAG
🔜 Embeddings
🔜 Repository Q&A
🔜 Multi-language Support
🔜 Neo4j / Persistent Graph Store