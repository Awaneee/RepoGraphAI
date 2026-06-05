from collections import Counter

from app.models.pydantic_models import (
    ParsedRepository,
    RepositoryGraph,
    GraphEdge,
    GraphStatistics,
)


ARCHITECTURE_BLACKLIST = {
    "Exception",
    "BaseModel",
    "FastAPI",
    "APIRouter",
    "Depends",
    "Query",
    "Body",
    "Header",
    "Cookie",
    "Path",
}


class GraphBuilder:

    def build_graph(
        self,
        repository: ParsedRepository,
    ) -> RepositoryGraph:

        nodes = set()
        edges = set()

        repository_symbols = set()

        # --------------------------------
        # PASS 1
        # Collect repository symbols
        # --------------------------------

        for parsed_file in repository.files:

            for function in parsed_file.functions:
                repository_symbols.add(
                    function.name
                )

            for cls in parsed_file.classes:

                if (
                    cls.name.endswith("Model")
                    or cls.name.endswith("Schema")
                ):
                    continue

                repository_symbols.add(
                    cls.name
                )

                for method in cls.methods:
                    repository_symbols.add(
                        method.name
                    )

        # --------------------------------
        # PASS 2
        # Build graph
        # --------------------------------

        for parsed_file in repository.files:

            # -----------------------------
            # Top-level functions
            # -----------------------------

            for function in parsed_file.functions:

                nodes.add(
                    function.name
                )

                for call in function.calls:

                    if (
                        call in repository_symbols
                        and call not in ARCHITECTURE_BLACKLIST
                    ):

                        nodes.add(call)

                        edges.add(
                            (
                                function.name,
                                call,
                                "calls",
                            )
                        )

            # -----------------------------
            # Classes + methods
            # -----------------------------

            for cls in parsed_file.classes:

                if (
                    cls.name.endswith("Model")
                    or cls.name.endswith("Schema")
                ):
                    continue

                nodes.add(
                    cls.name
                )

                # -----------------------------
                # Inheritance relationships
                # -----------------------------

                for parent in cls.inherits_from:

                    if (
                        parent
                        in ARCHITECTURE_BLACKLIST
                    ):
                        continue

                    nodes.add(parent)

                    edges.add(
                        (
                            cls.name,
                            parent,
                            "inherits",
                        )
                    )

                # -----------------------------
                # Methods
                # -----------------------------

                for method in cls.methods:

                    nodes.add(
                        method.name
                    )

                    # Class contains method

                    edges.add(
                        (
                            cls.name,
                            method.name,
                            "contains",
                        )
                    )

                    # Method calls

                    for call in method.calls:

                        if (
                            call in repository_symbols
                            and call not in ARCHITECTURE_BLACKLIST
                        ):

                            nodes.add(call)

                            edges.add(
                                (
                                    method.name,
                                    call,
                                    "calls",
                                )
                            )

            # -----------------------------
            # Import relationships
            # -----------------------------

            for imported_module in parsed_file.imports:

                nodes.add(
                    parsed_file.file_path
                )

                nodes.add(
                    imported_module
                )

                edges.add(
                    (
                        parsed_file.file_path,
                        imported_module,
                        "imports",
                    )
                )

        return RepositoryGraph(
            nodes=sorted(nodes),
            edges=[
                GraphEdge(
                    source=source,
                    target=target,
                    relationship=relationship,
                )
                for source, target, relationship
                in sorted(edges)
            ],
        )

    def build_import_graph(
        self,
        repository: ParsedRepository,
    ):

        edges = []

        for parsed_file in repository.files:

            for imported_module in parsed_file.imports:

                edges.append(
                    {
                        "source_file":
                        parsed_file.file_path,

                        "imported_module":
                        imported_module,
                    }
                )

        return edges

    def generate_statistics(
        self,
        graph: RepositoryGraph,
    ) -> GraphStatistics:

        relationship_counter = Counter()

        node_counter = Counter()

        for edge in graph.edges:

            relationship_counter[
                edge.relationship
            ] += 1

            node_counter[
                edge.source
            ] += 1

            node_counter[
                edge.target
            ] += 1

        most_connected = [
            node
            for node, _
            in node_counter.most_common(10)
        ]

        return GraphStatistics(
            total_nodes=len(
                graph.nodes
            ),

            total_edges=len(
                graph.edges
            ),

            contains_edges=
            relationship_counter[
                "contains"
            ],

            calls_edges=
            relationship_counter[
                "calls"
            ],

            imports_edges=
            relationship_counter[
                "imports"
            ],

            inherits_edges=
            relationship_counter[
                "inherits"
            ],

            most_connected_nodes=
            most_connected,
        )