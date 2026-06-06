# test_real_repo_stats.py

from pprint import pprint

from app.parsers.code_parser import CodeParser
from app.graph.graph_builder import GraphBuilder


parser = CodeParser()

# Parse RepoGraphAI source code
repository = parser.parse_repository(
    "app"
)

print(
    f"\nParsed {repository.total_python_files} Python files\n"
)

builder = GraphBuilder()

graph = builder.build_graph(
    repository
)

stats = builder.generate_statistics(
    graph
)

print("\n===== GRAPH STATISTICS =====\n")

pprint(
    stats.model_dump()
)

print("\n===== SUMMARY =====\n")

print(
    f"Nodes: {stats.total_nodes}"
)

print(
    f"Edges: {stats.total_edges}"
)

print(
    f"Architectural Hotspots: {len(stats.architectural_hotspots)}"
)

print(
    f"Top Files: {len(stats.top_files_by_degree)}"
)

print(
    f"Top Classes: {len(stats.top_classes_by_degree)}"
)

print(
    f"Top Functions: {len(stats.top_functions_by_degree)}"
)

print(
    f"Top Methods: {len(stats.top_methods_by_degree)}"
)