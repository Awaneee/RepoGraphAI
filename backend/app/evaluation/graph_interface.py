"""
graph_interface.py
==================
Graph analysis utilities for extracting public stable symbols and computing
importance metrics directly from the RepositoryGraph.
"""

from __future__ import annotations
import os
import re
from typing import Optional
from app.models.pydantic_models import (
    RepositoryGraph,
    GraphNode,
    GraphEdge,
    NodeType,
    RelationshipType
)

def compute_pagerank(
    node_ids: list[str],
    edges: list[GraphEdge],
    max_iter: int = 30,
    d: float = 0.85
) -> dict[str, float]:
    """
    Compute PageRank scores deterministically using power iteration.
    Edges directed from caller/user to callee/dependency (source -> target).
    """
    N = len(node_ids)
    if N == 0:
        return {}

    # Initialize pagerank values uniformly
    pr = {nid: 1.0 / N for nid in node_ids}
    
    # Adjacency structures
    out_degree = {nid: 0 for nid in node_ids}
    incoming_links = {nid: [] for nid in node_ids}

    for edge in edges:
        src, dst = edge.source, edge.target
        if src in pr and dst in pr:
            out_degree[src] += 1
            incoming_links[dst].append(src)

    # Power iteration
    for _ in range(max_iter):
        next_pr = {}
        # Sum of pagerank for dangling nodes (out-degree == 0)
        dangling_sum = sum(pr[nid] for nid in node_ids if out_degree[nid] == 0)

        for nid in node_ids:
            rank_sum = 0.0
            for src in incoming_links[nid]:
                if out_degree[src] > 0:
                    rank_sum += pr[src] / out_degree[src]
            
            next_pr[nid] = (1.0 - d) / N + d * (rank_sum + dangling_sum / N)
        
        pr = next_pr

    return pr

def is_test_node(node: GraphNode) -> bool:
    """Check if the node is part of test code."""
    file_path = node.file_path or ""
    if not file_path:
        # Check if node id looks like test
        lower_id = node.id.lower()
        return "test" in lower_id or "conftest" in lower_id
    
    normalized_path = file_path.replace("\\", "/").lower()
    path_parts = normalized_path.split("/")
    
    # Check if 'tests' is a directory in the path, or file starts with 'test_'
    if "tests" in path_parts or "test" in path_parts:
        return True
    
    filename = os.path.basename(normalized_path)
    if filename.startswith("test_") or filename.startswith("conftest"):
        return True
        
    return False

def is_stable_public_symbol(node: GraphNode) -> bool:
    """
    Apply strict filters to identify stable, public API symbols.
    Filters out:
      - Private methods (starting with _)
      - Dunder methods (starting and ending with __)
      - Helper/Utility wrappers with generic names
      - Test code/fixtures
      - Non-symbol node types (File, Module)
    """
    # Only CLASS, FUNCTION, and METHOD nodes can be public API symbols
    if node.type not in (NodeType.CLASS, NodeType.FUNCTION, NodeType.METHOD):
        return False

    # Filter out test nodes
    if is_test_node(node):
        return False

    # Check for private or dunder methods
    label = node.label
    if label.startswith("_"):
        return False

    # For qualified method IDs (e.g. Class._private_method), check individual parts
    if "." in label:
        parts = label.split(".")
        if any(part.startswith("_") for part in parts):
            return False

    # Filter out common helper/utility/temporary keyword suffixes or names
    generic_patterns = [
        r"^helper$", r"^helpers$", r"^util$", r"^utils$", r"^wrapper$", r"^wrappers$",
        r"^temp$", r"^tmp$", r"^dummy$", r"^mock$", r"^test$", r"^tests$",
        r"^deprecated$", r"^experimental$"
    ]
    lower_label = label.lower()
    for pattern in generic_patterns:
        if re.search(pattern, lower_label):
            return False

    # Check docstring for deprecation or experimental warnings
    doc = (node.docstring or "").lower()
    if "deprecated" in doc or "experimental" in doc or "internal use only" in doc:
        return False

    return True

def analyze_graph_importance(graph: RepositoryGraph) -> dict[str, dict[str, float]]:
    """
    Calculate graph-derived importance metrics for every node in the graph.
    Returns a dict mapping node_id to a dict of computed signals:
      - degree: total connections (in + out)
      - in_degree: incoming connections
      - out_degree: outgoing connections
      - pagerank: PageRank centrality score
      - reference_count: incoming calls, inherits, instantiates, or imports
    """
    node_ids = [node.id for node in graph.nodes]
    
    # Adjacency count structures
    in_edges = {nid: 0 for nid in node_ids}
    out_edges = {nid: 0 for nid in node_ids}
    ref_count = {nid: 0 for nid in node_ids}

    # Reference types that signal structural importance
    importance_rels = {
        RelationshipType.CALLS,
        RelationshipType.INHERITS,
        RelationshipType.INSTANTIATES,
        RelationshipType.IMPORTS
    }

    for edge in graph.edges:
        src, dst = edge.source, edge.target
        if src in out_edges:
            out_edges[src] += 1
        if dst in in_edges:
            in_edges[dst] += 1
        if dst in ref_count and edge.relationship in importance_rels:
            ref_count[dst] += 1

    # Compute PageRank
    pr_scores = compute_pagerank(node_ids, graph.edges)

    metrics = {}
    for nid in node_ids:
        in_d = in_edges[nid]
        out_d = out_edges[nid]
        metrics[nid] = {
            "degree": float(in_d + out_d),
            "in_degree": float(in_d),
            "out_degree": float(out_d),
            "pagerank": pr_scores.get(nid, 0.0),
            "reference_count": float(ref_count[nid])
        }

    return metrics
