from app.parsers.code_parser import (
    CodeParser
)

from app.graph.graph_builder import (
    GraphBuilder
)

import networkx as nx
import matplotlib.pyplot as plt


parser = CodeParser()

repository = parser.parse_repository(
    "app"
)

builder = GraphBuilder()

graph = builder.build_architecture_graph(
    repository
)

print(
    f"Nodes: {len(graph.nodes)}"
)

print(
    f"Edges: {len(graph.edges)}"
)

G = nx.DiGraph()

for node in graph.nodes:

    G.add_node(node)

for edge in graph.edges:

    G.add_edge(
        edge.source,
        edge.target,
        relationship=edge.relationship
    )

plt.figure(
    figsize=(16, 12)
)

pos = nx.spring_layout(
    G,
    seed=42,
    k=1.5
)

nx.draw(
    G,
    pos,
    with_labels=True,
    node_size=3000,
    font_size=8
)

edge_labels = {
    (
        edge.source,
        edge.target
    ): edge.relationship
    for edge in graph.edges
}

nx.draw_networkx_edge_labels(
    G,
    pos,
    edge_labels=edge_labels,
    font_size=7
)

plt.savefig(
    "architecture_graph.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()