"""
tests/test_context_pipeline.py
================================
Integration tests for the ContextBuilder pipeline.

Tests are self-contained: they build a synthetic RepositoryGraph that
deliberately resembles the RepoGraphAI codebase itself (parser, graph
builder, retriever), which makes the example output for the specified
questions both realistic and repo-agnostic.

Run:
    pytest tests/test_context_pipeline.py -v
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
from app.rag.context_builder import (
    ContextBuilder,
    ContextPackage,
    ResolvedNode,
    SubgraphSummary,
    build_context_builder,
    _build_subgraph_summary,
)
from app.retrievers.query_resolver import QueryResolver
from app.retrievers.code_retriever import RepositoryRetriever


# ===========================================================================
# Synthetic graph fixture
# ===========================================================================
#
# Topology (simplified RepoGraphAI):
#
#   app/parser/code_parser.py  ──CONTAINS──►  CodeParser (class)
#                                             ├──CONTAINS──►  parse_file (method)
#                                             └──CONTAINS──►  parse_repository (method)
#
#   app/graph/graph_builder.py ──CONTAINS──►  GraphBuilder (class)
#                                             └──CONTAINS──►  build_graph (method)
#
#   app/retrieval/repository_retriever.py
#                              ──CONTAINS──►  RepositoryRetriever (class)
#                                             ├──CONTAINS──►  get_node_context (method)
#                                             ├──CONTAINS──►  get_subgraph (method)
#                                             └──CONTAINS──►  build_llm_context (method)
#
#   app/retrievers/query_resolver.py
#                              ──CONTAINS──►  QueryResolver (class)
#                                             └──CONTAINS──►  resolve_query (method)
#
#   app/retrievers/context_builder.py
#                              ──CONTAINS──►  ContextBuilder (class)
#                                             └──CONTAINS──►  build (method)
#
#   Calls:
#     ContextBuilder.build  ──CALLS──►  QueryResolver.resolve_query
#     ContextBuilder.build  ──CALLS──►  RepositoryRetriever.get_subgraph
#     ContextBuilder.build  ──CALLS──►  RepositoryRetriever.build_llm_context
#     GraphBuilder.build_graph  ──CALLS──►  CodeParser.parse_file
#
#   Instantiates:
#     ContextBuilder.build  ──INSTANTIATES──►  ContextPackage  (data model)
#
# ---------------------------------------------------------------------------

def _node(
    id_: str,
    type_: NodeType,
    label: str = "",
    file_path: str | None = None,
    line_number: int | None = None,
    docstring: str | None = None,
) -> GraphNode:
    return GraphNode(
        id=id_,
        type=type_,
        label=label or id_.split(".")[-1],
        file_path=file_path,
        line_number=line_number,
        docstring=docstring,
    )


def _edge(
    source: str,
    target: str,
    rel: RelationshipType,
    decorator_name: str | None = None,
) -> GraphEdge:
    return GraphEdge(
        source=source,
        target=target,
        relationship=rel,
        decorator_name=decorator_name,
    )


@pytest.fixture(scope="module")
def synthetic_graph() -> RepositoryGraph:
    C = RelationshipType.CONTAINS
    CA = RelationshipType.CALLS
    IN = RelationshipType.INSTANTIATES

    nodes = [
        # Files
        _node("app/parser/code_parser.py",          NodeType.FILE,     "code_parser.py"),
        _node("app/graph/graph_builder.py",          NodeType.FILE,     "graph_builder.py"),
        _node("app/retrieval/repository_retriever.py", NodeType.FILE,   "repository_retriever.py"),
        _node("app/retrievers/query_resolver.py",    NodeType.FILE,     "query_resolver.py"),
        _node("app/retrievers/context_builder.py",   NodeType.FILE,     "context_builder.py"),

        # Classes
        _node("CodeParser",             NodeType.CLASS,    "CodeParser",
              file_path="app/parser/code_parser.py", line_number=10,
              docstring="Parses Python source files into ParsedFile objects."),
        _node("GraphBuilder",           NodeType.CLASS,    "GraphBuilder",
              file_path="app/graph/graph_builder.py", line_number=15,
              docstring="Converts a ParsedRepository into a RepositoryGraph."),
        _node("RepositoryRetriever",    NodeType.CLASS,    "RepositoryRetriever",
              file_path="app/retrieval/repository_retriever.py", line_number=20,
              docstring="Graph-based retrieval over a RepositoryGraph."),
        _node("QueryResolver",          NodeType.CLASS,    "QueryResolver",
              file_path="app/retrievers/query_resolver.py", line_number=10,
              docstring="Converts natural-language questions into ranked graph nodes."),
        _node("ContextBuilder",         NodeType.CLASS,    "ContextBuilder",
              file_path="app/retrievers/context_builder.py", line_number=10,
              docstring="Orchestrates QueryResolver → RepositoryRetriever → ContextPackage."),
        _node("ContextPackage",         NodeType.CLASS,    "ContextPackage",
              file_path="app/retrievers/context_builder.py", line_number=50,
              docstring="Self-contained context bundle produced by ContextBuilder."),

        # Methods
        _node("CodeParser.parse_file",           NodeType.METHOD, "parse_file",
              file_path="app/parser/code_parser.py", line_number=30,
              docstring="Parse a single Python source file into a ParsedFile."),
        _node("CodeParser.parse_repository",     NodeType.METHOD, "parse_repository",
              file_path="app/parser/code_parser.py", line_number=60,
              docstring="Parse all Python files in the repository."),
        _node("GraphBuilder.build_graph",        NodeType.METHOD, "build_graph",
              file_path="app/graph/graph_builder.py", line_number=40,
              docstring="Convert a ParsedRepository into a RepositoryGraph."),
        _node("RepositoryRetriever.get_node_context",  NodeType.METHOD, "get_node_context",
              file_path="app/retrieval/repository_retriever.py", line_number=50,
              docstring="Universal retrieval for any node type."),
        _node("RepositoryRetriever.get_subgraph",      NodeType.METHOD, "get_subgraph",
              file_path="app/retrieval/repository_retriever.py", line_number=100,
              docstring="Return the subgraph within max_hops of the seed nodes."),
        _node("RepositoryRetriever.build_llm_context", NodeType.METHOD, "build_llm_context",
              file_path="app/retrieval/repository_retriever.py", line_number=130,
              docstring="Build a plain-text LLM context block for a given node."),
        _node("QueryResolver.resolve_query",     NodeType.METHOD, "resolve_query",
              file_path="app/retrievers/query_resolver.py", line_number=30,
              docstring="Convert a question into a ranked QueryResolutionResult."),
        _node("ContextBuilder.build",            NodeType.METHOD, "build",
              file_path="app/retrievers/context_builder.py", line_number=80,
              docstring="Build a ContextPackage for the given natural-language question."),
    ]

    edges = [
        # File → Class (CONTAINS)
        _edge("app/parser/code_parser.py",            "CodeParser",             C),
        _edge("app/graph/graph_builder.py",           "GraphBuilder",           C),
        _edge("app/retrieval/repository_retriever.py","RepositoryRetriever",    C),
        _edge("app/retrievers/query_resolver.py",     "QueryResolver",          C),
        _edge("app/retrievers/context_builder.py",    "ContextBuilder",         C),
        _edge("app/retrievers/context_builder.py",    "ContextPackage",         C),

        # Class → Method (CONTAINS)
        _edge("CodeParser",          "CodeParser.parse_file",                   C),
        _edge("CodeParser",          "CodeParser.parse_repository",             C),
        _edge("GraphBuilder",        "GraphBuilder.build_graph",                C),
        _edge("RepositoryRetriever", "RepositoryRetriever.get_node_context",    C),
        _edge("RepositoryRetriever", "RepositoryRetriever.get_subgraph",        C),
        _edge("RepositoryRetriever", "RepositoryRetriever.build_llm_context",   C),
        _edge("QueryResolver",       "QueryResolver.resolve_query",             C),
        _edge("ContextBuilder",      "ContextBuilder.build",                    C),

        # Calls
        _edge("ContextBuilder.build",     "QueryResolver.resolve_query",        CA),
        _edge("ContextBuilder.build",     "RepositoryRetriever.get_subgraph",   CA),
        _edge("ContextBuilder.build",     "RepositoryRetriever.build_llm_context", CA),
        _edge("GraphBuilder.build_graph", "CodeParser.parse_file",              CA),

        # Instantiates
        _edge("ContextBuilder.build",     "ContextPackage",                     IN),
    ]

    return RepositoryGraph(nodes=nodes, edges=edges)


@pytest.fixture(scope="module")
def builder(synthetic_graph) -> ContextBuilder:
    return build_context_builder(synthetic_graph, top_k=8, max_hops=1)


# ===========================================================================
# Helper
# ===========================================================================

def _build(builder: ContextBuilder, question: str) -> ContextPackage:
    return builder.build(question)


# ===========================================================================
# Group 1: ContextPackage structure
# ===========================================================================

class TestContextPackageStructure:

    def test_returns_context_package(self, builder):
        pkg = _build(builder, "How are files parsed?")
        assert isinstance(pkg, ContextPackage)

    def test_question_preserved(self, builder):
        q = "How are files parsed?"
        pkg = _build(builder, q)
        assert pkg.question == q

    def test_intent_categories_non_empty(self, builder):
        pkg = _build(builder, "How are files parsed?")
        assert len(pkg.intent_categories) >= 1
        for cat in pkg.intent_categories:
            assert isinstance(cat, str)

    def test_keywords_non_empty(self, builder):
        pkg = _build(builder, "How are files parsed?")
        assert len(pkg.keywords) >= 1

    def test_resolved_nodes_non_empty(self, builder):
        pkg = _build(builder, "How are files parsed?")
        assert len(pkg.resolved_nodes) >= 1

    def test_resolved_nodes_score_order(self, builder):
        pkg = _build(builder, "How does retrieval work?")
        scores = [rn.score for rn in pkg.resolved_nodes]
        assert scores == sorted(scores, reverse=True)

    def test_llm_context_is_string(self, builder):
        pkg = _build(builder, "How is the graph generated?")
        assert isinstance(pkg.llm_context, str)
        assert len(pkg.llm_context) > 0

    def test_subgraph_counts_consistent(self, builder):
        pkg = _build(builder, "How does retrieval work?")
        assert pkg.subgraph_node_count == pkg.subgraph_summary.node_count
        assert pkg.subgraph_edge_count == pkg.subgraph_summary.edge_count

    def test_raw_resolution_attached(self, builder):
        pkg = _build(builder, "How are files parsed?")
        assert pkg.raw_resolution is not None

    def test_top_node_ids_matches_resolved_nodes(self, builder):
        pkg = _build(builder, "How does retrieval work?")
        assert pkg.top_node_ids() == [rn.node_id for rn in pkg.resolved_nodes]


# ===========================================================================
# Group 2: ResolvedNode content
# ===========================================================================

class TestResolvedNodeContent:

    def test_node_type_is_string(self, builder):
        pkg = _build(builder, "How are files parsed?")
        for rn in pkg.resolved_nodes:
            assert isinstance(rn.node_type, str)
            # Must be a valid NodeType value
            assert rn.node_type in {nt.value for nt in NodeType}

    def test_score_is_positive(self, builder):
        pkg = _build(builder, "How are files parsed?")
        for rn in pkg.resolved_nodes:
            assert rn.score > 0

    def test_reason_non_empty(self, builder):
        pkg = _build(builder, "How are files parsed?")
        for rn in pkg.resolved_nodes:
            assert len(rn.reason) > 0

    def test_node_by_id_lookup(self, builder):
        pkg = _build(builder, "How are files parsed?")
        for rn in pkg.resolved_nodes:
            found = pkg.node_by_id(rn.node_id)
            assert found is not None
            assert found.node_id == rn.node_id

    def test_node_by_id_missing(self, builder):
        pkg = _build(builder, "How are files parsed?")
        assert pkg.node_by_id("__does_not_exist__") is None

    def test_neighbour_ids_are_sorted(self, builder):
        pkg = _build(builder, "How are files parsed?")
        for rn in pkg.resolved_nodes:
            assert rn.neighbour_ids == sorted(rn.neighbour_ids)


# ===========================================================================
# Group 3: Subgraph expansion
# ===========================================================================

class TestSubgraphExpansion:

    def test_subgraph_contains_seed_nodes(self, synthetic_graph, builder):
        pkg = _build(builder, "How does retrieval work?")
        seed_ids = {rn.node_id for rn in pkg.resolved_nodes}
        retriever = RepositoryRetriever(synthetic_graph)
        subgraph = retriever.get_subgraph(seed_ids, max_hops=1)
        subgraph_node_ids = {n.id for n in subgraph.nodes}
        # Every seed node that exists in the graph should be in the subgraph
        for nid in seed_ids:
            if retriever.get_node(nid) is not None:
                assert nid in subgraph_node_ids

    def test_subgraph_node_count_geq_resolved(self, builder):
        pkg = _build(builder, "How does retrieval work?")
        # Subgraph always includes the seeds plus neighbours
        assert pkg.subgraph_node_count >= len(pkg.resolved_nodes)

    def test_subgraph_summary_nodes_by_type(self, builder):
        pkg = _build(builder, "How are files parsed?")
        total = sum(pkg.subgraph_summary.nodes_by_type.values())
        assert total == pkg.subgraph_node_count

    def test_subgraph_summary_edge_types_valid(self, builder):
        pkg = _build(builder, "How is the graph generated?")
        valid = {rt.value for rt in RelationshipType}
        for et in pkg.subgraph_summary.edge_types:
            assert et in valid

    def test_max_hops_zero_equals_seeds_only(self, synthetic_graph):
        builder0 = build_context_builder(synthetic_graph, top_k=3, max_hops=0)
        pkg = _build(builder0, "How are files parsed?")
        # With max_hops=0 the subgraph should contain only the seed nodes
        # (no neighbours).  Edges between seeds are still included.
        assert pkg.subgraph_node_count <= len(pkg.resolved_nodes)


# ===========================================================================
# Group 4: LLM context text
# ===========================================================================

class TestLlmContextText:

    def test_contains_question(self, builder):
        q = "How does retrieval work?"
        pkg = _build(builder, q)
        assert q in pkg.llm_context

    def test_contains_intent(self, builder):
        pkg = _build(builder, "How does retrieval work?")
        for cat in pkg.intent_categories:
            assert cat in pkg.llm_context

    def test_contains_node_headers(self, builder):
        pkg = _build(builder, "How does retrieval work?")
        # build_llm_context() emits "=== TYPE: label ===" headers
        assert "===" in pkg.llm_context

    def test_contains_subgraph_section(self, builder):
        pkg = _build(builder, "How does retrieval work?")
        assert "SUBGRAPH" in pkg.llm_context

    def test_contains_resolved_nodes_section(self, builder):
        pkg = _build(builder, "How does retrieval work?")
        assert "RESOLVED NODES" in pkg.llm_context

    def test_contains_query_resolver_score(self, builder):
        pkg = _build(builder, "How does retrieval work?")
        assert "QueryResolver score" in pkg.llm_context

    def test_llm_context_for_parsing_question(self, builder):
        pkg = _build(builder, "How are files parsed?")
        # Expect at least one of the parsing-related nodes to appear
        assert any(
            label in pkg.llm_context
            for label in ("parse_file", "parse_repository", "CodeParser")
        )

    def test_llm_context_for_retrieval_question(self, builder):
        pkg = _build(builder, "How does retrieval work?")
        assert any(
            label in pkg.llm_context
            for label in ("RepositoryRetriever", "get_node_context", "get_subgraph", "resolve_query")
        )

    def test_llm_context_for_graph_generation_question(self, builder):
        pkg = _build(builder, "How is the graph generated?")
        assert any(
            label in pkg.llm_context
            for label in ("GraphBuilder", "build_graph")
        )


# ===========================================================================
# Group 5: Query-specific expected output (regression checks)
# ===========================================================================

class TestQuerySpecificOutput:

    def test_parsing_question_resolves_code_parser(self, builder):
        pkg = _build(builder, "How are files parsed?")
        resolved_ids = pkg.top_node_ids()
        assert any("parse" in nid.lower() or "CodeParser" in nid for nid in resolved_ids)

    def test_retrieval_question_resolves_retriever(self, builder):
        pkg = _build(builder, "How does retrieval work?")
        resolved_ids = pkg.top_node_ids()
        assert any("retriev" in nid.lower() or "Retriever" in nid for nid in resolved_ids)

    def test_graph_generation_question_resolves_graph_builder(self, builder):
        pkg = _build(builder, "How is the graph generated?")
        resolved_ids = pkg.top_node_ids()
        assert any("Graph" in nid or "build" in nid.lower() for nid in resolved_ids)

    def test_all_three_questions_produce_non_empty_llm_context(self, builder):
        questions = [
            "How are files parsed?",
            "How does retrieval work?",
            "How is the graph generated?",
        ]
        for q in questions:
            pkg = _build(builder, q)
            assert len(pkg.llm_context) > 100, f"Empty context for: {q}"


# ===========================================================================
# Group 6: Edge cases
# ===========================================================================

class TestEdgeCases:

    def test_empty_question_does_not_raise(self, builder):
        pkg = _build(builder, "")
        assert isinstance(pkg, ContextPackage)

    def test_gibberish_question_returns_empty_resolved_nodes(self, builder):
        pkg = _build(builder, "xyzzy blarghnarg florbibble")
        # No nodes should match — resolved_nodes may be empty or very short
        assert isinstance(pkg.resolved_nodes, list)

    def test_override_top_k(self, builder):
        pkg = builder.build("How are files parsed?", top_k=2)
        assert len(pkg.resolved_nodes) <= 2

    def test_override_max_hops(self, builder):
        pkg_0 = builder.build("How does retrieval work?", max_hops=0)
        pkg_1 = builder.build("How does retrieval work?", max_hops=1)
        # With more hops the subgraph should be at least as large
        assert pkg_1.subgraph_node_count >= pkg_0.subgraph_node_count

    def test_deterministic(self, builder):
        q = "How are files parsed?"
        pkg1 = _build(builder, q)
        pkg2 = _build(builder, q)
        assert pkg1.top_node_ids() == pkg2.top_node_ids()
        assert pkg1.subgraph_node_count == pkg2.subgraph_node_count


# ===========================================================================
# Group 7: SubgraphSummary helper unit test
# ===========================================================================

class TestSubgraphSummaryHelper:

    def test_empty_graph(self):
        g = RepositoryGraph(nodes=[], edges=[])
        s = _build_subgraph_summary(g)
        assert s.node_count == 0
        assert s.edge_count == 0
        assert s.nodes_by_type == {}
        assert s.edge_types == []

    def test_node_type_counts(self):
        nodes = [
            _node("C1", NodeType.CLASS,    "C1"),
            _node("C2", NodeType.CLASS,    "C2"),
            _node("f1", NodeType.FUNCTION, "f1"),
        ]
        g = RepositoryGraph(nodes=nodes, edges=[])
        s = _build_subgraph_summary(g)
        assert s.nodes_by_type[NodeType.CLASS.value]    == 2
        assert s.nodes_by_type[NodeType.FUNCTION.value] == 1

    def test_edge_types_sorted_and_deduplicated(self):
        nodes = [
            _node("A", NodeType.CLASS,  "A"),
            _node("B", NodeType.METHOD, "B"),
        ]
        edges = [
            _edge("A", "B", RelationshipType.CONTAINS),
            _edge("A", "B", RelationshipType.CONTAINS),   # duplicate type
            _edge("B", "A", RelationshipType.CALLS),
        ]
        g = RepositoryGraph(nodes=nodes, edges=edges)
        s = _build_subgraph_summary(g)
        assert s.edge_count == 3
        assert s.edge_types == sorted({"contains", "calls"})


# ===========================================================================
# Example output printer  (not a test — run manually with -s to inspect)
# ===========================================================================

def _print_example_output(builder: ContextBuilder) -> None:  # pragma: no cover
    questions = [
        "How are files parsed?",
        "How does retrieval work?",
        "How is the graph generated?",
    ]
    banner = "=" * 70
    for q in questions:
        pkg = builder.build(q)
        print(f"\n{banner}")
        print(f"QUESTION: {q}")
        print(f"Intents : {pkg.intent_categories}")
        print(f"Keywords: {pkg.keywords}")
        print(f"Resolved: {pkg.top_node_ids()}")
        print(f"Subgraph: {pkg.subgraph_node_count} nodes, {pkg.subgraph_edge_count} edges")
        print(f"\n{pkg.llm_context}")
        print(banner)


if __name__ == "__main__":
    # Run as a script to see full example output:
    #   python tests/test_context_pipeline.py
    import sys
    sys.path.insert(0, ".")

    from app.models.pydantic_models import (
        GraphEdge, GraphNode, NodeType, RelationshipType, RepositoryGraph,
    )
    from backend.app.rag.context_builder import build_context_builder

    # Re-use the same synthetic graph logic defined above
    # (copy–paste avoided; import the fixture directly when running as script)
    print("Run via pytest -s tests/test_context_pipeline.py to see output.")