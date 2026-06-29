"""
app/retrievers/query_resolver.py
=================================
Query Understanding Layer for RepoGraphAI.

Responsibility
--------------
Convert a natural-language question into a ranked list of graph nodes that
are most likely to answer it.  No embeddings, no vector databases, no
external APIs — purely graph metadata and string heuristics.

Architecture
------------
::

    User Question
         ↓
    _detect_phrases()      — identify multi-word phrases BEFORE tokenising
                             so that "subgraph extracted" or "call graph"
                             are not split into misleading single tokens
                             (v4 NEW)
         ↓
    extract_keywords()     — tokenise + normalise the question
         ↓
    detect_intent()        — classify the query into one or more
                              IntentCategory values
         ↓
    expand_keywords()      — add SE-domain synonyms for each keyword
                              and for intent-specific terms
         ↓
    _generate_candidates() — match keywords against every node label/id
         ↓
    rank_candidates()      — score each candidate on weighted signals
         ↓
    QueryResolutionResult  — top-K QueryMatch objects ready for retrieval

Scoring signals (all additive, v5)
-----------------------------------
1.  EXACT_LABEL          (+10.0)  node.label == keyword (case-insensitive)
2.  EXACT_ID             (+8.0)   node.id == keyword
3.  PARTIAL_LABEL        (+4.0)   keyword in node.label
4.  PARTIAL_ID           (+2.0)   keyword in node.id
5.  NODE_TYPE_BASE       (+3.0)   CLASS / FUNCTION / METHOD preferred over
                                  FILE / MODULE
6.  HOTSPOT_BOOST        (+1.0 per edge, capped at +5.0)
7.  SNAKE_EXPANSION      (+3.0)   snake_case token expansion match
8.  INTENT_TYPE_BOOST    (+6.0)   node type matches the intent's preferred types
9.  CALLABLE_SUPREMACY   (+5.0)   METHOD / FUNCTION in an implementation query
10. DTO_PENALTY          (−15.0)  node looks like a data container, for
                                  implementation intents
11. PHRASE_MATCH         (+7.0)   node label/id contains a recognised multi-word
                                  phrase from the query (v4 NEW)
12. VERB_LABEL_BOOST     (+4.0)   node label contains an action-verb component
                                  that aligns with the detected intent (v4 NEW)
13. MULTI_KW_BONUS       (+5.0)   node matches 2+ distinct base keywords (v5 NEW)
14. LABEL_COVERAGE       (+3.0)   ≥67% of node snake_case parts match base
                                  keywords — rewards specific over generic names
                                  (v5 NEW)
15. GENERIC_PENALTY      (−6.0)   node matches only expanded keywords, not any
                                  base query keyword — penalises e.g. "build_all"
                                  matching "generated" via expansion (v5 NEW)

Design principles (v4 additions)
----------------------------------
- **Phrase detection** captures the semantic unit before it is destroyed by
  word-boundary tokenisation.  The phrase table covers common SE compound
  concepts (call graph, import chain, subgraph, dependency tree …) and maps
  each phrase to the intent(s) it implies.  None of the phrases are
  repository-specific; all describe generic code-analysis concepts.
- **Verb-label boost** rewards callables whose *label* contains a verb
  component that matches the detected intent (e.g. a RETRIEVAL query boosts
  nodes labelled "fetch_node" or "get_results").  This directly targets the
  reported weakness where retrieval and analytics queries surface data classes
  over implementation callables.
- **Graph-traversal intent** (new IntentCategory) recognises questions about
  subgraph extraction, graph walking, node/edge traversal, and similar
  structural operations.  Previously these queries fell into UNKNOWN or
  ANALYSIS, causing traversal callables to rank below unrelated nodes.
- **Aggregation intent** (new IntentCategory) recognises analytics questions
  about counting, ranking, summing, and computing aggregate statistics.
  Previously the STATISTICS intent lexicon was too broad and matched
  too many unrelated nodes.
- **DTO guard for graph infrastructure** — the DTO name patterns `node`,
  `edge`, `vertex`, `arc` are removed from the auto-DTO list.  These labels
  appear on graph infrastructure classes (GraphNode, GraphEdge) that are
  *not* data containers to be penalised; they are core domain objects.
  A new `_is_graph_infrastructure` signal explicitly exempts such nodes.

Changelog
----------
v5 (current)
  - Removed "build" and "create" from GENERATION intent lexicon and GENERATION
    verb components (too generic; caused "build_all", "build_lang", "create_model"
    to rank above domain-specific generation callables).
  - Removed "response" from ROUTING intent lexicon (caused the "Response" class
    to receive routing intent boost on generation queries like "How are responses
    generated?", competing with response-building callables).
  - Tightened query expansion: "generate" no longer expands to "build" to prevent
    "How are responses generated?" from surfacing generic build functions.
  - Added domain-specific expansions: response/route/middleware/request/session/
    adapter/redirect/register/command/argument/callback/option families.
  - New signal MULTI_KW_BONUS (+5.0): nodes matching 2+ distinct base keywords
    receive a bonus, preferring cross-concept matches (e.g. "handle_response"
    for "How are responses handled?") over single-concept matches.
  - New signal LABEL_COVERAGE (+3.0): nodes where ≥67% of snake_case parts
    match base query keywords receive a bonus, rewarding specific names over
    generic long names (e.g. "resolve_response" > "get_fields_from_routes").
  - New signal GENERIC_PENALTY (−6.0): nodes that only match via expanded
    keywords (not any base query keyword) are penalised, filtering out nodes
    like "build_all" that only match "generated" → "build" via expansion.

v4 (previous)
  - Phrase detection pre-pass (_detect_phrases, _PHRASE_TABLE).
  - Verb-label boost for retrieval, analytics, and graph-traversal intents.
  - New IntentCategory values: GRAPH_TRAVERSAL, AGGREGATION.
  - Expanded intent lexicons for GRAPH_TRAVERSAL and AGGREGATION.
  - Expanded query expansion table: graph, subgraph, hotspot, degree, rank,
    aggregate, compute, traverse, extract, call, dependency, import.
  - DTO detection: removed graph-node/edge suffix from DTO name patterns.
  - Scoring: _W_PHRASE_MATCH (+7.0), _W_VERB_LABEL_BOOST (+4.0).
  - Analytics queries: callable-supremacy now fires for STATISTICS and
    AGGREGATION intents in addition to IMPLEMENTATION_INTENTS.
  - Retrieval queries: separate retrieval-verb label boost.

v3 (previous)
  - Intent detection + per-intent node-type weighting.
  - Query expansion table for software-engineering vocabulary.
  - DTO / data-container penalty for implementation-oriented queries.
  - Richer reason strings (intent boost, expansion, penalty all logged).
  - IntentCategory enum, QueryIntent dataclass.

v2
  - camelCase expansion before lowercasing.
  - Light suffix stemming (_stem).
  - Snake-case component expansion bonus.
"""

from __future__ import annotations

import re
import string
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from app.models.pydantic_models import (
    GraphNode,
    NodeType,
    RelationshipType,
    RepositoryGraph,
)


# ===========================================================================
# Stop words
# ===========================================================================

_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "how", "what", "when", "where", "which", "who", "whom", "why",
    "this", "that", "these", "those", "it", "its",
    "i", "you", "he", "she", "we", "they", "me", "him", "her", "us", "them",
    "in", "on", "at", "by", "for", "with", "about", "against", "between",
    "into", "through", "during", "before", "after", "to", "from", "up",
    "down", "out", "of", "off", "over", "under", "again", "then", "once",
    "and", "but", "or", "nor", "so", "yet", "both", "either", "neither",
    "not", "no", "nor", "only", "own", "same", "than", "too", "very",
    "just", "because", "as", "until", "while", "though", "although",
    "get", "gets", "got", "getting", "work", "works", "working",
    "make", "makes", "made", "use", "used", "using", "done", "does",
    "way", "ways",
})


# ===========================================================================
# Light suffix stemming  (unchanged from v2)
# ===========================================================================

_STEM_RULES: list[tuple[str, int]] = [
    ("pping", 3),
    ("ning",  3),
    ("ing",   3),
    ("ation", 3),
    ("ations", 3),
    ("tion",  3),
    ("tions", 3),
    ("ed",    3),
    ("er",    3),
    ("ers",   3),
    ("es",    3),
    ("s",     3),
]


def _stem(token: str) -> str | None:
    """Return a stemmed form of *token* if any rule matches, else None."""
    for suffix, min_len in _STEM_RULES:
        if token.endswith(suffix) and len(token) - len(suffix) >= min_len:
            return token[: len(token) - len(suffix)]
    return None


# ===========================================================================
# Intent detection
# ===========================================================================

class IntentCategory(str, Enum):
    """
    Repository-agnostic query intent categories.

    These describe *what a developer is asking about* in terms of generic
    software-engineering concerns, not in terms of any specific codebase.
    """
    PARSING          = "parsing"
    GENERATION       = "generation"
    RETRIEVAL        = "retrieval"
    LOADING          = "loading"
    SAVING           = "saving"
    VISUALIZATION    = "visualization"
    STATISTICS       = "statistics"
    ANALYSIS         = "analysis"
    AUTHENTICATION   = "authentication"
    ROUTING          = "routing"
    VALIDATION       = "validation"
    EXECUTION        = "execution"
    CONFIGURATION    = "configuration"
    TRANSFORMATION   = "transformation"
    GRAPH_TRAVERSAL  = "graph_traversal"   # v4 NEW: subgraph, walk, traverse
    AGGREGATION      = "aggregation"       # v4 NEW: count, rank, aggregate, compute
    UNKNOWN          = "unknown"


# ---------------------------------------------------------------------------
# Intent lexicons
#
# Each entry maps an IntentCategory to the set of lowercase trigger words
# that, when found in a query, signal that intent.
#
# Rules for adding entries:
#   1. Every word must be a generic SE term — not a class / function name from
#      any specific repository.
#   2. Prefer verb roots (the stemmer will handle inflected forms arriving
#      from the question, but the lexicon words themselves are also compared
#      against stemmed query tokens).
# ---------------------------------------------------------------------------

_INTENT_LEXICONS: dict[IntentCategory, frozenset[str]] = {
    IntentCategory.PARSING: frozenset({
        "parse", "pars", "parsing", "parsed", "parser", "parsers",
        "read", "decode", "deserialise", "deserialize", "interpret",
        "tokenize", "tokenise", "lex", "lexer",
        "extract", "scan", "walk", "traverse",
    }),
    IntentCategory.GENERATION: frozenset({
        "generate", "generat", "generation", "construct",
        "produce", "render", "emit", "output", "synthesize",
        "format", "serialise", "serialize", "encode",
        "write", "compile",
    }),
    IntentCategory.RETRIEVAL: frozenset({
        "retriev", "retrieve", "retrieval", "search", "find", "lookup", "look",
        "fetch", "query", "filter", "select", "resolve", "index", "scan",
        # Explicit "get" kept out of stop words context but present here:
        "getter", "getsource", "getnode",
    }),
    IntentCategory.LOADING: frozenset({
        "load", "import", "read", "open", "ingest", "stream",
        "fetch", "download", "pull",
    }),
    IntentCategory.SAVING: frozenset({
        "save", "write", "store", "persist", "export", "dump",
        "upload", "push", "commit", "flush",
    }),
    IntentCategory.VISUALIZATION: frozenset({
        "visualize", "visualis", "plot", "chart", "graph", "draw",
        "render", "display", "show", "diagram", "view",
    }),
    IntentCategory.STATISTICS: frozenset({
        "statistic", "stats", "metric", "analytics", "analytic",
        "count", "measure", "aggregate", "histogram", "distribution",
        "summary", "report", "degree", "hotspot",
    }),
    IntentCategory.ANALYSIS: frozenset({
        "analys", "analyze", "analyse", "inspect", "detect",
        "identify", "profile", "audit", "check", "scan",
        "evaluate", "assess", "dependency", "dependencies",
        "impact", "blast", "radius",
    }),
    IntentCategory.AUTHENTICATION: frozenset({
        "auth", "authenticat", "login", "signin", "logout", "signout",
        "token", "permission", "authoriz", "authoris", "credential",
        "session", "oauth", "jwt",
    }),
    IntentCategory.ROUTING: frozenset({
        "route", "router", "endpoint", "url", "path", "dispatch",
        "handler", "middleware", "request",
        "register", "registr", "mount", "include", "add_route",
    }),
    IntentCategory.VALIDATION: frozenset({
        "validat", "validate", "check", "verify", "sanitiz", "sanitise",
        "schema", "constraint", "rule", "enforce",
    }),
    IntentCategory.EXECUTION: frozenset({
        "run", "execut", "invoke", "call", "trigger", "dispatch",
        "start", "launch", "schedule", "task",
    }),
    IntentCategory.CONFIGURATION: frozenset({
        "config", "configur", "setting", "option", "parameter",
        "env", "environment", "setup", "init", "initializ",
    }),
    IntentCategory.TRANSFORMATION: frozenset({
        "transform", "convert", "map", "translate", "normalize",
        "normalise", "clean", "process", "pipeline", "enrich",
    }),
    # v4: Graph traversal — questions about walking/extracting the graph itself
    IntentCategory.GRAPH_TRAVERSAL: frozenset({
        "subgraph", "traverse", "traversal", "walk", "visit", "hop",
        "neighbour", "neighbor", "adjacent", "reachable", "path",
        "chain", "ancestry", "ancestor", "descendant", "connected",
        "extract", "expand", "explore", "bfs", "dfs", "breadth", "depth",
        "spanning", "topology", "topological",
        "inherit", "inheritance", "hierarchy", "subclass", "parent",
    }),
    # v4: Aggregation — questions about computing metrics, rankings, summaries
    IntentCategory.AGGREGATION: frozenset({
        "aggregat", "aggregate", "count", "rank", "ranking", "ranked",
        "compute", "calculat", "calculate", "sum", "total", "average",
        "mean", "median", "top", "bottom", "most", "least",
        "distribution", "frequency", "histogram", "percentile",
        "hotspot", "hotspots", "degree", "centrality",
    }),
}

# ---------------------------------------------------------------------------
# Per-intent preferred node types
#
# For intents that are fundamentally *implementation* questions the answer
# should come from callable nodes (Method / Function) or implementation-style
# classes, not from data containers.
# ---------------------------------------------------------------------------

_IMPLEMENTATION_INTENTS: frozenset[IntentCategory] = frozenset({
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
    IntentCategory.GRAPH_TRAVERSAL,  # v4: traversal is always an operation
})

# v4: Intents for which callable-supremacy also fires (extends
# IMPLEMENTATION_INTENTS to include analytics/aggregation where the
# "how is X computed" question should surface the computing function,
# not the result data model).
_CALLABLE_SUPREMACY_INTENTS: frozenset[IntentCategory] = (
    _IMPLEMENTATION_INTENTS
    | frozenset({IntentCategory.STATISTICS, IntentCategory.AGGREGATION})
)

_INTENT_PREFERRED_TYPES: dict[IntentCategory, frozenset[NodeType]] = {
    # Implementation intents strongly prefer callables and service classes
    IntentCategory.PARSING:         frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.GENERATION:      frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.RETRIEVAL:       frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.LOADING:         frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.SAVING:          frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.ANALYSIS:        frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.AUTHENTICATION:  frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.ROUTING:         frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.EXECUTION:       frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.TRANSFORMATION:  frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.GRAPH_TRAVERSAL: frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    # Data-oriented intents may legitimately return schema / model nodes,
    # but callables still score at least as well.
    IntentCategory.STATISTICS:      frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.AGGREGATION:     frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.VALIDATION:      frozenset({NodeType.CLASS, NodeType.METHOD, NodeType.FUNCTION}),
    IntentCategory.VISUALIZATION:   frozenset({NodeType.FUNCTION, NodeType.METHOD, NodeType.CLASS}),
    IntentCategory.CONFIGURATION:   frozenset({NodeType.CLASS, NodeType.FUNCTION, NodeType.METHOD}),
}

# ---------------------------------------------------------------------------
# v4: Per-intent verb components for the VERB_LABEL_BOOST signal.
#
# When a node's snake_case or camelCase label components include one of
# these verbs AND the query has the matching intent, the node receives
# _W_VERB_LABEL_BOOST.  This rewards callables named after what they *do*
# (e.g. "fetch_candidates", "compute_degree", "extract_subgraph") rather
# than what data they hold.
#
# Design rule: all verb strings must be generic SE verb roots.
# ---------------------------------------------------------------------------

_INTENT_VERB_COMPONENTS: dict[IntentCategory, frozenset[str]] = {
    IntentCategory.RETRIEVAL: frozenset({
        "fetch", "retrieve", "retriev", "find", "search", "lookup",
        "resolve", "query", "filter", "select", "get",
    }),
    IntentCategory.PARSING: frozenset({
        "parse", "pars", "read", "decode", "extract", "lex",
        "tokenize", "tokenise", "scan", "load",
    }),
    IntentCategory.GENERATION: frozenset({
        "generate", "generat", "construct",
        "produce", "render", "emit", "format", "compile",
        "serialize", "serialise", "encode",
    }),
    IntentCategory.GRAPH_TRAVERSAL: frozenset({
        "traverse", "walk", "visit", "explore", "expand",
        "extract", "subgraph", "hop", "reach", "bfs", "dfs",
    }),
    IntentCategory.STATISTICS: frozenset({
        "compute", "calculat", "calculate", "aggregate", "count",
        "rank", "measure", "summarize", "summarise",
    }),
    IntentCategory.AGGREGATION: frozenset({
        "compute", "calculat", "calculate", "aggregate", "count",
        "rank", "sum", "total", "average",
    }),
    IntentCategory.ANALYSIS: frozenset({
        "analyze", "analyse", "inspect", "detect", "identify",
        "evaluate", "assess", "profile",
    }),
    IntentCategory.TRANSFORMATION: frozenset({
        "transform", "convert", "map", "translate", "normalize",
        "normalise", "clean", "process",
    }),
    IntentCategory.LOADING: frozenset({
        "load", "import", "ingest", "stream", "fetch", "download",
    }),
    IntentCategory.SAVING: frozenset({
        "save", "store", "persist", "export", "dump", "write",
    }),
    IntentCategory.EXECUTION: frozenset({
        "run", "execut", "invoke", "trigger", "dispatch", "launch",
        "send", "perform", "call", "execute",
    }),
    # v5: Added routing and authentication verb components
    IntentCategory.ROUTING: frozenset({
        "route", "register", "registr", "mount", "include",
        "handle", "dispatch", "redirect", "forward",
    }),
    IntentCategory.AUTHENTICATION: frozenset({
        "auth", "authenticat", "login", "logout", "verify",
        "validate", "token", "session",
    }),
    IntentCategory.VALIDATION: frozenset({
        "validat", "validate", "verify", "check", "sanitiz",
        "enforce", "constrain",
    }),
}


@dataclass(frozen=True)
class QueryIntent:
    """
    The detected intent(s) of a natural-language query.

    Attributes
    ----------
    categories : list[IntentCategory]
        All matched categories, ordered by confidence (most confident first).
        Empty list → UNKNOWN / general lookup.
    is_implementation_query : bool
        True when at least one detected category is in
        _IMPLEMENTATION_INTENTS.  Controls whether the DTO penalty fires.
    phrase_hints : list[str]
        Multi-word phrases detected in the raw query (v4 NEW).
        Stored for reason-string annotation; not used for scoring directly.
    """
    categories:             list[IntentCategory]
    is_implementation_query: bool
    phrase_hints:           list[str] = field(default_factory=list)


# ===========================================================================
# v4: Phrase detection
#
# Multi-word SE compound concepts that lose meaning when tokenised.
# The table maps each phrase (lowercase, normalised) to the set of
# IntentCategories it implies.  During candidate scoring, any node whose
# label or id contains the concatenated or snake-cased form of the phrase
# receives _W_PHRASE_MATCH.
#
# Design rule: every entry must be a generic code-analysis concept.
# No repository-specific terms.
# ===========================================================================

@dataclass(frozen=True)
class _PhraseEntry:
    """A recognised multi-word phrase and the intents it implies."""
    phrase:        str                   # lowercase, space-separated
    intents:       frozenset[IntentCategory]
    node_forms:    frozenset[str]        # how this phrase appears in node labels/ids


_PHRASE_TABLE: list[_PhraseEntry] = [
    # Graph structure phrases
    _PhraseEntry(
        phrase="call graph",
        intents=frozenset({IntentCategory.GRAPH_TRAVERSAL, IntentCategory.ANALYSIS}),
        node_forms=frozenset({"call_graph", "callgraph", "call graph"}),
    ),
    _PhraseEntry(
        phrase="import graph",
        intents=frozenset({IntentCategory.GRAPH_TRAVERSAL, IntentCategory.ANALYSIS}),
        node_forms=frozenset({"import_graph", "importgraph"}),
    ),
    _PhraseEntry(
        phrase="dependency graph",
        intents=frozenset({IntentCategory.GRAPH_TRAVERSAL, IntentCategory.ANALYSIS}),
        node_forms=frozenset({"dependency_graph", "dependencygraph", "dep_graph"}),
    ),
    _PhraseEntry(
        phrase="inheritance tree",
        intents=frozenset({IntentCategory.GRAPH_TRAVERSAL, IntentCategory.ANALYSIS}),
        node_forms=frozenset({"inheritance_tree", "inheritancetree", "class_hierarchy"}),
    ),
    _PhraseEntry(
        phrase="subgraph",
        intents=frozenset({IntentCategory.GRAPH_TRAVERSAL}),
        node_forms=frozenset({"subgraph", "sub_graph"}),
    ),
    _PhraseEntry(
        phrase="subgraph extracted",
        intents=frozenset({IntentCategory.GRAPH_TRAVERSAL, IntentCategory.RETRIEVAL}),
        node_forms=frozenset({"extract_subgraph", "subgraph_extract", "get_subgraph",
                               "build_subgraph", "subgraph"}),
    ),
    _PhraseEntry(
        phrase="import chain",
        intents=frozenset({IntentCategory.GRAPH_TRAVERSAL, IntentCategory.ANALYSIS}),
        node_forms=frozenset({"import_chain", "importchain", "dependency_chain"}),
    ),
    _PhraseEntry(
        phrase="call chain",
        intents=frozenset({IntentCategory.GRAPH_TRAVERSAL, IntentCategory.ANALYSIS}),
        node_forms=frozenset({"call_chain", "callchain", "invocation_chain"}),
    ),
    _PhraseEntry(
        phrase="blast radius",
        intents=frozenset({IntentCategory.ANALYSIS, IntentCategory.GRAPH_TRAVERSAL}),
        node_forms=frozenset({"blast_radius", "blastradius", "impact_radius"}),
    ),
    _PhraseEntry(
        phrase="impact analysis",
        intents=frozenset({IntentCategory.ANALYSIS}),
        node_forms=frozenset({"impact_analysis", "impactanalysis", "change_impact"}),
    ),
    # Analytics phrases
    _PhraseEntry(
        phrase="node degree",
        intents=frozenset({IntentCategory.AGGREGATION, IntentCategory.STATISTICS}),
        node_forms=frozenset({"node_degree", "nodedegree", "degree"}),
    ),
    _PhraseEntry(
        phrase="most connected",
        intents=frozenset({IntentCategory.AGGREGATION, IntentCategory.STATISTICS}),
        node_forms=frozenset({"most_connected", "top_connected", "hotspot"}),
    ),
    _PhraseEntry(
        phrase="architectural hotspot",
        intents=frozenset({IntentCategory.AGGREGATION, IntentCategory.STATISTICS}),
        node_forms=frozenset({"architectural_hotspot", "hotspot", "architectural_hotspots"}),
    ),
    _PhraseEntry(
        phrase="graph statistics",
        intents=frozenset({IntentCategory.STATISTICS, IntentCategory.AGGREGATION}),
        node_forms=frozenset({"graph_statistics", "graphstatistics", "graph_stats",
                               "compute_statistics", "calculate_statistics"}),
    ),
    _PhraseEntry(
        phrase="top files",
        intents=frozenset({IntentCategory.AGGREGATION, IntentCategory.STATISTICS}),
        node_forms=frozenset({"top_files", "files_by_degree", "ranked_files"}),
    ),
    # Retrieval phrases
    _PhraseEntry(
        phrase="node context",
        intents=frozenset({IntentCategory.RETRIEVAL, IntentCategory.GRAPH_TRAVERSAL}),
        node_forms=frozenset({"get_node_context", "node_context", "fetch_context"}),
    ),
    _PhraseEntry(
        phrase="callable context",
        intents=frozenset({IntentCategory.RETRIEVAL}),
        node_forms=frozenset({"get_callable_context", "callable_context"}),
    ),
    _PhraseEntry(
        phrase="class context",
        intents=frozenset({IntentCategory.RETRIEVAL}),
        node_forms=frozenset({"get_class_context", "class_context"}),
    ),
    _PhraseEntry(
        phrase="llm context",
        intents=frozenset({IntentCategory.RETRIEVAL, IntentCategory.GENERATION}),
        node_forms=frozenset({"build_llm_context", "llm_context", "llm_prompt"}),
    ),
    # v5.1: Generic graph-construction phrases
    # node_forms are generic naming patterns any codebase would use —
    # NOT names from this specific repo (no "GraphBuilder", "build_graph", etc.)
    _PhraseEntry(
        phrase="graph generated",
        intents=frozenset({IntentCategory.GENERATION, IntentCategory.GRAPH_TRAVERSAL}),
        node_forms=frozenset({"generate_graph", "construct_graph", "create_graph",
                               "make_graph", "build_graph"}),
    ),
    _PhraseEntry(
        phrase="graph built",
        intents=frozenset({IntentCategory.GENERATION, IntentCategory.GRAPH_TRAVERSAL}),
        node_forms=frozenset({"build_graph", "construct_graph", "create_graph",
                               "graph_builder", "graph_build"}),
    ),
    _PhraseEntry(
        phrase="graph nodes",
        intents=frozenset({IntentCategory.GRAPH_TRAVERSAL, IntentCategory.GENERATION}),
        node_forms=frozenset({"add_node", "create_node", "insert_node",
                               "build_graph", "construct_graph",
                               "graph_node", "node_create", "node_add"}),
    ),
    _PhraseEntry(
        phrase="graph edges",
        intents=frozenset({IntentCategory.GRAPH_TRAVERSAL, IntentCategory.GENERATION}),
        node_forms=frozenset({"add_edge", "create_edge", "insert_edge",
                               "build_graph", "construct_graph",
                               "graph_edge", "edge_create", "edge_add"}),
    ),
    # v5.1: Generic inheritance phrases
    _PhraseEntry(
        phrase="inheritance represented",
        intents=frozenset({IntentCategory.GRAPH_TRAVERSAL, IntentCategory.ANALYSIS}),
        node_forms=frozenset({"inherits", "inheritance", "inherit", "class_hierarchy",
                               "build_class_graph", "class_graph", "hierarchy_graph",
                               "inheritance_tree"}),
    ),
    _PhraseEntry(
        phrase="inheritance",
        intents=frozenset({IntentCategory.GRAPH_TRAVERSAL, IntentCategory.ANALYSIS}),
        node_forms=frozenset({"inherits", "inheritance", "inherit",
                               "class_hierarchy", "hierarchy",
                               "build_class_graph", "class_graph"}),
    ),
    # v5.1: Generic analytics / hotspot phrases
    _PhraseEntry(
        phrase="hotspots calculated",
        intents=frozenset({IntentCategory.AGGREGATION, IntentCategory.STATISTICS}),
        node_forms=frozenset({"generate_statistics", "compute_statistics",
                               "calculate_statistics", "calculate_hotspots",
                               "compute_hotspots", "hotspot_analysis"}),
    ),
    _PhraseEntry(
        phrase="hotspots computed",
        intents=frozenset({IntentCategory.AGGREGATION, IntentCategory.STATISTICS}),
        node_forms=frozenset({"generate_statistics", "compute_statistics",
                               "calculate_statistics", "hotspot_analysis"}),
    ),
    # v5.1: Generic context-building phrases
    _PhraseEntry(
        phrase="context built",
        intents=frozenset({IntentCategory.GENERATION, IntentCategory.RETRIEVAL}),
        node_forms=frozenset({"build_context", "context_builder", "build_llm_context",
                               "context_build", "create_context", "make_context"}),
    ),
    _PhraseEntry(
        phrase="context build",
        intents=frozenset({IntentCategory.GENERATION, IntentCategory.RETRIEVAL}),
        node_forms=frozenset({"build_context", "context_builder", "build_llm_context",
                               "create_context", "make_context"}),
    ),
]


def _detect_phrases(question: str) -> list[_PhraseEntry]:
    """
    Return all phrase table entries whose phrase appears in *question*.

    The match is case-insensitive.  Tokens in the phrase are checked both
    with their original spacing and with underscores (so "call graph" also
    matches "call_graph" in the question text).

    Returns the list of matching PhraseEntry objects.
    """
    q_lower = question.lower()
    # Normalise underscores → spaces for matching
    q_norm = q_lower.replace("_", " ")
    matched: list[_PhraseEntry] = []
    for entry in _PHRASE_TABLE:
        if entry.phrase in q_norm:
            matched.append(entry)
        else:
            # Also check underscore form
            phrase_snake = entry.phrase.replace(" ", "_")
            if phrase_snake in q_lower:
                matched.append(entry)
    return matched


# ===========================================================================
# Query expansion table
#
# Maps a root keyword (lowercase) to additional synonyms that should also
# be considered when scoring nodes.
#
# Design rule: all entries must be generic SE concepts.
# Nothing here should mention a specific library, framework, or project.
# ===========================================================================

_QUERY_EXPANSION: dict[str, list[str]] = {
    # ---- Parsing / reading ----
    "parse":      ["read", "load", "decode", "deserialise", "deserialize",
                   "extract", "scan", "lex", "tokenize"],
    "pars":       ["read", "load", "extract"],   # stemmed form
    "read":       ["parse", "load", "open", "ingest"],
    "load":       ["read", "parse", "open", "fetch", "import"],
    "decode":     ["parse", "deserialise", "deserialize"],

    # ---- Building / creating ----
    "build":      ["create", "construct", "generate", "make", "produce"],
    "generate":   ["construct", "create", "produce", "emit"],
    "generat":    ["construct", "create"],   # stemmed form
    "create":     ["construct", "build", "make", "produce", "add"],
    "creat":      ["construct", "build", "make", "add", "instantiate"],  # stemmed 'created'
    "construct":  ["build", "create", "instantiate"],

    # ---- Retrieval / search ----
    "retrieve":   ["search", "fetch", "find", "lookup", "query"],
    "retriev":    ["search", "fetch", "find", "lookup"],   # stemmed form
    "retrieval":  ["retrieve", "search", "fetch", "find"],
    "search":     ["find", "retrieve", "lookup", "filter", "query"],
    "find":       ["search", "retrieve", "lookup", "query"],
    "fetch":      ["retrieve", "load", "download"],
    "lookup":     ["find", "search", "retrieve", "resolve"],
    "query":      ["search", "find", "retrieve", "filter"],
    "resolve":    ["lookup", "find", "fetch", "retrieve"],

    # ---- Saving / persisting ----
    "save":       ["store", "write", "persist", "export", "dump"],
    "saved":      ["save", "store", "persist", "write"],   # past-tense form
    "sav":        ["save", "store", "persist"],            # stemmed form
    "store":      ["save", "persist", "write", "cache"],
    "persist":    ["save", "store", "write"],
    "write":      ["save", "store", "output", "emit"],
    "export":     ["write", "save", "dump", "output"],

    # ---- Traversal / walking ----
    "walk":       ["traverse", "visit", "iterate", "scan", "explore"],
    "traverse":   ["walk", "visit", "iterate", "explore", "subgraph"],
    "traversal":  ["traverse", "walk", "visit", "explore"],
    "visit":      ["walk", "traverse", "iterate"],
    "iterate":    ["walk", "traverse", "loop", "enumerate"],
    "explore":    ["traverse", "walk", "visit", "expand"],
    "expand":     ["explore", "traverse", "extend", "grow"],
    "subgraph":   ["traverse", "extract", "subgraph", "walk", "graph"],
    "hop":        ["traverse", "walk", "step", "neighbour"],
    "neighbour":  ["adjacent", "connected", "hop", "neighbor"],
    "neighbor":   ["adjacent", "connected", "hop", "neighbour"],

    # ---- Graph concepts ----
    "graph":      ["network", "topology", "structure"],
    "node":       ["vertex", "element", "symbol"],
    "edge":       ["link", "connection", "relationship", "arc"],
    "degree":     ["centrality", "connectivity", "hotspot", "rank"],
    "hotspot":    ["degree", "hub", "central", "connected", "statistic"],
    "hotspots":   ["degree", "hub", "statistic", "statistics"],
    "dependency": ["import", "require", "depend"],
    "chain":      ["path", "sequence", "pipeline"],
    "inheritance": ["inherits", "inherit", "hierarchy", "parent", "subclass",
                    "class_graph", "class_hierarchy"],
    "inherit":    ["inheritance", "extends", "subclass", "parent", "class_graph"],
    "inherits":   ["inheritance", "extends", "subclass", "class_graph"],
    "represent":  ["model", "encode", "capture", "store", "express"],   # stem of 'represented'

    # ---- Context building ----
    "context":    ["build", "prompt", "llm", "package"],
    "llm":        ["context", "prompt", "language", "model"],

    # ---- Analysis ----
    "analyse":    ["analyze", "inspect", "evaluate", "examine"],
    "analyze":    ["analyse", "inspect", "evaluate", "examine"],
    "inspect":    ["analyse", "analyze", "examine", "check"],
    "evaluate":   ["analyse", "analyze", "assess", "check"],
    "impact":     ["blast", "radius", "effect", "change"],

    # ---- Transformation ----
    "transform":  ["convert", "map", "translate", "process", "normalize"],
    "convert":    ["transform", "map", "translate", "cast"],
    "normalise":  ["normalize", "transform", "clean", "standardise"],
    "normalize":  ["normalise", "transform", "clean", "standardize"],

    # ---- Rendering / visualization ----
    "render":     ["display", "draw", "show", "visualize", "emit"],
    "visualize":  ["render", "display", "draw", "plot", "chart"],
    "display":    ["render", "show", "visualize", "draw"],
    "plot":       ["visualize", "chart", "render", "draw"],

    # ---- Validation ----
    "validate":   ["verify", "check", "sanitize", "enforce", "constrain"],
    "validat":    ["verify", "check", "sanitize"],   # stemmed form
    "verify":     ["validate", "check", "ensure", "confirm"],

    # ---- Statistics / aggregation ----
    "statistics": ["metrics", "analytics", "stats", "summary", "report"],
    "statistic":  ["metric", "analytic", "stat"],   # stemmed form
    "metrics":    ["statistics", "analytics", "stats", "measurements"],
    "analytics":  ["statistics", "metrics", "analysis", "reporting"],
    "aggregate":  ["count", "sum", "compute", "calculate", "rank"],
    "aggregat":   ["count", "sum", "compute", "rank"],   # stemmed form
    "compute":    ["calculate", "aggregate", "rank", "measure"],
    "calculat":   ["compute", "aggregate", "measure"],   # stemmed form
    "rank":       ["sort", "order", "top", "degree", "hotspot"],
    "count":      ["aggregate", "tally", "measure", "total"],

    # ---- Repository-level ----
    "repository": ["repo", "codebase", "project", "package"],
    "repo":       ["repository", "codebase", "project"],
    "file":       ["module", "source", "script"],
    "module":     ["file", "package", "component"],
    "class":      ["type", "model", "schema", "entity"],
    "function":   ["method", "callable", "procedure", "routine"],
    "method":     ["function", "callable", "procedure"],
    "callable":   ["function", "method", "routine"],
    "extract":    ["retrieve", "fetch", "get", "pull", "subgraph"],

    # ---- HTTP / web domain ----
    "response":   ["reply", "output", "return"],
    "responses":  ["reply", "output", "return"],
    "respons":    ["reply", "output"],   # stemmed form
    "route":      ["endpoint", "path", "url", "handler"],
    "routes":     ["route", "endpoints", "paths", "handlers"],
    "rout":       ["route", "endpoint", "path", "handler"],   # stemmed form
    "middleware":  ["interceptor", "filter", "hook"],
    "request":    ["http", "query", "call", "send"],
    "requests":   ["http", "query", "send"],
    "http":       ["request", "send", "connection", "transport"],
    "session":    ["connection", "client", "pool", "send"],
    "adapter":    ["transport", "connector", "client", "send"],
    "redirect":   ["forward", "location", "status"],
    "register":   ["add", "mount", "attach", "include"],
    "registered": ["added", "mounted", "attached"],
    "registr":    ["add", "mount", "attach"],   # stemmed form
    "execut":     ["run", "invoke", "send", "call", "perform", "dispatch"],  # stem of 'executed'
    "execute":    ["run", "invoke", "send", "call", "perform"],
    "manag":      ["handle", "control", "maintain", "create"],  # stem of 'managed'
    "manage":     ["handle", "control", "maintain", "create"],
    "handl":      ["process", "execute", "run", "dispatch"],    # stem of 'handled'
    "handle":     ["process", "execute", "run", "dispatch"],

    # ---- CLI domain ----
    "command":    ["cmd", "subcommand", "cli"],
    "argument":   ["arg", "param", "option", "flag"],
    "arguments":  ["args", "params", "options", "flags"],
    "argument":   ["arg", "param", "option"],   # type: ignore[dict-overwrite]
    "callback":   ["handler", "hook", "action"],
    "option":     ["flag", "param", "argument"],
    "options":    ["flags", "params", "arguments"],
}


# ===========================================================================
# DTO / data-container detection
# ===========================================================================

# Name prefixes/suffixes that suggest a DTO / schema / result object.
# All are generic SE naming conventions (not repo-specific).
#
# v4 CHANGE: Removed `(node|edge|vertex|arc)$` from this list.
# "GraphNode", "GraphEdge" are core domain infrastructure objects, not
# data containers to be penalised.  The edge-profile signal (Signal 3
# below) will still catch truly inert DTOs that happen to use those names.
_DTO_NAME_PATTERNS: list[re.Pattern[str]] = [
    # Prefix patterns — past-participle class names are almost always DTOs.
    re.compile(r"^parsed",     re.IGNORECASE),
    re.compile(r"^generated",  re.IGNORECASE),
    re.compile(r"^fetched",    re.IGNORECASE),
    re.compile(r"^loaded",     re.IGNORECASE),
    re.compile(r"^saved",      re.IGNORECASE),
    re.compile(r"^processed",  re.IGNORECASE),
    re.compile(r"^serialized", re.IGNORECASE),
    re.compile(r"^raw",        re.IGNORECASE),
    re.compile(r"^dto",        re.IGNORECASE),

    # Suffix patterns  (most common DTO naming conventions across frameworks)
    re.compile(r"(schema|dto|record)$",                   re.IGNORECASE),
    re.compile(r"(request|response|reply|payload|body)$", re.IGNORECASE),
    re.compile(r"(result|output|summary|report)$",        re.IGNORECASE),
    re.compile(r"(entity|document|row|item|entry)$",      re.IGNORECASE),
    re.compile(r"(config|settings|options|params|args)$", re.IGNORECASE),
    re.compile(r"(event|message|packet|frame|envelope)$", re.IGNORECASE),
    re.compile(r"(type|types|kind|enum)$",                re.IGNORECASE),
    re.compile(r"(degree|metric|stat|stats|counter)$",    re.IGNORECASE),  # v5.1: data holder
    # NOTE: "model" is intentionally excluded from the pattern suffix list
    # because many service/manager classes inherit from BaseModel in
    # Pydantic-based codebases.  The decorator signal handles Pydantic DTOs.
    # NOTE: "data" is excluded to prevent false positives on classes like
    # "DataLoader", "DataPipeline", "DataProcessor" which are implementation
    # classes, not DTOs.
]

# Decorator names that indicate a data-container class.
_DTO_DECORATOR_FRAGMENTS: frozenset[str] = frozenset({
    "dataclass",    # stdlib
    "basemodel",    # pydantic
    "model",        # generic
    "schema",       # marshmallow / generic
    "dataclasses",
    "attr",         # attrs
    "attrs",
    "frozen",
    "namedtuple",
})

# v4: Label fragments that suggest graph *infrastructure* (not DTOs).
# Nodes whose labels contain these fragments are exempt from DTO penalties
# because they are domain objects, not passive data containers.
_GRAPH_INFRA_LABEL_FRAGMENTS: frozenset[str] = frozenset({
    "graphnode", "graphedge", "repositorygraph",
    "graph_node", "graph_edge", "repository_graph",
    # camelCase splits:
    "graphbuilder", "graph_builder",
    "nodetype", "node_type",
    "edgetype", "edge_type",
    "relationshiptype", "relationship_type",
})


def _is_graph_infrastructure(node: GraphNode) -> bool:
    """
    Return True when *node* is a graph infrastructure object that should not
    be penalised as a DTO, even if its label ends in "Node", "Edge", etc.

    Specifically exempts: GraphNode, GraphEdge, RepositoryGraph, NodeType,
    RelationshipType, and their snake_case variants.
    """
    label_lower = node.label.lower().replace("_", "")
    for frag in _GRAPH_INFRA_LABEL_FRAGMENTS:
        if frag.replace("_", "") in label_lower:
            return True
    return False


def _looks_like_dto(node: GraphNode, graph: RepositoryGraph, dto_fixes: bool = False) -> bool:
    """
    Return True when *node* appears to be a data-container (DTO, schema,
    model, result object) rather than an implementation symbol.

    Detection uses three independent signals; any one is sufficient:

    1. **Name pattern** — the node label matches a known DTO naming
       convention (e.g. ends in "Schema", "Result", "Request", …).
    2. **Decorator** — the node's decorators (from DECORATES edges) suggest
       a data-class framework (e.g. @dataclass, @BaseModel, @schema).
    3. **Edge profile** — a CLASS node whose only outgoing edge type is
       CONTAINS and whose only incoming edge types are CONTAINS / IMPORTS
       is almost certainly a plain data container.

    v4: Graph infrastructure nodes are explicitly exempt (Signal 0).

    All signals are generic; none reference project-specific names.
    """
    if node.type not in (NodeType.CLASS, NodeType.FUNCTION, NodeType.METHOD):
        return False

    # ------------------------------------------------------------------
    # Signal 0 (v4 NEW): graph infrastructure exemption
    # ------------------------------------------------------------------
    if _is_graph_infrastructure(node):
        return False

    label = node.label

    # ------------------------------------------------------------------
    # Signal 1: name pattern — CLASS nodes only.
    # IMPORTANT: suffix patterns like 'args', 'response', 'options' must not
    # match FUNCTION/METHOD nodes (e.g. parse_args, iter_content, parse_options)
    # since those are execution callables, not data containers.
    # ------------------------------------------------------------------
    if node.type == NodeType.CLASS:
        for pattern in _DTO_NAME_PATTERNS:
            if pattern.search(label):
                return True

    # ------------------------------------------------------------------
    # Signal 2: DTO-like decorator on this node (via DECORATES edges)
    # ------------------------------------------------------------------
    for edge in graph.edges:
        if (
            edge.relationship == RelationshipType.DECORATES
            and edge.target == node.id
            and edge.decorator_name
        ):
            dec_lower = edge.decorator_name.lower().split(".")[-1]
            for frag in _DTO_DECORATOR_FRAGMENTS:
                if frag in dec_lower:
                    return True

    # ------------------------------------------------------------------
    # Signal 2b (v5.2): INHERITS from a known DTO base class.
    # Catches classes like Components(BaseModel) or MySchema(BaseModel)
    # where the DTO pattern is expressed via inheritance rather than a
    # decorator.  Only the direct parent label is checked (one hop).
    # ------------------------------------------------------------------
    for edge in graph.edges:
        if edge.relationship == RelationshipType.INHERITS and edge.source == node.id:
            parent_label_lower = edge.target.lower().split(".")[-1]
            for frag in _DTO_DECORATOR_FRAGMENTS:
                if frag in parent_label_lower:
                    return True

    # ------------------------------------------------------------------
    # Signal 3: edge profile (CLASS only)
    # ------------------------------------------------------------------
    if node.type == NodeType.CLASS:
        outgoing_rel: set[RelationshipType] = set()
        incoming_rel: set[RelationshipType] = set()
        for edge in graph.edges:
            if edge.source == node.id:
                outgoing_rel.add(edge.relationship)
            if edge.target == node.id:
                incoming_rel.add(edge.relationship)

        implementation_rels = {
            RelationshipType.CALLS,
            RelationshipType.INSTANTIATES,
            RelationshipType.INHERITS,
        }

        has_no_implementation_outgoing = not (outgoing_rel & implementation_rels)
        has_no_callers = RelationshipType.CALLS not in incoming_rel
        has_no_instantiators = RelationshipType.INSTANTIATES not in incoming_rel

        if has_no_implementation_outgoing and has_no_callers and has_no_instantiators:
            return True
        

    return False


# ===========================================================================
# Scoring weights
# ===========================================================================

_W_EXACT_LABEL:      float = 10.0
_W_EXACT_ID:         float = 8.0
_W_PARTIAL_LABEL:    float = 4.0
_W_PARTIAL_ID:       float = 2.0
_W_NODE_TYPE_BASE:   float = 3.0    # generic code-node boost (CLASS/FN/METHOD)
_W_HOTSPOT:          float = 1.0    # per edge
_W_HOTSPOT_CAP:      float = 5.0
_W_SNAKE:            float = 3.0    # snake_case component match
_W_INTENT_TYPE:      float = 6.0    # node type matches intent's preferred types
_W_CALLABLE_BOOST:   float = 5.0    # extra boost for METHOD/FUNCTION in impl queries
_W_DTO_PENALTY:      float = -15.0  # node looks like a data container
_W_PHRASE_MATCH:     float = 7.0    # v4: node label/id matches a recognised phrase
_W_VERB_LABEL_BOOST: float = 4.0    # v4: node label verb component matches intent

# v5: New signals
_W_MULTI_KW_BONUS:   float = 5.0    # v5: node matches 2+ distinct base keywords
_W_LABEL_COVERAGE:   float = 3.0    # v5: most snake parts of label match query keywords
_W_GENERIC_PENALTY:  float = -4.0   # v5: node matches only expanded (not base) keywords
_W_SUBJECT_PRIORITY: float = 4.0    # v5.2: node matches subject (non-verb) query keyword

# Why these values?
# -----------------
# A DTO node can accumulate up to ~16 pts from keyword hits alone before any
# boost/penalty.  The callable-supremacy (+5) + verb-label-boost (+4) ensures
# that an implementation callable with the same keyword score outranks by ≥9.
# The DTO penalty (−15) guarantees that even a maximum-match DTO falls below a
# minimum-match callable.
# Phrase match (+7) is higher than a partial-label hit (+4) but lower than an
# exact-label hit (+10), reflecting that phrase containment is stronger than
# substring matching but the node may not be the primary implementation site.

_CODE_NODE_TYPES: frozenset[NodeType] = frozenset({
    NodeType.CLASS,
    NodeType.FUNCTION,
    NodeType.METHOD,
})


# ===========================================================================
# Output models
# ===========================================================================

@dataclass
class QueryMatch:
    """
    A single candidate node matched against a natural-language query.

    Fields
    ------
    node_id   : str         — graph node ID
    node_type : NodeType    — type of the node
    score     : float       — aggregate weighted score (higher = more relevant)
    reason    : str         — human-readable explanation of every scoring signal
                              that fired for this node (keyword matches, intent
                              boosts, penalties, etc.)
    """
    node_id:   str
    node_type: NodeType
    score:     float
    reason:    str

    def __repr__(self) -> str:
        return (
            f"QueryMatch(id={self.node_id!r}, "
            f"type={self.node_type.value}, "
            f"score={self.score:.2f})"
        )


@dataclass
class QueryResolutionResult:
    """
    The full result of resolving a natural-language query.

    Fields
    ------
    query             : str                — original question
    keywords          : list[str]          — base keywords extracted
    expanded_keywords : list[str]          — all keywords after synonym expansion
    intent            : QueryIntent        — detected intent(s)
    matches           : list[QueryMatch]   — top-K candidates, sorted by score desc
    """
    query:             str
    keywords:          list[str]
    expanded_keywords: list[str]
    intent:            QueryIntent
    matches:           list[QueryMatch] = field(default_factory=list)

    def top_node_ids(self, k: int | None = None) -> list[str]:
        """Return the node IDs of the top-k matches."""
        matches = self.matches[:k] if k else self.matches
        return [m.node_id for m in matches]

    def __repr__(self) -> str:
        cats = [c.value for c in self.intent.categories]
        return (
            f"QueryResolutionResult("
            f"keywords={self.keywords}, "
            f"intent={cats}, "
            f"matches={len(self.matches)})"
        )


# ===========================================================================
# QueryResolver
# ===========================================================================

class QueryResolver:
    """
    Converts a natural-language question into a ranked list of graph nodes.

    v4 improvements over v3
    -----------------------
    1. **Phrase detection** — a pre-pass identifies multi-word SE compound
       concepts (e.g. "subgraph extracted", "call graph", "node degree")
       before tokenisation.  Nodes whose labels match these phrases receive
       a dedicated phrase-match boost that outranks pure substring hits.
    2. **Verb-label boost** — callables whose snake_case/camelCase label
       contains an action-verb component matching the detected intent receive
       _W_VERB_LABEL_BOOST, directly addressing the reported weakness where
       retrieval and analytics queries surface data classes over callables.
    3. **GRAPH_TRAVERSAL intent** — traversal questions ("how is the subgraph
       extracted?") now have their own intent category with dedicated lexicon,
       preferred types, and verb components.
    4. **AGGREGATION intent** — analytics computation questions ("how is the
       hotspot score calculated?") separate from broad STATISTICS matches.
    5. **Graph infrastructure exemption** — GraphNode, GraphEdge, and similar
       core domain objects are exempt from the DTO penalty.
    6. **Callable-supremacy extended** — now fires for STATISTICS and
       AGGREGATION in addition to the implementation intents.
    7. **Tighter DTO patterns** — removed node/edge/vertex/arc suffix
       patterns which caused false positives on infrastructure classes.

    Parameters
    ----------
    graph : RepositoryGraph
    default_top_k : int

    Usage
    -----
    ::

        resolver = QueryResolver(graph)
        result   = resolver.resolve_query("How is the subgraph extracted?")
        for m in result.matches:
            print(m.node_id, m.score, m.reason)
    """

    def __init__(
        self,
        graph: RepositoryGraph,
        default_top_k: int = 10,
        ablation_toggles: Optional[dict[str, bool]] = None,
    ) -> None:
        self._graph = graph
        self._default_top_k = default_top_k
        if ablation_toggles is None:
            # Production defaults — only tweaks validated to improve (or not harm) metrics.
            # dto_fixes: DISABLED — ablation showed Top-1 -3.4% regression (DTO propagation
            #   incorrectly penalises execution methods like parse_args and iter_content).
            # generate_build: DISABLED — no isolated gain; with generic-penalty, build_graph
            #   only gets 'build' as an expansion hit and is suppressed, causing Top-5 regression.
            self.ablation_toggles = {
                "dto_fixes": False,
                "private_penalties": True,
                "dunder_penalties": True,
                "generate_build": False,
                "resolution_resolve": True,
                "retrieval_synonyms": True,
                "symbol_candidate": True,
                "file_module_penalty": True,
                "visualization_penalty": True,
                "verb_lexicon_cleanup": True,
            }
        else:
            self.ablation_toggles = ablation_toggles

        self._nodes: dict[str, GraphNode] = {
            node.id: node for node in graph.nodes
        }

        self._degree: dict[str, int] = defaultdict(int)
        for edge in graph.edges:
            self._degree[edge.source] += 1
            self._degree[edge.target] += 1

        # Pre-compute DTO status for every node — O(N·E) but done once.
        self._is_dto: dict[str, bool] = {
            node_id: _looks_like_dto(node, graph, dto_fixes=self.ablation_toggles.get("dto_fixes", False))
            for node_id, node in self._nodes.items()
        }

        # Propagation of DTO penalty to methods of DTO classes
        if self.ablation_toggles.get("dto_fixes", False):
            for edge in graph.edges:
                if (
                    edge.relationship == RelationshipType.CONTAINS
                    and edge.source in self._is_dto
                    and self._is_dto[edge.source]
                    and edge.target in self._nodes
                    and self._nodes[edge.target].type == NodeType.METHOD
                ):
                    self._is_dto[edge.target] = True

        # Pre-compute label components for every node — used by verb-label
        # boost.  Combines snake_case parts and camelCase splits.
        self._label_parts: dict[str, frozenset[str]] = {}
        for node_id, node in self._nodes.items():
            parts: set[str] = set()
            parts.update(_snake_parts(node.label))
            parts.update(_split_camel_case(node.label))
            # Also include the full lowercased label
            parts.add(node.label.lower())
            self._label_parts[node_id] = frozenset(parts)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve_query(
        self,
        question: str,
        top_k: Optional[int] = None,
    ) -> QueryResolutionResult:
        """
        Main entry point.  Convert *question* into a ranked list of nodes.

        Returns
        -------
        QueryResolutionResult with intent, keywords, expanded keywords,
        and ranked matches.
        """
        k = top_k if top_k is not None else self._default_top_k

        base_keywords = self.extract_keywords(question)
        intent        = self.detect_intent(base_keywords, question)
        expanded_kws  = self.expand_keywords(base_keywords)
        matches       = self.rank_candidates(question, expanded_kws, intent)[:k]

        return QueryResolutionResult(
            query=question,
            keywords=base_keywords,
            expanded_keywords=expanded_kws,
            intent=intent,
            matches=matches,
        )

    # ------------------------------------------------------------------
    # Step 1 — keyword extraction  (identical pipeline to v2/v3)
    # ------------------------------------------------------------------

    def extract_keywords(self, question: str) -> list[str]:
        """
        Extract meaningful tokens from a natural-language question.

        Pipeline
        --------
        1. Split on whitespace (preserving original casing).
        2. Per token:
           a. camelCase / PascalCase split BEFORE lowercasing.
           b. Lowercase + strip punctuation (underscores preserved).
           c. Light suffix stemming — stemmed form added as extra keyword.
           d. snake_case component expansion.
        3. Remove stop words and single-char tokens.
        4. Deduplicate preserving insertion order.
        """
        punct_no_underscore = string.punctuation.replace("_", "")

        seen: set[str] = set()
        keywords: list[str] = []

        def _add(token: str) -> None:
            t = token.strip()
            if t and len(t) >= 2 and t not in _STOP_WORDS and t not in seen:
                seen.add(t)
                keywords.append(t)

        for raw in question.split():
            camel_parts = _split_camel_case(raw)
            if len(camel_parts) > 1:
                for part in camel_parts:
                    _add(part)

            token = raw.lower().translate(
                str.maketrans("", "", punct_no_underscore)
            )
            if not token:
                continue

            _add(token)

            if token not in _STOP_WORDS:
                stem = _stem(token)
                if stem:
                    _add(stem)

            if "_" in token:
                for part in token.split("_"):
                    _add(part)
                    stem2 = _stem(part)
                    if stem2:
                        _add(stem2)

        return keywords

    # ------------------------------------------------------------------
    # Step 2 — intent detection  (v4: also takes raw question for phrases)
    # ------------------------------------------------------------------

    def detect_intent(
        self,
        keywords: list[str],
        question: str = "",
    ) -> QueryIntent:
        """
        Classify the query into one or more IntentCategory values.

        Strategy
        --------
        1. For every keyword (and its stemmed form), count lexicon hits.
        2. (v4) Run phrase detection on the raw question; each matched
           phrase's implied intents receive bonus hits proportional to
           phrase specificity (2 × the phrase word count).
        3. Return all categories that received at least one hit, ordered
           by hit count descending.

        The detection is vocabulary-driven and repository-agnostic.

        Returns
        -------
        QueryIntent with categories, is_implementation_query flag, and
        phrase_hints (v4 NEW).
        """
        category_scores: dict[IntentCategory, int] = defaultdict(int)

        kw_set = set(keywords)
        for kw in list(kw_set):
            s = _stem(kw)
            if s:
                kw_set.add(s)

        for category, lexicon in _INTENT_LEXICONS.items():
            hits = len(kw_set & lexicon)
            if hits > 0:
                category_scores[category] += hits

        # v4: phrase-based intent boosting
        phrase_matches = _detect_phrases(question) if question else []
        phrase_hints: list[str] = []
        for entry in phrase_matches:
            phrase_hints.append(entry.phrase)
            bonus = max(2, len(entry.phrase.split()))  # longer phrase → higher bonus
            for cat in entry.intents:
                category_scores[cat] += bonus

        if not category_scores:
            return QueryIntent(
                categories=[IntentCategory.UNKNOWN],
                is_implementation_query=False,
                phrase_hints=phrase_hints,
            )

        sorted_cats = sorted(
            category_scores.keys(),
            key=lambda c: -category_scores[c],
        )

        is_impl = any(c in _IMPLEMENTATION_INTENTS for c in sorted_cats)

        return QueryIntent(
            categories=sorted_cats,
            is_implementation_query=is_impl,
            phrase_hints=phrase_hints,
        )

    # ------------------------------------------------------------------
    # Step 3 — query expansion
    # ------------------------------------------------------------------

    def expand_keywords(self, base_keywords: list[str]) -> list[str]:
        """
        Expand base keywords with SE-domain synonyms.

        For each keyword (and its stemmed form) that appears in the
        expansion table, add the mapped synonyms to the keyword list.
        Synonyms are appended (lower priority than originals).

        Returns
        -------
        A new list: original keywords + expansion terms (deduplicated).
        """
        seen: set[str] = set(base_keywords)
        result: list[str] = list(base_keywords)

        def _try_add(term: str) -> None:
            if term not in seen and term not in _STOP_WORDS and len(term) >= 2:
                seen.add(term)
                result.append(term)

        # Get local expansion dict
        local_expansion = dict(_QUERY_EXPANSION)
        if self.ablation_toggles.get("generate_build", False):
            local_expansion["generate"] = list(set(local_expansion.get("generate", []) + ["build"]))
            local_expansion["generat"] = list(set(local_expansion.get("generat", []) + ["build"]))
        if self.ablation_toggles.get("resolution_resolve", False):
            local_expansion["resolution"] = list(set(local_expansion.get("resolution", []) + ["resolve"]))
            local_expansion["resolu"] = list(set(local_expansion.get("resolu", []) + ["resolve"]))
        if self.ablation_toggles.get("retrieval_synonyms", False):
            local_expansion["retrieval"] = list(set(local_expansion.get("retrieval", []) + ["retriever", "retrieve"]))
            local_expansion["retriever"] = list(set(local_expansion.get("retriever", []) + ["retrieval", "retrieve"]))
        if self.ablation_toggles.get("symbol_candidate", False):
            local_expansion["symbol"] = list(set(local_expansion.get("symbol", []) + ["candidate"]))
            local_expansion["symbols"] = list(set(local_expansion.get("symbols", []) + ["candidate"]))

        for kw in base_keywords:
            for expanded in local_expansion.get(kw, []):
                _try_add(expanded)
            s = _stem(kw)
            if s:
                for expanded in local_expansion.get(s, []):
                    _try_add(expanded)

        return result

    # ------------------------------------------------------------------
    # Step 4 — scoring / ranking
    # ------------------------------------------------------------------

    def rank_candidates(
        self,
        question: str,
        keywords: Optional[list[str]] = None,
        intent: Optional[QueryIntent] = None,
    ) -> list[QueryMatch]:
        """
        Score every graph node against the (expanded) keyword list and return
        a ranked list.

        Scoring signals (additive)
        --------------------------
        Per keyword hit:
          +10.0  exact label match
          + 8.0  exact node ID match
          + 4.0  partial label match
          + 2.0  partial node ID match
          + 3.0  snake_case component match

        Per node (once, independent of keyword count):
          + 3.0  base code-node type boost (CLASS / FUNCTION / METHOD)
          + 6.0  intent-type boost
          + 5.0  callable-supremacy boost (METHOD / FUNCTION in impl or
                 analytics queries)
          + 0–5  hotspot boost (proportional to node degree)
          + 7.0  phrase-match boost (v4 NEW)
          + 4.0  verb-label boost (v4 NEW)
          −15.0  DTO penalty
        """
        if keywords is None:
            base_kws = self.extract_keywords(question)
            intent   = self.detect_intent(base_kws, question)
            keywords = self.expand_keywords(base_kws)

        if intent is None:
            base_kws = self.extract_keywords(question)
            intent   = self.detect_intent(base_kws, question)

        if not keywords:
            return []

        scores:  dict[str, float]      = defaultdict(float)
        reasons: dict[str, list[str]]  = defaultdict(list)

        base_kws_set: set[str] = set(self.extract_keywords(question))

        # v5: track which base keywords each node matches (for multi-kw bonus)
        base_kw_hits: dict[str, set[str]] = defaultdict(set)
        # v5: track if a node has ANY base keyword hit (vs only expansion hits)
        has_base_hit: dict[str, bool] = defaultdict(bool)

        # Pre-compute snake parts cache
        snake_parts_cache: dict[str, list[str]] = {}
        for node_id, node in self._nodes.items():
            parts = _snake_parts(node.label)
            if parts:
                snake_parts_cache[node_id] = parts

        # Determine preferred node types for the detected intent
        preferred_types: frozenset[NodeType] = frozenset()
        if intent.categories and intent.categories[0] != IntentCategory.UNKNOWN:
            primary_intent = intent.categories[0]
            preferred_types = _INTENT_PREFERRED_TYPES.get(primary_intent, frozenset())

        # v4: collect phrase entries matched in this question
        phrase_matches = _detect_phrases(question)

        # v4: collect all intent verb sets for the detected categories
        active_verb_sets: list[frozenset[str]] = []
        for cat in intent.categories:
            vset = _INTENT_VERB_COMPONENTS.get(cat)
            if vset:
                if self.ablation_toggles.get("verb_lexicon_cleanup", False) and cat == IntentCategory.AUTHENTICATION:
                    vset = frozenset(vset - {"session"})
                active_verb_sets.append(vset)

        # ----------------------------------------------------------------
        # First pass: keyword-driven signals
        # ----------------------------------------------------------------
        for keyword in keywords:
            kw_lower = keyword.lower()
            is_expansion = keyword not in base_kws_set
            kw_tag = f"'{keyword}'" + (" [expanded]" if is_expansion else "")

            for node_id, node in self._nodes.items():
                label_lower = node.label.lower()
                id_lower    = node.id.lower()

                matched_this_kw = False

                if label_lower == kw_lower:
                    scores[node_id] += _W_EXACT_LABEL
                    reasons[node_id].append(f"exact label {kw_tag} +{_W_EXACT_LABEL:.0f}")
                    matched_this_kw = True

                elif id_lower == kw_lower:
                    scores[node_id] += _W_EXACT_ID
                    reasons[node_id].append(f"exact id {kw_tag} +{_W_EXACT_ID:.0f}")
                    matched_this_kw = True

                else:
                    if kw_lower in label_lower:
                        scores[node_id] += _W_PARTIAL_LABEL
                        reasons[node_id].append(
                            f"partial label {kw_tag} +{_W_PARTIAL_LABEL:.0f}"
                        )
                        matched_this_kw = True

                    if kw_lower in id_lower:
                        scores[node_id] += _W_PARTIAL_ID
                        reasons[node_id].append(
                            f"partial id {kw_tag} +{_W_PARTIAL_ID:.0f}"
                        )
                        matched_this_kw = True

                    parts = snake_parts_cache.get(node_id, [])
                    if kw_lower in parts:
                        scores[node_id] += _W_SNAKE
                        reasons[node_id].append(
                            f"snake component {kw_tag} +{_W_SNAKE:.0f}"
                        )
                        matched_this_kw = True

                # v5: track base keyword coverage
                if matched_this_kw and not is_expansion:
                    base_kw_hits[node_id].add(kw_lower)
                    has_base_hit[node_id] = True

        # ----------------------------------------------------------------
        # Second pass: per-node boosts and penalties
        # ----------------------------------------------------------------
        intent_label = (
            intent.categories[0].value
            if intent.categories and intent.categories[0] != IntentCategory.UNKNOWN
            else None
        )

        for node_id in list(scores.keys()):
            node = self._nodes[node_id]

            # Base code-node type boost
            if node.type in _CODE_NODE_TYPES:
                scores[node_id] += _W_NODE_TYPE_BASE
                reasons[node_id].append(
                    f"code-node type={node.type.value} +{_W_NODE_TYPE_BASE:.0f}"
                )

            # File/module penalty
            if self.ablation_toggles.get("file_module_penalty", False):
                if node.type in (NodeType.FILE, NodeType.MODULE):
                    file_keywords = {"file", "files", "module", "modules", "path", "paths", "folder", "directory"}
                    if not (base_kws_set & file_keywords):
                        non_file_intents = {
                            IntentCategory.PARSING, IntentCategory.GENERATION, IntentCategory.RETRIEVAL,
                            IntentCategory.EXECUTION, IntentCategory.AUTHENTICATION, IntentCategory.ROUTING,
                            IntentCategory.VALIDATION, IntentCategory.TRANSFORMATION, IntentCategory.GRAPH_TRAVERSAL,
                            IntentCategory.STATISTICS, IntentCategory.AGGREGATION, IntentCategory.ANALYSIS,
                            IntentCategory.UNKNOWN,  # also penalise when intent not detected
                        }
                        if any(c in non_file_intents for c in intent.categories):
                            scores[node_id] -= 12.0
                            reasons[node_id].append("file/module-penalty (intent-aware) -12")
            else:
                if (
                    intent.is_implementation_query
                    and node.type in (NodeType.FILE, NodeType.MODULE)
                ):
                    scores[node_id] -= 8.0
                    reasons[node_id].append("file/module-penalty (impl query) -8")

            # Intent-aware visualization penalty
            if self.ablation_toggles.get("visualization_penalty", False):
                if not (intent.categories and intent.categories[0] == IntentCategory.VISUALIZATION):
                    vis_lexicon = {"visualize", "visualis", "plot", "chart", "draw", "diagram", "visualizer", "visualiser"}
                    node_label_parts_lower = {p.lower() for p in self._label_parts.get(node_id, frozenset())}
                    if node_label_parts_lower & vis_lexicon:
                        scores[node_id] -= 4.0
                        reasons[node_id].append("visualization-demotion-penalty -4")

            # Dunder and Private penalties
            if self.ablation_toggles.get("dunder_penalties", False):
                if node.label.startswith("__") and node.label.endswith("__"):
                    scores[node_id] -= 15.0
                    reasons[node_id].append("dunder-penalty -15")
            if self.ablation_toggles.get("private_penalties", False):
                if node.label.startswith("_") and not node.label.startswith("__"):
                    scores[node_id] -= 4.0
                    reasons[node_id].append("private-penalty -4")
                elif "." in node_id:
                    parts = node_id.split(".")
                    if any(part.startswith("_") and not part.startswith("__") for part in parts[:-1]):
                        scores[node_id] -= 4.0
                        reasons[node_id].append("private-class-method-penalty -4")

            # Intent-type boost
            if preferred_types and node.type in preferred_types:
                scores[node_id] += _W_INTENT_TYPE
                reasons[node_id].append(
                    f"intent={intent_label} prefers {node.type.value} +{_W_INTENT_TYPE:.0f}"
                )

            # Callable supremacy boost (v4: extended to STATISTICS + AGGREGATION)
            if (
                any(c in _CALLABLE_SUPREMACY_INTENTS for c in intent.categories)
                and node.type in (NodeType.METHOD, NodeType.FUNCTION)
            ):
                scores[node_id] += _W_CALLABLE_BOOST
                reasons[node_id].append(
                    f"callable-supremacy {node.type.value} +{_W_CALLABLE_BOOST:.0f}"
                )

            # v4: Verb-label boost — reward callables whose label contains a
            # verb component that aligns with the active intent(s).
            # v5.2: Requires that the node has a base keyword hit on a SUBJECT
            # term (not just the verb itself).  This prevents generic verb-named
            # functions (e.g. generate_lang_path, generate_docs) from being
            # boosted on queries like "How are responses generated?" where they
            # match 'generat' (the verb) but have no overlap with 'responses'
            # (the subject).  Only nodes matching both the verb AND the subject
            # receive the boost (e.g. generate_response).
            if node.type in (NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS):
                node_label_parts = self._label_parts.get(node_id, frozenset())
                # Collect all verb tokens across all active verb sets
                all_active_verbs: frozenset[str] = frozenset().union(*active_verb_sets) if active_verb_sets else frozenset()
                # Node's base hits that are NOT verb tokens = subject hits
                node_base_hits = base_kw_hits.get(node_id, set())
                has_subject_hit = bool(node_base_hits - all_active_verbs)
                if has_subject_hit:
                    for verb_set in active_verb_sets:
                        if node_label_parts & verb_set:
                            matching_verbs = sorted(node_label_parts & verb_set)
                            scores[node_id] += _W_VERB_LABEL_BOOST
                            reasons[node_id].append(
                                f"verb-label {matching_verbs} intent={intent_label}"
                                f" +{_W_VERB_LABEL_BOOST:.0f}"
                            )
                            break  # one verb-label boost per node maximum

            # v4: Phrase-match boost — reward nodes whose label/id contains
            # a recognised phrase from the query.
            if phrase_matches:
                label_lower = node.label.lower()
                id_lower    = node.id.lower()
                for entry in phrase_matches:
                    for form in entry.node_forms:
                        form_lower = form.lower()
                        if form_lower in label_lower or form_lower in id_lower:
                            scores[node_id] += _W_PHRASE_MATCH
                            reasons[node_id].append(
                                f"phrase-match '{entry.phrase}' ({form})"
                                f" +{_W_PHRASE_MATCH:.0f}"
                            )
                            break  # one phrase-match boost per phrase per node

            # Hotspot boost
            degree = self._degree.get(node_id, 0)
            hotspot_bonus = min(degree * _W_HOTSPOT, _W_HOTSPOT_CAP)
            if hotspot_bonus > 0:
                scores[node_id] += hotspot_bonus
                reasons[node_id].append(
                    f"degree={degree} hotspot +{hotspot_bonus:.1f}"
                )

            # DTO penalty — only fires for implementation-oriented queries
            if intent.is_implementation_query and self._is_dto.get(node_id, False):
                scores[node_id] += _W_DTO_PENALTY
                reasons[node_id].append(
                    f"dto-penalty (impl query) {_W_DTO_PENALTY:.0f}"
                )

            # v5: Multi-keyword bonus — node matches 2+ distinct base keywords
            base_hits = base_kw_hits.get(node_id, set())
            if len(base_hits) >= 2:
                scores[node_id] += _W_MULTI_KW_BONUS
                reasons[node_id].append(
                    f"multi-kw-bonus hits={sorted(base_hits)} +{_W_MULTI_KW_BONUS:.0f}"
                )

            # v5.2: Subject-keyword priority — for intent-driven queries, prefer
            # nodes that match the SUBJECT of the query (the domain term) over
            # nodes that only match the VERB (the intent term).
            # Example: "How are responses generated?"
            #   - serialize_response matches 'respons' (subject) → priority boost
            #   - generate_lang_path matches 'generat' (verb/intent) → no boost
            # This prevents high-degree verb-named functions from outranking
            # lower-degree subject-named functions via hotspot score alone.
            if intent.categories and intent.categories[0] != IntentCategory.UNKNOWN:
                all_active_verbs_for_priority: frozenset[str] = (
                    frozenset().union(*active_verb_sets) if active_verb_sets else frozenset()
                )
                node_base_hits_for_priority = base_kw_hits.get(node_id, set())
                subject_hits_for_priority = node_base_hits_for_priority - all_active_verbs_for_priority
                if subject_hits_for_priority:
                    scores[node_id] += _W_SUBJECT_PRIORITY
                    reasons[node_id].append(
                        f"subject-priority hits={sorted(subject_hits_for_priority)}"
                        f" +{_W_SUBJECT_PRIORITY:.0f}"
                    )

            # v5: Label coverage bonus — most snake_case parts of the node label
            # match query base keywords (rewards specific, targeted names over
            # generic "build_all" or "get_fields_from_routes" that only partially match)
            snake_parts = snake_parts_cache.get(node_id, [])
            if snake_parts:
                content_parts = [p for p in snake_parts if p not in _STOP_WORDS and len(p) >= 3]
                if content_parts:
                    matched_parts = sum(
                        1 for p in content_parts
                        if any(p in kw or kw in p for kw in base_kws_set)
                    )
                    coverage = matched_parts / len(content_parts)
                    if coverage >= 0.67:  # most parts match
                        scores[node_id] += _W_LABEL_COVERAGE
                        reasons[node_id].append(
                            f"label-coverage={coverage:.0%} +{_W_LABEL_COVERAGE:.0f}"
                        )

            # v5: Generic penalty — node only got hits from expanded keywords,
            # not from any base keywords.  This penalises nodes like "build_all"
            # that only match because "generate" expands to "build".
            if node_id in scores and not has_base_hit.get(node_id, False):
                scores[node_id] += _W_GENERIC_PENALTY
                reasons[node_id].append(
                    f"generic-penalty (expansion-only hits) {_W_GENERIC_PENALTY:.0f}"
                )

        # Build QueryMatch objects
        matches: list[QueryMatch] = []
        for node_id, score in scores.items():
            node = self._nodes[node_id]
            reason_str = "; ".join(dict.fromkeys(reasons[node_id]))
            matches.append(QueryMatch(
                node_id=node_id,
                node_type=node.type,
                score=round(score, 4),
                reason=reason_str,
            ))

        matches.sort(key=lambda m: (-m.score, m.node_id))
        return matches

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def resolve_to_node_ids(
        self,
        question: str,
        top_k: Optional[int] = None,
    ) -> list[str]:
        """Return only node IDs ready to pass to RepositoryRetriever."""
        result = self.resolve_query(question, top_k=top_k)
        return result.top_node_ids()

    def get_ranking_diagnostics(self, match: QueryMatch) -> str:
        """
        Return a clean, multi-line diagnostic breakdown of the scoring
        reasons for a single candidate node match.
        """
        lines = []
        lines.append(match.node_id)
        lines.append(f"Final Score = {match.score}")
        if match.reason:
            parts = [p.strip() for p in match.reason.split(";")]
            for part in parts:
                match_sign = re.search(r"([-+]\d+(?:\.\d+)?)$", part)
                if match_sign:
                    val = match_sign.group(1)
                    desc = part[:match_sign.start()].strip()
                    lines.append(f"{val:>4} {desc}")
                else:
                    lines.append(f"     {part}")
        return "\n".join(lines)


# ===========================================================================
# Private helpers
# ===========================================================================

def _split_camel_case(text: str) -> list[str]:
    """
    Split a camelCase or PascalCase string into lowercase parts.

    IMPORTANT: call on ORIGINAL-cased token, before lowercasing.

    Examples
    --------
    "GraphBuilder"    → ["graph", "builder"]
    "parseRepository" → ["parse", "repository"]
    "HTTPSHandler"    → ["https", "handler"]
    """
    parts = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    parts = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", parts)
    return [p.lower() for p in parts.split() if p]


def _snake_parts(label: str) -> list[str]:
    """
    Return lowercase components of a snake_case label.

    Examples
    --------
    "parse_file"   → ["parse", "file"]
    "build_graph"  → ["build", "graph"]
    "CodeParser"   → []
    """
    if "_" not in label:
        return []
    return [p.lower() for p in label.split("_") if p]