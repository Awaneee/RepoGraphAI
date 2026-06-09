"""
tests/test_query_resolver_v3.py
================================
Quality-focused tests for QueryResolver v3.

Design philosophy
-----------------
Every test uses a **synthetic** repository graph — no RepoGraphAI symbols,
no FastAPI symbols, no framework-specific names.  The graphs are
deliberately minimal so that each test exercises exactly one behaviour.

The test names describe what a user of *any* Python repository would
expect, not what the current codebase happens to contain.

Coverage map
------------
1.  Intent detection
      - parse-family queries → PARSING intent
      - generate-family queries → GENERATION intent
      - ambiguous / mixed queries → multiple intents detected
      - unknown-domain query → UNKNOWN intent

2.  Query expansion
      - "parse" expands to include "read", "load", "decode", etc.
      - "retrieve" expands to include "search", "fetch", "find", etc.
      - "generate" expands to include "build", "create", etc.

3.  Node-type weighting for implementation intents
      - Methods score higher than plain classes for PARSING query
      - Functions score higher than plain classes for RETRIEVAL query

4.  DTO penalty for implementation queries
      - "*Schema", "*Model", "*Request", "*Response", "*Result" nodes
        are penalised when the query is implementation-oriented
      - DTO nodes are NOT penalised for non-implementation queries
        (e.g. a statistics / config question about a model)

5.  End-to-end ranking correctness
      - "How are files parsed?" → parse_file / FileParser rank above
        ParsedFile / ParsedResult
      - "How is content generated?" → generate_output / ContentBuilder
        rank above GeneratedContent / OutputResult
      - "How is data retrieved?" → fetch_data / DataRetriever rank
        above RetrievalResult / FetchedData

6.  Reason-string explainability
      - intent boost is present in reason when it fires
      - DTO penalty is present in reason when it fires
      - expanded-keyword hits are annotated with [expanded]

7.  Edge cases
      - empty graph returns no matches
      - query with only stop words returns no matches
      - single-node graph returns that node when its label matches
"""

from __future__ import annotations

import pytest
from collections import defaultdict
from typing import Optional

# ---------------------------------------------------------------------------
# Minimal stub of pydantic_models so the tests can run without the full app.
# If the real models are importable, they will be used instead.
# ---------------------------------------------------------------------------
try:
    from app.models.pydantic_models import (
        GraphEdge,
        GraphNode,
        NodeType,
        RelationshipType,
        RepositoryGraph,
    )
except ImportError:
    # Inline stubs so the test file is self-contained
    from enum import Enum
    from dataclasses import dataclass, field
    from pydantic import BaseModel

    class NodeType(str, Enum):
        FILE     = "File"
        MODULE   = "Module"
        CLASS    = "Class"
        FUNCTION = "Function"
        METHOD   = "Method"

    class RelationshipType(str, Enum):
        CONTAINS    = "contains"
        IMPORTS     = "imports"
        CALLS       = "calls"
        INHERITS    = "inherits"
        INSTANTIATES = "instantiates"
        DECORATES   = "decorates"
        OVERRIDES   = "overrides"

    class GraphNode(BaseModel):
        id:            str
        type:          NodeType
        label:         str
        file_path:     Optional[str] = None
        line_number:   Optional[int] = None
        docstring:     Optional[str] = None
        module_origin: Optional[str] = None

    class GraphEdge(BaseModel):
        source:         str
        target:         str
        relationship:   RelationshipType
        decorator_name: Optional[str] = None

    class RepositoryGraph(BaseModel):
        nodes: list[GraphNode]
        edges: list[GraphEdge]


# ---------------------------------------------------------------------------
# Import the module under test.
# Adjust the import path if your project layout differs.
# ---------------------------------------------------------------------------
try:
    from app.retrievers.query_resolver import (
        QueryResolver,
        IntentCategory,
        QueryIntent,
        _looks_like_dto,
        _split_camel_case,
        _snake_parts,
        _stem,
    )
except ImportError:
    # Allow running the test file directly against the output artefact
    import importlib.util, sys, os
    _spec = importlib.util.spec_from_file_location(
        "query_resolver",
        os.path.join(os.path.dirname(__file__), "query_resolver.py"),
    )
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    sys.modules["query_resolver"] = _mod
    QueryResolver     = _mod.QueryResolver
    IntentCategory    = _mod.IntentCategory
    QueryIntent       = _mod.QueryIntent
    _looks_like_dto   = _mod._looks_like_dto
    _split_camel_case = _mod._split_camel_case
    _snake_parts      = _mod._snake_parts
    _stem             = _mod._stem


# ===========================================================================
# Helpers
# ===========================================================================

def _node(
    node_id: str,
    node_type: NodeType,
    label: Optional[str] = None,
) -> GraphNode:
    return GraphNode(
        id=node_id,
        type=node_type,
        label=label or node_id,
    )


def _edge(
    source: str,
    target: str,
    rel: RelationshipType,
    decorator_name: Optional[str] = None,
) -> GraphEdge:
    return GraphEdge(
        source=source,
        target=target,
        relationship=rel,
        decorator_name=decorator_name,
    )


def _make_graph(
    nodes: list[GraphNode],
    edges: Optional[list[GraphEdge]] = None,
) -> RepositoryGraph:
    return RepositoryGraph(nodes=nodes, edges=edges or [])


def _top_ids(resolver: QueryResolver, question: str, k: int = 5) -> list[str]:
    return resolver.resolve_to_node_ids(question, top_k=k)


# ===========================================================================
# 1. Intent detection
# ===========================================================================

class TestIntentDetection:

    def _resolver(self) -> QueryResolver:
        return QueryResolver(_make_graph([_node("x", NodeType.FUNCTION)]))

    def test_parsing_intent_from_verb_parse(self):
        r = self._resolver()
        intent = r.detect_intent(["parse", "file"])
        assert IntentCategory.PARSING in intent.categories

    def test_parsing_intent_from_noun_parser(self):
        r = self._resolver()
        intent = r.detect_intent(["parser", "module"])
        assert IntentCategory.PARSING in intent.categories

    def test_parsing_intent_from_inflection_parsed(self):
        r = self._resolver()
        # "parsed" stems to "pars" which is in the PARSING lexicon
        kws = r.extract_keywords("How are files parsed?")
        intent = r.detect_intent(kws)
        assert IntentCategory.PARSING in intent.categories
        assert intent.is_implementation_query is True

    def test_generation_intent_from_generate(self):
        r = self._resolver()
        intent = r.detect_intent(["generate", "report"])
        assert IntentCategory.GENERATION in intent.categories
        assert intent.is_implementation_query is True

    def test_generation_intent_from_build(self):
        r = self._resolver()
        intent = r.detect_intent(["build", "graph"])
        assert IntentCategory.GENERATION in intent.categories

    def test_retrieval_intent_from_search(self):
        r = self._resolver()
        intent = r.detect_intent(["search", "nodes"])
        assert IntentCategory.RETRIEVAL in intent.categories
        assert intent.is_implementation_query is True

    def test_statistics_intent_not_implementation(self):
        r = self._resolver()
        intent = r.detect_intent(["statistics", "metrics"])
        assert IntentCategory.STATISTICS in intent.categories
        # Statistics is not in _IMPLEMENTATION_INTENTS
        # (it can return schema/model nodes legitimately)
        # However, it still uses METHOD/FUNCTION preferred types,
        # so we only check that it is NOT flagged as impl query
        # if no other implementation intent is detected.
        # With only "statistics" + "metrics", no implementation intent
        # should fire.
        impl_intents_found = [
            c for c in intent.categories
            if c in {
                IntentCategory.PARSING,
                IntentCategory.GENERATION,
                IntentCategory.RETRIEVAL,
                IntentCategory.LOADING,
                IntentCategory.SAVING,
                IntentCategory.ANALYSIS,
                IntentCategory.AUTHENTICATION,
                IntentCategory.ROUTING,
                IntentCategory.EXECUTION,
                IntentCategory.TRANSFORMATION,
            }
        ]
        assert not impl_intents_found, (
            f"Statistics-only query should not trigger implementation intents, "
            f"but got: {impl_intents_found}"
        )

    def test_unknown_intent_for_generic_question(self):
        r = self._resolver()
        intent = r.detect_intent(["repository", "structure"])
        # "repository" and "structure" are not in any intent lexicon
        assert intent.categories == [IntentCategory.UNKNOWN]
        assert intent.is_implementation_query is False

    def test_multiple_intents_for_mixed_query(self):
        r = self._resolver()
        # "load and parse" hits both LOADING and PARSING
        intent = r.detect_intent(["load", "parse", "file"])
        assert len(intent.categories) >= 2
        assert IntentCategory.PARSING in intent.categories
        assert IntentCategory.LOADING in intent.categories


# ===========================================================================
# 2. Query expansion
# ===========================================================================

class TestQueryExpansion:

    def _resolver(self) -> QueryResolver:
        return QueryResolver(_make_graph([_node("x", NodeType.FUNCTION)]))

    def test_parse_expands_to_read(self):
        r = self._resolver()
        expanded = r.expand_keywords(["parse"])
        assert "read" in expanded

    def test_parse_expands_to_decode(self):
        r = self._resolver()
        expanded = r.expand_keywords(["parse"])
        assert "decode" in expanded

    def test_retrieve_expands_to_fetch(self):
        r = self._resolver()
        expanded = r.expand_keywords(["retrieve"])
        assert "fetch" in expanded

    def test_retrieve_expands_to_search(self):
        r = self._resolver()
        expanded = r.expand_keywords(["retrieve"])
        assert "search" in expanded

    def test_generate_expands_to_build(self):
        r = self._resolver()
        expanded = r.expand_keywords(["generate"])
        assert "build" in expanded

    def test_original_keywords_preserved(self):
        r = self._resolver()
        base = ["parse", "file"]
        expanded = r.expand_keywords(base)
        assert "parse" in expanded
        assert "file" in expanded

    def test_no_duplicate_keywords(self):
        r = self._resolver()
        expanded = r.expand_keywords(["parse", "read"])
        # "read" is an expansion of "parse" but also a base keyword;
        # it should appear exactly once.
        assert expanded.count("read") == 1

    def test_unknown_keyword_not_expanded(self):
        r = self._resolver()
        expanded = r.expand_keywords(["frobulate"])
        assert expanded == ["frobulate"]


# ===========================================================================
# 3. Node-type weighting for implementation intents
# ===========================================================================

class TestNodeTypeWeighting:

    def _parsing_graph(self) -> RepositoryGraph:
        """
        A minimal graph with:
          - parse_record   (METHOD)    — implementation
          - RecordReader   (CLASS)     — implementation (has CALLS edges)
          - ParsedRecord   (CLASS)     — DTO (name pattern, no CALLS edges)
        """
        nodes = [
            _node("parse_record",  NodeType.METHOD),
            _node("RecordReader",  NodeType.CLASS),
            _node("ParsedRecord",  NodeType.CLASS),
        ]
        edges = [
            _edge("RecordReader", "parse_record", RelationshipType.CONTAINS),
            _edge("parse_record", "RecordReader", RelationshipType.CALLS),
        ]
        return _make_graph(nodes, edges)

    def test_method_outranks_dto_class_for_parsing_query(self):
        resolver = QueryResolver(self._parsing_graph())
        top = _top_ids(resolver, "How are records parsed?", k=3)
        # parse_record (METHOD) should appear before ParsedRecord (DTO CLASS)
        assert "parse_record" in top
        method_pos = top.index("parse_record")
        if "ParsedRecord" in top:
            dto_pos = top.index("ParsedRecord")
            assert method_pos < dto_pos, (
                f"parse_record (pos {method_pos}) should rank before "
                f"ParsedRecord (pos {dto_pos})"
            )

    def test_implementation_class_outranks_dto_for_parsing_query(self):
        """
        RecordReader (has CALLS edges → not a DTO) should rank above
        ParsedRecord (no CALLS edges → detected as DTO).
        """
        resolver = QueryResolver(self._parsing_graph())
        result = resolver.resolve_query("How does record parsing work?", top_k=5)
        ids = result.top_node_ids()
        if "RecordReader" in ids and "ParsedRecord" in ids:
            assert ids.index("RecordReader") < ids.index("ParsedRecord"), (
                "Implementation class should rank above DTO class"
            )

    def _retrieval_graph(self) -> RepositoryGraph:
        nodes = [
            _node("fetch_items",     NodeType.FUNCTION),
            _node("ItemRetriever",   NodeType.CLASS),
            _node("FetchedItems",    NodeType.CLASS),    # DTO
            _node("RetrievalResult", NodeType.CLASS),   # DTO
        ]
        edges = [
            _edge("ItemRetriever", "fetch_items",   RelationshipType.CONTAINS),
            _edge("fetch_items",   "FetchedItems",  RelationshipType.INSTANTIATES),
        ]
        return _make_graph(nodes, edges)

    def test_function_outranks_dto_for_retrieval_query(self):
        resolver = QueryResolver(self._retrieval_graph())
        top = _top_ids(resolver, "How is data retrieved?", k=5)
        assert "fetch_items" in top
        if "FetchedItems" in top:
            assert top.index("fetch_items") < top.index("FetchedItems"), (
                "fetch_items (FUNCTION) should rank above FetchedItems (DTO)"
            )


# ===========================================================================
# 4. DTO detection and penalty
# ===========================================================================

class TestDTODetectionAndPenalty:

    def _simple_graph_with_dto(self) -> RepositoryGraph:
        """
        graph:
          DocumentParser (CLASS, has CALLS edges → impl)
          parse_document (METHOD)
          ParsedDocument (CLASS, no CALLS/INSTANTIATES → DTO)
          DocumentSchema (CLASS, name ends in Schema → DTO)
          DocumentResult (CLASS, name ends in Result → DTO)
          DocumentRequest(CLASS, name ends in Request → DTO)
        """
        nodes = [
            _node("DocumentParser",  NodeType.CLASS),
            _node("parse_document",  NodeType.METHOD),
            _node("ParsedDocument",  NodeType.CLASS),
            _node("DocumentSchema",  NodeType.CLASS),
            _node("DocumentResult",  NodeType.CLASS),
            _node("DocumentRequest", NodeType.CLASS),
        ]
        edges = [
            _edge("DocumentParser", "parse_document", RelationshipType.CONTAINS),
            _edge("parse_document", "DocumentParser", RelationshipType.CALLS),
        ]
        return _make_graph(nodes, edges)

    def test_parsed_prefix_detected_as_dto(self):
        graph = self._simple_graph_with_dto()
        node = next(n for n in graph.nodes if n.id == "ParsedDocument")
        assert _looks_like_dto(node, graph), "ParsedDocument should be DTO"

    def test_schema_suffix_detected_as_dto(self):
        graph = self._simple_graph_with_dto()
        node = next(n for n in graph.nodes if n.id == "DocumentSchema")
        assert _looks_like_dto(node, graph), "DocumentSchema should be DTO"

    def test_result_suffix_detected_as_dto(self):
        graph = self._simple_graph_with_dto()
        node = next(n for n in graph.nodes if n.id == "DocumentResult")
        assert _looks_like_dto(node, graph), "DocumentResult should be DTO"

    def test_request_suffix_detected_as_dto(self):
        graph = self._simple_graph_with_dto()
        node = next(n for n in graph.nodes if n.id == "DocumentRequest")
        assert _looks_like_dto(node, graph), "DocumentRequest should be DTO"

    def test_implementation_class_not_dto(self):
        graph = self._simple_graph_with_dto()
        node = next(n for n in graph.nodes if n.id == "DocumentParser")
        assert not _looks_like_dto(node, graph), (
            "DocumentParser (has CALLS edges) should NOT be detected as DTO"
        )

    def test_dto_penalty_fires_for_implementation_query(self):
        resolver = QueryResolver(self._simple_graph_with_dto())
        result = resolver.resolve_query("How are documents parsed?", top_k=10)

        # Find matches for DTO nodes
        dto_matches = {
            m.node_id: m
            for m in result.matches
            if m.node_id in {"ParsedDocument", "DocumentSchema",
                             "DocumentResult", "DocumentRequest"}
        }
        for node_id, match in dto_matches.items():
            assert "dto-penalty" in match.reason, (
                f"{node_id} should have dto-penalty in reason, got: {match.reason}"
            )

    def test_dto_nodes_rank_below_implementation_nodes(self):
        resolver = QueryResolver(self._simple_graph_with_dto())
        result = resolver.resolve_query("How are documents parsed?", top_k=10)
        ids = result.top_node_ids()

        impl_nodes = {"DocumentParser", "parse_document"}
        dto_nodes  = {"ParsedDocument", "DocumentSchema",
                      "DocumentResult", "DocumentRequest"}

        for impl_id in impl_nodes:
            if impl_id not in ids:
                continue
            for dto_id in dto_nodes:
                if dto_id not in ids:
                    continue
                assert ids.index(impl_id) < ids.index(dto_id), (
                    f"{impl_id} should rank before {dto_id} but "
                    f"got positions {ids.index(impl_id)} vs {ids.index(dto_id)}"
                )

    def test_dataclass_decorator_detected_as_dto(self):
        """A class with @dataclass decorator should be flagged as DTO."""
        nodes = [
            _node("Record", NodeType.CLASS),
            _node("record_decorator", NodeType.FUNCTION),
        ]
        edges = [
            _edge("record_decorator", "Record",
                  RelationshipType.DECORATES,
                  decorator_name="dataclass"),
        ]
        graph = _make_graph(nodes, edges)
        record_node = graph.nodes[0]
        assert _looks_like_dto(record_node, graph), (
            "Class with @dataclass decorator should be DTO"
        )

    def test_basemodel_decorator_detected_as_dto(self):
        """A class with @BaseModel / pydantic model decorator → DTO."""
        nodes = [_node("UserProfile", NodeType.CLASS)]
        edges = [
            _edge("pydantic", "UserProfile",
                  RelationshipType.DECORATES,
                  decorator_name="BaseModel"),
        ]
        graph = _make_graph(nodes, edges)
        node = graph.nodes[0]
        assert _looks_like_dto(node, graph)


# ===========================================================================
# 5. End-to-end ranking (the headline test cases)
# ===========================================================================

class TestEndToEndRanking:

    def _file_parsing_graph(self) -> RepositoryGraph:
        """
        Represents a generic 'file parsing' subsystem:
          FileParser     (CLASS)    — implementation class
          parse_file     (METHOD)   — implementation method
          parse_all      (METHOD)   — implementation method
          ParsedFile     (CLASS)    — DTO
          ParsedContent  (CLASS)    — DTO
          FileResult     (CLASS)    — DTO
        """
        nodes = [
            _node("FileParser",    NodeType.CLASS),
            _node("parse_file",    NodeType.METHOD),
            _node("parse_all",     NodeType.METHOD),
            _node("ParsedFile",    NodeType.CLASS),
            _node("ParsedContent", NodeType.CLASS),
            _node("FileResult",    NodeType.CLASS),
        ]
        edges = [
            _edge("FileParser", "parse_file", RelationshipType.CONTAINS),
            _edge("FileParser", "parse_all",  RelationshipType.CONTAINS),
            _edge("parse_file", "FileParser", RelationshipType.CALLS),
            _edge("parse_all",  "parse_file", RelationshipType.CALLS),
        ]
        return _make_graph(nodes, edges)

    def test_parse_file_ranks_above_parsed_file(self):
        """
        "How are files parsed?" should retrieve parse_file above ParsedFile.
        This is the headline regression test from the bug report.
        """
        resolver = QueryResolver(self._file_parsing_graph())
        result = resolver.resolve_query("How are files parsed?", top_k=6)
        ids = result.top_node_ids()

        assert "parse_file" in ids, "parse_file should be in top results"
        assert "ParsedFile"  in ids, "ParsedFile should be in top results"
        assert ids.index("parse_file") < ids.index("ParsedFile"), (
            f"parse_file should rank before ParsedFile. "
            f"Got order: {ids}"
        )

    def test_file_parser_class_ranks_above_dto_classes(self):
        resolver = QueryResolver(self._file_parsing_graph())
        ids = _top_ids(resolver, "How are files parsed?", k=6)
        if "FileParser" in ids:
            for dto in ("ParsedFile", "ParsedContent", "FileResult"):
                if dto in ids:
                    assert ids.index("FileParser") < ids.index(dto), (
                        f"FileParser should rank above {dto}"
                    )

    def _generation_graph(self) -> RepositoryGraph:
        nodes = [
            _node("generate_output",   NodeType.FUNCTION),
            _node("ContentBuilder",    NodeType.CLASS),
            _node("build_content",     NodeType.METHOD),
            _node("GeneratedContent",  NodeType.CLASS),   # DTO
            _node("OutputResult",      NodeType.CLASS),   # DTO
        ]
        edges = [
            _edge("ContentBuilder", "build_content",    RelationshipType.CONTAINS),
            _edge("build_content",  "ContentBuilder",   RelationshipType.CALLS),
            _edge("generate_output","GeneratedContent", RelationshipType.INSTANTIATES),
        ]
        return _make_graph(nodes, edges)

    def test_generate_output_ranks_above_generated_content(self):
        resolver = QueryResolver(self._generation_graph())
        ids = _top_ids(resolver, "How is content generated?", k=5)
        assert "generate_output" in ids
        if "GeneratedContent" in ids:
            assert ids.index("generate_output") < ids.index("GeneratedContent"), (
                "generate_output (FUNCTION) should rank above GeneratedContent (DTO)"
            )

    def _retrieval_graph(self) -> RepositoryGraph:
        nodes = [
            _node("fetch_records",    NodeType.METHOD),
            _node("DataRetriever",    NodeType.CLASS),
            _node("search_index",     NodeType.METHOD),
            _node("RetrievalResult",  NodeType.CLASS),   # DTO
            _node("FetchedData",      NodeType.CLASS),   # DTO
        ]
        edges = [
            _edge("DataRetriever", "fetch_records",  RelationshipType.CONTAINS),
            _edge("DataRetriever", "search_index",   RelationshipType.CONTAINS),
            _edge("fetch_records", "DataRetriever",  RelationshipType.CALLS),
            _edge("search_index",  "DataRetriever",  RelationshipType.CALLS),
        ]
        return _make_graph(nodes, edges)

    def test_retrieval_methods_rank_above_dto_results(self):
        resolver = QueryResolver(self._retrieval_graph())
        ids = _top_ids(resolver, "How is data retrieved?", k=5)
        impl_nodes = ["fetch_records", "search_index", "DataRetriever"]
        dto_nodes  = ["RetrievalResult", "FetchedData"]
        for impl in impl_nodes:
            if impl not in ids:
                continue
            for dto in dto_nodes:
                if dto not in ids:
                    continue
                assert ids.index(impl) < ids.index(dto), (
                    f"{impl} should rank before {dto}"
                )


# ===========================================================================
# 6. Reason-string explainability
# ===========================================================================

class TestReasonStrings:

    def _graph(self) -> RepositoryGraph:
        nodes = [
            _node("parse_record",  NodeType.METHOD),
            _node("ParsedRecord",  NodeType.CLASS),
        ]
        edges = [
            _edge("parse_record", "ParsedRecord", RelationshipType.INSTANTIATES),
        ]
        return _make_graph(nodes, edges)

    def test_intent_boost_in_reason_for_implementation_node(self):
        resolver = QueryResolver(self._graph())
        result = resolver.resolve_query("How are records parsed?", top_k=5)
        parse_match = next(
            (m for m in result.matches if m.node_id == "parse_record"), None
        )
        assert parse_match is not None
        assert "intent=" in parse_match.reason, (
            f"Intent boost should appear in reason; got: {parse_match.reason}"
        )

    def test_dto_penalty_in_reason_for_dto_node(self):
        resolver = QueryResolver(self._graph())
        result = resolver.resolve_query("How are records parsed?", top_k=5)
        dto_match = next(
            (m for m in result.matches if m.node_id == "ParsedRecord"), None
        )
        assert dto_match is not None
        assert "dto-penalty" in dto_match.reason, (
            f"DTO penalty should appear in reason; got: {dto_match.reason}"
        )

    def test_expanded_keyword_annotated_in_reason(self):
        """
        "read" is an expansion of "parse"; when it hits a node label that
        contains "read", the reason should include "[expanded]".
        """
        nodes = [
            _node("read_source",  NodeType.METHOD),
            _node("parse_source", NodeType.METHOD),
        ]
        graph = _make_graph(nodes, [
            _edge("read_source", "parse_source", RelationshipType.CALLS),
        ])
        resolver = QueryResolver(graph)
        result = resolver.resolve_query("How is source parsed?", top_k=5)
        read_match = next(
            (m for m in result.matches if m.node_id == "read_source"), None
        )
        assert read_match is not None
        assert "[expanded]" in read_match.reason, (
            f"Expanded keyword hit should be annotated in reason; "
            f"got: {read_match.reason}"
        )

    def test_exact_label_in_reason(self):
        nodes = [_node("parser", NodeType.CLASS)]
        graph = _make_graph(nodes)
        resolver = QueryResolver(graph)
        result = resolver.resolve_query("parser", top_k=1)
        assert result.matches
        assert "exact label" in result.matches[0].reason

    def test_partial_label_in_reason(self):
        nodes = [_node("FileParser", NodeType.CLASS)]
        graph = _make_graph(nodes)
        resolver = QueryResolver(graph)
        result = resolver.resolve_query("parser class", top_k=1)
        assert result.matches
        assert "partial label" in result.matches[0].reason


# ===========================================================================
# 7. Edge cases
# ===========================================================================

class TestEdgeCases:

    def test_empty_graph_returns_no_matches(self):
        resolver = QueryResolver(_make_graph([]))
        result = resolver.resolve_query("How are files parsed?")
        assert result.matches == []

    def test_stop_words_only_query_returns_no_matches(self):
        nodes = [_node("Parser", NodeType.CLASS)]
        resolver = QueryResolver(_make_graph(nodes))
        result = resolver.resolve_query("how is it done")
        assert result.matches == []

    def test_single_node_exact_match(self):
        nodes = [_node("load_config", NodeType.FUNCTION)]
        resolver = QueryResolver(_make_graph(nodes))
        result = resolver.resolve_query("load config", top_k=1)
        assert result.matches
        assert result.matches[0].node_id == "load_config"

    def test_camel_case_query_term_expands_correctly(self):
        """
        A PascalCase term in the question (e.g. "FileParser") should be
        split and matched against nodes.
        """
        nodes = [
            _node("FileParser",   NodeType.CLASS),
            _node("parse_file",   NodeType.METHOD),
        ]
        graph = _make_graph(nodes, [
            _edge("FileParser", "parse_file", RelationshipType.CONTAINS),
        ])
        resolver = QueryResolver(graph)
        kws = resolver.extract_keywords("What does FileParser do?")
        assert "file" in kws
        assert "parser" in kws or "pars" in kws

    def test_inflected_verb_still_matches(self):
        """
        "parsing" in the question should match "parse_file" and "FileParser"
        via stemming.
        """
        nodes = [
            _node("parse_file", NodeType.METHOD),
            _node("FileParser", NodeType.CLASS),
        ]
        graph = _make_graph(nodes)
        resolver = QueryResolver(graph)
        result = resolver.resolve_query("How does parsing work?", top_k=5)
        ids = result.top_node_ids()
        assert "parse_file" in ids or "FileParser" in ids, (
            "Inflected 'parsing' should still match parse_file or FileParser"
        )

    def test_resolve_query_result_has_intent(self):
        nodes = [_node("fetch_data", NodeType.FUNCTION)]
        resolver = QueryResolver(_make_graph(nodes))
        result = resolver.resolve_query("How is data fetched?")
        assert result.intent is not None
        assert isinstance(result.intent.categories, list)

    def test_resolve_query_result_has_expanded_keywords(self):
        nodes = [_node("load_file", NodeType.FUNCTION)]
        resolver = QueryResolver(_make_graph(nodes))
        result = resolver.resolve_query("How are files parsed?")
        assert len(result.expanded_keywords) >= len(result.keywords), (
            "Expanded keywords should be a superset of base keywords"
        )


# ===========================================================================
# 8. Utility function unit tests
# ===========================================================================

class TestHelperFunctions:

    def test_split_camel_case_pascal(self):
        assert _split_camel_case("GraphBuilder") == ["graph", "builder"]

    def test_split_camel_case_camel(self):
        assert _split_camel_case("parseRepository") == ["parse", "repository"]

    def test_split_camel_case_acronym(self):
        result = _split_camel_case("HTTPSHandler")
        assert "https" in result
        assert "handler" in result

    def test_split_camel_case_simple_word(self):
        assert _split_camel_case("simple") == ["simple"]

    def test_snake_parts_basic(self):
        assert _snake_parts("parse_file") == ["parse", "file"]

    def test_snake_parts_no_underscore(self):
        assert _snake_parts("CodeParser") == []

    def test_snake_parts_triple(self):
        assert _snake_parts("build_call_graph") == ["build", "call", "graph"]

    def test_stem_ing(self):
        assert _stem("parsing") == "pars"

    def test_stem_ed(self):
        assert _stem("parsed") == "pars"

    def test_stem_er(self):
        assert _stem("parser") == "pars"

    def test_stem_s(self):
        assert _stem("files") == "fil"  # min len 3 after stripping

    def test_stem_no_match(self):
        assert _stem("code") is None


# ===========================================================================
# 9. Repository-independence verification
#
# These tests demonstrate that the resolver produces sensible results for
# node sets representative of other well-known Python projects (FastAPI,
# Django, Pandas) — without hard-coding any framework-specific names.
# ===========================================================================

class TestRepositoryIndependence:

    def _fastapi_like_graph(self) -> RepositoryGraph:
        """
        Nodes representative of a FastAPI-like routing layer.
        No framework logic is assumed — just naming conventions.
        """
        nodes = [
            _node("include_router",  NodeType.METHOD),
            _node("add_route",       NodeType.METHOD),
            _node("Router",          NodeType.CLASS),
            _node("RouteDefinition", NodeType.CLASS),   # DTO-ish
            _node("RouteResult",     NodeType.CLASS),   # DTO
        ]
        edges = [
            _edge("Router", "include_router", RelationshipType.CONTAINS),
            _edge("Router", "add_route",       RelationshipType.CONTAINS),
            _edge("include_router", "Router",  RelationshipType.CALLS),
            _edge("add_route",      "Router",  RelationshipType.CALLS),
        ]
        return _make_graph(nodes, edges)

    def test_fastapi_like_routing_query(self):
        resolver = QueryResolver(self._fastapi_like_graph())
        ids = _top_ids(resolver, "How are routes added?", k=5)
        # add_route (METHOD) should rank above RouteResult (DTO)
        assert "add_route" in ids
        if "RouteResult" in ids:
            assert ids.index("add_route") < ids.index("RouteResult")

    def _django_like_graph(self) -> RepositoryGraph:
        """Nodes representative of a Django-like ORM layer."""
        nodes = [
            _node("save",            NodeType.METHOD),
            _node("full_clean",      NodeType.METHOD),
            _node("Model",           NodeType.CLASS),
            _node("ValidationResult",NodeType.CLASS),   # DTO
            _node("SavedInstance",   NodeType.CLASS),   # DTO
        ]
        edges = [
            _edge("Model", "save",       RelationshipType.CONTAINS),
            _edge("Model", "full_clean", RelationshipType.CONTAINS),
            _edge("save",  "Model",      RelationshipType.CALLS),
        ]
        return _make_graph(nodes, edges)

    def test_django_like_save_query(self):
        resolver = QueryResolver(self._django_like_graph())
        ids = _top_ids(resolver, "How are models saved?", k=5)
        assert "save" in ids
        if "SavedInstance" in ids:
            assert ids.index("save") < ids.index("SavedInstance")

    def _pandas_like_graph(self) -> RepositoryGraph:
        """Nodes representative of a Pandas-like data-transform layer."""
        nodes = [
            _node("read_csv",      NodeType.FUNCTION),
            _node("parse_dates",   NodeType.FUNCTION),
            _node("DataFrame",     NodeType.CLASS),
            _node("ParsedData",    NodeType.CLASS),   # DTO
            _node("ReadResult",    NodeType.CLASS),   # DTO
        ]
        edges = [
            _edge("read_csv",    "DataFrame",  RelationshipType.INSTANTIATES),
            _edge("parse_dates", "read_csv",   RelationshipType.CALLS),
        ]
        return _make_graph(nodes, edges)

    def test_pandas_like_csv_reading_query(self):
        resolver = QueryResolver(self._pandas_like_graph())
        ids = _top_ids(resolver, "How are CSV files read?", k=5)
        assert "read_csv" in ids
        if "ReadResult" in ids:
            assert ids.index("read_csv") < ids.index("ReadResult")

    def test_pandas_like_date_parsing_query(self):
        resolver = QueryResolver(self._pandas_like_graph())
        ids = _top_ids(resolver, "How are dates parsed?", k=5)
        assert "parse_dates" in ids
        if "ParsedData" in ids:
            assert ids.index("parse_dates") < ids.index("ParsedData")