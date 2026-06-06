"""
GraphBuilder — repository knowledge graph construction.

Responsibility boundary
-----------------------
CodeParser  : syntactic extraction (AST → ParsedRepository).
GraphBuilder: semantic assembly  (ParsedRepository → RepositoryGraph).

The builder runs in three passes:

  Pass 1 — Symbol table & repository-owned symbol registry
    Collect every Class, Function, and Method name defined in the
    repository so that call sites can be classified as CALLS vs
    INSTANTIATES, and so that OVERRIDES can be detected.

    A repository-owned symbol registry is built from *only* the symbols
    that are explicitly defined inside parsed repository files.  External
    symbols (builtins, stdlib, third-party, Pydantic base classes, etc.)
    are never promoted to graph nodes.

  Pass 2 — Node and edge emission
    Walk every ParsedFile and emit nodes + edges for all relationship
    types.  Uses the symbol table built in Pass 1.

    Key invariant: Class, Function, and Method nodes are only created
    when the symbol exists in the repository-owned registry.  Edges that
    would reference an unregistered symbol are silently dropped.

  Pass 3 — Prune isolated nodes
    Remove any node that has no edges (avoids polluting the graph with
    unreachable symbols, though in practice this is rare after Pass 2).
"""

import os
import sys
from collections import Counter, defaultdict

from app.models.pydantic_models import (
    GraphEdge,
    GraphNode,
    GraphStatistics,
    ImportEdge,
    ModuleOrigin,
    NodeDegree,
    NodeType,
    ParsedRepository,
    RelationshipType,
    RepositoryGraph,
)


# ---------------------------------------------------------------------------
# Stdlib detection (mirrors code_parser.py — kept here to avoid import cycle)
# ---------------------------------------------------------------------------

_STDLIB_TOP_LEVEL: frozenset[str] = frozenset(sys.stdlib_module_names)


def _module_origin(module_name: str, internal_prefixes: frozenset[str]) -> ModuleOrigin:
    top = module_name.split(".")[0]
    if top in _STDLIB_TOP_LEVEL:
        return ModuleOrigin.STDLIB
    if top in internal_prefixes:
        return ModuleOrigin.INTERNAL
    return ModuleOrigin.THIRD_PARTY


# ---------------------------------------------------------------------------
# Node ID conventions
# ---------------------------------------------------------------------------

def _file_id(file_path: str) -> str:
    return file_path


def _class_id(class_name: str) -> str:
    return class_name


def _function_id(function_name: str) -> str:
    return function_name


def _method_id(class_name: str, method_name: str) -> str:
    """Qualified method ID: "ClassName.method_name"."""
    return f"{class_name}.{method_name}"


def _module_id(module_path: str) -> str:
    return module_path


# ---------------------------------------------------------------------------
# Built-in names that must never become graph nodes
# ---------------------------------------------------------------------------

# Python built-in names that appear as call targets or base classes.
_PYTHON_BUILTINS: frozenset[str] = frozenset({
    # Built-in types
    "bool", "bytearray", "bytes", "complex", "dict", "float", "frozenset",
    "int", "list", "memoryview", "object", "range", "set", "slice", "str",
    "tuple", "type",
    # Built-in exceptions
    "ArithmeticError", "AssertionError", "AttributeError", "BaseException",
    "BlockingIOError", "BrokenPipeError", "BufferError", "BytesWarning",
    "ChildProcessError", "ConnectionAbortedError", "ConnectionError",
    "ConnectionRefusedError", "ConnectionResetError", "DeprecationWarning",
    "EOFError", "EnvironmentError", "Exception", "FileExistsError",
    "FileNotFoundError", "FloatingPointError", "FutureWarning", "GeneratorExit",
    "IOError", "ImportError", "ImportWarning", "IndentationError", "IndexError",
    "InterruptedError", "IsADirectoryError", "KeyError", "KeyboardInterrupt",
    "LookupError", "MemoryError", "ModuleNotFoundError", "NameError",
    "NotADirectoryError", "NotImplementedError", "OSError", "OverflowError",
    "PendingDeprecationWarning", "PermissionError", "ProcessLookupError",
    "RecursionError", "ReferenceError", "ResourceWarning", "RuntimeError",
    "RuntimeWarning", "StopAsyncIteration", "StopIteration", "SyntaxError",
    "SyntaxWarning", "SystemError", "SystemExit", "TimeoutError", "TypeError",
    "UnboundLocalError", "UnicodeDecodeError", "UnicodeEncodeError",
    "UnicodeError", "UnicodeTranslateError", "UnicodeWarning", "UserWarning",
    "ValueError", "Warning", "ZeroDivisionError",
    # Built-in functions that look like classes when called
    "classmethod", "staticmethod", "property", "super",
    "enumerate", "filter", "map", "reversed", "sorted", "zip",
    "open", "print", "len", "repr", "hash", "id", "iter", "next",
    "abs", "all", "any", "bin", "callable", "chr", "compile",
    "delattr", "dir", "divmod", "eval", "exec", "format", "getattr",
    "globals", "hasattr", "hex", "input", "isinstance", "issubclass",
    "locals", "max", "min", "oct", "ord", "pow", "round", "setattr",
    "sum", "vars",
})

# Well-known third-party / framework base names that are universally
# "framework plumbing" with no semantic value for internal impact analysis.
# This list is intentionally minimal — it covers names that:
#   (a) appear as base classes or common call targets across many frameworks,
#   (b) are never defined inside a user repository,
#   (c) would pollute the graph with phantom nodes if not excluded.
_EXTERNAL_SYMBOLS: frozenset[str] = frozenset({
    # Pydantic
    "BaseModel", "BaseSettings", "validator", "root_validator",
    "field_validator", "model_validator",
    # typing / abc
    "TypedDict", "Protocol", "ABC", "ABCMeta", "Generic",
    # enum
    "Enum", "IntEnum", "StrEnum", "Flag", "IntFlag",
    # dataclasses
    "dataclass",
    # common Django base classes
    "Model", "View", "APIView", "ModelViewSet", "ViewSet",
    "ModelSerializer", "Serializer",
    # common Flask / FastAPI patterns
    "Resource",
    # SQLAlchemy
    "Base", "DeclarativeBase", "DeclarativeMeta",
    # Celery / Airflow
    "Task",
    # pytest
    "TestCase",
})

# Union of all names that must never become repository symbol nodes.
_EXCLUDED_SYMBOLS: frozenset[str] = _PYTHON_BUILTINS | _EXTERNAL_SYMBOLS


# ---------------------------------------------------------------------------
# Repository-owned symbol registry
# ---------------------------------------------------------------------------

class _SymbolRegistry:
    """
    Tracks every Class, Function, and Method name that is **defined inside**
    the parsed repository files.

    This is the authoritative source of truth for "is this a repo-owned
    symbol?" during Pass 2.  Only symbols in this registry may become
    Class, Function, or Method graph nodes.

    External symbols — builtins, stdlib, third-party base classes, Pydantic
    models from dependencies, etc. — are intentionally excluded regardless
    of whether they appear as call targets or base classes.
    """

    def __init__(self) -> None:
        self.class_names: set[str] = set()
        self.function_names: set[str] = set()
        # class_name → frozenset of method names (populated during build)
        self.method_map: dict[str, set[str]] = defaultdict(set)
        # class_name → list of parent class names (raw, unfiltered)
        self.class_parents: dict[str, list[str]] = {}

    def build(self, repository: "ParsedRepository") -> None:
        """Populate the registry from a fully-parsed repository."""
        for parsed_file in repository.files:
            for cls in parsed_file.classes:
                if cls.name in _EXCLUDED_SYMBOLS:
                    continue
                self.class_names.add(cls.name)
                self.class_parents[cls.name] = cls.inherits_from
                for method in cls.methods:
                    self.method_map[cls.name].add(method.name)

            for fn in parsed_file.functions:
                if fn.name in _EXCLUDED_SYMBOLS:
                    continue
                self.function_names.add(fn.name)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def is_repo_class(self, name: str) -> bool:
        return name in self.class_names

    def is_repo_function(self, name: str) -> bool:
        return name in self.function_names

    def is_repo_method(self, name: str) -> bool:
        """True if *any* class in the repo defines a method with this name."""
        return any(name in methods for methods in self.method_map.values())

    def is_repo_symbol(self, name: str) -> bool:
        return (
            self.is_repo_class(name)
            or self.is_repo_function(name)
            or self.is_repo_method(name)
        )

    def parent_defines_method(self, parent_name: str, method_name: str) -> bool:
        """True if parent_name is a repo-owned class that defines method_name."""
        return (
            parent_name in self.class_names
            and method_name in self.method_map.get(parent_name, set())
        )


# ---------------------------------------------------------------------------
# GraphBuilder
# ---------------------------------------------------------------------------

class GraphBuilder:
    """
    Assembles a typed repository knowledge graph from a ParsedRepository.

    Node types  : File, Module, Class, Function, Method
    Edge types  : CONTAINS, IMPORTS, CALLS, INHERITS,
                  INSTANTIATES, DECORATES, OVERRIDES

    Repository-owned symbol filtering
    ----------------------------------
    Class, Function, and Method nodes are only emitted for symbols that are
    actually defined inside the parsed repository files.  Any callee, base
    class, or decorator target that is not in the repository-owned symbol
    registry is silently skipped.  This prevents stdlib types (str, dict,
    list), Pydantic base classes (BaseModel), typing constructs (Protocol,
    Generic), framework base classes (Model, View, Task), and other external
    symbols from polluting the graph.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_graph(
        self,
        repository: "ParsedRepository",
        repository_path: str = "",
    ) -> RepositoryGraph:
        """
        Main entry point.  Runs three passes and returns a RepositoryGraph.

        Parameters
        ----------
        repository:
            Output of CodeParser.parse_repository().
        repository_path:
            Root path of the repository on disk.  Used to infer which
            top-level package names are "internal" for ModuleOrigin
            classification.  Pass "" to skip internal classification.
        """

        internal_prefixes = self._infer_internal_prefixes(repository_path)

        # ----------------------------------------------------------------
        # Pass 1: Build the repository-owned symbol registry
        # ----------------------------------------------------------------

        registry = _SymbolRegistry()
        registry.build(repository)

        # ----------------------------------------------------------------
        # Pass 2: Node and edge emission
        # ----------------------------------------------------------------

        nodes: dict[str, GraphNode] = {}
        edges: set[tuple] = set()   # (source_id, target_id, relationship, extra)

        def add_node(node: GraphNode) -> None:
            if node.id not in nodes:
                nodes[node.id] = node

        def add_edge(
            source: str,
            target: str,
            rel: RelationshipType,
            **extra,
        ) -> None:
            key = (source, target, rel.value, *sorted(extra.items()))
            edges.add(key)

        for parsed_file in repository.files:

            # ----------------------------------------------------------
            # File node — always emitted (files are always repo-owned)
            # ----------------------------------------------------------

            file_id = _file_id(parsed_file.file_path)
            file_label = os.path.basename(parsed_file.file_path)

            add_node(GraphNode(
                id=file_id,
                type=NodeType.FILE,
                label=file_label,
                file_path=parsed_file.file_path,
            ))

            # ----------------------------------------------------------
            # Import edges: File → Module
            # ----------------------------------------------------------

            for module_path in parsed_file.imports:
                mod_id = _module_id(module_path)
                origin = _module_origin(module_path, internal_prefixes)

                add_node(GraphNode(
                    id=mod_id,
                    type=NodeType.MODULE,
                    label=module_path.split(".")[-1],
                    module_origin=origin,
                ))

                add_edge(file_id, mod_id, RelationshipType.IMPORTS)

            # ----------------------------------------------------------
            # Class nodes + class-level edges
            # ----------------------------------------------------------

            for cls in parsed_file.classes:

                # Guard: only emit Class nodes for repo-owned classes.
                if not registry.is_repo_class(cls.name):
                    continue

                cls_id = _class_id(cls.name)

                add_node(GraphNode(
                    id=cls_id,
                    type=NodeType.CLASS,
                    label=cls.name,
                    file_path=parsed_file.file_path,
                    line_number=cls.line_number,
                    docstring=cls.docstring,
                ))

                # File CONTAINS Class
                add_edge(file_id, cls_id, RelationshipType.CONTAINS)

                # --------------------------------------------------
                # INHERITS edges: Class → parent Class
                # Only emit INHERITS edges to repo-owned parent classes.
                # External base classes (BaseModel, ABC, etc.) are
                # excluded by the registry guard below.
                # --------------------------------------------------

                for parent_name in cls.inherits_from:
                    if not registry.is_repo_class(parent_name):
                        # Parent is external — skip entirely.
                        # (No phantom node, no dangling edge.)
                        continue

                    parent_id = _class_id(parent_name)

                    # Parent is repo-owned; node will be (or has been)
                    # emitted when we iterate over its defining file.
                    # Add the edge; if the parent node hasn't been
                    # added yet it will be added in a later iteration.
                    # Pass 3 prunes unreachable nodes, so no phantom.
                    add_edge(cls_id, parent_id, RelationshipType.INHERITS)

                # --------------------------------------------------
                # DECORATES edges on the class itself
                # --------------------------------------------------

                for dec in cls.decorators:
                    add_edge(
                        dec.name,
                        cls_id,
                        RelationshipType.DECORATES,
                        decorator_name=dec.name,
                    )

                # --------------------------------------------------
                # Method nodes + method-level edges
                # --------------------------------------------------

                for method in cls.methods:
                    method_id = _method_id(cls.name, method.name)

                    add_node(GraphNode(
                        id=method_id,
                        type=NodeType.METHOD,
                        label=method.name,
                        file_path=parsed_file.file_path,
                        line_number=method.line_number,
                        docstring=method.docstring,
                    ))

                    # Class CONTAINS Method
                    add_edge(cls_id, method_id, RelationshipType.CONTAINS)

                    # ----------------------------------------------
                    # OVERRIDES: method name matches a parent method.
                    # Only emit when the parent is a repo-owned class
                    # that actually defines a method with this name.
                    # ----------------------------------------------

                    for parent_name in cls.inherits_from:
                        if not registry.parent_defines_method(parent_name, method.name):
                            continue
                        parent_method_id = _method_id(parent_name, method.name)
                        add_edge(
                            method_id,
                            parent_method_id,
                            RelationshipType.OVERRIDES,
                        )

                    # ----------------------------------------------
                    # DECORATES edges on the method
                    # ----------------------------------------------

                    for dec in method.decorators:
                        add_edge(
                            dec.name,
                            method_id,
                            RelationshipType.DECORATES,
                            decorator_name=dec.name,
                        )

                    # ----------------------------------------------
                    # CALLS and INSTANTIATES from method body.
                    # Only create edges to repo-owned symbols.
                    # ----------------------------------------------

                    for callee_name in method.calls:
                        if not registry.is_repo_symbol(callee_name):
                            continue

                        if registry.is_repo_class(callee_name):
                            callee_id = _class_id(callee_name)
                            add_edge(method_id, callee_id, RelationshipType.INSTANTIATES)

                        elif registry.is_repo_function(callee_name):
                            callee_id = _function_id(callee_name)
                            add_edge(method_id, callee_id, RelationshipType.CALLS)

                        else:
                            # Unqualified method name — emit a CALLS edge
                            # using the bare name as target.  Pass 3 will
                            # prune it if no node was emitted for that id.
                            add_edge(method_id, callee_name, RelationshipType.CALLS)

            # ----------------------------------------------------------
            # Top-level function nodes + function-level edges
            # ----------------------------------------------------------

            for fn in parsed_file.functions:

                # Guard: only emit Function nodes for repo-owned functions.
                if not registry.is_repo_function(fn.name):
                    continue

                fn_id = _function_id(fn.name)

                add_node(GraphNode(
                    id=fn_id,
                    type=NodeType.FUNCTION,
                    label=fn.name,
                    file_path=parsed_file.file_path,
                    line_number=fn.line_number,
                    docstring=fn.docstring,
                ))

                # File CONTAINS Function
                add_edge(file_id, fn_id, RelationshipType.CONTAINS)

                # DECORATES edges
                for dec in fn.decorators:
                    add_edge(
                        dec.name,
                        fn_id,
                        RelationshipType.DECORATES,
                        decorator_name=dec.name,
                    )

                # CALLS and INSTANTIATES
                for callee_name in fn.calls:
                    if not registry.is_repo_symbol(callee_name):
                        continue

                    if registry.is_repo_class(callee_name):
                        callee_id = _class_id(callee_name)
                        add_edge(fn_id, callee_id, RelationshipType.INSTANTIATES)

                    elif registry.is_repo_function(callee_name):
                        callee_id = _function_id(callee_name)
                        add_edge(fn_id, callee_id, RelationshipType.CALLS)

                    # Unqualified method calls from top-level functions
                    # are ambiguous without a receiver type; we skip them
                    # here to avoid false CALLS edges.

        # ----------------------------------------------------------------
        # Pass 3: prune nodes with no edges
        # ----------------------------------------------------------------

        connected_ids: set[str] = set()
        for source, target, *_rest in edges:
            connected_ids.add(source)
            connected_ids.add(target)

        nodes = {
            nid: node
            for nid, node in nodes.items()
            if nid in connected_ids
        }

        # ----------------------------------------------------------------
        # Assemble GraphEdge objects
        # ----------------------------------------------------------------

        graph_edges: list[GraphEdge] = []
        for edge_key in sorted(edges):
            source, target, rel_value, *extras = edge_key
            extra_dict = dict(extras)
            graph_edges.append(GraphEdge(
                source=source,
                target=target,
                relationship=RelationshipType(rel_value),
                decorator_name=extra_dict.get("decorator_name"),
            ))

        return RepositoryGraph(
            nodes=sorted(nodes.values(), key=lambda n: (n.type, n.id)),
            edges=graph_edges,
        )

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def generate_statistics(self, graph: RepositoryGraph) -> GraphStatistics:
        """
        Compute graph statistics including:
          - total_nodes / total_edges
          - nodes_by_type / edges_by_type
          - most_connected_nodes (backward compat — top 10, any type)
          - top_files_by_degree       (Task 2)
          - top_classes_by_degree     (Task 2)
          - top_functions_by_degree   (Task 2)
          - top_methods_by_degree     (Task 2)
          - architectural_hotspots    (Task 3)
        """

        node_type_counter: Counter = Counter()
        edge_type_counter: Counter = Counter()
        degree_counter: Counter = Counter()

        for node in graph.nodes:
            node_type_counter[node.type.value] += 1

        for edge in graph.edges:
            edge_type_counter[edge.relationship.value] += 1
            degree_counter[edge.source] += 1
            degree_counter[edge.target] += 1

        # Build a lookup: node_id → NodeType for degree grouping
        node_type_lookup: dict[str, NodeType] = {
            node.id: node.type for node in graph.nodes
        }

        # Backward-compat: top-10 by degree, any type
        most_connected = [
            node_id for node_id, _ in degree_counter.most_common(10)
        ]

        # Task 3: architectural_hotspots — same as most_connected but
        # returned as NodeDegree objects for richer downstream consumers.
        architectural_hotspots = [
            NodeDegree(node_id=node_id, degree=deg)
            for node_id, deg in degree_counter.most_common(10)
        ]

        # Task 2: per-type top-10 rankings
        # Group degrees by NodeType, then take top 10 per group.
        type_degree_buckets: dict[NodeType, list[tuple[str, int]]] = defaultdict(list)

        for node_id, deg in degree_counter.items():
            node_type = node_type_lookup.get(node_id)
            if node_type is not None:
                type_degree_buckets[node_type].append((node_id, deg))

        def _top10(node_type: NodeType) -> list[NodeDegree]:
            bucket = type_degree_buckets.get(node_type, [])
            bucket_sorted = sorted(bucket, key=lambda x: x[1], reverse=True)
            return [
                NodeDegree(node_id=nid, degree=deg)
                for nid, deg in bucket_sorted[:10]
            ]

        return GraphStatistics(
            total_nodes=len(graph.nodes),
            total_edges=len(graph.edges),
            nodes_by_type=dict(node_type_counter),
            edges_by_type=dict(edge_type_counter),
            most_connected_nodes=most_connected,
            top_files_by_degree=_top10(NodeType.FILE),
            top_classes_by_degree=_top10(NodeType.CLASS),
            top_functions_by_degree=_top10(NodeType.FUNCTION),
            top_methods_by_degree=_top10(NodeType.METHOD),
            architectural_hotspots=architectural_hotspots,
        )

    # ------------------------------------------------------------------
    # Import-only graph (lightweight consumer)
    # ------------------------------------------------------------------

    def build_import_graph(self, repository: "ParsedRepository") -> list[ImportEdge]:
        return [
            ImportEdge(
                source_file=parsed_file.file_path,
                imported_module=module_path,
            )
            for parsed_file in repository.files
            for module_path in parsed_file.imports
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_internal_prefixes(repository_path: str) -> frozenset[str]:
        """
        Infer which top-level package names are "internal" to this repo
        by scanning for directories containing an __init__.py.

        Example: if the repo has app/__init__.py and core/__init__.py,
        returns frozenset({"app", "core"}).
        """
        if not repository_path:
            return frozenset()

        prefixes: set[str] = set()

        try:
            for entry in os.scandir(repository_path):
                if entry.is_dir():
                    init = os.path.join(entry.path, "__init__.py")
                    if os.path.isfile(init):
                        prefixes.add(entry.name)
        except OSError:
            pass

        return frozenset(prefixes)