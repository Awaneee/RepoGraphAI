from app.parsers.code_parser import (
    CodeParser
)

from app.graph.graph_builder import (
    GraphBuilder
)


class GraphService:

    def __init__(self):

        self.parser = CodeParser()

        self.builder = GraphBuilder()

    def generate_graph(
        self,
        repository_path: str
    ):

        parsed_repository = (
            self.parser.parse_repository(
                repository_path
            )
        )

        return self.builder.build_graph(
            parsed_repository
        )