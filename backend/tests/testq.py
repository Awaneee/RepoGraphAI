from app.parsers.code_parser import CodeParser
from app.graph.graph_builder import GraphBuilder
from app.retrievers.query_resolver import QueryResolver


QUESTIONS = [

    # Parser

    "How are files parsed?",
    "How are classes extracted?",
    "How are functions extracted?",
    "How are imports detected?",

    # Graph

    "How is the graph generated?",
    "How are graph nodes created?",
    "How are graph edges created?",
    "How is inheritance represented?",

    # Analytics

    "How are graph statistics generated?",
    "How are hotspots calculated?",
    "What are the most connected nodes?",

    # Retrieval

    "How does retrieval work?",
    "How are neighbours retrieved?",
    "How is a subgraph extracted?",
    "How is LLM context built?",

    # Query Resolution

    "How does query resolution work?",
    "How are symbols ranked?",
    "How are search results scored?",

    # Repository Services

    "How does repository cloning work?",
    "How is repository analysis performed?",

    # Visualization

    "How are graph views built?",
    "How is the architecture graph generated?",
    "How is the call graph generated?",
    "How is the class graph generated?",

    # General Architecture

    "What builds the knowledge graph?",
    "How does the parser connect to the graph?",
    "How does the retrieval layer use the graph?",
]


def main():

    print("\nBuilding graph...\n")

    parser = CodeParser()

    repository = parser.parse_repository(
        "app"
    )

    graph = GraphBuilder().build_graph(
        repository
    )

    resolver = QueryResolver(
        graph
    )

    total_questions = 0
    total_with_results = 0

    for query in QUESTIONS:

        total_questions += 1

        print("\n" + "=" * 100)
        print("QUESTION:")
        print(query)

        result = resolver.resolve_query(
            query
        )

        print("\nKEYWORDS:")
        print(result.keywords)

        print("\nMATCH COUNT:")
        print(len(result.matches))

        if not result.matches:

            print("\nNO MATCHES FOUND")
            continue

        total_with_results += 1

        print("\nTOP 5 MATCHES:\n")

        for rank, match in enumerate(
            result.matches[:5],
            start=1,
        ):

            print(
                f"{rank}. {match.node_id}"
            )

            print(
                f"   type   : {match.node_type.value}"
            )

            print(
                f"   score  : {match.score:.2f}"
            )

            print(
                f"   reason : {match.reason}"
            )

            print()

    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)

    print(
        f"Questions: {total_questions}"
    )

    print(
        f"Returned Matches: {total_with_results}"
    )

    print(
        f"Coverage: "
        f"{(100 * total_with_results / total_questions):.1f}%"
    )


if __name__ == "__main__":
    main()