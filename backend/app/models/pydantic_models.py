from enum import Enum
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Repository request
# ---------------------------------------------------------------------------

class RepositoryRequest(BaseModel):
    repo_url: str


# ---------------------------------------------------------------------------
# Repository summary (filesystem level — unchanged)
# ---------------------------------------------------------------------------

class RepositorySummary(BaseModel):

    repository_name: str
    repository_path: str

    repository_type: str
    framework: str | None

    total_files: int
    total_directories: int

    repository_size_bytes: int

    language_distribution: dict[str, int]
    file_extension_distribution: dict[str, int]
    file_category_distribution: dict[str, int]

    top_level_directories: list[str]
    largest_files: list[dict]


# ---------------------------------------------------------------------------
# Node types
# ---------------------------------------------------------------------------

class NodeType(str, Enum):
    """
    Enumerated node types for the repository knowledge graph.

    FILE     — A Python source file (.py).  Unit of import and deployment.
    MODULE   — A dotted import path, e.g. "os.path", "fastapi", "app.utils".
               Separates stdlib / third-party / internal concerns.
               Makes dependency analysis first-class.
    CLASS    — A class definition.  Hub for INHERITS, CONTAINS, INSTANTIATES.
    FUNCTION — A module-level (top-level) function.
    METHOD   — A function defined inside a class body.
               Kept separate from FUNCTION so that OVERRIDES can be expressed
               and so that class-level call graphs stay unambiguous.
    """

    FILE = "File"
    MODULE = "Module"
    CLASS = "Class"
    FUNCTION = "Function"
    METHOD = "Method"


class ModuleOrigin(str, Enum):
    """
    Where a Module node comes from.
    Lets consumers filter "only internal" or "only third-party" without
    running an extra resolver pass.
    """
    STDLIB = "stdlib"
    THIRD_PARTY = "third_party"
    INTERNAL = "internal"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Edge / relationship types
# ---------------------------------------------------------------------------

class RelationshipType(str, Enum):
    """
    Enumerated edge types for the repository knowledge graph.

    CONTAINS    — Structural containment.
                  File → Class, File → Function, Class → Method.
                  Enables hierarchical traversal and scope resolution.

    IMPORTS     — File imports a Module.
                  Backbone of dependency and blast-radius analysis.

    CALLS       — A Function or Method calls another Function or Method.
                  Core of the call graph; used for impact analysis and RAG
                  ("what would break if I change X?").

    INHERITS    — Class inherits from another Class.
                  OOP hierarchy; combined with OVERRIDES enables full MRO
                  impact analysis.

    INSTANTIATES — A Function or Method constructs an instance of a Class
                   via a direct call whose callee name matches a known class.
                   Example: `session = DatabaseSession()`.
                   Critical for dependency injection tracing and lifetime
                   analysis ("who creates a RedisClient?").

    DECORATES   — A decorator is applied to a Function, Method, or Class.
                  Stored as: decorator_ref → target.
                  Framework-agnostic: captures @router.get, @task,
                  @pytest.fixture, @property, @staticmethod, @cached_property,
                  @login_required, etc.
                  Essential for answering "which functions are API endpoints?"
                  or "which are Airflow tasks?" without hardcoding framework
                  names.

    OVERRIDES   — A Method in a subclass overrides a Method with the same name
                  in a direct parent class (detected via INHERITS + method name
                  matching).
                  Enables precise impact analysis: changing a base method
                  signature propagates to all OVERRIDES edges.

    NOT IMPLEMENTED (and why):
    - RETURNS   : requires type inference beyond what the AST provides reliably.
    - REFERENCES: "name appears in scope" is too broad without a full symbol
                  resolver; would produce massive false-positive noise.
    - USES      : same problem as REFERENCES — too ambiguous at AST level.
    """

    CONTAINS = "contains"
    IMPORTS = "imports"
    CALLS = "calls"
    INHERITS = "inherits"
    INSTANTIATES = "instantiates"
    DECORATES = "decorates"
    OVERRIDES = "overrides"


# ---------------------------------------------------------------------------
# Parsed AST models (output of CodeParser)
# ---------------------------------------------------------------------------

class ParsedDecorator(BaseModel):
    """A single decorator applied to a function, method, or class."""

    name: str
    """
    Best-effort string representation of the decorator reference.
    For `@property`            → "property"
    For `@router.get`          → "router.get"
    For `@app.route("/path")`  → "app.route"
    The argument list is intentionally dropped; we capture the reference,
    not the invocation, to keep the graph schema stable.
    """

    is_call: bool
    """True when the decorator is invoked with arguments: @decorator(...)."""


class ParsedFunction(BaseModel):

    name: str
    line_number: int
    arguments: list[str]
    return_type: str | None
    docstring: str | None

    calls: list[str]
    """Names of callables invoked inside this function body."""

    instantiates: list[str]
    """
    Names of classes directly instantiated inside this function body.
    Extracted when a Call node's callee is a known class name (resolved
    in a second pass by GraphBuilder after the full symbol table is built).
    At parse time this contains ALL calls; GraphBuilder filters to classes.
    """

    decorators: list[ParsedDecorator]
    """Decorators applied to this function, in source order."""


class ParsedClass(BaseModel):

    name: str
    line_number: int
    inherits_from: list[str] = []
    docstring: str | None = None

    methods: list[ParsedFunction]

    decorators: list[ParsedDecorator]
    """Decorators applied to this class."""


class ParsedFile(BaseModel):

    file_path: str

    imports: list[str]
    """
    Deduplicated list of dotted module paths imported by this file.
    These become Module nodes; the File→Module edge is IMPORTS.
    """

    classes: list[ParsedClass]
    functions: list[ParsedFunction]


class ParsedRepository(BaseModel):

    repository_name: str
    total_python_files: int
    files: list[ParsedFile]


# ---------------------------------------------------------------------------
# Graph models (output of GraphBuilder)
# ---------------------------------------------------------------------------

class GraphNode(BaseModel):
    """
    A typed node in the repository knowledge graph.

    Using typed nodes (instead of bare strings) allows graph databases,
    vector stores, and RAG retrievers to filter by node type without
    parsing the node ID.
    """

    id: str
    """
    Stable unique identifier for this node.
    Convention:
      File     → absolute or repo-relative path, e.g. "app/utils.py"
      Module   → dotted import path, e.g. "os.path" or "fastapi"
      Class    → "ClassName"  (or "module::ClassName" when ambiguous)
      Function → "function_name"
      Method   → "ClassName.method_name"
    """

    type: NodeType

    label: str
    """Human-readable short label (last component of id)."""

    # Optional enrichment fields — present when available
    file_path: str | None = None
    line_number: int | None = None
    docstring: str | None = None
    module_origin: ModuleOrigin | None = None  # Only for MODULE nodes


class GraphEdge(BaseModel):
    """A typed, directed edge in the repository knowledge graph."""

    source: str
    """ID of the source node."""

    target: str
    """ID of the target node."""

    relationship: RelationshipType

    # Optional enrichment
    decorator_name: str | None = None
    """For DECORATES edges: the decorator string representation."""


class RepositoryGraph(BaseModel):

    nodes: list[GraphNode]
    edges: list[GraphEdge]


# ---------------------------------------------------------------------------
# Graph statistics
# ---------------------------------------------------------------------------

class NodeDegree(BaseModel):
    """A node ID paired with its total degree (in + out edges)."""
    node_id: str
    degree: int


class GraphStatistics(BaseModel):

    total_nodes: int
    total_edges: int

    nodes_by_type: dict[str, int]
    """Count of nodes per NodeType value."""

    edges_by_type: dict[str, int]
    """Count of edges per RelationshipType value."""

    most_connected_nodes: list[str]
    """
    Top-10 node IDs by total degree (in + out), regardless of type.
    Preserved for backward compatibility.
    """

    # ------------------------------------------------------------------
    # Task 2: Per-type degree rankings (top 10 each)
    # ------------------------------------------------------------------

    top_files_by_degree: list[NodeDegree]
    """Top-10 File nodes by total degree."""

    top_classes_by_degree: list[NodeDegree]
    """Top-10 Class nodes by total degree."""

    top_functions_by_degree: list[NodeDegree]
    """Top-10 Function nodes by total degree."""

    top_methods_by_degree: list[NodeDegree]
    """Top-10 Method nodes by total degree."""

    # ------------------------------------------------------------------
    # Task 3: Architectural hotspots
    # ------------------------------------------------------------------

    architectural_hotspots: list[NodeDegree]
    """
    Top-10 most connected nodes regardless of type.
    Intended for repository summaries, architecture explanations, and
    GraphRAG retrieval ranking.
    """


# ---------------------------------------------------------------------------
# Import edge (lightweight, for import-only consumers)
# ---------------------------------------------------------------------------

class ImportEdge(BaseModel):
    source_file: str
    imported_module: str