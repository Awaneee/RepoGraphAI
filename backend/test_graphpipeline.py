"""
test_graph_pipeline.py

Unit and integration tests for the repository knowledge graph pipeline.

Tests cover:
  1. Graph builds successfully from a synthetic ParsedRepository.
  2. Repository-owned symbol filtering (Task 1):
       - External symbols (str, dict, BaseModel, Exception, ABC, Enum, …)
         do NOT become Class/Function/Method nodes.
       - Only symbols defined in the repo's parsed files are promoted.
  3. Statistics build successfully (Task 2):
       - top_files_by_degree, top_classes_by_degree,
         top_functions_by_degree, top_methods_by_degree are populated.
       - Degree values are non-negative integers.
       - At most 10 entries per category.
  4. Hotspot analysis (Task 3):
       - architectural_hotspots is populated.
       - Hotspots are ordered by degree descending.
       - At most 10 entries.

Run with:
    pytest test_graph_pipeline.py -v
"""

import pytest

from app.models.pydantic_models import (
    GraphStatistics,
    NodeDegree,
    NodeType,
    ParsedClass,
    ParsedDecorator,
    ParsedFile,
    ParsedFunction,
    ParsedRepository,
    RelationshipType,
    RepositoryGraph,
)
from app.graph.graph_builder import GraphBuilder, _SymbolRegistry, _EXCLUDED_SYMBOLS


# ---------------------------------------------------------------------------
# Fixtures — synthetic repository
# ---------------------------------------------------------------------------

def _make_function(
    name: str,
    calls: list[str] | None = None,
    decorators: list[ParsedDecorator] | None = None,
) -> ParsedFunction:
    return ParsedFunction(
        name=name,
        line_number=1,
        arguments=[],
        return_type=None,
        docstring=None,
        calls=calls or [],
        instantiates=[],
        decorators=decorators or [],
    )


def _make_class(
    name: str,
    methods: list[ParsedFunction] | None = None,
    inherits_from: list[str] | None = None,
    decorators: list[ParsedDecorator] | None = None,
) -> ParsedClass:
    return ParsedClass(
        name=name,
        line_number=1,
        inherits_from=inherits_from or [],
        docstring=None,
        methods=methods or [],
        decorators=decorators or [],
    )


@pytest.fixture
def simple_repository() -> ParsedRepository:
    """
    A minimal repository with:
      - Two files
      - Three repo-owned classes (Animal, Dog, Cat)
      - Dog inherits Animal (repo-owned parent)
      - Cat inherits BaseModel (external — must be filtered)
      - Several methods
      - One top-level function
      - Calls to both internal and external symbols
    """
    animal_cls = _make_class(
        name="Animal",
        methods=[
            _make_function("speak"),
            _make_function("eat"),
        ],
    )

    dog_cls = _make_class(
        name="Dog",
        inherits_from=["Animal", "BaseModel"],   # BaseModel must be filtered
        methods=[
            _make_function("speak"),              # overrides Animal.speak
            _make_function("fetch", calls=["Animal", "str", "dict"]),
        ],
    )

    # Cat inherits an external base only
    cat_cls = _make_class(
        name="Cat",
        inherits_from=["BaseModel", "ABC"],      # all external
        methods=[
            _make_function("purr"),
        ],
    )

    factory_fn = _make_function(
        name="create_animal",
        calls=["Animal", "Dog", "Exception", "list"],
    )

    file_1 = ParsedFile(
        file_path="app/animals.py",
        imports=["abc", "pydantic"],
        classes=[animal_cls, dog_cls],
        functions=[factory_fn],
    )

    file_2 = ParsedFile(
        file_path="app/cats.py",
        imports=["pydantic"],
        classes=[cat_cls],
        functions=[],
    )

    return ParsedRepository(
        repository_name="test_repo",
        total_python_files=2,
        files=[file_1, file_2],
    )


@pytest.fixture
def builder() -> GraphBuilder:
    return GraphBuilder()


@pytest.fixture
def built_graph(builder: GraphBuilder, simple_repository: ParsedRepository) -> RepositoryGraph:
    return builder.build_graph(simple_repository, repository_path="")


@pytest.fixture
def statistics(builder: GraphBuilder, built_graph: RepositoryGraph) -> GraphStatistics:
    return builder.generate_statistics(built_graph)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _node_ids_by_type(graph: RepositoryGraph, node_type: NodeType) -> set[str]:
    return {n.id for n in graph.nodes if n.type == node_type}


# ---------------------------------------------------------------------------
# Task 1 — Repository-owned symbol filtering
# ---------------------------------------------------------------------------

class TestSymbolRegistry:
    """Unit tests for _SymbolRegistry in isolation."""

    def test_registers_repo_classes(self, simple_repository):
        registry = _SymbolRegistry()
        registry.build(simple_repository)
        assert "Animal" in registry.class_names
        assert "Dog" in registry.class_names
        assert "Cat" in registry.class_names

    def test_registers_repo_functions(self, simple_repository):
        registry = _SymbolRegistry()
        registry.build(simple_repository)
        assert "create_animal" in registry.function_names

    def test_excludes_external_bases(self, simple_repository):
        registry = _SymbolRegistry()
        registry.build(simple_repository)
        assert "BaseModel" not in registry.class_names
        assert "ABC" not in registry.class_names

    def test_is_repo_symbol(self, simple_repository):
        registry = _SymbolRegistry()
        registry.build(simple_repository)
        assert registry.is_repo_symbol("Animal")
        assert registry.is_repo_symbol("speak")        # method name
        assert not registry.is_repo_symbol("BaseModel")
        assert not registry.is_repo_symbol("str")
        assert not registry.is_repo_symbol("dict")
        assert not registry.is_repo_symbol("Exception")

    def test_excluded_symbols_set_coverage(self):
        """Critical external names must be in the exclusion set."""
        must_exclude = {
            # Builtins
            "str", "dict", "list", "tuple", "set", "int", "float", "bool",
            "object", "type", "bytes",
            # Exceptions
            "Exception", "BaseException", "ValueError", "TypeError",
            "RuntimeError", "NotImplementedError",
            # Framework
            "BaseModel", "TypedDict", "Protocol", "ABC",
            "Enum", "IntEnum", "StrEnum",
        }
        for name in must_exclude:
            assert name in _EXCLUDED_SYMBOLS, (
                f"'{name}' must be in _EXCLUDED_SYMBOLS but is missing"
            )


class TestGraphSymbolFiltering:
    """Integration tests: external symbols must not appear as graph nodes."""

    def test_no_basemodel_node(self, built_graph):
        class_ids = _node_ids_by_type(built_graph, NodeType.CLASS)
        assert "BaseModel" not in class_ids, (
            "BaseModel (Pydantic) must not become a Class node"
        )

    def test_no_abc_node(self, built_graph):
        class_ids = _node_ids_by_type(built_graph, NodeType.CLASS)
        assert "ABC" not in class_ids, "ABC must not become a Class node"

    def test_no_exception_node(self, built_graph):
        class_ids = _node_ids_by_type(built_graph, NodeType.CLASS)
        assert "Exception" not in class_ids, "Exception must not become a Class node"

    def test_no_builtin_type_nodes(self, built_graph):
        class_ids = _node_ids_by_type(built_graph, NodeType.CLASS)
        for builtin in ("str", "dict", "list", "tuple", "set", "int", "float"):
            assert builtin not in class_ids, (
                f"Built-in type '{builtin}' must not become a Class node"
            )

    def test_repo_classes_are_present(self, built_graph):
        class_ids = _node_ids_by_type(built_graph, NodeType.CLASS)
        assert "Animal" in class_ids
        assert "Dog" in class_ids
        assert "Cat" in class_ids

    def test_repo_function_is_present(self, built_graph):
        fn_ids = _node_ids_by_type(built_graph, NodeType.FUNCTION)
        assert "create_animal" in fn_ids

    def test_inherits_edge_only_for_repo_parents(self, built_graph):
        """Dog → Animal INHERITS should exist; Dog → BaseModel must not."""
        inherits_edges = [
            e for e in built_graph.edges
            if e.relationship == RelationshipType.INHERITS
        ]
        targets = {e.target for e in inherits_edges}
        assert "Animal" in targets, "Dog should inherit Animal"
        assert "BaseModel" not in targets, "Dog must NOT have INHERITS edge to BaseModel"

    def test_instantiates_edge_only_for_repo_classes(self, built_graph):
        """
        create_animal calls Animal, Dog, Exception, list.
        Only Animal and Dog are repo-owned; Exception and list must be filtered.
        """
        instantiates_edges = [
            e for e in built_graph.edges
            if e.relationship == RelationshipType.INSTANTIATES
        ]
        targets = {e.target for e in instantiates_edges}
        assert "Animal" in targets or "Dog" in targets, (
            "create_animal should INSTANTIATES at least one repo-owned class"
        )
        assert "Exception" not in targets
        assert "list" not in targets

    def test_no_dangling_class_nodes(self, built_graph):
        """Every Class node must have at least one edge."""
        node_ids_with_edges: set[str] = set()
        for edge in built_graph.edges:
            node_ids_with_edges.add(edge.source)
            node_ids_with_edges.add(edge.target)

        class_nodes = [n for n in built_graph.nodes if n.type == NodeType.CLASS]
        for node in class_nodes:
            assert node.id in node_ids_with_edges, (
                f"Class node '{node.id}' has no edges (dangling)"
            )


# ---------------------------------------------------------------------------
# Basic graph structure
# ---------------------------------------------------------------------------

class TestGraphStructure:

    def test_graph_has_nodes(self, built_graph):
        assert len(built_graph.nodes) > 0

    def test_graph_has_edges(self, built_graph):
        assert len(built_graph.edges) > 0

    def test_file_nodes_present(self, built_graph):
        file_ids = _node_ids_by_type(built_graph, NodeType.FILE)
        assert "app/animals.py" in file_ids
        assert "app/cats.py" in file_ids

    def test_module_nodes_present(self, built_graph):
        mod_ids = _node_ids_by_type(built_graph, NodeType.MODULE)
        assert len(mod_ids) > 0

    def test_contains_edges_exist(self, built_graph):
        contains = [e for e in built_graph.edges if e.relationship == RelationshipType.CONTAINS]
        assert len(contains) > 0

    def test_imports_edges_exist(self, built_graph):
        imports = [e for e in built_graph.edges if e.relationship == RelationshipType.IMPORTS]
        assert len(imports) > 0

    def test_all_edge_nodes_exist(self, built_graph):
        """Every edge source and target must reference a real node."""
        node_ids = {n.id for n in built_graph.nodes}
        # Decorator edges use the decorator name as source — those may not
        # have corresponding nodes (they are strings, not repo symbols).
        # We only check non-DECORATES edges for this invariant.
        non_decorator_edges = [
            e for e in built_graph.edges
            if e.relationship != RelationshipType.DECORATES
        ]
        for edge in non_decorator_edges:
            assert edge.source in node_ids, (
                f"Edge source '{edge.source}' not in node set"
            )
            assert edge.target in node_ids, (
                f"Edge target '{edge.target}' not in node set"
            )

    def test_overrides_edge_for_dog_speak(self, built_graph):
        """Dog.speak overrides Animal.speak — OVERRIDES edge must exist."""
        overrides = [
            e for e in built_graph.edges
            if e.relationship == RelationshipType.OVERRIDES
        ]
        pairs = {(e.source, e.target) for e in overrides}
        assert ("Dog.speak", "Animal.speak") in pairs, (
            "Dog.speak should OVERRIDE Animal.speak"
        )


# ---------------------------------------------------------------------------
# Task 2 — Advanced graph analytics (per-type degree rankings)
# ---------------------------------------------------------------------------

class TestGraphStatistics:

    def test_statistics_build(self, statistics):
        assert statistics.total_nodes > 0
        assert statistics.total_edges > 0

    def test_nodes_by_type_keys(self, statistics):
        valid_types = {t.value for t in NodeType}
        for key in statistics.nodes_by_type:
            assert key in valid_types

    def test_edges_by_type_keys(self, statistics):
        valid_rels = {r.value for r in RelationshipType}
        for key in statistics.edges_by_type:
            assert key in valid_rels

    def test_top_files_by_degree_type(self, statistics):
        assert isinstance(statistics.top_files_by_degree, list)
        for entry in statistics.top_files_by_degree:
            assert isinstance(entry, NodeDegree)
            assert isinstance(entry.node_id, str)
            assert isinstance(entry.degree, int)
            assert entry.degree >= 0

    def test_top_classes_by_degree_type(self, statistics):
        for entry in statistics.top_classes_by_degree:
            assert isinstance(entry, NodeDegree)
            assert entry.degree >= 0

    def test_top_functions_by_degree_type(self, statistics):
        for entry in statistics.top_functions_by_degree:
            assert isinstance(entry, NodeDegree)
            assert entry.degree >= 0

    def test_top_methods_by_degree_type(self, statistics):
        for entry in statistics.top_methods_by_degree:
            assert isinstance(entry, NodeDegree)
            assert entry.degree >= 0

    def test_at_most_10_per_category(self, statistics):
        assert len(statistics.top_files_by_degree) <= 10
        assert len(statistics.top_classes_by_degree) <= 10
        assert len(statistics.top_functions_by_degree) <= 10
        assert len(statistics.top_methods_by_degree) <= 10

    def test_per_type_rankings_sorted_descending(self, statistics):
        for category_name, entries in [
            ("top_files_by_degree", statistics.top_files_by_degree),
            ("top_classes_by_degree", statistics.top_classes_by_degree),
            ("top_functions_by_degree", statistics.top_functions_by_degree),
            ("top_methods_by_degree", statistics.top_methods_by_degree),
        ]:
            degrees = [e.degree for e in entries]
            assert degrees == sorted(degrees, reverse=True), (
                f"{category_name} must be sorted descending by degree"
            )

    def test_file_degree_nodes_are_files(self, built_graph, statistics):
        """node_ids in top_files_by_degree must correspond to FILE nodes."""
        file_node_ids = _node_ids_by_type(built_graph, NodeType.FILE)
        for entry in statistics.top_files_by_degree:
            assert entry.node_id in file_node_ids, (
                f"'{entry.node_id}' in top_files_by_degree is not a FILE node"
            )

    def test_class_degree_nodes_are_classes(self, built_graph, statistics):
        class_node_ids = _node_ids_by_type(built_graph, NodeType.CLASS)
        for entry in statistics.top_classes_by_degree:
            assert entry.node_id in class_node_ids, (
                f"'{entry.node_id}' in top_classes_by_degree is not a CLASS node"
            )

    def test_most_connected_nodes_backward_compat(self, statistics):
        """most_connected_nodes must still be a list[str] for backward compat."""
        assert isinstance(statistics.most_connected_nodes, list)
        for item in statistics.most_connected_nodes:
            assert isinstance(item, str)
        assert len(statistics.most_connected_nodes) <= 10


# ---------------------------------------------------------------------------
# Task 3 — Architectural hotspots
# ---------------------------------------------------------------------------

class TestArchitecturalHotspots:

    def test_hotspots_present(self, statistics):
        assert isinstance(statistics.architectural_hotspots, list)

    def test_hotspots_at_most_10(self, statistics):
        assert len(statistics.architectural_hotspots) <= 10

    def test_hotspots_sorted_descending(self, statistics):
        degrees = [h.degree for h in statistics.architectural_hotspots]
        assert degrees == sorted(degrees, reverse=True), (
            "architectural_hotspots must be sorted descending by degree"
        )

    def test_hotspots_are_node_degree_objects(self, statistics):
        for h in statistics.architectural_hotspots:
            assert isinstance(h, NodeDegree)
            assert isinstance(h.node_id, str)
            assert isinstance(h.degree, int)
            assert h.degree >= 0

    def test_hotspots_cover_any_type(self, built_graph, statistics):
        """
        Hotspots are not restricted to one type — they span File, Class,
        Method, etc.  Verify they reference real node IDs.
        Decorator strings are allowed to appear (they are edge participants
        even without formal nodes), so we only soft-check.
        """
        node_ids = {n.id for n in built_graph.nodes}
        # At least one hotspot must be a known node id
        hotspot_ids = {h.node_id for h in statistics.architectural_hotspots}
        overlap = hotspot_ids & node_ids
        assert len(overlap) > 0, (
            "At least one architectural hotspot must correspond to a graph node"
        )

    def test_top_hotspot_has_highest_degree(self, statistics):
        """The first hotspot must have the highest or equal degree."""
        if len(statistics.architectural_hotspots) >= 2:
            assert (
                statistics.architectural_hotspots[0].degree
                >= statistics.architectural_hotspots[1].degree
            )


# ---------------------------------------------------------------------------
# Import graph (smoke test — unchanged code path)
# ---------------------------------------------------------------------------

class TestImportGraph:

    def test_import_graph_builds(self, builder, simple_repository):
        import_edges = builder.build_import_graph(simple_repository)
        assert len(import_edges) > 0
        for edge in import_edges:
            assert edge.source_file
            assert edge.imported_module


# ---------------------------------------------------------------------------
# Larger synthetic repository (stress test for filtering)
# ---------------------------------------------------------------------------

class TestLargeRepositoryFiltering:
    """
    A more complex repository that exercises filtering across multiple files,
    cross-file inheritance, and a variety of external symbols.
    """

    @pytest.fixture
    def large_repo(self) -> ParsedRepository:
        base_service = _make_class(
            name="BaseService",
            methods=[
                _make_function("execute"),
                _make_function("validate"),
            ],
        )

        user_service = _make_class(
            name="UserService",
            inherits_from=["BaseService", "ABC", "object"],
            methods=[
                _make_function("execute", calls=["BaseService", "dict", "list"]),
                _make_function("get_user", calls=["UserRepository", "ValueError"]),
            ],
        )

        user_repository = _make_class(
            name="UserRepository",
            inherits_from=["BaseModel"],
            methods=[
                _make_function("find", calls=["str", "int"]),
                _make_function("save"),
            ],
        )

        bootstrap_fn = _make_function(
            name="bootstrap",
            calls=["UserService", "UserRepository", "Exception", "BaseModel"],
        )

        file_a = ParsedFile(
            file_path="services/base.py",
            imports=["abc"],
            classes=[base_service],
            functions=[],
        )
        file_b = ParsedFile(
            file_path="services/user_service.py",
            imports=["abc", "pydantic"],
            classes=[user_service],
            functions=[bootstrap_fn],
        )
        file_c = ParsedFile(
            file_path="repositories/user_repository.py",
            imports=["pydantic"],
            classes=[user_repository],
            functions=[],
        )
        return ParsedRepository(
            repository_name="large_test_repo",
            total_python_files=3,
            files=[file_a, file_b, file_c],
        )

    def test_no_external_class_nodes(self, builder, large_repo):
        graph = builder.build_graph(large_repo)
        class_ids = _node_ids_by_type(graph, NodeType.CLASS)
        for forbidden in ("BaseModel", "ABC", "object", "Exception", "ValueError"):
            assert forbidden not in class_ids, (
                f"External symbol '{forbidden}' must not become a Class node"
            )

    def test_repo_classes_present(self, builder, large_repo):
        graph = builder.build_graph(large_repo)
        class_ids = _node_ids_by_type(graph, NodeType.CLASS)
        assert "BaseService" in class_ids
        assert "UserService" in class_ids
        assert "UserRepository" in class_ids

    def test_cross_file_inherits(self, builder, large_repo):
        graph = builder.build_graph(large_repo)
        inherits = {
            (e.source, e.target)
            for e in graph.edges
            if e.relationship == RelationshipType.INHERITS
        }
        assert ("UserService", "BaseService") in inherits

    def test_overrides_across_files(self, builder, large_repo):
        graph = builder.build_graph(large_repo)
        overrides = {
            (e.source, e.target)
            for e in graph.edges
            if e.relationship == RelationshipType.OVERRIDES
        }
        assert ("UserService.execute", "BaseService.execute") in overrides

    def test_statistics_generate_for_large_repo(self, builder, large_repo):
        graph = builder.build_graph(large_repo)
        stats = builder.generate_statistics(graph)
        assert stats.total_nodes > 0
        assert stats.total_edges > 0
        assert len(stats.architectural_hotspots) > 0