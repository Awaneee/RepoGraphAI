"""
examples/graphrag_example_usage.py
====================================
End-to-end example: parse a repository, build its knowledge graph, and ask
it questions through GraphRAG v1.

This mirrors the existing setup pattern from ``retrieval_benchmark.py`` —
same CodeParser -> GraphBuilder -> build_context_builder pipeline — with one
new final step: wrapping the ContextBuilder in a GraphRAGEngine to get
actual natural-language answers instead of raw retrieval results.

Run with a real LLM
--------------------
::

    export ANTHROPIC_API_KEY=sk-...
    python examples/graphrag_example_usage.py /path/to/some/repo --model <current-model-id>

Run without any API key (offline diagnostic mode)
----------------------------------------------------
::

    python examples/graphrag_example_usage.py /path/to/some/repo --echo
"""

from __future__ import annotations

import argparse
import os
import sys

# Adjust this if your project layout differs — mirrors retrieval_benchmark.py's
# own sys.path handling so this script can be dropped next to it.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..","..")))

from app.parsers.code_parser import CodeParser
from app.graph.graph_builder import GraphBuilder
from app.rag.graphrag_engine import (
    AnthropicLLMProvider,
    EchoLLMProvider,
    GraphRAGPromptBuilder,
    build_graphrag_engine,
)


def build_engine(repository_path: str, *, use_echo: bool, model: str | None):
    print(f"Parsing repository: {repository_path}")
    parsed_repository = CodeParser().parse_repository(repository_path)

    print("Building knowledge graph...")
    graph = GraphBuilder().build_graph(parsed_repository)

    if use_echo:
        print("Using EchoLLMProvider (no real LLM call, diagnostic mode).")
        llm_provider = EchoLLMProvider()
    else:
        if not model:
            raise SystemExit(
                "Pass --model <model-id> to use AnthropicLLMProvider, or pass "
                "--echo to run without a real LLM."
            )
        print(f"Using AnthropicLLMProvider (model={model}).")
        llm_provider = AnthropicLLMProvider(model=model)

    return build_graphrag_engine(
        graph,
        llm_provider,
        prompt_builder=GraphRAGPromptBuilder(),
        top_k=5,
        max_hops=1,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask GraphRAG v1 questions about a Python repository.")
    parser.add_argument("repository_path", help="Path to the repository to analyze.")
    parser.add_argument("--model", help="Anthropic model id to use (see https://docs.claude.com).")
    parser.add_argument("--echo", action="store_true", help="Use EchoLLMProvider instead of a real LLM.")
    parser.add_argument(
        "--question",
        action="append",
        dest="questions",
        help="A question to ask. Pass multiple times for multiple questions.",
    )
    args = parser.parse_args()

    questions = args.questions or [
        "How does retrieval work?",
        "How is the knowledge graph generated?",
        "How are graph statistics computed?",
    ]

    engine = build_engine(args.repository_path, use_echo=args.echo, model=args.model)

    for question in questions:
        print("\n" + "=" * 70)
        print(f"Q: {question}")
        print("=" * 70)

        response = engine.answer(question)

        print(f"\nA: {response.answer}\n")
        print("Source nodes:")
        for node in response.source_nodes:
            location = f"{node.file_path}:{node.line_number}" if node.file_path else "—"
            print(f"  - [{node.node_type}] {node.node_id}  (score={node.score:.2f}, {location})")

        meta = response.retrieval_metadata
        print(
            f"\nRetrieval metadata: intent={meta.intent_categories}, "
            f"keywords={meta.keywords}, "
            f"resolved={meta.resolved_node_count}, "
            f"subgraph={meta.subgraph_node_count} nodes / {meta.subgraph_edge_count} edges, "
            f"top_k={meta.top_k}, max_hops={meta.max_hops}"
        )


if __name__ == "__main__":
    main()
