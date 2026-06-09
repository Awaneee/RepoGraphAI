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
    extract_keywords()      — tokenise + normalise the question
         ↓
    detect_intent()         — classify the query into one or more
                              IntentCategory values (v3 NEW)
         ↓
    expand_keywords()       — add SE-domain synonyms for each keyword
                              and for intent-specific terms (v3 NEW)
         ↓
    _generate_candidates()  — match keywords against every node label/id
         ↓
    rank_candidates()       — score each candidate on weighted signals
         ↓
    QueryResolutionResult   — top-K QueryMatch objects ready for retrieval

Scoring signals (all additive, v3.1)
-----------------------------------
1.  EXACT_LABEL         (+10.0)  node.label == keyword (case-insensitive)
2.  EXACT_ID            (+8.0)   node.id == keyword
3.  PARTIAL_LABEL       (+4.0)   keyword in node.label
4.  PARTIAL_ID          (+2.0)   keyword in node.id
5.  NODE_TYPE_BASE      (+3.0)   CLASS / FUNCTION / METHOD preferred over
                                 FILE / MODULE
6.  HOTSPOT_BOOST       (+1.0 per edge, capped at +5.0)
7.  SNAKE_EXPANSION     (+3.0)   snake_case token expansion match
8.  INTENT_TYPE_BOOST   (+6.0)   node type matches the intent's preferred types
9.  CALLABLE_SUPREMACY  (+5.0)   METHOD / FUNCTION in an implementation query
                                 (v3.1 NEW — ensures callables always outrank
                                 DTO classes that accumulate equal keyword hits)
10. DTO_PENALTY         (−15.0)  node looks like a data container, for
                                 implementation intents (v3.1: increased from −8)

Design principles (v3 additions)
----------------------------------
- **Intent detection** is purely vocabulary-driven; no repo-specific knowledge.
  The intent lexicons describe *what developers do* (parse, generate, render,
  validate…), not what any particular codebase calls things.
- **Query expansion** maps generic SE verbs to their common synonyms so that
  "parse" also matches nodes whose labels say "read" or "load", and vice-versa.
- **DTO detection** uses structural signals only: Pydantic/dataclass decorators,
  "Parsed"/"Schema"/"Model"/"Result"/"Request"/"Response" naming patterns, or
  nodes whose only edges are CONTAINS / IMPORTS (not CALLS / INSTANTIATES).
  None of these signals are repository-specific.
- **Explainability** — every score contribution is surfaced in
  QueryMatch.reason so the caller (or a developer) can see exactly why a
  node ranked where it did.

Changelog
----------
v3 (current)
  - Intent detection + per-intent node-type weighting.
  - Query expansion table for software-engineering vocabulary.
  - DTO / data-container penalty for implementation-oriented queries.
  - Richer reason strings (intent boost, expansion, penalty all logged).
  - IntentCategory enum, QueryIntent dataclass.

v2 (previous)
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
    PARSING        = "parsing"
    GENERATION     = "generation"
    RETRIEVAL      = "retrieval"
    LOADING        = "loading"
    SAVING         = "saving"
    VISUALIZATION  = "visualization"
    STATISTICS     = "statistics"
    ANALYSIS       = "analysis"
    AUTHENTICATION = "authentication"
    ROUTING        = "routing"
    VALIDATION     = "validation"
    EXECUTION      = "execution"
    CONFIGURATION  = "configuration"
    TRANSFORMATION = "transformation"
    UNKNOWN        = "unknown"


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
        "generate", "generat", "generation", "build", "construct",
        "create", "produce", "render", "emit", "output", "synthesize",
        "format", "serialise", "serialize", "encode",
        "write", "compile",
    }),
    IntentCategory.RETRIEVAL: frozenset({
        "retriev", "retrieve", "search", "find", "lookup", "look",
        "fetch", "query", "filter", "select", "get", "load",
        "resolve", "index", "scan",
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
        "evaluate", "assess",
    }),
    IntentCategory.AUTHENTICATION: frozenset({
        "auth", "authenticat", "login", "signin", "logout", "signout",
        "token", "permission", "authoriz", "authoris", "credential",
        "session", "oauth", "jwt",
    }),
    IntentCategory.ROUTING: frozenset({
        "route", "router", "endpoint", "url", "path", "dispatch",
        "handler", "middleware", "request", "response",
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
})

_INTENT_PREFERRED_TYPES: dict[IntentCategory, frozenset[NodeType]] = {
    # Implementation intents strongly prefer callables and service classes
    IntentCategory.PARSING:        frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.GENERATION:     frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.RETRIEVAL:      frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.LOADING:        frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.SAVING:         frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.ANALYSIS:       frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.AUTHENTICATION: frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.ROUTING:        frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.EXECUTION:      frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.TRANSFORMATION: frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    # Data-oriented intents may legitimately return schema / model nodes
    IntentCategory.STATISTICS:     frozenset({NodeType.METHOD, NodeType.FUNCTION, NodeType.CLASS}),
    IntentCategory.VALIDATION:     frozenset({NodeType.CLASS, NodeType.METHOD, NodeType.FUNCTION}),
    IntentCategory.VISUALIZATION:  frozenset({NodeType.FUNCTION, NodeType.METHOD, NodeType.CLASS}),
    IntentCategory.CONFIGURATION:  frozenset({NodeType.CLASS, NodeType.FUNCTION, NodeType.METHOD}),
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
    """
    categories: list[IntentCategory]
    is_implementation_query: bool


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
    "generate":   ["build", "create", "construct", "produce", "emit"],
    "generat":    ["build", "create", "construct"],   # stemmed form
    "create":     ["build", "generate", "construct", "make"],
    "construct":  ["build", "create", "instantiate"],

    # ---- Retrieval / search ----
    "retrieve":   ["search", "fetch", "find", "lookup", "query", "get"],
    "retriev":    ["search", "fetch", "find", "lookup"],   # stemmed form
    "search":     ["find", "retrieve", "lookup", "filter", "query"],
    "find":       ["search", "retrieve", "lookup", "query"],
    "fetch":      ["retrieve", "get", "load", "download"],
    "lookup":     ["find", "search", "retrieve", "resolve"],
    "query":      ["search", "find", "retrieve", "filter"],

    # ---- Saving / persisting ----
    "save":       ["store", "write", "persist", "export", "dump"],
    "store":      ["save", "persist", "write", "cache"],
    "persist":    ["save", "store", "write"],
    "write":      ["save", "store", "output", "emit"],
    "export":     ["write", "save", "dump", "output"],

    # ---- Traversal / walking ----
    "walk":       ["traverse", "visit", "iterate", "scan", "explore"],
    "traverse":   ["walk", "visit", "iterate", "explore"],
    "visit":      ["walk", "traverse", "iterate"],
    "iterate":    ["walk", "traverse", "loop", "enumerate"],

    # ---- Analysis ----
    "analyse":    ["analyze", "inspect", "evaluate", "examine"],
    "analyze":    ["analyse", "inspect", "evaluate", "examine"],
    "inspect":    ["analyse", "analyze", "examine", "check"],
    "evaluate":   ["analyse", "analyze", "assess", "check"],

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

    # ---- Statistics / metrics ----
    "statistics": ["metrics", "analytics", "stats", "summary", "report"],
    "statistic":  ["metric", "analytic", "stat"],   # stemmed form
    "metrics":    ["statistics", "analytics", "stats", "measurements"],
    "analytics":  ["statistics", "metrics", "analysis", "reporting"],

    # ---- Repository-level ----
    "repository": ["repo", "codebase", "project", "package"],
    "repo":       ["repository", "codebase", "project"],
    "file":       ["module", "source", "script"],
    "module":     ["file", "package", "component"],
    "class":      ["type", "model", "schema", "entity"],
    "function":   ["method", "callable", "procedure", "routine"],
    "method":     ["function", "callable", "procedure"],
}


# ===========================================================================
# DTO / data-container detection
# ===========================================================================

# Name prefixes/suffixes that suggest a DTO / schema / result object.
# All are generic SE naming conventions (not repo-specific).
_DTO_NAME_PATTERNS: list[re.Pattern[str]] = [
    # Prefix patterns
    re.compile(r"^parsed",     re.IGNORECASE),
    re.compile(r"^serialized", re.IGNORECASE),
    re.compile(r"^raw",        re.IGNORECASE),
    re.compile(r"^dto",        re.IGNORECASE),

    # Suffix patterns  (most common DTO naming conventions across frameworks)
    re.compile(r"(schema|model|dto|data|record)$",            re.IGNORECASE),
    re.compile(r"(request|response|reply|payload|body)$",     re.IGNORECASE),
    re.compile(r"(result|output|summary|report)$",            re.IGNORECASE),
    re.compile(r"(entity|document|row|item|entry)$",          re.IGNORECASE),
    re.compile(r"(config|settings|options|params|args)$",     re.IGNORECASE),
    re.compile(r"(event|message|packet|frame|envelope)$",     re.IGNORECASE),
    re.compile(r"(node|edge|vertex|arc)$",                    re.IGNORECASE),
    re.compile(r"(type|types|kind|enum)$",                    re.IGNORECASE),
]

# Decorator names that indicate a data-container class.
# These are framework-agnostic decorator patterns, not hard-coded names.
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


def _looks_like_dto(node: GraphNode, graph: RepositoryGraph) -> bool:
    """
    Return True when *node* appears to be a data-container (DTO, schema,
    model, result object) rather than an implementation symbol.

    Detection uses three independent signals; any one is sufficient:

    1. **Name pattern** — the node label matches a known DTO naming
       convention (e.g. ends in "Schema", "Model", "Result", "Request", …).
    2. **Decorator** — the node's decorators (derived from graph edges that
       carry decorator metadata) suggest a data-class framework
       (e.g. @dataclass, @BaseModel, @schema).
    3. **Edge profile** — a CLASS node whose only outgoing edge type is
       CONTAINS and whose only incoming edge types are CONTAINS / IMPORTS
       is almost certainly a plain data container (it is never called or
       instantiated by anything in the graph).

    All three signals are generic; none reference project-specific names.
    """
    if node.type not in (NodeType.CLASS, NodeType.FUNCTION, NodeType.METHOD):
        return False

    label = node.label

    # ------------------------------------------------------------------
    # Signal 1: name pattern
    # ------------------------------------------------------------------
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
            dec_lower = edge.decorator_name.lower().split(".")[-1]  # "router.get" → "get"
            # Check if any fragment of the decorator name matches a DTO decorator
            for frag in _DTO_DECORATOR_FRAGMENTS:
                if frag in dec_lower:
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
_W_NODE_TYPE_BASE:   float = 3.0   # generic code-node boost (CLASS/FN/METHOD)
_W_HOTSPOT:          float = 1.0   # per edge
_W_HOTSPOT_CAP:      float = 5.0
_W_SNAKE:            float = 3.0   # snake_case component match
_W_INTENT_TYPE:      float = 6.0   # node type matches intent's preferred types
_W_CALLABLE_BOOST:   float = 5.0   # extra boost for METHOD/FUNCTION in impl queries
_W_DTO_PENALTY:      float = -15.0 # node looks like a data container

# Why these values?
# -----------------
# A DTO node can accumulate up to ~16 pts from keyword hits alone (e.g. a
# name like "ParsedRecord" matches "parsed", "record", "pars", "records"
# each at +4 partial-label = +16) before any boost/penalty.  An equivalent
# METHOD node ("parse_record") accumulates comparable keyword points BUT
# also earns _W_CALLABLE_BOOST (+5) on top.  The penalty of −15 guarantees
# that even a maximum-match DTO (16 + 3 base + 6 intent = +25) falls below
# a minimum-match callable (+keyword_score + 3 + 6 + 5 = keyword_score+14).
# For the penalty NOT to fire on non-implementation queries, it is gated on
# intent.is_implementation_query.

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
    query    : str                — original question
    keywords : list[str]          — base keywords extracted from the query
    expanded_keywords : list[str] — all keywords after synonym expansion
    intent   : QueryIntent        — detected intent(s)
    matches  : list[QueryMatch]   — top-K candidates, sorted by score descending
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

    v3 improvements over v2
    -----------------------
    1. **Intent detection** — classifies the query (parsing, generation,
       retrieval, …) and adjusts which node types are preferred.
    2. **Query expansion** — adds SE-domain synonyms so that, e.g., "parse"
       also matches nodes containing "read", "decode", "extract", etc.
    3. **DTO penalty** — nodes that look like data containers receive a
       negative score adjustment for implementation-oriented queries, so that
       `parse_file` outranks `ParsedFile` when the question is "How are files
       parsed?".
    4. **Richer reason strings** — every scoring signal (including expansion
       hits, intent boosts, and penalties) is reflected in the reason field.

    Parameters
    ----------
    graph : RepositoryGraph
    default_top_k : int

    Usage
    -----
    ::

        resolver = QueryResolver(graph)
        result   = resolver.resolve_query("How are files parsed?")
        for m in result.matches:
            print(m.node_id, m.score, m.reason)
    """

    def __init__(
        self,
        graph: RepositoryGraph,
        default_top_k: int = 10,
    ) -> None:
        self._graph = graph
        self._default_top_k = default_top_k

        self._nodes: dict[str, GraphNode] = {
            node.id: node for node in graph.nodes
        }

        self._degree: dict[str, int] = defaultdict(int)
        for edge in graph.edges:
            self._degree[edge.source] += 1
            self._degree[edge.target] += 1

        # Pre-compute DTO status for every node — O(N·E) but done once.
        self._is_dto: dict[str, bool] = {
            node_id: _looks_like_dto(node, graph)
            for node_id, node in self._nodes.items()
        }

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

        base_keywords    = self.extract_keywords(question)
        intent           = self.detect_intent(base_keywords)
        expanded_kws     = self.expand_keywords(base_keywords)
        matches          = self.rank_candidates(question, expanded_kws, intent)[:k]

        return QueryResolutionResult(
            query=question,
            keywords=base_keywords,
            expanded_keywords=expanded_kws,
            intent=intent,
            matches=matches,
        )

    # ------------------------------------------------------------------
    # Step 1 — keyword extraction  (identical pipeline to v2)
    # ------------------------------------------------------------------

    def extract_keywords(self, question: str) -> list[str]:
        """
        Extract meaningful tokens from a natural-language question.

        Pipeline (same as v2)
        ---------------------
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
    # Step 2 — intent detection
    # ------------------------------------------------------------------

    def detect_intent(self, keywords: list[str]) -> QueryIntent:
        """
        Classify the query into one or more IntentCategory values.

        Strategy
        --------
        For every keyword (and its stemmed form), count how many intent
        lexicons it appears in.  Return all categories that received at
        least one hit, ordered by hit count descending.

        The detection is vocabulary-driven and repository-agnostic: it
        relies only on generic SE terms, never on project-specific names.

        Returns
        -------
        QueryIntent with categories and is_implementation_query flag.
        """
        category_scores: dict[IntentCategory, int] = defaultdict(int)

        kw_set = set(keywords)
        # Also include stemmed forms of the keywords
        for kw in list(kw_set):
            s = _stem(kw)
            if s:
                kw_set.add(s)

        for category, lexicon in _INTENT_LEXICONS.items():
            hits = len(kw_set & lexicon)
            if hits > 0:
                category_scores[category] += hits

        if not category_scores:
            return QueryIntent(
                categories=[IntentCategory.UNKNOWN],
                is_implementation_query=False,
            )

        sorted_cats = sorted(
            category_scores.keys(),
            key=lambda c: -category_scores[c],
        )

        is_impl = any(c in _IMPLEMENTATION_INTENTS for c in sorted_cats)

        return QueryIntent(categories=sorted_cats, is_implementation_query=is_impl)

    # ------------------------------------------------------------------
    # Step 3 — query expansion
    # ------------------------------------------------------------------

    def expand_keywords(self, base_keywords: list[str]) -> list[str]:
        """
        Expand base keywords with SE-domain synonyms.

        For each keyword (and its stemmed form) that appears in the
        expansion table, add the mapped synonyms to the keyword list.
        Synonyms are added at a lower priority than original keywords
        (they are appended, not prepended) to avoid swamping exact
        matches.

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

        for kw in base_keywords:
            for expanded in _QUERY_EXPANSION.get(kw, []):
                _try_add(expanded)
            # Also try stemmed form of keyword
            s = _stem(kw)
            if s:
                for expanded in _QUERY_EXPANSION.get(s, []):
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
          + 6.0  intent-type boost — node type matches the detected intent's
                 preferred types
          + 5.0  callable-supremacy boost — METHOD / FUNCTION in an
                 implementation query (v3.1 NEW)
          + 0–5  hotspot boost — proportional to node degree
          −15.0  DTO penalty — node looks like a data container AND the query
                 intent is implementation-oriented (v3.1: increased from −8)

        Every signal that fires is appended to the node's reason string.
        """
        if keywords is None:
            base_kws = self.extract_keywords(question)
            intent   = self.detect_intent(base_kws)
            keywords = self.expand_keywords(base_kws)

        if intent is None:
            base_kws = self.extract_keywords(question)
            intent   = self.detect_intent(base_kws)

        if not keywords:
            return []

        scores:  dict[str, float]      = defaultdict(float)
        reasons: dict[str, list[str]]  = defaultdict(list)

        # Identify which keywords are "expanded" (not in base set) for
        # reporting purposes.  We track the original base set via a simple
        # heuristic: the first len(base_kws) entries.
        # Since we always pass expanded_keywords here, mark the boundary.
        # (We re-extract base keywords only to annotate reason strings.)
        base_kws_set: set[str] = set(self.extract_keywords(question))

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

                if label_lower == kw_lower:
                    scores[node_id] += _W_EXACT_LABEL
                    reasons[node_id].append(f"exact label {kw_tag} +{_W_EXACT_LABEL:.0f}")

                elif id_lower == kw_lower:
                    scores[node_id] += _W_EXACT_ID
                    reasons[node_id].append(f"exact id {kw_tag} +{_W_EXACT_ID:.0f}")

                else:
                    if kw_lower in label_lower:
                        scores[node_id] += _W_PARTIAL_LABEL
                        reasons[node_id].append(f"partial label {kw_tag} +{_W_PARTIAL_LABEL:.0f}")

                    if kw_lower in id_lower:
                        scores[node_id] += _W_PARTIAL_ID
                        reasons[node_id].append(f"partial id {kw_tag} +{_W_PARTIAL_ID:.0f}")

                    parts = snake_parts_cache.get(node_id, [])
                    if kw_lower in parts:
                        scores[node_id] += _W_SNAKE
                        reasons[node_id].append(f"snake component {kw_tag} +{_W_SNAKE:.0f}")

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

            # Intent-type boost
            if preferred_types and node.type in preferred_types:
                scores[node_id] += _W_INTENT_TYPE
                reasons[node_id].append(
                    f"intent={intent_label} prefers {node.type.value} +{_W_INTENT_TYPE:.0f}"
                )

            # Callable supremacy boost — METHOD and FUNCTION nodes receive an
            # additional boost over CLASS nodes for implementation queries.
            # Rationale: when a user asks "how does X work?", the answer is
            # almost always a function or method, not a class definition.
            # This bonus is intentionally larger than a single partial-label
            # hit so that an implementation callable always outranks a DTO
            # class that matched the same keyword set.
            if (
                intent.is_implementation_query
                and node.type in (NodeType.METHOD, NodeType.FUNCTION)
            ):
                scores[node_id] += _W_CALLABLE_BOOST
                reasons[node_id].append(
                    f"callable-supremacy {node.type.value} +{_W_CALLABLE_BOOST:.0f}"
                )

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