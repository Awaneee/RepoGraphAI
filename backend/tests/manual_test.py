from app.parsers.code_parser import CodeParser
from app.graph.graph_builder import GraphBuilder
from app.rag.context_builder import build_context_builder


QUESTIONS = [
    "How are files parsed?",
    "How does retrieval work?",
    "How is the graph generated?",
    "How does query resolution work?",
    "How are hotspots calculated?",
]


def main():

    parser = CodeParser()

    repository = parser.parse_repository(
        "app"
    )

    graph = GraphBuilder().build_graph(
        repository
    )

    builder = build_context_builder(
        graph
    )

    for question in QUESTIONS:

        print("\n" + "=" * 100)

        print("\nQUESTION:")
        print(question)

        package = builder.build(
            question=question,
            top_k=5,
            max_hops=1,
        )

        print("\nPACKAGE SCHEMA:")
        print(package.model_dump())

        print("\nLLM CONTEXT:")
        print(package.llm_context[:3000])

        print("\n" + "=" * 100)


if __name__ == "__main__":
    main()