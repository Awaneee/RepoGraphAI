"""
app/retrievers/context_builder.py
==================================
Context Builder — the bridge between QueryResolver and GraphRAG.

Responsibility
--------------
Given a natural-language question, produce a ``ContextPackage``: a
self-contained data structure that bundles every piece of graph knowledge
needed to answer the question.  The package is consumed directly in tests
and diagnostics today; tomorrow it becomes the input to a GraphRAG LLM call.

Architecture
------------
::

    Natural-language question
            ↓
    QueryResolver.resolve_query()
            ↓
    Top-K QueryMatch objects  (ranked node IDs + scores + reasons)
            ↓
    ContextBuilder._collect_retrieval_results()
            ↓  For each resolved node:
            |    NODE    → RepositoryRetriever.get_node_context()
            |    CLASS   → RepositoryRetriever.get_class_context()
            |    METHOD  → RepositoryRetriever.get_callable_context()
            |    FUNCTION→ RepositoryRetriever.get_callable_context()
            ↓
    ContextBuilder._expand_subgraph()
            ↓  RepositoryRetriever.get_subgraph(seed_ids, max_hops)
            ↓
    ContextBuilder._build_llm_context_text()
            ↓  RepositoryRetriever.build_llm_context() per seed node
            |  + subgraph edge summary
            ↓
    ContextPackage  ←  ready for LLM or further processing

Design principles
-----------------
- **Composition, not inheritance.** ContextBuilder holds a QueryResolver and
  a RepositoryRetriever; it does not subclass either.
- **No new graph abstractions.** Uses RepositoryGraph, GraphNode, GraphEdge
  exactly as returned by the existing layer.
- **Generic across Python repositories.** No hardcoded framework names,
  class names, or file paths.
- **Deterministic.** Given the same inputs, produces the same output.
  Sorted collections everywhere.
- **GraphRAG-ready.** The ContextPackage fields map 1-to-1 onto the inputs
  that a GraphRAG retrieval loop will need (see Future GraphRAG Integration
  section at the bottom of this file).

Future GraphRAG Integration
---------------------------
See the bottom of this file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Internal imports — adjust the import paths to match your project layout.
# If your project uses  ``from app.retrievers.query_resolver import …``  that
# is the canonical path; the names below must match what the file exports.
# ---------------------------------------------------------------------------
from app.models.pydantic_models import (
    GraphEdge,
    GraphNode,
    NodeType,
    RelationshipType,
    RepositoryGraph,
)
from app.retrievers.query_resolver import (
    QueryMatch,
    QueryResolutionResult,
    QueryResolver,
)
from app.retrievers.code_retriever import (
    RetrievalResult,
    RepositoryRetriever,
)


# ===========================================================================
# ContextPackage — the output model
# ===========================================================================

class ResolvedNode(BaseModel):
    """
    A single node resolved from the query, with its query-match metadata.

    This is intentionally a flat, serialisable model so it can be stored,
    logged, or streamed to a frontend without extra processing.
    """

    node_id:   str
    node_type: str          # NodeType.value — kept as str for JSON friendliness
    label:     str
    score:     float
    reason:    str          # human-readable scoring explanation from QueryResolver

    file_path:    Optional[str] = None
    line_number:  Optional[int] = None
    docstring:    Optional[str] = None

    # Relationship summary (populated by ContextBuilder)
    outgoing_count: int = 0
    incoming_count: int = 0
    neighbour_ids:  list[str] = field(default_factory=list)


class SubgraphSummary(BaseModel):
    """
    A compact, serialisable description of the expanded subgraph.

    The full RepositoryGraph object is available on ContextPackage for
    callers that need it; this summary is for logging and diagnostics.
    """

    node_count:    int
    edge_count:    int
    nodes_by_type: dict[str, int]   # NodeType.value → count
    edge_types:    list[str]        # RelationshipType.value, deduplicated, sorted


class ContextPackage(BaseModel):
    """
    The complete context bundle produced by ContextBuilder.

    Fields
    ------
    question : str
        The original natural-language question.

    intent_categories : list[str]
        Intent categories detected by QueryResolver (e.g. ["retrieval"]).

    keywords : list[str]
        Base keywords extracted from the question (pre-expansion).

    resolved_nodes : list[ResolvedNode]
        Top-K nodes that best answer the question, ranked by score.

    subgraph_node_count : int
        Total nodes in the expanded neighbourhood subgraph.

    subgraph_edge_count : int
        Total edges in the expanded neighbourhood subgraph.

    subgraph_summary : SubgraphSummary
        Structural breakdown of the expanded subgraph.

    llm_context : str
        A multi-section plain-text block, ready to embed in an LLM prompt.
        Each resolved node gets its own ``build_llm_context()`` block,
        followed by the subgraph edge list for relational grounding.

    raw_resolution : QueryResolutionResult | None
        The full QueryResolver output.  Not serialised by default (excluded
        from model_dump) but available at runtime for debugging.
    """

    class Config:
        arbitrary_types_allowed = True   # for QueryResolutionResult dataclass

    question:            str
    intent_categories:   list[str]
    keywords:            list[str]

    resolved_nodes:      list[ResolvedNode]

    subgraph_node_count: int
    subgraph_edge_count: int
    subgraph_summary:    SubgraphSummary

    llm_context:         str

    # Runtime-only — excluded from serialisation
    raw_resolution: Optional[QueryResolutionResult] = None

    # -----------------------------------------------------------------------
    # Convenience
    # -----------------------------------------------------------------------

    def top_node_ids(self) -> list[str]:
        """Return resolved node IDs in score order."""
        return [rn.node_id for rn in self.resolved_nodes]

    def node_by_id(self, node_id: str) -> Optional[ResolvedNode]:
        """Return the ResolvedNode for *node_id*, or None."""
        for rn in self.resolved_nodes:
            if rn.node_id == node_id:
                return rn
        return None

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"ContextPackage("
            f"question={self.question!r}, "
            f"resolved={len(self.resolved_nodes)}, "
            f"subgraph_nodes={self.subgraph_node_count}, "
            f"subgraph_edges={self.subgraph_edge_count})"
        )


# ===========================================================================
# ContextBuilder
# ===========================================================================

class ContextBuilder:
    """
    Orchestrates QueryResolver → RepositoryRetriever → ContextPackage.

    Parameters
    ----------
    resolver   : QueryResolver
        Pre-constructed resolver wrapping the same graph as *retriever*.
    retriever  : RepositoryRetriever
        Pre-constructed retriever wrapping the master (or filtered) graph.
    top_k      : int
        Number of top-scoring nodes to resolve.  Default: 10.
    max_hops   : int
        Number of neighbourhood hops for subgraph expansion.  Default: 1.
        Increase to 2 for deeper structural context (richer, but larger).
    max_llm_neighbours : int
        Maximum number of neighbour lines emitted per node in the LLM
        context text.  Prevents runaway context for highly-connected hubs.

    Usage
    -----
    ::

        resolver  = QueryResolver(graph)
        retriever = RepositoryRetriever(graph)
        builder   = ContextBuilder(resolver, retriever)

        package = builder.build("How does retrieval work?")
        print(package.llm_context)
    """

    def __init__(
        self,
        resolver:  QueryResolver,
        retriever: RepositoryRetriever,
        *,
        top_k:               int = 10,
        max_hops:            int = 1,
        max_llm_neighbours:  int = 20,
    ) -> None:
        self._resolver  = resolver
        self._retriever = retriever
        self._top_k     = top_k
        self._max_hops  = max_hops
        self._max_llm_neighbours = max_llm_neighbours

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(
        self,
        question: str,
        *,
        top_k:    Optional[int] = None,
        max_hops: Optional[int] = None,
    ) -> ContextPackage:
        """
        Build a ContextPackage for *question*.

        Parameters
        ----------
        question : str
            The natural-language question to answer.
        top_k : int | None
            Override the instance-level top_k for this call.
        max_hops : int | None
            Override the instance-level max_hops for this call.

        Returns
        -------
        ContextPackage
        """
        effective_k    = top_k    if top_k    is not None else self._top_k
        effective_hops = max_hops if max_hops is not None else self._max_hops

        # --- Step 1: resolve query to ranked node IDs --------------------
        resolution = self._resolver.resolve_query(question, top_k=effective_k)

        # --- Step 2: per-node retrieval ----------------------------------
        retrieval_results = self._collect_retrieval_results(resolution.matches)

        # --- Step 3: subgraph expansion ----------------------------------
        seed_ids  = {m.node_id for m in resolution.matches}
        subgraph  = self._retriever.get_subgraph(seed_ids, max_hops=effective_hops)

        # --- Step 4: build output models ---------------------------------
        resolved_nodes = self._build_resolved_nodes(
            resolution.matches, retrieval_results
        )
        subgraph_summary = _build_subgraph_summary(subgraph)
        llm_context = self._build_llm_context_text(
            question, resolution, resolved_nodes, retrieval_results, subgraph
        )

        return ContextPackage(
            question            = question,
            intent_categories   = [c.value for c in resolution.intent.categories],
            keywords            = resolution.keywords,
            resolved_nodes      = resolved_nodes,
            subgraph_node_count = len(subgraph.nodes),
            subgraph_edge_count = len(subgraph.edges),
            subgraph_summary    = subgraph_summary,
            llm_context         = llm_context,
            raw_resolution      = resolution,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collect_retrieval_results(
        self,
        matches: list[QueryMatch],
    ) -> dict[str, RetrievalResult]:
        """
        For each matched node ID, call the most appropriate retrieval method.

        Returns a mapping  node_id → RetrievalResult.
        Nodes not found in the graph (stale QueryMatch) are silently skipped.
        """
        results: dict[str, RetrievalResult] = {}

        for match in matches:
            node_id   = match.node_id
            node_type = match.node_type

            try:
                if node_type == NodeType.CLASS:
                    result = self._retriever.get_class_context(node_id)
                elif node_type in (NodeType.FUNCTION, NodeType.METHOD):
                    result = self._retriever.get_callable_context(node_id)
                else:
                    result = self._retriever.get_node_context(node_id)

                results[node_id] = result

            except KeyError:
                # Node was scored by QueryResolver but is absent from the
                # retriever's graph (should not happen with a consistent
                # graph, but guard defensively).
                pass

        return results

    @staticmethod
    def _build_resolved_nodes(
        matches:          list[QueryMatch],
        retrieval_results: dict[str, RetrievalResult],
    ) -> list[ResolvedNode]:
        """Convert QueryMatch + RetrievalResult pairs into ResolvedNode objects."""
        resolved: list[ResolvedNode] = []

        for match in matches:
            rr = retrieval_results.get(match.node_id)
            if rr is None:
                # No retrieval result — node was in the scored list but absent
                # from the graph.  Skip rather than emit a half-populated record.
                continue

            node = rr.query_node
            outgoing_count = sum(len(g.edges) for g in rr.outgoing)
            incoming_count = sum(len(g.edges) for g in rr.incoming)

            resolved.append(ResolvedNode(
                node_id        = node.id,
                node_type      = node.type.value,
                label          = node.label,
                score          = match.score,
                reason         = match.reason,
                file_path      = node.file_path,
                line_number    = node.line_number,
                docstring      = node.docstring,
                outgoing_count = outgoing_count,
                incoming_count = incoming_count,
                neighbour_ids  = sorted(rr.neighbour_ids()),
            ))

        return resolved

    def _build_llm_context_text(
        self,
        question:         str,
        resolution:       QueryResolutionResult,
        resolved_nodes:   list[ResolvedNode],
        retrieval_results: dict[str, RetrievalResult],
        subgraph:         RepositoryGraph,
    ) -> str:
        """
        Assemble the multi-section plain-text context block.

        Structure
        ---------
        QUESTION
        INTENT
        ─────────────────────────────────────────
        [per-node context blocks from build_llm_context()]
        ─────────────────────────────────────────
        SUBGRAPH RELATIONSHIPS
        """
        lines: list[str] = []
        sep = "─" * 60

        # Header
        lines.append("QUESTION")
        lines.append(question)
        lines.append("")
        lines.append("DETECTED INTENT")
        lines.append(", ".join(c.value for c in resolution.intent.categories))
        lines.append("")
        lines.append("KEYWORDS")
        lines.append(", ".join(resolution.keywords) if resolution.keywords else "(none)")
        lines.append("")

        # Per-node context blocks
        lines.append(sep)
        lines.append(f"RESOLVED NODES  ({len(resolved_nodes)} nodes)")
        lines.append(sep)

        for rn in resolved_nodes:
            # Use the retriever's own LLM context formatter for consistency.
            try:
                node_block = self._retriever.build_llm_context(
                    rn.node_id,
                    max_neighbours=self._max_llm_neighbours,
                )
            except KeyError:
                node_block = f"[{rn.node_type}] {rn.node_id}  (context unavailable)"

            lines.append(node_block)
            lines.append(f"  [QueryResolver score: {rn.score:.2f}  |  {rn.reason}]")
            lines.append("")

        # Subgraph relationship summary
        lines.append(sep)
        lines.append(
            f"SUBGRAPH  ({len(subgraph.nodes)} nodes, {len(subgraph.edges)} edges)"
        )
        lines.append(sep)

        if subgraph.edges:
            # Group edges by type for readability
            by_rel: dict[str, list[GraphEdge]] = {}
            for edge in subgraph.edges:
                key = edge.relationship.value.upper()
                by_rel.setdefault(key, []).append(edge)

            for rel_name in sorted(by_rel.keys()):
                edges = by_rel[rel_name]
                lines.append(f"\n  [{rel_name}]  ({len(edges)} edges)")
                for edge in sorted(edges, key=lambda e: (e.source, e.target)):
                    dec = f"  @{edge.decorator_name}" if edge.decorator_name else ""
                    lines.append(f"    {edge.source}  →  {edge.target}{dec}")
        else:
            lines.append("  (no edges in expanded subgraph)")

        return "\n".join(lines)


# ===========================================================================
# Private helpers
# ===========================================================================

def _build_subgraph_summary(subgraph: RepositoryGraph) -> SubgraphSummary:
    """Derive a SubgraphSummary from a RepositoryGraph."""
    nodes_by_type: dict[str, int] = {}
    for node in subgraph.nodes:
        key = node.type.value
        nodes_by_type[key] = nodes_by_type.get(key, 0) + 1

    edge_types = sorted({edge.relationship.value for edge in subgraph.edges})

    return SubgraphSummary(
        node_count    = len(subgraph.nodes),
        edge_count    = len(subgraph.edges),
        nodes_by_type = nodes_by_type,
        edge_types    = edge_types,
    )


# ===========================================================================
# Factory convenience
# ===========================================================================

def build_context_builder(
    graph: RepositoryGraph,
    *,
    top_k:              int = 10,
    max_hops:           int = 1,
    max_llm_neighbours: int = 20,
) -> ContextBuilder:
    """
    One-call factory: build a ContextBuilder from a RepositoryGraph.

    This is the typical entry point for application code that only has the
    graph and wants a ready-to-use builder without manually constructing the
    resolver and retriever.

    Parameters
    ----------
    graph : RepositoryGraph
        The master (or filtered) graph.
    top_k : int
        Top-K nodes to resolve per question.
    max_hops : int
        Neighbourhood expansion depth.
    max_llm_neighbours : int
        Per-node neighbour line cap in LLM context text.

    Returns
    -------
    ContextBuilder
    """
    resolver  = QueryResolver(graph)
    retriever = RepositoryRetriever(graph)
    return ContextBuilder(
        resolver,
        retriever,
        top_k=top_k,
        max_hops=max_hops,
        max_llm_neighbours=max_llm_neighbours,
    )


# ===========================================================================
# Future GraphRAG Integration
# ===========================================================================
#
# The ContextPackage produced by ContextBuilder is designed as the drop-in
# input to a GraphRAG retrieval loop.  Recommended integration path:
#
# 1.  Embedding layer (add-on, not a replacement)
#     -------------------------------------------
#     After graph construction, embed each node's ``build_llm_context()``
#     text with a model such as text-embedding-3-small.  Store
#     (node_id, embedding) in a vector index (Chroma, Qdrant, pgvector).
#
#     The QueryResolver continues to operate as a fast structural pre-filter.
#     The embedding index adds a *semantic* re-ranking pass over the resolved
#     node set.
#
# 2.  Hybrid retrieval
#     -----------------
#     On a user query:
#       a. Call  ContextBuilder.build(question)  for the structural pass.
#          This yields  ContextPackage.resolved_nodes  (keyword / graph signal
#          ranked).
#       b. Embed the question.  Re-rank the resolved node IDs by cosine
#          similarity to their stored embeddings.
#       c. Merge the two ranked lists (RRF or weighted sum).
#
# 3.  LLM call
#     ---------
#     Pass  ContextPackage.llm_context  as the system-prompt prefix.  The
#     LLM already has:
#       - per-node structural context (callers, callees, inheritance, …)
#       - the full subgraph edge list for relational grounding
#       - the original question at the top of the context
#
#     The only thing a basic implementation needs to add is the LLM call
#     itself:
#
#       package = builder.build(question)
#       answer  = llm.complete(
#           system  = package.llm_context,
#           user    = question,
#       )
#
# 4.  Incremental graph updates
#     --------------------------
#     When a repository changes, re-parse only the modified files, update the
#     master graph with the delta, and invalidate the embedding entries for the
#     affected node IDs.  The ContextBuilder is stateless between calls so no
#     other invalidation is needed.
#
# Key class to add:
#   GraphRAGBuilder(ContextBuilder, VectorIndex)
#     .build_hybrid(question: str, top_k: int) -> ContextPackage
#       — structural pass via ContextBuilder.build()
#       — semantic re-rank via VectorIndex.query()
#       — merged ContextPackage with llm_context ready for the LLM