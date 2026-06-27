# Cross Repository Benchmark

Generated: 2026-06-28 01:44:41.803980

# FastAPI

## Graph Statistics

- Python Files: 73
- Graph Nodes: 761
- Graph Edges: 1837

## Question

How are routes registered?

### Timing

- Retrieval time: 0.0086s
- Generation time: 0.0050s
- Total time: 0.0136s

### Retrieved Nodes

- **APIRouter.add_api_route** (Method) [score=50.00] repos\fastapi\fastapi\routing.py:2080
- **APIRoute.get_route_handler** (Method) [score=49.00] repos\fastapi\fastapi\routing.py:1164
- **APIRouter.add_api_websocket_route** (Method) [score=49.00] repos\fastapi\fastapi\routing.py:2226
- **APIRouter.add_route** (Method) [score=49.00] repos\fastapi\fastapi\routing.py:2015
- **APIRouter.add_websocket_route** (Method) [score=49.00] repos\fastapi\fastapi\routing.py:2032

### Retrieval Metadata

- Intent Categories: ['routing']
- Keywords: ['routes', 'rout', 'registered', 'register']
- Resolved Nodes: 5
- Subgraph Nodes: 11
- Subgraph Edges: 10
- top_k: 5
- max_hops: 1

### Answer

[EchoLLMProvider — no real LLM configured]
system_prompt length: 496 chars
user_prompt length: 5613 chars
Replace this provider with a real LLMProvider implementation (e.g. AnthropicLLMProvider) to get an actual answer.

---

## Question

How does dependency injection work?

### Timing

- Retrieval time: 0.0046s
- Generation time: 0.0012s
- Total time: 0.0058s

### Retrieved Nodes

- **add_non_field_param_to_dependency** (Function) [score=36.00] repos\fastapi\fastapi\dependencies\utils.py:362
- **DependencyScopeError** (Class) [score=28.00] repos\fastapi\fastapi\exceptions.py:167
- **get_dependant** (Function) [score=21.00] repos\fastapi\fastapi\dependencies\utils.py:286
- **get_flat_dependant** (Function) [score=21.00] repos\fastapi\fastapi\dependencies\utils.py:138
- **solve_dependencies** (Function) [score=21.00] repos\fastapi\fastapi\dependencies\utils.py:598

### Retrieval Metadata

- Intent Categories: ['analysis']
- Keywords: ['dependency', 'injection', 'injec']
- Resolved Nodes: 5
- Subgraph Nodes: 29
- Subgraph Edges: 60
- top_k: 5
- max_hops: 1

### Answer

[EchoLLMProvider — no real LLM configured]
system_prompt length: 496 chars
user_prompt length: 10366 chars
Replace this provider with a real LLMProvider implementation (e.g. AnthropicLLMProvider) to get an actual answer.

---

## Question

How are requests handled?

### Timing

- Retrieval time: 0.0071s
- Generation time: 0.0007s
- Total time: 0.0078s

### Retrieved Nodes

- **get_request_handler** (Function) [score=46.00] repos\fastapi\fastapi\routing.py:360
- **request_validation_exception_handler** (Function) [score=40.00] repos\fastapi\fastapi\exception_handlers.py:20
- **websocket_request_validation_exception_handler** (Function) [score=40.00] repos\fastapi\fastapi\exception_handlers.py:29
- **http_exception_handler** (Function) [score=36.00] repos\fastapi\fastapi\exception_handlers.py:11
- **APIRoute.handle** (Method) [score=33.00] repos\fastapi\fastapi\routing.py:1200

### Retrieval Metadata

- Intent Categories: ['routing']
- Keywords: ['requests', 'request', 'handled', 'handl']
- Resolved Nodes: 5
- Subgraph Nodes: 26
- Subgraph Edges: 43
- top_k: 5
- max_hops: 1

### Answer

[EchoLLMProvider — no real LLM configured]
system_prompt length: 496 chars
user_prompt length: 8514 chars
Replace this provider with a real LLMProvider implementation (e.g. AnthropicLLMProvider) to get an actual answer.

---

## Question

How are responses generated?

### Timing

- Retrieval time: 0.0051s
- Generation time: 0.0000s
- Total time: 0.0051s

### Retrieved Nodes

- **ORJSONResponse.render** (Method) [score=26.00] repos\fastapi\fastapi\responses.py:94
- **UJSONResponse.render** (Method) [score=26.00] repos\fastapi\fastapi\responses.py:64
- **generate_lang_path** (Function) [score=25.00] repos\fastapi\scripts\translate.py:41
- **ResponseValidationError** (Class) [score=24.00] repos\fastapi\fastapi\exceptions.py:234
- **create_model_field** (Function) [score=24.00] repos\fastapi\fastapi\utils.py:58

### Retrieval Metadata

- Intent Categories: ['generation']
- Keywords: ['responses', 'respons', 'generated', 'generat']
- Resolved Nodes: 5
- Subgraph Nodes: 26
- Subgraph Edges: 37
- top_k: 5
- max_hops: 1

### Answer

[EchoLLMProvider — no real LLM configured]
system_prompt length: 496 chars
user_prompt length: 6753 chars
Replace this provider with a real LLMProvider implementation (e.g. AnthropicLLMProvider) to get an actual answer.

---

## Question

How are middleware components registered?

### Timing

- Retrieval time: 0.0085s
- Generation time: 0.0000s
- Total time: 0.0085s

### Retrieved Nodes

- **FastAPI.middleware** (Method) [score=29.00] repos\fastapi\fastapi\applications.py:4603
- **FastAPI.build_middleware_stack** (Method) [score=28.00] repos\fastapi\fastapi\applications.py:1019
- **APIRouter.include_router** (Method) [score=24.00] repos\fastapi\fastapi\routing.py:2324
- **add_missing** (Function) [score=24.00] repos\fastapi\scripts\translate.py:393
- **add_permalinks_page** (Function) [score=24.00] repos\fastapi\scripts\docs.py:780

### Retrieval Metadata

- Intent Categories: ['routing']
- Keywords: ['middleware', 'components', 'component', 'registered', 'register']
- Resolved Nodes: 5
- Subgraph Nodes: 22
- Subgraph Edges: 27
- top_k: 5
- max_hops: 1

### Answer

[EchoLLMProvider — no real LLM configured]
system_prompt length: 496 chars
user_prompt length: 6330 chars
Replace this provider with a real LLMProvider implementation (e.g. AnthropicLLMProvider) to get an actual answer.

---

# Typer

## Graph Statistics

- Python Files: 35
- Graph Nodes: 731
- Graph Edges: 1678

## Question

How are CLI commands registered?

### Timing

- Retrieval time: 0.0106s
- Generation time: 0.0000s
- Total time: 0.0106s

### Retrieved Nodes

- **TyperCLIGroup.list_commands** (Method) [score=44.00] repos\typer\typer\cli.py:55
- **TyperGroup._click_resolve_command** (Method) [score=43.00] repos\typer\typer\core.py:1148
- **TyperGroup.format_commands** (Method) [score=43.00] repos\typer\typer\core.py:1048
- **TyperCLIGroup.get_command** (Method) [score=41.00] repos\typer\typer\cli.py:59
- **_complete_visible_commands** (Function) [score=41.00] repos\typer\typer\_click\core.py:42

### Retrieval Metadata

- Intent Categories: ['routing']
- Keywords: ['cli', 'commands', 'command', 'registered', 'register']
- Resolved Nodes: 5
- Subgraph Nodes: 13
- Subgraph Edges: 17
- top_k: 5
- max_hops: 1

### Answer

[EchoLLMProvider — no real LLM configured]
system_prompt length: 496 chars
user_prompt length: 6027 chars
Replace this provider with a real LLMProvider implementation (e.g. AnthropicLLMProvider) to get an actual answer.

---

## Question

How are command arguments parsed?

### Timing

- Retrieval time: 0.0152s
- Generation time: 0.0000s
- Total time: 0.0152s

### Retrieved Nodes

- **get_install_completion_arguments** (Function) [score=48.00] repos\typer\typer\main.py:112
- **_OptionParser.add_argument** (Method) [score=44.00] repos\typer\typer\_click\parser.py:265
- **Command.parse_args** (Method) [score=40.00] repos\typer\typer\_click\core.py:717
- **Argument** (Function) [score=39.00] repos\typer\typer\params.py:1007
- **TyperArgument._parse_decls** (Method) [score=39.00] repos\typer\typer\core.py:404

### Retrieval Metadata

- Intent Categories: ['parsing']
- Keywords: ['command', 'arguments', 'argument', 'parsed', 'pars']
- Resolved Nodes: 5
- Subgraph Nodes: 21
- Subgraph Edges: 22
- top_k: 5
- max_hops: 1

### Answer

[EchoLLMProvider — no real LLM configured]
system_prompt length: 496 chars
user_prompt length: 6516 chars
Replace this provider with a real LLMProvider implementation (e.g. AnthropicLLMProvider) to get an actual answer.

---

## Question

How are options defined?

### Timing

- Retrieval time: 0.0089s
- Generation time: 0.0220s
- Total time: 0.0310s

### Retrieved Nodes

- **Command.format_options** (Method) [score=37.00] repos\typer\typer\_click\core.py:681
- **TyperGroup.format_options** (Method) [score=37.00] repos\typer\typer\core.py:1132
- **TyperCommand.format_options** (Method) [score=36.00] repos\typer\typer\core.py:936
- **_print_options_panel** (Function) [score=36.00] repos\typer\typer\rich_utils.py:351
- **_typer_format_options** (Function) [score=36.00] repos\typer\typer\core.py:857

### Retrieval Metadata

- Intent Categories: ['configuration']
- Keywords: ['options', 'option', 'defined', 'defin']
- Resolved Nodes: 5
- Subgraph Nodes: 12
- Subgraph Edges: 17
- top_k: 5
- max_hops: 1

### Answer

[EchoLLMProvider — no real LLM configured]
system_prompt length: 496 chars
user_prompt length: 5887 chars
Replace this provider with a real LLMProvider implementation (e.g. AnthropicLLMProvider) to get an actual answer.

---

## Question

How is help text generated?

### Timing

- Retrieval time: 0.0407s
- Generation time: 0.0000s
- Total time: 0.0407s

### Retrieved Nodes

- **Command.format_help_text** (Method) [score=49.00] repos\typer\typer\_click\core.py:658
- **_get_help_text** (Function) [score=48.00] repos\typer\typer\rich_utils.py:188
- **_sanitize_help_text** (Function) [score=46.00] repos\typer\typer\_completion_classes.py:19
- **Context.get_help** (Method) [score=39.00] repos\typer\typer\_click\core.py:468
- **HelpFormatter.write_text** (Method) [score=37.00] repos\typer\typer\_click\formatting.py:172

### Retrieval Metadata

- Intent Categories: ['generation']
- Keywords: ['help', 'text', 'generated', 'generat']
- Resolved Nodes: 5
- Subgraph Nodes: 17
- Subgraph Edges: 17
- top_k: 5
- max_hops: 1

### Answer

[EchoLLMProvider — no real LLM configured]
system_prompt length: 496 chars
user_prompt length: 6122 chars
Replace this provider with a real LLMProvider implementation (e.g. AnthropicLLMProvider) to get an actual answer.

---

## Question

How are callbacks executed?

### Timing

- Retrieval time: 0.0115s
- Generation time: 0.0039s
- Total time: 0.0154s

### Retrieved Nodes

- **get_callback** (Function) [score=41.00] repos\typer\typer\main.py:1487
- **callback** (Function) [score=39.00] repos\typer\scripts\docs.py:22
- **Typer.callback** (Method) [score=38.00] repos\typer\typer\main.py:549
- **get_param_callback** (Function) [score=38.00] repos\typer\typer\main.py:1786
- **install_callback** (Function) [score=37.00] repos\typer\typer\completion.py:30

### Retrieval Metadata

- Intent Categories: ['execution']
- Keywords: ['callbacks', 'callback', 'executed', 'execut']
- Resolved Nodes: 5
- Subgraph Nodes: 29
- Subgraph Edges: 47
- top_k: 5
- max_hops: 1

### Answer

[EchoLLMProvider — no real LLM configured]
system_prompt length: 496 chars
user_prompt length: 7847 chars
Replace this provider with a real LLMProvider implementation (e.g. AnthropicLLMProvider) to get an actual answer.

---

# Requests

## Graph Statistics

- Python Files: 20
- Graph Nodes: 358
- Graph Edges: 760

## Question

How are HTTP requests executed?

### Timing

- Retrieval time: 0.0087s
- Generation time: 0.0000s
- Total time: 0.0087s

### Retrieved Nodes

- **HTTPAdapter.send** (Method) [score=39.00] repos\requests\src\requests\adapters.py:634
- **HTTPDigestAuth.__call__** (Method) [score=38.00] repos\requests\src\requests\auth.py:321
- **HTTPAdapter.request_url** (Method) [score=37.00] repos\requests\src\requests\adapters.py:565
- **HTTPBasicAuth.__call__** (Method) [score=37.00] repos\requests\src\requests\auth.py:111
- **HTTPProxyAuth.__call__** (Method) [score=36.00] repos\requests\src\requests\auth.py:119

### Retrieval Metadata

- Intent Categories: ['routing', 'execution']
- Keywords: ['http', 'requests', 'request', 'executed', 'execut']
- Resolved Nodes: 5
- Subgraph Nodes: 21
- Subgraph Edges: 21
- top_k: 5
- max_hops: 1

### Answer

[EchoLLMProvider — no real LLM configured]
system_prompt length: 496 chars
user_prompt length: 6425 chars
Replace this provider with a real LLMProvider implementation (e.g. AnthropicLLMProvider) to get an actual answer.

---

## Question

How are sessions managed?

### Timing

- Retrieval time: 0.0051s
- Generation time: 0.0004s
- Total time: 0.0054s

### Retrieved Nodes

- **HTTPAdapter.init_poolmanager** (Method) [score=31.00] repos\requests\src\requests\adapters.py:239
- **Session.send** (Method) [score=31.00] repos\requests\src\requests\sessions.py:752
- **HTTPAdapter.build_connection_pool_key_attributes** (Method) [score=30.00] repos\requests\src\requests\adapters.py:403
- **SessionRedirectMixin.send** (Method) [score=28.00] repos\requests\src\requests\sessions.py:132
- **HTTPAdapter.proxy_manager_for** (Method) [score=27.00] repos\requests\src\requests\adapters.py:269

### Retrieval Metadata

- Intent Categories: ['authentication']
- Keywords: ['sessions', 'session', 'managed', 'manag']
- Resolved Nodes: 5
- Subgraph Nodes: 14
- Subgraph Edges: 15
- top_k: 5
- max_hops: 1

### Answer

[EchoLLMProvider — no real LLM configured]
system_prompt length: 496 chars
user_prompt length: 5346 chars
Replace this provider with a real LLMProvider implementation (e.g. AnthropicLLMProvider) to get an actual answer.

---

## Question

How are adapters used?

### Timing

- Retrieval time: 0.0018s
- Generation time: 0.0003s
- Total time: 0.0021s

### Retrieved Nodes

- **repos\requests\src\requests\adapters.py** (File) [score=22.00] repos\requests\src\requests\adapters.py
- **Session.get_adapter** (Method) [score=15.00] repos\requests\src\requests\sessions.py:870
- **BaseAdapter** (Class) [score=14.00] repos\requests\src\requests\adapters.py:122
- **HTTPAdapter** (Class) [score=14.00] repos\requests\src\requests\adapters.py:158
- **HTTPAdapter.build_response** (Method) [score=10.00] repos\requests\src\requests\adapters.py:365

### Retrieval Metadata

- Intent Categories: ['unknown']
- Keywords: ['adapters', 'adapt']
- Resolved Nodes: 5
- Subgraph Nodes: 41
- Subgraph Edges: 45
- top_k: 5
- max_hops: 1

### Answer

[EchoLLMProvider — no real LLM configured]
system_prompt length: 496 chars
user_prompt length: 9025 chars
Replace this provider with a real LLMProvider implementation (e.g. AnthropicLLMProvider) to get an actual answer.

---

## Question

How are redirects handled?

### Timing

- Retrieval time: 0.0028s
- Generation time: 0.0001s
- Total time: 0.0029s

### Retrieved Nodes

- **SessionRedirectMixin.resolve_redirects** (Method) [score=28.00] repos\requests\src\requests\sessions.py:186
- **HTTPDigestAuth.handle_redirect** (Method) [score=27.00] repos\requests\src\requests\auth.py:268
- **TooManyRedirects** (Class) [score=23.00] repos\requests\src\requests\exceptions.py:106
- **Response.is_redirect** (Method) [score=17.00] repos\requests\src\requests\models.py:877
- **HTTPDigestAuth.handle_401** (Method) [score=14.00] repos\requests\src\requests\auth.py:273

### Retrieval Metadata

- Intent Categories: ['unknown']
- Keywords: ['redirects', 'redirect', 'handled', 'handl']
- Resolved Nodes: 5
- Subgraph Nodes: 18
- Subgraph Edges: 18
- top_k: 5
- max_hops: 1

### Answer

[EchoLLMProvider — no real LLM configured]
system_prompt length: 496 chars
user_prompt length: 6149 chars
Replace this provider with a real LLMProvider implementation (e.g. AnthropicLLMProvider) to get an actual answer.

---

## Question

How are responses processed?

### Timing

- Retrieval time: 0.0039s
- Generation time: 0.0000s
- Total time: 0.0039s

### Retrieved Nodes

- **stream_decode_response_unicode** (Function) [score=26.00] repos\requests\src\requests\utils.py:594
- **Response.iter_content** (Method) [score=25.00] repos\requests\src\requests\models.py:907
- **Response.links** (Method) [score=24.00] repos\requests\src\requests\models.py:1127
- **Response.__init__** (Method) [score=23.00] repos\requests\src\requests\models.py:765
- **Response.content** (Method) [score=23.00] repos\requests\src\requests\models.py:1035

### Retrieval Metadata

- Intent Categories: ['transformation']
- Keywords: ['responses', 'respons', 'processed', 'process']
- Resolved Nodes: 5
- Subgraph Nodes: 15
- Subgraph Edges: 16
- top_k: 5
- max_hops: 1

### Answer

[EchoLLMProvider — no real LLM configured]
system_prompt length: 496 chars
user_prompt length: 5134 chars
Replace this provider with a real LLMProvider implementation (e.g. AnthropicLLMProvider) to get an actual answer.

---

# Summary

- Total Questions: 15
- Successful Questions: 15
- Failed Questions: 0
- Average Retrieval Time: 0.0095s
- Average Generation Time: 0.0022s
