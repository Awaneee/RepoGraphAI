from app.graph.graph_builder import GraphBuilder
from app.graph.graph_visualizer import GraphVisualizer
from app.parsers.code_parser import CodeParser

parser = CodeParser()
builder = GraphBuilder()

repo_path = "repos/fastapi"  # or any repo you already have cloned
parsed = parser.parse_repository(repo_path)
master = builder.build_graph(parsed, repo_path)

arch  = builder.build_architecture_graph(master)
cls   = builder.build_class_graph(master)
call  = builder.build_call_graph(master)

viz = GraphVisualizer(output_dir=".")
viz.save_architecture_graph(arch)
viz.save_class_graph(cls)
viz.save_call_graph(call)