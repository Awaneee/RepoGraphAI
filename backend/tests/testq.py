from app.parsers.code_parser import CodeParser
from app.graph.graph_builder import GraphBuilder
from app.retrievers.query_resolver import QueryResolver


print("\nParsing repository...\n")

parser = CodeParser()

repository = parser.parse_repository(
    "app"
)

graph = GraphBuilder().build_graph(
    repository
)

resolver = QueryResolver(
    graph=graph
)

TEST_QUERIES = [

    # Parser

    "How are files parsed?",

    # Graph

    "How is the graph generated?",

    # Retrieval

    "How does retrieval work?",

    # Repository analysis

    "How does repository cloning work?",

    # Analytics

    "How are hotspots calculated?",

    # Architecture

    "What builds the knowledge graph?",

    # Statistics

    "Where are graph statistics generated?",

    # Visualization

    "How are graph views created?",
]

for query in TEST_QUERIES:

    print("\n" + "=" * 100)
    print("QUESTION:")
    print(query)

    result = resolver.resolve_query(query)

    print("\nKEYWORDS:")
    print(result.keywords)

    print("\nTOP MATCHES:\n")

    if not result.matches:
        print("No matches found.")
        continue

    for rank, match in enumerate(
        result.matches[:10],
        start=1,
    ):

        print(
            f"{rank:2d}. "
            f"{match.node_id}"
        )

        print(
            f"    Type   : {match.node_type.value}"
        )

        print(
            f"    Score  : {match.score}"
        )

        print(
            f"    Reason : {match.reason}"
        )

        print()

    print(
        "TOP NODE IDS:"
    )

    print(
        result.top_node_ids(5)
    )

print("\n" + "=" * 100)
print("DONE")