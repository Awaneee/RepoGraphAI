from pprint import pprint

from app.parsers.code_parser import (
    CodeParser
)

from app.graph.graph_builder import (
    GraphBuilder
)

parser = CodeParser()

repository = (
    parser.parse_repository(
        "app"
    )
)

builder = GraphBuilder()

graph = builder.build_graph(
    repository
)

pprint(
    graph.model_dump()
)