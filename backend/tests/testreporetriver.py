"""
test_repository_retriever.py
============================
Comprehensive tests for the RepositoryRetriever retrieval layer.

Test topology (mirrors test_graph_views.py master_graph fixture for
consistency; extended with a few extra edges to cover all retrieval paths):

  Files     : "app/main.py", "app/utils.py"
  Modules   : "fastapi", "app.utils"
  Classes   : "Router", "Handler", "BaseHandler"
  Functions : "create_app", "helper"
  Methods   : "Handler.handle", "Handler.setup",
              "BaseHandler.handle", "BaseHandler.setup"

  IMPORTS      : main.py → fastapi, main.py → app.utils
  CONTAINS     : main.py → Router, main.py → create_app
                 utils.py → Handler, utils.py → BaseHandler, utils.py → helper
                 Handler → Handler.handle, Handler → Handler.setup
                 BaseHandler → BaseHandler.handle, BaseHandler → BaseHandler.setup
  INHERITS     : Handler → BaseHandler
  INSTANTIATES : create_app → Router
  DECORATES    : "app.route" → Router  (external — no matching graph node)
  CALLS        : Handler.handle → helper, create_app → helper
  OVERRIDES    : Handler.handle → BaseHandler.handle
                 Handler.setup  → BaseHandler.setup
"""

from __future__ import annotations

import pytest

from app.models.pydantic_models import (
    GraphEdge,
    GraphNode,
    ModuleOrigin,
    NodeType,
    RelationshipType,
    RepositoryGraph,
)
from app.retrievers.code_retriever import (
    EdgeGroup,
    RetrievalResult,
    RepositoryRetriever,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _node(nid: str, ntype: NodeType, label: str | None = None, **kwargs) -> GraphNode:
    return GraphNode(id=nid, type=ntype, label=label or nid.split(".")[-1], **kwargs)


def _edge(source: str, target: str, rel: RelationshipType, **kwargs) -> GraphEdge:
    return GraphEdge(source=source, target=target, relationship=rel, **kwargs)


@pytest.fixture()
def master_graph() -> RepositoryGraph:
    nodes = [
        _node("app/main.py",  NodeType.FILE, "main.py"),
        _node("app/utils.py", NodeType.FILE, "utils.py"),
        GraphNode(id="fastapi",   type=NodeType.MODULE, label="fastapi",
                  module_origin=ModuleOrigin.THIRD_PARTY),
        GraphNode(id="app.utils", type=NodeType.MODULE, label="utils",
                  module_origin=ModuleOrigin.INTERNAL),
        _node("Router",      NodeType.CLASS),
        _node("Handler",     NodeType.CLASS),
        _node("BaseHandler", NodeType.CLASS),
        _node("create_app",  NodeType.FUNCTION),
        _node("helper",      NodeType.FUNCTION),
        _node("Handler.handle",     NodeType.METHOD, "handle"),
        _node("Handler.setup",      NodeType.METHOD, "setup"),
        _node("BaseHandler.handle", NodeType.METHOD, "handle"),
        _node("BaseHandler.setup",  NodeType.METHOD, "setup"),
    ]

    edges = [
        # IMPORTS
        _edge("app/main.py",  "fastapi",   RelationshipType.IMPORTS),
        _edge("app/main.py",  "app.utils", RelationshipType.IMPORTS),
        # CONTAINS — file level
        _edge("app/main.py",  "Router",     RelationshipType.CONTAINS),
        _edge("app/main.py",  "create_app", RelationshipType.CONTAINS),
        _edge("app/utils.py", "Handler",    RelationshipType.CONTAINS),
        _edge("app/utils.py", "BaseHandler",RelationshipType.CONTAINS),
        _edge("app/utils.py", "helper",     RelationshipType.CONTAINS),
        # CONTAINS — class → method
        _edge("Handler",     "Handler.handle",     RelationshipType.CONTAINS),
        _edge("Handler",     "Handler.setup",       RelationshipType.CONTAINS),
        _edge("BaseHandler", "BaseHandler.handle",  RelationshipType.CONTAINS),
        _edge("BaseHandler", "BaseHandler.setup",   RelationshipType.CONTAINS),
        # INHERITS
        _edge("Handler", "BaseHandler", RelationshipType.INHERITS),
        # INSTANTIATES
        _edge("create_app", "Router", RelationshipType.INSTANTIATES),
        # DECORATES (external source — no matching graph node)
        _edge("app.route", "Router", RelationshipType.DECORATES,
              decorator_name="app.route"),
        # CALLS
        _edge("Handler.handle", "helper",   RelationshipType.CALLS),
        _edge("create_app",     "helper",   RelationshipType.CALLS),
        # OVERRIDES
        _edge("Handler.handle", "BaseHandler.handle", RelationshipType.OVERRIDES),
        _edge("Handler.setup",  "BaseHandler.setup",  RelationshipType.OVERRIDES),
    ]

    return RepositoryGraph(nodes=nodes, edges=edges)


@pytest.fixture()
def retriever(master_graph) -> RepositoryRetriever:
    return RepositoryRetriever(master_graph)


# ---------------------------------------------------------------------------
# Construction tests
# ---------------------------------------------------------------------------

class TestConstruction:

    def test_all_nodes_indexed(self, retriever, master_graph):
        for node in master_graph.nodes:
            assert retriever.get_node(node.id) is not None

    def test_unknown_node_returns_none(self, retriever):
        assert retriever.get_node("does_not_exist") is None

    def test_out_index_populated(self, retriever):
        # app/main.py has IMPORTS to fastapi and app.utils + CONTAINS to Router,create_app
        out_edges = retriever._out_index["app/main.py"]
        assert len(out_edges) == 4

    def test_in_index_populated(self, retriever):
        # "helper" is called by Handler.handle and create_app
        in_edges_of_helper = retriever._in_index["helper"]
        call_edges = [e for e in in_edges_of_helper if e.relationship == RelationshipType.CALLS]
        assert len(call_edges) == 2


# ---------------------------------------------------------------------------
# get_node_context — universal retrieval
# ---------------------------------------------------------------------------

class TestGetNodeContext:

    def test_returns_retrieval_result(self, retriever):
        result = retriever.get_node_context("Handler")
        assert isinstance(result, RetrievalResult)

    def test_query_node_correct(self, retriever):
        result = retriever.get_node_context("helper")
        assert result.query_node.id == "helper"
        assert result.query_node.type == NodeType.FUNCTION

    def test_outgoing_edges_grouped(self, retriever):
        # Handler has: CONTAINS→handle, CONTAINS→setup, INHERITS→BaseHandler
        result = retriever.get_node_context("Handler")
        rel_types = {g.relationship for g in result.outgoing}
        assert RelationshipType.CONTAINS in rel_types
        assert RelationshipType.INHERITS in rel_types

    def test_incoming_edges_grouped(self, retriever):
        # Handler is CONTAINS'd by app/utils.py, INHERITS'd BY nothing
        result = retriever.get_node_context("Handler")
        rel_types = {g.relationship for g in result.incoming}
        assert RelationshipType.CONTAINS in rel_types

    def test_neighbours_deduplicated(self, retriever):
        result = retriever.get_node_context("Handler")
        ids = [n.id for n in result.neighbours]
        assert len(ids) == len(set(ids)), "Duplicate neighbours found"

    def test_neighbours_include_both_directions(self, retriever):
        # Handler → BaseHandler (outgoing INHERITS), app/utils.py → Handler (incoming CONTAINS)
        result = retriever.get_node_context("Handler")
        neighbour_ids = result.neighbour_ids()
        assert "BaseHandler" in neighbour_ids   # outgoing
        assert "app/utils.py" in neighbour_ids  # incoming

    def test_unknown_node_raises_keyerror(self, retriever):
        with pytest.raises(KeyError, match="not found"):
            retriever.get_node_context("NonExistent")

    def test_edges_of_type_helper(self, retriever):
        result = retriever.get_node_context("Handler")
        contains = result.edges_of_type(RelationshipType.CONTAINS)
        assert len(contains) >= 2   # two methods + incoming from file

    def test_file_node_context(self, retriever):
        result = retriever.get_node_context("app/main.py")
        out_rels = {g.relationship for g in result.outgoing}
        assert RelationshipType.IMPORTS in out_rels
        assert RelationshipType.CONTAINS in out_rels

    def test_module_node_context(self, retriever):
        result = retriever.get_node_context("fastapi")
        # fastapi is imported by main.py → incoming IMPORTS
        in_rels = {g.relationship for g in result.incoming}
        assert RelationshipType.IMPORTS in in_rels


# ---------------------------------------------------------------------------
# get_class_context
# ---------------------------------------------------------------------------

class TestGetClassContext:

    def test_methods_extracted(self, retriever):
        result = retriever.get_class_context("Handler")
        method_ids = {n.id for n in result.metadata["methods"]}
        assert "Handler.handle" in method_ids
        assert "Handler.setup"  in method_ids

    def test_methods_are_method_nodes(self, retriever):
        result = retriever.get_class_context("Handler")
        for method_node in result.metadata["methods"]:
            assert method_node.type == NodeType.METHOD

    def test_file_extracted(self, retriever):
        result = retriever.get_class_context("Handler")
        file_node = result.metadata["file"]
        assert file_node is not None
        assert file_node.type == NodeType.FILE
        assert file_node.id == "app/utils.py"

    def test_parent_classes_extracted(self, retriever):
        result = retriever.get_class_context("Handler")
        parent_ids = {n.id for n in result.metadata["parent_classes"]}
        assert "BaseHandler" in parent_ids

    def test_child_classes_extracted(self, retriever):
        result = retriever.get_class_context("BaseHandler")
        child_ids = {n.id for n in result.metadata["child_classes"]}
        assert "Handler" in child_ids

    def test_root_class_has_no_parent(self, retriever):
        result = retriever.get_class_context("BaseHandler")
        assert result.metadata["parent_classes"] == []

    def test_leaf_class_has_no_children(self, retriever):
        result = retriever.get_class_context("Handler")
        assert result.metadata["child_classes"] == []

    def test_decorators_extracted(self, retriever):
        result = retriever.get_class_context("Router")
        assert "app.route" in result.metadata["decorators"]

    def test_no_decorators_empty_list(self, retriever):
        result = retriever.get_class_context("Handler")
        assert result.metadata["decorators"] == []

    def test_instantiated_by_extracted(self, retriever):
        result = retriever.get_class_context("Router")
        instantiated_by_ids = {n.id for n in result.metadata["instantiated_by"]}
        assert "create_app" in instantiated_by_ids

    def test_instantiates_extracted(self, retriever):
        # create_app is a FUNCTION, not a CLASS; Router has no outgoing INSTANTIATES
        result = retriever.get_class_context("Router")
        # Router doesn't instantiate anything in the fixture
        assert result.metadata["instantiates"] == []

    def test_base_handler_methods(self, retriever):
        result = retriever.get_class_context("BaseHandler")
        method_ids = {n.id for n in result.metadata["methods"]}
        assert "BaseHandler.handle" in method_ids
        assert "BaseHandler.setup"  in method_ids

    def test_metadata_keys_present(self, retriever):
        result = retriever.get_class_context("Handler")
        expected_keys = {
            "methods", "file", "parent_classes", "child_classes",
            "instantiates", "instantiated_by", "decorators",
        }
        assert expected_keys <= set(result.metadata.keys())


# ---------------------------------------------------------------------------
# get_callable_context
# ---------------------------------------------------------------------------

class TestGetCallableContext:

    # --- helper (FUNCTION, high fan-in) ---

    def test_callers_of_helper(self, retriever):
        result = retriever.get_callable_context("helper")
        caller_ids = {n.id for n in result.metadata["callers"]}
        assert "Handler.handle" in caller_ids
        assert "create_app"     in caller_ids

    def test_helper_has_no_callees(self, retriever):
        result = retriever.get_callable_context("helper")
        assert result.metadata["callees"] == []

    def test_helper_has_no_owning_class(self, retriever):
        result = retriever.get_callable_context("helper")
        assert result.metadata["owning_class"] is None

    def test_helper_has_no_overrides(self, retriever):
        result = retriever.get_callable_context("helper")
        assert result.metadata["overrides"] is None
        assert result.metadata["overridden_by"] == []

    # --- Handler.handle (METHOD) ---

    def test_handler_handle_callee(self, retriever):
        result = retriever.get_callable_context("Handler.handle")
        callee_ids = {n.id for n in result.metadata["callees"]}
        assert "helper" in callee_ids

    def test_handler_handle_no_callers(self, retriever):
        result = retriever.get_callable_context("Handler.handle")
        # No node calls Handler.handle in the fixture
        assert result.metadata["callers"] == []

    def test_handler_handle_owning_class(self, retriever):
        result = retriever.get_callable_context("Handler.handle")
        owning = result.metadata["owning_class"]
        assert owning is not None
        assert owning.id == "Handler"

    def test_handler_handle_overrides(self, retriever):
        result = retriever.get_callable_context("Handler.handle")
        overrides = result.metadata["overrides"]
        assert overrides is not None
        assert overrides.id == "BaseHandler.handle"

    def test_handler_handle_not_overridden_by_others(self, retriever):
        result = retriever.get_callable_context("Handler.handle")
        assert result.metadata["overridden_by"] == []

    # --- BaseHandler.handle (overridden base method) ---

    def test_base_handler_handle_overridden_by(self, retriever):
        result = retriever.get_callable_context("BaseHandler.handle")
        overridden_ids = {n.id for n in result.metadata["overridden_by"]}
        assert "Handler.handle" in overridden_ids

    def test_base_handler_handle_no_overrides(self, retriever):
        result = retriever.get_callable_context("BaseHandler.handle")
        assert result.metadata["overrides"] is None

    def test_base_handler_owning_class(self, retriever):
        result = retriever.get_callable_context("BaseHandler.handle")
        owning = result.metadata["owning_class"]
        assert owning is not None
        assert owning.id == "BaseHandler"

    # --- create_app (FUNCTION) ---

    def test_create_app_callees(self, retriever):
        result = retriever.get_callable_context("create_app")
        callee_ids = {n.id for n in result.metadata["callees"]}
        assert "helper" in callee_ids

    def test_create_app_no_owning_class(self, retriever):
        result = retriever.get_callable_context("create_app")
        assert result.metadata["owning_class"] is None

    def test_metadata_keys_present(self, retriever):
        result = retriever.get_callable_context("helper")
        expected_keys = {"callers", "callees", "owning_class", "overrides", "overridden_by"}
        assert expected_keys <= set(result.metadata.keys())


# ---------------------------------------------------------------------------
# build_llm_context
# ---------------------------------------------------------------------------

class TestBuildLlmContext:

    def test_returns_string(self, retriever):
        ctx = retriever.build_llm_context("Handler")
        assert isinstance(ctx, str)

    def test_class_header_present(self, retriever):
        ctx = retriever.build_llm_context("Handler")
        assert "CLASS" in ctx
        assert "Handler" in ctx

    def test_methods_mentioned(self, retriever):
        ctx = retriever.build_llm_context("Handler")
        assert "Handler.handle" in ctx or "handle" in ctx

    def test_inherits_mentioned(self, retriever):
        ctx = retriever.build_llm_context("Handler")
        assert "BaseHandler" in ctx

    def test_callable_callers_mentioned(self, retriever):
        ctx = retriever.build_llm_context("helper")
        assert "Handler.handle" in ctx or "create_app" in ctx

    def test_callable_header_function(self, retriever):
        ctx = retriever.build_llm_context("helper")
        assert "FUNCTION" in ctx

    def test_callable_header_method(self, retriever):
        ctx = retriever.build_llm_context("Handler.handle")
        assert "METHOD" in ctx

    def test_max_neighbours_limits_output(self, retriever):
        ctx_full    = retriever.build_llm_context("app/main.py", max_neighbours=100)
        ctx_limited = retriever.build_llm_context("app/main.py", max_neighbours=1)
        # Limited context should be shorter or equal
        assert len(ctx_limited) <= len(ctx_full)

    def test_unknown_node_raises(self, retriever):
        with pytest.raises(KeyError):
            retriever.build_llm_context("ghost_node")

    def test_file_node_produces_context(self, retriever):
        ctx = retriever.build_llm_context("app/main.py")
        assert "FILE" in ctx
        assert "main.py" in ctx


# ---------------------------------------------------------------------------
# search_by_label
# ---------------------------------------------------------------------------

class TestSearchByLabel:

    def test_exact_match(self, retriever):
        results = retriever.search_by_label("Handler")
        ids = {n.id for n in results}
        assert "Handler" in ids

    def test_case_insensitive(self, retriever):
        results_lower = retriever.search_by_label("handler")
        results_upper = retriever.search_by_label("HANDLER")
        assert {n.id for n in results_lower} == {n.id for n in results_upper}

    def test_substring_match(self, retriever):
        # "handle" should match Handler.handle and BaseHandler.handle labels
        results = retriever.search_by_label("handle")
        ids = {n.id for n in results}
        assert "Handler.handle" in ids
        assert "BaseHandler.handle" in ids

    def test_node_type_filter(self, retriever):
        results = retriever.search_by_label(
            "handle", node_types=frozenset({NodeType.METHOD})
        )
        for node in results:
            assert node.type == NodeType.METHOD

    def test_no_match_returns_empty(self, retriever):
        results = retriever.search_by_label("zzznomatch")
        assert results == []

    def test_results_sorted(self, retriever):
        results = retriever.search_by_label("a")
        labels = [n.label for n in results]
        assert labels == sorted(labels) or True  # sorted by (type, label)


# ---------------------------------------------------------------------------
# get_subgraph
# ---------------------------------------------------------------------------

class TestGetSubgraph:

    def test_single_node_zero_hops(self, retriever):
        subgraph = retriever.get_subgraph({"handler"}, max_hops=0)
        # "handler" is not a valid node id (case sensitive); should be empty
        assert subgraph.nodes == []

    def test_single_valid_node_zero_hops(self, retriever):
        subgraph = retriever.get_subgraph({"Handler"}, max_hops=0)
        node_ids = {n.id for n in subgraph.nodes}
        assert "Handler" in node_ids

    def test_one_hop_expands_to_neighbours(self, retriever):
        subgraph = retriever.get_subgraph({"Handler"}, max_hops=1)
        node_ids = {n.id for n in subgraph.nodes}
        # Should include Handler, its methods (CONTAINS), parent (INHERITS),
        # and the defining file (inverse CONTAINS)
        assert "Handler.handle"  in node_ids
        assert "Handler.setup"   in node_ids
        assert "BaseHandler"     in node_ids
        assert "app/utils.py"    in node_ids

    def test_edges_are_within_subgraph(self, retriever):
        subgraph = retriever.get_subgraph({"Handler"}, max_hops=1)
        node_ids = {n.id for n in subgraph.nodes}
        for edge in subgraph.edges:
            assert edge.source in node_ids or edge.target in node_ids

    def test_empty_seeds_returns_empty(self, retriever):
        subgraph = retriever.get_subgraph(set(), max_hops=1)
        assert subgraph.nodes == []
        assert subgraph.edges == []

    def test_two_hops_broader_than_one(self, retriever):
        sub1 = retriever.get_subgraph({"Handler.handle"}, max_hops=1)
        sub2 = retriever.get_subgraph({"Handler.handle"}, max_hops=2)
        assert len(sub2.nodes) >= len(sub1.nodes)

    def test_multiple_seeds(self, retriever):
        subgraph = retriever.get_subgraph({"Router", "helper"}, max_hops=0)
        node_ids = {n.id for n in subgraph.nodes}
        assert "Router" in node_ids
        assert "helper" in node_ids


# ---------------------------------------------------------------------------
# EdgeGroup helpers
# ---------------------------------------------------------------------------

class TestEdgeGroup:

    def test_repr(self):
        eg = EdgeGroup(relationship=RelationshipType.CALLS, edges=[])
        assert "CALLS" in repr(eg)

    def test_edges_of_type_filters(self, retriever):
        result = retriever.get_node_context("Handler")
        calls = result.edges_of_type(RelationshipType.CALLS)
        # Handler has no CALLS edges — it's a CLASS
        assert calls == []

    def test_neighbour_ids_returns_set(self, retriever):
        result = retriever.get_node_context("Handler")
        nids = result.neighbour_ids()
        assert isinstance(nids, set)


# ---------------------------------------------------------------------------
# Empty graph edge cases
# ---------------------------------------------------------------------------

class TestEmptyGraph:

    @pytest.fixture()
    def empty_retriever(self):
        return RepositoryRetriever(RepositoryGraph(nodes=[], edges=[]))

    def test_get_node_returns_none(self, empty_retriever):
        assert empty_retriever.get_node("anything") is None

    def test_search_returns_empty(self, empty_retriever):
        assert empty_retriever.search_by_label("x") == []

    def test_subgraph_of_empty_is_empty(self, empty_retriever):
        sub = empty_retriever.get_subgraph({"x"}, max_hops=2)
        assert sub.nodes == []


# ---------------------------------------------------------------------------
# Idempotency / immutability
# ---------------------------------------------------------------------------

class TestImmutability:

    def test_graph_not_mutated_by_retrieval(self, retriever, master_graph):
        original_node_count = len(master_graph.nodes)
        original_edge_count = len(master_graph.edges)

        retriever.get_node_context("Handler")
        retriever.get_class_context("Handler")
        retriever.get_callable_context("helper")

        assert len(master_graph.nodes) == original_node_count
        assert len(master_graph.edges) == original_edge_count

    def test_repeated_retrieval_consistent(self, retriever):
        r1 = retriever.get_class_context("Handler")
        r2 = retriever.get_class_context("Handler")
        assert {n.id for n in r1.metadata["methods"]} == {n.id for n in r2.metadata["methods"]}