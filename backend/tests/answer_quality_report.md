# RepoGraphAI -- Answer Quality Evaluation Report

Generated: 2026-07-01T01:12:17.828599

## Summary

- Evaluated questions: 30
- Passed (overall >= 4 and hallucination >= 4): 1 (3.3%)
- Average Correctness: 1.53/5
- Average Groundedness: 1.67/5
- Average Completeness: 1.43/5
- Average Hallucination (absence of): 1.73/5
- Average Overall Score: 1.43/5

## Per-Repository Breakdown

- **RepoGraphAI**: 15 questions, overall avg 1.87/5, pass rate 6.7%
- **FastAPI**: 5 questions, overall avg 1.0/5, pass rate 0.0%
- **Typer**: 5 questions, overall avg 1.0/5, pass rate 0.0%
- **Requests**: 5 questions, overall avg 1.0/5, pass rate 0.0%

## Best Answers

- **[RepoGraphAI / Graph Construction]** How is the graph generated?
  - Overall: 5/5 (correctness=5, groundedness=5, completeness=5, hallucination=5)
  - Reason: The answer accurately identifies the core components and steps for graph generation, providing highly grounded details such as specific method and class names, internal helper functions, and even the 'three passes' mechanism. It fully covers the expected behavior and adds valuable, accurate context.
- **[RepoGraphAI / Parsing]** How are files parsed?
  - Overall: 3/5 (correctness=4, groundedness=5, completeness=3, hallucination=5)
  - Reason: The answer correctly identifies the main method and the high-level components extracted (classes, functions, imports, ParsedFile). However, it misses the crucial detail of using `ast.parse` and walking the AST, as well as the UTF-8 encoding and error handling specifics.
- **[RepoGraphAI / Parsing]** How are imports extracted?
  - Overall: 3/5 (correctness=3, groundedness=4, completeness=3, hallucination=5)
  - Reason: The answer correctly identifies the method and class used for import extraction. However, it fails to mention the crucial detail that relative imports are deliberately skipped, which is an important part of the expected behavior.
- **[RepoGraphAI / Parsing]** How are classes extracted?
  - Overall: 3/5 (correctness=3, groundedness=4, completeness=3, hallucination=4)
  - Reason: The answer correctly identifies the main method and output object but misses key details like the input node type, the 'walking' mechanism, and the specific components of the `ParsedClass`. The mention of `_extract_decorator` is an unrequested detail and its role in `ParsedClass` construction isn't clarified as per the `EXPECTED BEHAVIOUR`.
- **[RepoGraphAI / Graph Construction]** How are graph edges created?
  - Overall: 3/5 (correctness=4, groundedness=4, completeness=3, hallucination=5)
  - Reason: The answer correctly identifies `GraphBuilder.build_graph` as the location and `GraphEdge` objects. However, it misses the detail about typed relationships (e.g., CALLS, IMPORTS) and that edges connect existing node IDs, which were important parts of the expected behavior.

## Weakest Answers

- **[RepoGraphAI / Graph Construction]** How are graph nodes created?
  - Overall: 2/5 (correctness=3, groundedness=4, completeness=2, hallucination=4)
  - Reason: The answer identifies methods that instantiate nodes, but it misses crucial details from the expected behavior, such as deduplication and the types of entities represented (files, classes, functions). It also introduces other node types (ResolvedNode, SourceNode) that seem to be a different layer of abstraction or a later processing step, rather than the core graph node creation mechanism described.
- **[RepoGraphAI / Parsing]** How are files parsed?
  - Overall: 3/5 (correctness=4, groundedness=5, completeness=3, hallucination=5)
  - Reason: The answer correctly identifies the main method and the high-level components extracted (classes, functions, imports, ParsedFile). However, it misses the crucial detail of using `ast.parse` and walking the AST, as well as the UTF-8 encoding and error handling specifics.
- **[RepoGraphAI / Parsing]** How are imports extracted?
  - Overall: 3/5 (correctness=3, groundedness=4, completeness=3, hallucination=5)
  - Reason: The answer correctly identifies the method and class used for import extraction. However, it fails to mention the crucial detail that relative imports are deliberately skipped, which is an important part of the expected behavior.
- **[RepoGraphAI / Parsing]** How are classes extracted?
  - Overall: 3/5 (correctness=3, groundedness=4, completeness=3, hallucination=4)
  - Reason: The answer correctly identifies the main method and output object but misses key details like the input node type, the 'walking' mechanism, and the specific components of the `ParsedClass`. The mention of `_extract_decorator` is an unrequested detail and its role in `ParsedClass` construction isn't clarified as per the `EXPECTED BEHAVIOUR`.
- **[RepoGraphAI / Graph Construction]** How are graph edges created?
  - Overall: 3/5 (correctness=4, groundedness=4, completeness=3, hallucination=5)
  - Reason: The answer correctly identifies `GraphBuilder.build_graph` as the location and `GraphEdge` objects. However, it misses the detail about typed relationships (e.g., CALLS, IMPORTS) and that edges connect existing node IDs, which were important parts of the expected behavior.

## Common Failure Patterns

- 22/30 questions failed during answer generation (GraphRAG/LLM provider errors) before ever reaching the judge.
- 2/30 questions could not be scored because the judge call failed or returned unparseable output.
- 22/30 answers scored low on hallucination risk (categories: Analytics, Context Building, FastAPI, Query Resolution, Requests, Retrieval, Typer) -- the model likely stated specifics not supported by the retrieved context.
- 22/30 answers scored low on groundedness (categories: Analytics, Context Building, FastAPI, Query Resolution, Requests, Retrieval, Typer) -- answers leaned generic rather than citing specific repository detail.
- 23/30 answers scored low on completeness (categories: Analytics, Context Building, FastAPI, Graph Construction, Query Resolution, Requests, Retrieval, Typer) -- important parts of the expected behaviour were left out.

## Recommendations

- Tighten the GraphRAG system prompt's grounding instructions, or reduce top_k/max_hops noise, to reduce hallucination risk.
- Consider including more concrete code snippets or node-level detail in ContextBuilder's llm_context so answers can cite specifics.
- Investigate whether retrieval (top_k/max_hops) is surfacing enough related nodes for multi-part questions, since incomplete context limits how complete an answer can be.
- Pass rate is below 70%% -- re-run this evaluation after any prompt or retrieval change to confirm answer quality is trending upward, not just retrieval metrics.

## All Results

### [FAIL] How are files parsed?

- Repository: RepoGraphAI
- Category: Parsing
- Expected Symbol(s): CodeParser.parse_file
- Expected Behaviour: CodeParser.parse_file reads a single Python file as UTF-8 text, parses it into an AST via ast.parse (raising a clear ValueError on a syntax error rather than crashing silently), and walks that AST to extract the file's classes, functions, and imports into a ParsedFile.
- Generated Answer: Files are parsed by the `CodeParser.parse_file` method.

This method is responsible for:
1.  Extracting classes from the file by calling `CodeParser._extract_class`.
2.  Extracting imports by calling `CodeParser._extract_imports` (though `_extract_imports` itself is not detailed in the provided context, its call is shown).
3.  Extracting functions by calling `CodeParser.extract_function`.
4.  Finally, it instantiates a `ParsedFile` object, which presumably holds the results of this parsing process.
- Scores: correctness=4, groundedness=5, completeness=3, hallucination=5, overall=3
- Reason: The answer correctly identifies the main method and the high-level components extracted (classes, functions, imports, ParsedFile). However, it misses the crucial detail of using `ast.parse` and walking the AST, as well as the UTF-8 encoding and error handling specifics.

### [FAIL] How are imports extracted?

- Repository: RepoGraphAI
- Category: Parsing
- Expected Symbol(s): CodeParser._extract_imports
- Expected Behaviour: CodeParser._extract_imports walks the top level of a module's AST collecting `import` and `from X import Y` statements into dotted module paths (e.g. "os.path"). Relative imports (`from .x import y`) are deliberately skipped because resolving them requires package context the parser does not have at this stage.
- Generated Answer: Imports are extracted by the `CodeParser` class using the `CodeParser._extract_imports` method. This method is responsible for extracting all imported module paths from the top level of a given module.
- Scores: correctness=3, groundedness=4, completeness=3, hallucination=5, overall=3
- Reason: The answer correctly identifies the method and class used for import extraction. However, it fails to mention the crucial detail that relative imports are deliberately skipped, which is an important part of the expected behavior.

### [FAIL] How are classes extracted?

- Repository: RepoGraphAI
- Category: Parsing
- Expected Symbol(s): CodeParser._extract_class
- Expected Behaviour: CodeParser._extract_class takes an ast.ClassDef node, extracts its base classes, and walks the class body collecting any FunctionDef/AsyncFunctionDef children as methods (via extract_function), producing a ParsedClass with a name, base list, and method list.
- Generated Answer: Classes are extracted by the `CodeParser._extract_class` method (ID: `CodeParser._extract_class`).

This method is responsible for parsing a class definition and constructing a `ParsedClass` object (ID: `ParsedClass`). During its operation, it calls helper methods to extract specific details:
*   `_extract_bases`: To identify the base classes from which the class inherits.
*   `_extract_decorator`: To identify any decorators applied to the class.
*   `extract_function`: To extract functions (presumably methods) defined within the class.
- Scores: correctness=3, groundedness=4, completeness=3, hallucination=4, overall=3
- Reason: The answer correctly identifies the main method and output object but misses key details like the input node type, the 'walking' mechanism, and the specific components of the `ParsedClass`. The mention of `_extract_decorator` is an unrequested detail and its role in `ParsedClass` construction isn't clarified as per the `EXPECTED BEHAVIOUR`.

### [PASS] How is the graph generated?

- Repository: RepoGraphAI
- Category: Graph Construction
- Expected Symbol(s): GraphBuilder.build_graph
- Expected Behaviour: GraphBuilder.build_graph takes a ParsedRepository and builds the master RepositoryGraph: it creates a node for every file, class, and function, and edges for the relationships between them (e.g. containment, calls, imports, inheritance).
- Generated Answer: The graph generation process is primarily orchestrated by the `GraphService.generate_graph` method (GraphService.generate_graph). This method calls `parse_repository` (details not provided in the context) and then delegates the core graph construction to the `GraphBuilder.build_graph` method (GraphBuilder.build_graph).

The `GraphBuilder.build_graph` method is described as the "Main entry point" for generating the graph. It performs three passes and returns a `RepositoryGraph`. During its execution, it instantiates:
*   `RepositoryGraph` to hold the entire graph structure.
*   `GraphNode` for individual nodes in the graph.
*   `GraphEdge` for relationships between nodes.
*   `RelationshipType` to define the types of connections.
*   `_SymbolRegistry` for managing symbols.

This method also calls various internal helper functions, such as `_class_id`, `_file_id`, `_function_id`, `_method_id`, `_module_id`, and `_module_origin`, which likely assist in identifying and structuring the elements that form the graph.

After the graph is built, the `GraphBuilder.generate_statistics` method (GraphBuilder.generate_statistics) can be called to compute various graph statistics, including node degrees. This method instantiates `GraphStatistics` and `NodeDegree` objects.
- Scores: correctness=5, groundedness=5, completeness=5, hallucination=5, overall=5
- Reason: The answer accurately identifies the core components and steps for graph generation, providing highly grounded details such as specific method and class names, internal helper functions, and even the 'three passes' mechanism. It fully covers the expected behavior and adds valuable, accurate context.

### [FAIL] How are graph nodes created?

- Repository: RepoGraphAI
- Category: Graph Construction
- Expected Symbol(s): GraphBuilder.build_graph
- Expected Behaviour: Node creation is done by an internal helper (nested inside build_graph) that adds a node -- representing a file, class, or function -- to the graph, keyed by a unique node id and deduplicated so the same symbol is never added twice.
- Generated Answer: Graph nodes are created in a few different ways, depending on the type of node:

1.  **Core `GraphNode` objects** are instantiated by the `GraphBuilder.build_graph` method. This method serves as the main entry point for constructing a `RepositoryGraph`.
2.  **`ResolvedNode` objects** are instantiated by the `ContextBuilder._build_resolved_nodes` method. This method converts `QueryMatch` and `RetrievalResult` pairs into `ResolvedNode` objects.
3.  **`SourceNode` objects** are instantiated by the `GraphRAGEngine._build_source_nodes` method. This method projects `ResolvedNode` objects into the `SourceNode` shape.
- Scores: correctness=3, groundedness=4, completeness=2, hallucination=4, overall=2
- Reason: The answer identifies methods that instantiate nodes, but it misses crucial details from the expected behavior, such as deduplication and the types of entities represented (files, classes, functions). It also introduces other node types (ResolvedNode, SourceNode) that seem to be a different layer of abstraction or a later processing step, rather than the core graph node creation mechanism described.

### [FAIL] How are graph edges created?

- Repository: RepoGraphAI
- Category: Graph Construction
- Expected Symbol(s): GraphBuilder.build_graph
- Expected Behaviour: Edge creation is done by an internal helper (nested inside build_graph) that records a typed relationship (e.g. CALLS, IMPORTS, CONTAINS, INHERITS) between two node ids that already exist in the graph.
- Generated Answer: Graph edges are created by instantiating `GraphEdge` objects within the `GraphBuilder.build_graph` method ([GraphBuilder.build_graph](_GraphBuilder.build_graph)). This method is the main entry point for building a `RepositoryGraph` and is responsible for running passes that likely identify relationships and then create the corresponding edge objects.
- Scores: correctness=4, groundedness=4, completeness=3, hallucination=5, overall=3
- Reason: The answer correctly identifies `GraphBuilder.build_graph` as the location and `GraphEdge` objects. However, it misses the detail about typed relationships (e.g., CALLS, IMPORTS) and that edges connect existing node IDs, which were important parts of the expected behavior.

### [FAIL] How is inheritance represented?

- Repository: RepoGraphAI
- Category: Graph Construction
- Expected Symbol(s): GraphBuilder.build_class_graph
- Expected Behaviour: GraphBuilder.build_class_graph derives a class-only view of the master graph by connecting class nodes with INHERITS edges (plus INSTANTIATES/DECORATES), so class hierarchies can be queried or visualised independently of functions and files.
- Generated Answer: Inheritance is represented as a connection type called `INHERITS` within the class view of the generated graph.

This relationship is explicitly used when building the class graph, as stated in the docstring for `GraphBuilder.build_class_graph`:
"Class view: Class-only nodes connected by INHERITS, INSTANTIATES,"

Additionally, the system tracks parent-child class relationships, which is fundamental to inheritance, as indicated by the `_SymbolRegistry.parent_defines_method`. This method checks if a `parent_name` (a class) defines a given `method_name`, implying the tracking of inherited methods.
- Scores: correctness=1, groundedness=1, completeness=1, hallucination=1, overall=1
- Reason: Judge LLM call failed; see judge_error.
- Judge Error: ClientError: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 5, model: gemini-2.5-flash\nPlease retry in 53.812100167s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-2.5-flash'}, 'quotaValue': '5'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '53s'}]}}

### [FAIL] How are hotspots calculated?

- Repository: RepoGraphAI
- Category: Analytics
- Expected Symbol(s): GraphBuilder.generate_statistics
- Expected Behaviour: GraphBuilder.generate_statistics computes the most-connected nodes in the graph (ranked by edge degree) as part of its statistics output; these high-degree nodes act as a proxy for "hotspots" -- symbols that are heavily depended upon or tightly coupled to many others.
- Generated Answer: Based on the provided repository context, the term "hotspots" is not explicitly defined or calculated as a distinct metric using that exact terminology.

However, the repository does compute graph statistics, which can be used to identify areas of high activity or importance, akin to "hotspots". The `GraphBuilder.generate_statistics` method is responsible for computing these graph statistics. As part of this process, it instantiates `NodeDegree` objects (NodeDegree).

A `NodeDegree` object represents "A node ID paired with its total degree (in + out edges)" (NodeDegree). In graph theory, nodes with a high degree (many incoming and outgoing connections) are often considered central or significant, and could be interpreted as "hotspots" within the graph representation of the repository.

Therefore, while not explicitly named "hotspots", the underlying mechanism involves computing node degrees via `GraphBuilder.generate_statistics`.
- Scores: correctness=1, groundedness=1, completeness=1, hallucination=1, overall=1
- Reason: Judge LLM call failed; see judge_error.
- Judge Error: ClientError: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 5, model: gemini-2.5-flash\nPlease retry in 49.067665189s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-2.5-flash'}, 'quotaValue': '5'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '49s'}]}}

### [FAIL] How are graph statistics generated?

- Repository: RepoGraphAI
- Category: Analytics
- Expected Symbol(s): GraphBuilder.generate_statistics
- Expected Behaviour: GraphBuilder.generate_statistics computes total node/edge counts, counts broken down by node type and edge type, and the most-connected nodes, returning a GraphStatistics object summarising the whole graph.
- Generation Error: LLM provider failed to generate an answer for question: 'How are graph statistics generated?'

### [FAIL] How does retrieval work?

- Repository: RepoGraphAI
- Category: Retrieval
- Expected Symbol(s): RepositoryRetriever.get_node_context
- Expected Behaviour: RepositoryRetriever.get_node_context is the universal entry point for retrieving context about a single node id: it returns a RetrievalResult bundling that node together with its relevant neighbours and relationships, used as the building block for answering questions about any node type.
- Generation Error: LLM provider failed to generate an answer for question: 'How does retrieval work?'

### [FAIL] How are neighbours retrieved?

- Repository: RepoGraphAI
- Category: Retrieval
- Expected Symbol(s): RepositoryRetriever._collect_neighbours
- Expected Behaviour: RepositoryRetriever._collect_neighbours returns the deduplicated one-hop neighbours of a node by walking both the outgoing and incoming edge indexes, so callers get every directly connected node regardless of edge direction.
- Generation Error: LLM provider failed to generate an answer for question: 'How are neighbours retrieved?'

### [FAIL] How is a subgraph extracted?

- Repository: RepoGraphAI
- Category: Retrieval
- Expected Symbol(s): RepositoryRetriever.get_subgraph
- Expected Behaviour: RepositoryRetriever.get_subgraph takes a set of node ids plus a max_hops limit and returns a new RepositoryGraph containing those nodes plus everything reachable within max_hops -- this is the focused slice of the graph that ultimately becomes the LLM's context.
- Generation Error: LLM provider failed to generate an answer for question: 'How is a subgraph extracted?'

### [FAIL] How does query resolution work?

- Repository: RepoGraphAI
- Category: Query Resolution
- Expected Symbol(s): QueryResolver.resolve_query
- Expected Behaviour: QueryResolver.resolve_query is the main entry point: it takes a natural-language question, extracts keywords and detects intent, ranks candidate graph nodes against them, and returns a QueryResolutionResult containing the ranked list of matching nodes.
- Generation Error: LLM provider failed to generate an answer for question: 'How does query resolution work?'

### [FAIL] How are symbols ranked?

- Repository: RepoGraphAI
- Category: Query Resolution
- Expected Symbol(s): QueryResolver.rank_candidates
- Expected Behaviour: QueryResolver.rank_candidates scores candidate nodes against the question's extracted keywords and detected intent, producing an ordered list of QueryMatch objects (best match first) that downstream code uses to select the top_k nodes.
- Generation Error: LLM provider failed to generate an answer for question: 'How are symbols ranked?'

### [FAIL] How is LLM context built?

- Repository: RepoGraphAI
- Category: Context Building
- Expected Symbol(s): ContextBuilder.build
- Expected Behaviour: ContextBuilder.build(question, top_k, max_hops) resolves the question via QueryResolver, retrieves a subgraph around the resolved nodes via RepositoryRetriever, and assembles all of that into a ContextPackage -- including an llm_context string -- ready to be handed to an LLM provider.
- Generation Error: LLM provider failed to generate an answer for question: 'How is LLM context built?'

### [FAIL] How are routes registered?

- Repository: FastAPI
- Category: FastAPI
- Expected Symbol(s): APIRouter.add_api_route, APIRouter.add_route, APIRouter.add_api_websocket_route
- Expected Behaviour: Routes are registered on an APIRouter (or on a FastAPI app, which delegates to its own router) via add_api_route, which builds an APIRoute object from the path, endpoint function, HTTP methods, and dependencies, and appends it to the router's route list. add_route and add_api_websocket_route are the equivalent entry points for plain ASGI routes and websocket routes respectively.
- Generation Error: LLM provider failed to generate an answer for question: 'How are routes registered?'

### [FAIL] How does dependency injection work?

- Repository: FastAPI
- Category: FastAPI
- Expected Symbol(s): get_dependant, solve_dependencies, add_non_field_param_to_dependency
- Expected Behaviour: FastAPI inspects a path operation function's signature via get_dependant to build a Dependant tree describing its parameters and any nested sub-dependencies. At request time, solve_dependencies recursively walks that tree -- calling sub-dependency callables and validating/injecting parameter values -- to produce the arguments ultimately passed into the endpoint function.
- Generation Error: LLM provider failed to generate an answer for question: 'How does dependency injection work?'

### [FAIL] How are requests handled?

- Repository: FastAPI
- Category: FastAPI
- Expected Symbol(s): get_request_handler, APIRoute.handle, request_validation_exception_handler
- Expected Behaviour: get_request_handler builds the ASGI callable used for a given route: it validates the incoming request, solves dependencies, calls the endpoint function, and serialises the result into a response. APIRoute.handle is the per-route ASGI entry point that this handler is wired into, and request_validation_exception_handler formats the 422 response returned when request validation fails.
- Generation Error: LLM provider failed to generate an answer for question: 'How are requests handled?'

### [FAIL] How are responses generated?

- Repository: FastAPI
- Category: FastAPI
- Expected Symbol(s): ORJSONResponse.render, UJSONResponse.render, serialize_response
- Expected Behaviour: serialize_response converts an endpoint's return value (respecting any declared response_model) into a JSON-serialisable structure; response classes such as ORJSONResponse and UJSONResponse then render that structure into the raw response bytes using their respective fast JSON encoders.
- Generation Error: LLM provider failed to generate an answer for question: 'How are responses generated?'

### [FAIL] How are middleware components registered?

- Repository: FastAPI
- Category: FastAPI
- Expected Symbol(s): FastAPI.middleware, FastAPI.build_middleware_stack, AsyncExitStackMiddleware.__call__
- Expected Behaviour: Middleware is registered either declaratively (the middleware list passed when constructing FastAPI) or imperatively via the FastAPI.middleware decorator / add_middleware. FastAPI.build_middleware_stack then assembles all registered middleware -- including the built-in AsyncExitStackMiddleware, which manages dependency cleanup -- into the final ASGI call chain.
- Generation Error: LLM provider failed to generate an answer for question: 'How are middleware components registered?'

### [FAIL] How are CLI commands registered?

- Repository: Typer
- Category: Typer
- Expected Symbol(s): TyperCLIGroup.list_commands, TyperGroup.format_commands, TyperGroup._click_resolve_command
- Expected Behaviour: Commands are registered on a Typer app via the @app.command() decorator, which wraps the decorated function into a Click Command and adds it to the app's underlying Click Group. TyperGroup/TyperCLIGroup then expose listing (list_commands), formatting (format_commands), and resolution (_click_resolve_command) of those registered commands at runtime.
- Generation Error: LLM provider failed to generate an answer for question: 'How are CLI commands registered?'

### [FAIL] How are command arguments parsed?

- Repository: Typer
- Category: Typer
- Expected Symbol(s): Command.parse_args, TyperArgument._parse_decls, _OptionParser.add_argument
- Expected Behaviour: Typer builds Click Arguments and Options from a function's type-annotated parameters -- TyperArgument._parse_decls determines an argument's declaration/name -- and registers them with an internal option parser (_OptionParser.add_argument). At invocation time, Click's Command.parse_args drives the actual parsing of sys.argv into resolved parameter values.
- Generation Error: LLM provider failed to generate an answer for question: 'How are command arguments parsed?'

### [FAIL] How are options defined?

- Repository: Typer
- Category: Typer
- Expected Symbol(s): Command.format_options, TyperCommand.format_options, TyperGroup.format_options
- Expected Behaviour: Options are defined by converting typed function parameters that have defaults into Click Option objects. format_options (overridden by TyperCommand/TyperGroup) is responsible for rendering those options' listing/help text whenever --help is invoked.
- Generation Error: LLM provider failed to generate an answer for question: 'How are options defined?'

### [FAIL] How is help text generated?

- Repository: Typer
- Category: Typer
- Expected Symbol(s): Command.format_help_text, _get_help_text, _sanitize_help_text
- Expected Behaviour: Help text is derived primarily from a command's docstring. _get_help_text and _sanitize_help_text clean and format that docstring (handling whitespace and Click's tag stripping), and Command.format_help_text renders the final formatted text into the --help output.
- Generation Error: LLM provider failed to generate an answer for question: 'How is help text generated?'

### [FAIL] How are callbacks executed?

- Repository: Typer
- Category: Typer
- Expected Symbol(s): get_callback, Typer.callback, get_param_callback
- Expected Behaviour: Typer.callback() registers a function that runs before any of a Typer app's subcommands (typically for shared options or setup). get_callback wraps a function into the Click-compatible callable that Click actually invokes, and get_param_callback does the equivalent for individual parameter-level callbacks such as validation callbacks.
- Generation Error: LLM provider failed to generate an answer for question: 'How are callbacks executed?'

### [FAIL] How are HTTP requests executed?

- Repository: Requests
- Category: Requests
- Expected Symbol(s): HTTPAdapter.send, Session.send, HTTPAdapter.request_url
- Expected Behaviour: A Session prepares a PreparedRequest and passes it to Session.send, which looks up the appropriate transport adapter for the request's URL and calls HTTPAdapter.send to actually perform the HTTP request over urllib3 (using request_url to build the final request URL), wrapping the raw response into a Response object.
- Generation Error: LLM provider failed to generate an answer for question: 'How are HTTP requests executed?'

### [FAIL] How are sessions managed?

- Repository: Requests
- Category: Requests
- Expected Symbol(s): Session.send, Session.__init__, session
- Expected Behaviour: Session.__init__ sets up persistent state -- cookies, default headers, mounted adapters, auth -- that is reused across multiple requests. The module-level session() factory function creates a Session for one-off use, and Session.send is the shared internal call that every public method (get/post/put/etc.) ultimately funnels through.
- Generation Error: LLM provider failed to generate an answer for question: 'How are sessions managed?'

### [FAIL] How are adapters used?

- Repository: Requests
- Category: Requests
- Expected Symbol(s): HTTPAdapter, BaseAdapter, Session.get_adapter
- Expected Behaviour: HTTPAdapter (implementing the abstract BaseAdapter interface) provides the actual HTTP transport -- connection pooling, retries, SSL handling -- and is mounted on a Session against a URL prefix. Session.get_adapter looks up the correct mounted adapter for a given request URL before the request is sent.
- Generation Error: LLM provider failed to generate an answer for question: 'How are adapters used?'

### [FAIL] How are redirects handled?

- Repository: Requests
- Category: Requests
- Expected Symbol(s): SessionRedirectMixin.resolve_redirects, HTTPDigestAuth.handle_redirect, Response.is_redirect
- Expected Behaviour: After a response is received, Response.is_redirect checks the status code and Location header to detect a redirect. If one is found, SessionRedirectMixin.resolve_redirects generates each subsequent request needed to follow the redirect chain -- re-applying auth via hooks such as HTTPDigestAuth.handle_redirect -- up to the configured redirect limit.
- Generation Error: LLM provider failed to generate an answer for question: 'How are redirects handled?'

### [FAIL] How are responses processed?

- Repository: Requests
- Category: Requests
- Expected Symbol(s): Response.iter_content, Response.content, stream_decode_response_unicode
- Expected Behaviour: Response.content lazily reads and caches the full response body in memory. Response.iter_content streams the body in chunks instead of loading it all at once, and stream_decode_response_unicode decodes those raw byte chunks into text using the response's detected or declared encoding.
- Generation Error: LLM provider failed to generate an answer for question: 'How are responses processed?'

