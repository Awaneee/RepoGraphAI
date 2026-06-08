"""
GraphVisualizer — render filtered RepositoryGraph views as PNG files.

Three outputs
-------------
  architecture_graph.png  — File / Module / Class nodes, IMPORTS + CONTAINS
                             edges.  Hierarchical layout (Graphviz dot via
                             PyGraphviz when available; Kamada-Kawai fallback).

  class_graph.png         — Class-only nodes, INHERITS + INSTANTIATES +
                             DECORATES edges.  Spring layout biased toward
                             tree structure to surface the inheritance
                             hierarchy clearly.

  call_graph.png          — Function + Method nodes, CALLS edges.
                             Force-directed layout (spring_layout) which
                             naturally clusters tightly-coupled callers.

Layout recommendations
----------------------
Architecture graph   → Graphviz "dot" (top-down DAG) is ideal because the
                       file→module→class containment relationship is
                       inherently hierarchical.  Kamada-Kawai is used as a
                       fallback because it respects edge length and avoids
                       the crossing-heavy look of random spring layouts.

Class graph          → Graphviz "dot" or "twopi" (radial) surfaces the
                       inheritance tree.  Spring layout with a high k value
                       separates clusters well when Graphviz is unavailable.

Call graph           → spring_layout (Fruchterman–Reingold) is the standard
                       choice for call graphs: high fan-in nodes gravitate
                       to the centre, leaf callees to the periphery.  This
                       makes entry points and hot-path hubs immediately
                       visible.

Colour coding (consistent across all three graphs)
---------------------------------------------------
  FILE     : #4A90D9  (steel blue)
  MODULE   : #7ED321  (grass green)
  CLASS    : #F5A623  (amber)
  FUNCTION : #9B59B6  (purple)
  METHOD   : #E74C3C  (red)
  UNKNOWN  : #95A5A6  (grey, for decorator-source nodes not in the graph)

Edge colour by relationship
---------------------------
  IMPORTS     : #7ED321  (green — same family as MODULE nodes)
  CONTAINS    : #4A90D9  (blue — same family as FILE nodes)
  INHERITS    : #E67E22  (dark orange — inheritance hierarchy)
  INSTANTIATES: #9B59B6  (purple — creation relationship)
  DECORATES   : #1ABC9C  (teal — decoration / AOP concern)
  CALLS       : #E74C3C  (red — execution flow)
  OVERRIDES   : #F39C12  (gold)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import matplotlib
matplotlib.use("Agg")                           # headless — no display needed
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx

from app.models.pydantic_models import (
    NodeType,
    RelationshipType,
    RepositoryGraph,
)

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Colour maps
# ---------------------------------------------------------------------------

_NODE_COLOURS: dict[NodeType, str] = {
    NodeType.FILE:     "#4A90D9",
    NodeType.MODULE:   "#7ED321",
    NodeType.CLASS:    "#F5A623",
    NodeType.FUNCTION: "#9B59B6",
    NodeType.METHOD:   "#E74C3C",
}

_EDGE_COLOURS: dict[RelationshipType, str] = {
    RelationshipType.IMPORTS:      "#7ED321",
    RelationshipType.CONTAINS:     "#4A90D9",
    RelationshipType.INHERITS:     "#E67E22",
    RelationshipType.INSTANTIATES: "#9B59B6",
    RelationshipType.DECORATES:    "#1ABC9C",
    RelationshipType.CALLS:        "#E74C3C",
    RelationshipType.OVERRIDES:    "#F39C12",
}

_DEFAULT_NODE_COLOUR = "#95A5A6"
_DEFAULT_EDGE_COLOUR = "#BDC3C7"


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def _best_layout(
    G: nx.DiGraph,
    preferred: str,
    seed: int = 42,
) -> dict:
    """
    Attempt the preferred layout; fall back gracefully.

    preferred options: "dot", "kamada_kawai", "spring", "twopi"
    """

    if preferred in ("dot", "twopi", "neato"):
        try:
            return nx.nx_agraph.graphviz_layout(G, prog=preferred)
        except Exception:
            pass  # PyGraphviz / Graphviz not installed — fall through

    if preferred == "kamada_kawai":
        try:
            return nx.kamada_kawai_layout(G)
        except Exception:
            pass

    # Final fallback: Fruchterman–Reingold spring layout
    return nx.spring_layout(G, seed=seed, k=2.5 / max(len(G) ** 0.5, 1))


# ---------------------------------------------------------------------------
# Core rendering routine
# ---------------------------------------------------------------------------

def _render_graph(
    view: RepositoryGraph,
    output_path: str,
    title: str,
    preferred_layout: str,
    fig_size: tuple[int, int] = (18, 12),
    node_size_base: int = 600,
    font_size: int = 7,
) -> None:
    """
    Render a RepositoryGraph view to a PNG file.

    Parameters
    ----------
    view:
        A filtered RepositoryGraph (output of one of the build_*_graph methods).
    output_path:
        Destination PNG file path.
    title:
        Figure title.
    preferred_layout:
        Layout algorithm hint — see _best_layout().
    fig_size:
        Matplotlib figure size in inches.
    node_size_base:
        Base node size; actual size scales with degree.
    font_size:
        Label font size in points.
    """

    if not view.nodes:
        print(f"[GraphVisualizer] Skipping '{title}' — no nodes to render.")
        return

    G = nx.DiGraph()

    # Build a fast lookup: node_id → NodeType
    node_type_map: dict[str, NodeType] = {}
    for node in view.nodes:
        G.add_node(node.id, label=node.label, node_type=node.type)
        node_type_map[node.id] = node.type

    # Collect edge colours
    edge_colour_list: list[str] = []
    edge_alpha_list: list[float] = []

    for edge in view.edges:
        G.add_edge(edge.source, edge.target, relationship=edge.relationship)
        colour = _EDGE_COLOURS.get(edge.relationship, _DEFAULT_EDGE_COLOUR)
        edge_colour_list.append(colour)
        edge_alpha_list.append(0.6)

    # Compute layout
    pos = _best_layout(G, preferred=preferred_layout)

    # Node colours and sizes
    degrees = dict(G.degree())
    node_colours: list[str] = []
    node_sizes: list[int] = []

    for node_id in G.nodes():
        ntype = node_type_map.get(node_id)
        colour = _NODE_COLOURS.get(ntype, _DEFAULT_NODE_COLOUR) if ntype else _DEFAULT_NODE_COLOUR
        node_colours.append(colour)
        deg = degrees.get(node_id, 1)
        node_sizes.append(node_size_base + deg * 60)

    # Labels — use the short label stored in the node, not the full ID
    labels: dict[str, str] = {
        node.id: node.label
        for node in view.nodes
    }
    # Also add decorator-source nodes that have no GraphNode entry
    for node_id in G.nodes():
        if node_id not in labels:
            labels[node_id] = node_id.split(".")[-1]

    # ---------------------------------------------------------------
    # Draw
    # ---------------------------------------------------------------

    fig, ax = plt.subplots(figsize=fig_size)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=16)
    ax.axis("off")

    # Draw edges first (underneath nodes)
    nx.draw_networkx_edges(
        G,
        pos,
        ax=ax,
        edge_color=edge_colour_list,
        alpha=0.65,
        arrows=True,
        arrowsize=12,
        arrowstyle="-|>",
        connectionstyle="arc3,rad=0.08",
        width=1.2,
    )

    # Draw nodes
    nx.draw_networkx_nodes(
        G,
        pos,
        ax=ax,
        node_color=node_colours,
        node_size=node_sizes,
        alpha=0.92,
    )

    # Draw labels
    nx.draw_networkx_labels(
        G,
        pos,
        labels=labels,
        ax=ax,
        font_size=font_size,
        font_color="#1A1A2E",
        font_weight="bold",
    )

    # ---------------------------------------------------------------
    # Legend — node types present in this view
    # ---------------------------------------------------------------
    present_node_types: set[NodeType] = {
        ntype for ntype in node_type_map.values()
    }
    present_edge_types: set[RelationshipType] = {
        edge.relationship for edge in view.edges
    }

    legend_handles: list[mpatches.Patch] = []

    for ntype in sorted(present_node_types, key=lambda t: t.value):
        colour = _NODE_COLOURS.get(ntype, _DEFAULT_NODE_COLOUR)
        legend_handles.append(
            mpatches.Patch(color=colour, label=f"[N] {ntype.value}")
        )

    for rel in sorted(present_edge_types, key=lambda r: r.value):
        colour = _EDGE_COLOURS.get(rel, _DEFAULT_EDGE_COLOUR)
        legend_handles.append(
            mpatches.Patch(color=colour, label=f"[E] {rel.value.upper()}")
        )

    if legend_handles:
        ax.legend(
            handles=legend_handles,
            loc="lower left",
            fontsize=7,
            framealpha=0.85,
            ncol=2,
        )

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    node_count = len(view.nodes)
    edge_count = len(view.edges)
    print(
        f"[GraphVisualizer] Saved '{title}' → {output_path} "
        f"({node_count} nodes, {edge_count} edges)"
    )


# ---------------------------------------------------------------------------
# GraphVisualizer — public API
# ---------------------------------------------------------------------------

class GraphVisualizer:
    """
    Renders the three standard graph views as PNG files.

    Usage
    -----
    ::

        from app.graph.graph_builder import GraphBuilder
        from app.graph.graph_visualizer import GraphVisualizer

        builder    = GraphBuilder()
        master     = builder.build_graph(parsed_repo, repo_path)

        arch_view  = builder.build_architecture_graph(master)
        class_view = builder.build_class_graph(master)
        call_view  = builder.build_call_graph(master)

        viz = GraphVisualizer(output_dir="outputs/graphs")
        viz.save_architecture_graph(arch_view)
        viz.save_class_graph(class_view)
        viz.save_call_graph(call_view)

    Parameters
    ----------
    output_dir:
        Directory where PNG files are written.  Created if absent.
    """

    def __init__(self, output_dir: str = ".") -> None:
        self.output_dir = output_dir

    def _path(self, filename: str) -> str:
        return os.path.join(self.output_dir, filename)

    # ------------------------------------------------------------------

    def save_architecture_graph(
        self,
        view: RepositoryGraph,
        filename: str = "architecture_graph.png",
        fig_size: tuple[int, int] = (20, 14),
    ) -> str:
        """
        Render the architecture view to PNG.

        Layout: Graphviz "dot" (top-down hierarchy) → Kamada-Kawai fallback.

        "dot" is preferred because the File → Module / File → Class
        CONTAINS and IMPORTS relationships form a partial DAG.  A
        top-down hierarchical layout makes the layering (file layer →
        module layer → class layer) immediately legible.

        Kamada-Kawai is the best non-Graphviz fallback: it minimises edge
        crossings by optimising pairwise graph-theoretic distances, giving
        a cleaner result than random spring layouts for moderately-sized
        architectural graphs.
        """
        out = self._path(filename)
        _render_graph(
            view=view,
            output_path=out,
            title="Architecture Graph — File / Module / Class",
            preferred_layout="dot",
            fig_size=fig_size,
            node_size_base=700,
            font_size=8,
        )
        return out

    def save_class_graph(
        self,
        view: RepositoryGraph,
        filename: str = "class_graph.png",
        fig_size: tuple[int, int] = (16, 12),
    ) -> str:
        """
        Render the class view to PNG.

        Layout: Graphviz "dot" → spring fallback.

        Inheritance hierarchies are trees (or forests), and "dot" renders
        trees beautifully — parent classes at the top, leaf subclasses at
        the bottom.  For repositories with many cross-class INSTANTIATES
        edges the spring fallback produces reasonable clustering.
        """
        out = self._path(filename)
        _render_graph(
            view=view,
            output_path=out,
            title="Class Graph — Inheritance / Instantiation / Decoration",
            preferred_layout="dot",
            fig_size=fig_size,
            node_size_base=800,
            font_size=9,
        )
        return out

    def save_call_graph(
        self,
        view: RepositoryGraph,
        filename: str = "call_graph.png",
        fig_size: tuple[int, int] = (20, 14),
    ) -> str:
        """
        Render the call view to PNG.

        Layout: spring_layout (Fruchterman–Reingold force-directed).

        Call graphs are rarely DAGs — they contain cycles from mutual
        recursion and helper patterns.  Force-directed layouts handle
        cycles gracefully: frequently-called (high fan-in) nodes
        accumulate many spring forces and gravitate toward the centre,
        while leaf callees are pushed to the periphery.  This makes
        hot-path hubs visually salient without any additional annotation.
        """
        out = self._path(filename)
        _render_graph(
            view=view,
            output_path=out,
            title="Call Graph — Function / Method CALLS",
            preferred_layout="spring",
            fig_size=fig_size,
            node_size_base=600,
            font_size=8,
        )
        return out