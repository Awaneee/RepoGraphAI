"""
app/retrieval/repository_retriever.py
======================================
Graph-based retrieval layer for RepoGraphAI.

Architecture
------------
RepositoryRetriever wraps a ``RepositoryGraph`` (master or filtered view) and
exposes a set of targeted query methods that return structured ``RetrievalResult``
objects.  Every method is purely in-memory — no embeddings, no databases.

Internal data structures
~~~~~~~~~~~~~~~~~~~~~~~~
Two adjacency indices are built once at construction time from the flat edge
list, in O(E):

  _out_index : dict[node_id, list[GraphEdge]]   — edges *leaving* a node
  _in_index  : dict[node_id, list[GraphEdge]]   — edges *arriving* at a node

Both indices contain the full GraphEdge objects, so callers can inspect the
relationship type and any extra metadata (e.g. decorator_name) without
additional lookups.

A node dictionary ``_nodes`` (node_id → GraphNode) is built in O(N) for
constant-time node lookups.

Query methods
~~~~~~~~~~~~~
get_node_context(node_id)
    The universal entry point.  Returns the target node, all incoming/outgoing
    edges grouped by relationship type, and the full set of one-hop neighbours.
    Works for any node type.

get_class_context(class_id)
    Specialised view for a CLASS node.  Appends:
      - Methods contained in the class (CONTAINS edges to METHOD nodes).
      - The file that defines the class (inverse CONTAINS from FILE nodes).
      - Inheritance chain: parents the class INHERITS from, and children that
        INHERIT from it.
      - Classes this class INSTANTIATES and classes that INSTANTIATE it.

get_callable_context(node_id)
    Specialised view for FUNCTION or METHOD nodes.  Appends:
      - Callers  : nodes that CALLS this node (fan-in).
      - Callees  : nodes this node CALLS (fan-out).
      - For METHOD nodes: the owning CLASS (inverse CONTAINS).
      - If the method OVERRIDES another method, the overridden target.

build_llm_context(node_id, max_neighbours)
    Packages a RetrievalResult into a plain-text block ready for use as an
    LLM prompt prefix.  Caller controls the maximum number of neighbour
    lines to prevent context overflow.

search_by_label(label, node_types)
    Fuzzy substring search across node labels (case-insensitive).  Useful
    when the caller does not know the exact node ID.

GraphRAG integration notes
~~~~~~~~~~~~~~~~~~~~~~~~~~
See ``Future GraphRAG Integration`` at the bottom of this file.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from app.models.pydantic_models import (
    GraphEdge,
    GraphNode,
    NodeType,
    RelationshipType,
    RepositoryGraph,
)


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------

@dataclass
class EdgeGroup:
    """A set of edges sharing the same relationship type."""
    relationship: RelationshipType
    edges: list[GraphEdge] = field(default_factory=list)

    def __repr__(self) -> str:  # pragma: no cover
        return f"EdgeGroup({self.relationship.value.upper()}, n={len(self.edges)})"


@dataclass
class RetrievalResult:
    """
    The structured result returned by every retrieval query.

    Fields
    ------
    query_node : GraphNode
        The node that was queried.
    outgoing : list[EdgeGroup]
        Outgoing edges grouped by RelationshipType.
    incoming : list[EdgeGroup]
        Incoming edges grouped by RelationshipType.
    neighbours : list[GraphNode]
        All one-hop neighbour nodes (both directions), deduplicated.
    metadata : dict
        Extra context added by specialised retrieval methods
        (e.g. "methods", "file", "callers", "callees").
    """

    query_node: GraphNode
    outgoing: list[EdgeGroup] = field(default_factory=list)
    incoming: list[EdgeGroup] = field(default_factory=list)
    neighbours: list[GraphNode] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    # Convenience accessors -----------------------------------------------

    def edges_of_type(self, rel: RelationshipType) -> list[GraphEdge]:
        """Return all edges (in or out) matching a specific relationship type."""
        results: list[GraphEdge] = []
        for group in self.outgoing + self.incoming:
            if group.relationship == rel:
                results.extend(group.edges)
        return results

    def neighbour_ids(self) -> set[str]:
        return {n.id for n in self.neighbours}

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"RetrievalResult(node={self.query_node.id!r}, "
            f"out_groups={len(self.outgoing)}, "
            f"in_groups={len(self.incoming)}, "
            f"neighbours={len(self.neighbours)})"
        )


# ---------------------------------------------------------------------------
# RepositoryRetriever
# ---------------------------------------------------------------------------

class RepositoryRetriever:
    """
    Graph-based retrieval over a RepositoryGraph.

    Parameters
    ----------
    graph : RepositoryGraph
        The master graph (or any filtered view) produced by GraphBuilder.

    Usage
    -----
    ::

        retriever = RepositoryRetriever(master_graph)

        # Universal lookup
        ctx = retriever.get_node_context("RepositoryService")

        # Class-specialised lookup
        ctx = retriever.get_class_context("RepositoryService")

        # Callable-specialised lookup
        ctx = retriever.get_callable_context("RepositoryService.build_graph")

        # LLM-ready text block
        text = retriever.build_llm_context("RepositoryService")
    """

    def __init__(self, graph: RepositoryGraph) -> None:
        self._graph = graph

        # O(N) node index
        self._nodes: dict[str, GraphNode] = {
            node.id: node for node in graph.nodes
        }

        # O(E) adjacency indices
        self._out_index: dict[str, list[GraphEdge]] = defaultdict(list)
        self._in_index:  dict[str, list[GraphEdge]] = defaultdict(list)

        for edge in graph.edges:
            self._out_index[edge.source].append(edge)
            self._in_index[edge.target].append(edge)

    # ------------------------------------------------------------------
    # Public API — universal
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Return the GraphNode for *node_id*, or None if not found."""
        return self._nodes.get(node_id)

    def get_node_context(self, node_id: str) -> RetrievalResult:
        """
        Universal retrieval for any node type.

        Returns
        -------
        RetrievalResult with:
          - query_node  : the target GraphNode
          - outgoing    : all edges leaving this node, grouped by type
          - incoming    : all edges arriving at this node, grouped by type
          - neighbours  : one-hop neighbours from both edge directions

        Raises
        ------
        KeyError if node_id is not in the graph.
        """
        node = self._require_node(node_id)

        outgoing = self._group_edges(self._out_index.get(node_id, []))
        incoming = self._group_edges(self._in_index.get(node_id, []))
        neighbours = self._collect_neighbours(node_id)

        return RetrievalResult(
            query_node=node,
            outgoing=outgoing,
            incoming=incoming,
            neighbours=neighbours,
        )

    # ------------------------------------------------------------------
    # Public API — class-specialised
    # ------------------------------------------------------------------

    def get_class_context(self, class_id: str) -> RetrievalResult:
        """
        Specialised retrieval for a CLASS node.

        Extra metadata keys
        -------------------
        "methods"            : list[GraphNode]   — METHOD nodes contained in this class
        "file"               : GraphNode | None  — FILE node that defines this class
        "parent_classes"     : list[GraphNode]   — classes this class INHERITS from
        "child_classes"      : list[GraphNode]   — classes that INHERIT from this one
        "instantiates"       : list[GraphNode]   — classes this class INSTANTIATES
        "instantiated_by"    : list[GraphNode]   — classes / functions that INSTANTIATE this
        "decorators"         : list[str]         — decorator source names from DECORATES edges
        """
        result = self.get_node_context(class_id)

        # Methods — outgoing CONTAINS to METHOD nodes
        methods = [
            self._nodes[e.target]
            for e in self._out_index.get(class_id, [])
            if e.relationship == RelationshipType.CONTAINS
            and e.target in self._nodes
            and self._nodes[e.target].type == NodeType.METHOD
        ]

        # Defining file — incoming CONTAINS from a FILE node
        file_node: Optional[GraphNode] = None
        for e in self._in_index.get(class_id, []):
            if (
                e.relationship == RelationshipType.CONTAINS
                and e.source in self._nodes
                and self._nodes[e.source].type == NodeType.FILE
            ):
                file_node = self._nodes[e.source]
                break

        # Parent classes — outgoing INHERITS
        parent_classes = [
            self._nodes[e.target]
            for e in self._out_index.get(class_id, [])
            if e.relationship == RelationshipType.INHERITS
            and e.target in self._nodes
        ]

        # Child classes — incoming INHERITS
        child_classes = [
            self._nodes[e.source]
            for e in self._in_index.get(class_id, [])
            if e.relationship == RelationshipType.INHERITS
            and e.source in self._nodes
        ]

        # Classes this class instantiates — outgoing INSTANTIATES
        instantiates = [
            self._nodes[e.target]
            for e in self._out_index.get(class_id, [])
            if e.relationship == RelationshipType.INSTANTIATES
            and e.target in self._nodes
        ]

        # Classes / functions that instantiate this one — incoming INSTANTIATES
        instantiated_by = [
            self._nodes[e.source]
            for e in self._in_index.get(class_id, [])
            if e.relationship == RelationshipType.INSTANTIATES
            and e.source in self._nodes
        ]

        # Decorators — incoming DECORATES (source may not be a graph node)
        decorators = [
            e.source
            for e in self._in_index.get(class_id, [])
            if e.relationship == RelationshipType.DECORATES
        ]

        result.metadata = {
            "methods":         methods,
            "file":            file_node,
            "parent_classes":  parent_classes,
            "child_classes":   child_classes,
            "instantiates":    instantiates,
            "instantiated_by": instantiated_by,
            "decorators":      decorators,
        }

        return result

    # ------------------------------------------------------------------
    # Public API — callable-specialised (FUNCTION or METHOD)
    # ------------------------------------------------------------------

    def get_callable_context(self, node_id: str) -> RetrievalResult:
        """
        Specialised retrieval for FUNCTION or METHOD nodes.

        Extra metadata keys
        -------------------
        "callers"        : list[GraphNode]   — nodes that CALL this callable
        "callees"        : list[GraphNode]   — nodes this callable CALLS
        "owning_class"   : GraphNode | None  — CLASS node (METHOD only)
        "overrides"      : GraphNode | None  — METHOD this overrides (METHOD only)
        "overridden_by"  : list[GraphNode]   — METHODs that override this (METHOD only)
        """
        result = self.get_node_context(node_id)

        # Callers — incoming CALLS edges
        callers = [
            self._nodes[e.source]
            for e in self._in_index.get(node_id, [])
            if e.relationship == RelationshipType.CALLS
            and e.source in self._nodes
        ]

        # Callees — outgoing CALLS edges
        callees = [
            self._nodes[e.target]
            for e in self._out_index.get(node_id, [])
            if e.relationship == RelationshipType.CALLS
            and e.target in self._nodes
        ]

        # Owning class — incoming CONTAINS from a CLASS node (METHOD only)
        owning_class: Optional[GraphNode] = None
        node = self._nodes[node_id]
        if node.type == NodeType.METHOD:
            for e in self._in_index.get(node_id, []):
                if (
                    e.relationship == RelationshipType.CONTAINS
                    and e.source in self._nodes
                    and self._nodes[e.source].type == NodeType.CLASS
                ):
                    owning_class = self._nodes[e.source]
                    break

        # OVERRIDES — outgoing (this method overrides something)
        overrides: Optional[GraphNode] = None
        for e in self._out_index.get(node_id, []):
            if e.relationship == RelationshipType.OVERRIDES and e.target in self._nodes:
                overrides = self._nodes[e.target]
                break

        # Overridden_by — incoming OVERRIDES (other methods override this one)
        overridden_by = [
            self._nodes[e.source]
            for e in self._in_index.get(node_id, [])
            if e.relationship == RelationshipType.OVERRIDES
            and e.source in self._nodes
        ]

        result.metadata = {
            "callers":       callers,
            "callees":       callees,
            "owning_class":  owning_class,
            "overrides":     overrides,
            "overridden_by": overridden_by,
        }

        return result

    # ------------------------------------------------------------------
    # Public API — LLM context builder
    # ------------------------------------------------------------------

    def build_llm_context(
        self,
        node_id: str,
        max_neighbours: int = 20,
    ) -> str:
        """
        Build a plain-text LLM context block for a given node.

        The output is a structured, human-readable summary of the node and
        its graph neighbourhood.  Pass it as a prefix to the LLM prompt so
        the model has structural context before answering questions about
        the symbol.

        Parameters
        ----------
        node_id : str
            The node to build context for.
        max_neighbours : int
            Maximum number of neighbour lines to emit (prevents runaway
            context for highly-connected hubs).

        Returns
        -------
        str
            Multi-line text block, typically 200–800 tokens for an average
            node.
        """
        node = self._require_node(node_id)
        node_type = node.type

        # Route to the most informative retrieval method.
        if node_type == NodeType.CLASS:
            result = self.get_class_context(node_id)
        elif node_type in (NodeType.FUNCTION, NodeType.METHOD):
            result = self.get_callable_context(node_id)
        else:
            result = self.get_node_context(node_id)

        lines: list[str] = []

        # --- Header ---
        lines.append(f"=== {node_type.value.upper()}: {node.label} ===")
        lines.append(f"ID: {node.id}")
        if getattr(node, "file_path", None):
            lines.append(f"File: {node.file_path}")
        if getattr(node, "line_number", None):
            lines.append(f"Line: {node.line_number}")
        if getattr(node, "docstring", None):
            doc = node.docstring.split("\n")[0]  # first line only
            lines.append(f"Docstring: {doc}")

        # --- Specialised metadata ---
        meta = result.metadata

        if node_type == NodeType.CLASS:
            _emit_nodes(lines, "Defined in file",   [meta["file"]] if meta.get("file") else [])
            _emit_nodes(lines, "Methods",            meta.get("methods", []))
            _emit_nodes(lines, "Inherits from",      meta.get("parent_classes", []))
            _emit_nodes(lines, "Subclassed by",      meta.get("child_classes", []))
            _emit_nodes(lines, "Instantiates",       meta.get("instantiates", []))
            _emit_nodes(lines, "Instantiated by",    meta.get("instantiated_by", []))
            decorators = meta.get("decorators", [])
            if decorators:
                lines.append(f"Decorators: {', '.join(decorators)}")

        elif node_type in (NodeType.FUNCTION, NodeType.METHOD):
            _emit_nodes(lines, "Owning class", [meta["owning_class"]] if meta.get("owning_class") else [])
            _emit_nodes(lines, "Callers",      meta.get("callers", []))
            _emit_nodes(lines, "Calls",        meta.get("callees", []))
            if meta.get("overrides"):
                lines.append(f"Overrides: {meta['overrides'].id}")
            _emit_nodes(lines, "Overridden by", meta.get("overridden_by", []))

        # --- Generic outgoing edges ---
        if result.outgoing:
            lines.append("\nOutgoing relationships:")
            for group in result.outgoing:
                for edge in group.edges[:max_neighbours]:
                    lines.append(f"  --[{group.relationship.value}]--> {edge.target}")

        # --- Generic incoming edges ---
        if result.incoming:
            lines.append("\nIncoming relationships:")
            for group in result.incoming:
                for edge in group.edges[:max_neighbours]:
                    lines.append(f"  <--[{group.relationship.value}]-- {edge.source}")

        # --- Neighbours summary ---
        neighbours = result.neighbours[:max_neighbours]
        if neighbours:
            lines.append(f"\nNeighbours ({len(result.neighbours)} total, showing {len(neighbours)}):")
            for n in neighbours:
                lines.append(f"  [{n.type.value}] {n.id}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Public API — search
    # ------------------------------------------------------------------

    def search_by_label(
        self,
        label: str,
        node_types: Optional[frozenset[NodeType]] = None,
    ) -> list[GraphNode]:
        """
        Case-insensitive substring search over node labels.

        Parameters
        ----------
        label : str
            Search string.  A node matches if ``label.lower()`` is a
            substring of ``node.label.lower()``.
        node_types : frozenset[NodeType] | None
            If provided, restrict matches to these node types.

        Returns
        -------
        list[GraphNode]  — sorted by label for deterministic ordering.
        """
        query = label.lower()
        results = [
            node
            for node in self._nodes.values()
            if query in node.label.lower()
            and (node_types is None or node.type in node_types)
        ]
        return sorted(results, key=lambda n: (n.type.value, n.label))

    def get_subgraph(
        self,
        node_ids: set[str],
        max_hops: int = 1,
    ) -> RepositoryGraph:
        """
        Return a RepositoryGraph containing *node_ids* and all nodes within
        *max_hops* of any seed node, plus the edges that connect them.

        This is the core primitive for GraphRAG chunk construction: given a
        set of semantically-relevant seed nodes, expand to their structural
        neighbourhood and return a self-contained subgraph that can be
        serialised as LLM context.

        Parameters
        ----------
        node_ids : set[str]
            Seed nodes for the expansion.
        max_hops : int
            Number of edge hops to expand.  1 = immediate neighbours only.

        Returns
        -------
        RepositoryGraph
        """
        visited: set[str] = set()
        frontier: set[str] = {nid for nid in node_ids if nid in self._nodes}

        for _ in range(max_hops):
            next_frontier: set[str] = set()
            for nid in frontier:
                if nid in visited:
                    continue
                visited.add(nid)
                for edge in self._out_index.get(nid, []):
                    if edge.target in self._nodes:
                        next_frontier.add(edge.target)
                for edge in self._in_index.get(nid, []):
                    if edge.source in self._nodes:
                        next_frontier.add(edge.source)
            frontier = next_frontier - visited

        all_ids = visited | frontier

        subgraph_nodes = [self._nodes[nid] for nid in all_ids if nid in self._nodes]
        subgraph_edges = [
            edge
            for nid in all_ids
            for edge in self._out_index.get(nid, [])
            if edge.target in all_ids
        ]

        return RepositoryGraph(
            nodes=sorted(subgraph_nodes, key=lambda n: (n.type.value, n.id)),
            edges=subgraph_edges,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_node(self, node_id: str) -> GraphNode:
        node = self._nodes.get(node_id)
        if node is None:
            known = sorted(self._nodes.keys())[:10]
            raise KeyError(
                f"Node '{node_id}' not found in graph. "
                f"Sample known IDs: {known}"
            )
        return node

    def _group_edges(self, edges: list[GraphEdge]) -> list[EdgeGroup]:
        """Group a flat edge list by relationship type."""
        buckets: dict[RelationshipType, list[GraphEdge]] = defaultdict(list)
        for edge in edges:
            buckets[edge.relationship].append(edge)
        return [
            EdgeGroup(relationship=rel, edges=edge_list)
            for rel, edge_list in sorted(buckets.items(), key=lambda kv: kv[0].value)
        ]

    def _collect_neighbours(self, node_id: str) -> list[GraphNode]:
        """Return deduplicated one-hop neighbours in both edge directions."""
        seen: set[str] = set()
        neighbours: list[GraphNode] = []

        for edge in self._out_index.get(node_id, []):
            if edge.target not in seen and edge.target in self._nodes:
                seen.add(edge.target)
                neighbours.append(self._nodes[edge.target])

        for edge in self._in_index.get(node_id, []):
            if edge.source not in seen and edge.source in self._nodes:
                seen.add(edge.source)
                neighbours.append(self._nodes[edge.source])

        return sorted(neighbours, key=lambda n: (n.type.value, n.id))


# ---------------------------------------------------------------------------
# Private text-emission helper
# ---------------------------------------------------------------------------

def _emit_nodes(lines: list[str], label: str, nodes: list[GraphNode]) -> None:
    if not nodes:
        return
    node_strs = ", ".join(n.id for n in nodes)
    lines.append(f"{label}: {node_strs}")


# ---------------------------------------------------------------------------
# Future GraphRAG Integration
# ---------------------------------------------------------------------------
#
# This retrieval layer is designed as the structural foundation for GraphRAG.
# Here is the recommended integration path:
#
# 1.  Node embedding
#     ---------------
#     After graph construction, call ``build_llm_context(node_id)`` for every
#     node and embed the resulting text with an embedding model
#     (e.g. text-embedding-3-small).  Store (node_id, embedding) in a vector
#     index (Chroma, Qdrant, pgvector).
#
# 2.  Hybrid retrieval
#     -----------------
#     On a user query:
#       a. Embed the query.
#       b. Find the top-k most similar nodes via ANN search (semantic layer).
#       c. Call ``get_subgraph(seed_node_ids, max_hops=1)`` on the top-k
#          results to expand to their structural neighbourhood (graph layer).
#       d. Serialise the subgraph edges + node labels as additional context.
#
# 3.  Context construction
#     ----------------------
#     For each retrieved seed node, prepend ``build_llm_context(node_id)``
#     as a structured context block.  Append the raw subgraph edge list
#     for relational context.  Feed both to the LLM in the system prompt.
#
# 4.  Answer generation
#     ------------------
#     The LLM answers with grounding from both semantic similarity (which
#     nodes are conceptually relevant) and graph structure (how those nodes
#     relate to each other, who calls whom, what file defines what).
#
# Key classes to add:
#   GraphRAGRetriever(RepositoryRetriever, VectorIndex)
#     .retrieve(query: str, top_k: int) -> list[RetrievalResult]
#     .build_prompt_context(results: list[RetrievalResult]) -> str