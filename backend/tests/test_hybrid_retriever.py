"""
tests/test_hybrid_retriever.py
================================
Tests for hybrid retrieval (semantic + keyword RRF fusion).

Tests use a small synthetic graph so they run quickly without downloading
models. The EmbeddingModel.is_available() check ensures the suite doesn't
fail when sentence-transformers / torch is absent.
"""
from __future__ import annotations

import pytest

from app.models.pydantic_models import (
    GraphEdge,
    GraphNode,
    NodeType,
    RelationshipType,
    RepositoryGraph,
)
from app.retrievers.code_retriever import RepositoryRetriever
from app.retrievers.query_resolver import QueryResolver
from app.embeddings.embedding_model import EmbeddingModel


# ---------------------------------------------------------------------------
# Synthetic graph
# ---------------------------------------------------------------------------

def _make_graph() -> RepositoryGraph:
    nodes = [
        GraphNode(id="Foo",           type=NodeType.CLASS,    label="Foo",    docstring="Foo class does foo things."),
        GraphNode(id="Foo.bar",       type=NodeType.METHOD,   label="bar",    docstring="bar method processes input."),
        GraphNode(id="Foo.baz",       type=NodeType.METHOD,   label="baz",    docstring="baz method handles output."),
        GraphNode(id="helper",        type=NodeType.FUNCTION, label="helper", docstring="Helper utility function."),
        GraphNode(id="app.py",        type=NodeType.FILE,     label="app.py"),
        GraphNode(id="os",            type=NodeType.MODULE,   label="os"),
    ]
    edges = [
        GraphEdge(source="app.py",  target="Foo",     relationship=RelationshipType.CONTAINS),
        GraphEdge(source="Foo",     target="Foo.bar", relationship=RelationshipType.CONTAINS),
        GraphEdge(source="Foo",     target="Foo.baz", relationship=RelationshipType.CONTAINS),
        GraphEdge(source="app.py",  target="helper",  relationship=RelationshipType.CONTAINS),
        GraphEdge(source="Foo.bar", target="helper",  relationship=RelationshipType.CALLS),
        GraphEdge(source="app.py",  target="os",      relationship=RelationshipType.IMPORTS),
    ]
    return RepositoryGraph(nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# EmbeddingModel tests (no model download required)
# ---------------------------------------------------------------------------

class TestEmbeddingModel:

    def test_is_available_returns_bool(self):
        result = EmbeddingModel.is_available()
        assert isinstance(result, bool)

    def test_default_model_name(self):
        model = EmbeddingModel()
        assert model.model_name == "all-MiniLM-L6-v2"

    def test_custom_model_name(self):
        model = EmbeddingModel(model_name="custom-model")
        assert model.model_name == "custom-model"

    def test_encode_empty_list_returns_empty(self):
        model = EmbeddingModel()
        result = model.encode([])
        assert result == []

    @pytest.mark.skipif(not EmbeddingModel.is_available(), reason="sentence-transformers not installed")
    def test_encode_returns_list_of_floats(self):
        model = EmbeddingModel()
        vecs = model.encode(["hello world", "foo bar"])
        assert len(vecs) == 2
        assert all(isinstance(v, list) for v in vecs)
        assert all(isinstance(x, float) for x in vecs[0])

    @pytest.mark.skipif(not EmbeddingModel.is_available(), reason="sentence-transformers not installed")
    def test_encode_one_returns_flat_list(self):
        model = EmbeddingModel()
        vec = model.encode_one("test string")
        assert isinstance(vec, list)
        assert all(isinstance(x, float) for x in vec)

    @pytest.mark.skipif(not EmbeddingModel.is_available(), reason="sentence-transformers not installed")
    def test_encode_produces_same_dim_for_all_inputs(self):
        model = EmbeddingModel()
        vecs = model.encode(["short", "a much longer sentence with many words"])
        assert len(vecs[0]) == len(vecs[1])

    @pytest.mark.skipif(not EmbeddingModel.is_available(), reason="sentence-transformers not installed")
    def test_encode_one_matches_batch(self):
        model = EmbeddingModel()
        batch = model.encode(["hello world"])
        single = model.encode_one("hello world")
        assert len(batch[0]) == len(single)
        # Values should be close (may not be exactly equal due to batch vs single path)
        assert all(abs(a - b) < 1e-4 for a, b in zip(batch[0], single))


# ---------------------------------------------------------------------------
# SemanticIndex tests
# ---------------------------------------------------------------------------

class TestSemanticIndex:

    def test_build_produces_index(self):
        from app.retrievers.hybrid_retriever import SemanticIndex
        graph = _make_graph()
        retriever = RepositoryRetriever(graph)
        idx = SemanticIndex.build(graph, retriever)
        assert len(idx.node_ids) > 0
        assert idx.backend_name in ("sentence-transformers", "tfidf")

    def test_index_has_all_graph_nodes(self):
        from app.retrievers.hybrid_retriever import SemanticIndex
        graph = _make_graph()
        retriever = RepositoryRetriever(graph)
        idx = SemanticIndex.build(graph, retriever)
        for node in graph.nodes:
            assert node.id in idx.node_ids

    def test_query_returns_ranks(self):
        from app.retrievers.hybrid_retriever import SemanticIndex
        graph = _make_graph()
        retriever = RepositoryRetriever(graph)
        idx = SemanticIndex.build(graph, retriever)
        ranks = idx.query("class processes input", top_k=3)
        assert isinstance(ranks, dict)
        assert all(isinstance(v, int) for v in ranks.values())
        assert all(v >= 1 for v in ranks.values())

    def test_query_returns_at_most_top_k(self):
        from app.retrievers.hybrid_retriever import SemanticIndex
        graph = _make_graph()
        retriever = RepositoryRetriever(graph)
        idx = SemanticIndex.build(graph, retriever)
        ranks = idx.query("anything", top_k=2)
        assert len(ranks) <= 2

    def test_query_ranks_are_unique(self):
        from app.retrievers.hybrid_retriever import SemanticIndex
        graph = _make_graph()
        retriever = RepositoryRetriever(graph)
        idx = SemanticIndex.build(graph, retriever)
        ranks = idx.query("foo bar", top_k=5)
        assert len(set(ranks.values())) == len(ranks)


# ---------------------------------------------------------------------------
# HybridQueryResolver tests
# ---------------------------------------------------------------------------

class TestHybridQueryResolver:

    def _make_hybrid(self, kw_weight=3.0):
        from app.retrievers.hybrid_retriever import SemanticIndex, HybridQueryResolver
        graph = _make_graph()
        retriever = RepositoryRetriever(graph)
        idx = SemanticIndex.build(graph, retriever)
        return HybridQueryResolver(graph, idx, keyword_weight=kw_weight), graph

    def test_resolve_returns_query_resolution_result(self):
        from app.retrievers.query_resolver import QueryResolutionResult
        hybrid, _ = self._make_hybrid()
        result = hybrid.resolve_query("What does Foo do?")
        assert isinstance(result, QueryResolutionResult)

    def test_resolve_returns_correct_number_of_matches(self):
        hybrid, _ = self._make_hybrid()
        result = hybrid.resolve_query("Foo bar method", top_k=3)
        assert len(result.matches) <= 3

    def test_resolve_matches_have_required_fields(self):
        hybrid, _ = self._make_hybrid()
        result = hybrid.resolve_query("helper function", top_k=5)
        for match in result.matches:
            assert match.node_id
            assert match.node_type
            assert match.score >= 0
            assert match.reason

    def test_resolve_preserves_intent_detection(self):
        hybrid, _ = self._make_hybrid()
        result = hybrid.resolve_query("How is Foo parsed?")
        # Intent should be detected by underlying QueryResolver
        assert result.intent is not None

    def test_resolve_preserves_keywords(self):
        hybrid, _ = self._make_hybrid()
        result = hybrid.resolve_query("Foo bar baz")
        assert len(result.keywords) > 0

    def test_weighted_higher_kw_gives_more_keyword_like_results(self):
        """Higher kw_weight should produce results closer to keyword-only."""
        from app.retrievers.hybrid_retriever import SemanticIndex, HybridQueryResolver
        graph = _make_graph()
        retriever = RepositoryRetriever(graph)
        idx = SemanticIndex.build(graph, retriever)

        kw_resolver  = QueryResolver(graph, default_top_k=5)
        hybrid_high  = HybridQueryResolver(graph, idx, keyword_weight=10.0)
        hybrid_low   = HybridQueryResolver(graph, idx, keyword_weight=1.0)

        question = "What does Foo do?"
        kw_result    = kw_resolver.resolve_query(question, top_k=5)
        high_result  = hybrid_high.resolve_query(question, top_k=5)
        low_result   = hybrid_low.resolve_query(question, top_k=5)

        kw_ids   = [m.node_id for m in kw_result.matches]
        high_ids = [m.node_id for m in high_result.matches]
        low_ids  = [m.node_id for m in low_result.matches]

        # High kw_weight should overlap more with pure keyword result
        high_overlap = len(set(kw_ids) & set(high_ids))
        low_overlap  = len(set(kw_ids) & set(low_ids))
        assert high_overlap >= low_overlap, (
            f"High kw_weight ({high_overlap} overlap) should >= low kw_weight ({low_overlap})"
        )

    def test_rrf_reason_contains_ranks(self):
        hybrid, _ = self._make_hybrid()
        result = hybrid.resolve_query("helper function")
        for m in result.matches[:3]:
            assert "keyword_rank" in m.reason
            assert "semantic_rank" in m.reason

    def test_forward_extract_keywords(self):
        hybrid, _ = self._make_hybrid()
        kws = hybrid.extract_keywords("How does Foo process data?")
        assert isinstance(kws, list)
        assert len(kws) > 0

    def test_forward_expand_keywords(self):
        hybrid, _ = self._make_hybrid()
        expanded = hybrid.expand_keywords(["retrieve", "fetch"])
        assert len(expanded) >= 2


# ---------------------------------------------------------------------------
# build_hybrid_context_builder integration test
# ---------------------------------------------------------------------------

class TestBuildHybridContextBuilder:

    def test_returns_context_builder(self):
        from app.retrievers.hybrid_retriever import build_hybrid_context_builder
        from app.rag.context_builder import ContextBuilder
        graph = _make_graph()
        cb = build_hybrid_context_builder(graph, top_k=5)
        assert isinstance(cb, ContextBuilder)

    def test_build_returns_context_package(self):
        from app.retrievers.hybrid_retriever import build_hybrid_context_builder
        from app.rag.context_builder import ContextPackage
        graph = _make_graph()
        cb = build_hybrid_context_builder(graph, top_k=5)
        package = cb.build("What does Foo do?")
        assert isinstance(package, ContextPackage)
        assert package.question == "What does Foo do?"
        assert len(package.llm_context) > 0

    def test_build_populates_resolved_nodes(self):
        from app.retrievers.hybrid_retriever import build_hybrid_context_builder
        graph = _make_graph()
        cb = build_hybrid_context_builder(graph, top_k=5)
        package = cb.build("Foo class")
        # Should resolve at least one node for "Foo class"
        assert len(package.resolved_nodes) > 0
