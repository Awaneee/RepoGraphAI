
import os
import sys
from collections import defaultdict

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.app.parsers.code_parser import CodeParser
from backend.app.graph.graph_builder import GraphBuilder
from backend.app.rag.context_builder import build_context_builder

# --- Configuration --- #
# Path to the repository to benchmark against (assuming current project for now)
REPOSITORY_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app'))

class RetrievalBenchmark:
    def __init__(self, repository_path: str):
        self.repository_path = repository_path
        self.context_builder = None

    def setup_pipeline(self):
        print(f"Parsing repository: {self.repository_path}")
        parser = CodeParser()
        parsed_repository = parser.parse_repository(self.repository_path)
        print("Building knowledge graph...")
        graph = GraphBuilder().build_graph(parsed_repository)
        self.context_builder = build_context_builder(graph)
        print("Pipeline setup complete.")

    def define_benchmark_questions(self):
        # Define benchmark questions and their expected symbols
        # Format: {"category": "", "question": "", "expected_symbol": ""}
        return [
            {
                "category": "Parsing",
                "question": "How are files parsed?",
                "expected_symbol": "CodeParser.parse_file"
            },
            {
                "category": "Parsing",
                "question": "How are imports extracted?",
                "expected_symbol": "CodeParser._extract_imports"
            },
            {
                "category": "Parsing",
                "question": "How are classes extracted?",
                "expected_symbol": "CodeParser._extract_class"
            },
            {
                "category": "Graph Construction",
                "question": "How is the graph generated?",
                "expected_symbol": "GraphBuilder.build_graph"
            },
            {
                "category": "Graph Construction",
                "question": "How are graph nodes created?",
                "expected_symbol": "GraphBuilder._add_node"
            },
            {
                "category": "Graph Construction",
                "question": "How are graph edges created?",
                "expected_symbol": "GraphBuilder._add_edge"
            },
            {
                "category": "Graph Construction",
                "question": "How is inheritance represented?",
                "expected_symbol": "GraphBuilder.build_graph"
            },
            {
                "category": "Analytics",
                "question": "How are hotspots calculated?",
                "expected_symbol": "GraphBuilder.generate_statistics"
            },
            {
                "category": "Analytics",
                "question": "How are graph statistics generated?",
                "expected_symbol": "GraphBuilder.generate_statistics"
            },
            {
                "category": "Retrieval",
                "question": "How does retrieval work?",
                "expected_symbol": "RepositoryRetriever.get_node_context"
            },
            {
                "category": "Retrieval",
                "question": "How are neighbours retrieved?",
                "expected_symbol": "RepositoryRetriever._collect_neighbours"
            },
            {
                "category": "Retrieval",
                "question": "How is a subgraph extracted?",
                "expected_symbol": "RepositoryRetriever.get_subgraph"
            },
            {
                "category": "Query Resolution",
                "question": "How does query resolution work?",
                "expected_symbol": "QueryResolver.resolve_query"
            },
            {
                "category": "Query Resolution",
                "question": "How are symbols ranked?",
                "expected_symbol": "QueryResolver.rank_candidates"
            },
            {
                "category": "Context Building",
                "question": "How is LLM context built?",
                "expected_symbol": "ContextBuilder.build"
            },
        ]

    def evaluate_retrieval(self):
        benchmark_cases = self.define_benchmark_questions()
        results = []

        for case in benchmark_cases:
            question = case["question"]
            expected_symbol = case["expected_symbol"]

            # Run ContextBuilder.build() to get resolved nodes
            package = self.context_builder.build(question, top_k=5, max_hops=1)
            resolved_nodes = package.resolved_nodes

            # Extract actual symbol names from resolved_nodes
            returned_symbols = [node.node_id for node in resolved_nodes]

            top_1_hit = False
            top_3_hit = False
            top_5_hit = False

            if returned_symbols:
                if returned_symbols[0] == expected_symbol:
                    top_1_hit = True
                if expected_symbol in returned_symbols[:3]:
                    top_3_hit = True
                if expected_symbol in returned_symbols[:5]:
                    top_5_hit = True

            results.append({
                "category": case["category"],
                "question": question,
                "expected_symbol": expected_symbol,
                "returned_top_5": returned_symbols[:5],
                "top_1_hit": top_1_hit,
                "top_3_hit": top_3_hit,
                "top_5_hit": top_5_hit,
            })
        return results

    def print_report(self, results):
        print("\n--- Retrieval Benchmark Report ---")
        print("{:<20} {:<40} {:<30} {:<40} {:<10}".format("Category", "Question", "Expected Symbol", "Returned Top 5", "PASS/FAIL"))
        print("-" * 155)

        total_cases = len(results)
        top_1_accurate = 0
        top_3_accurate = 0
        top_5_accurate = 0

        for r in results:
            pass_fail = "PASS" if r["top_1_hit"] or r["top_3_hit"] or r["top_5_hit"] else "FAIL"
            print("{:<20} {:<40} {:<30} {:<40} {:<10}".format(
                r["category"],
                r["question"],
                r["expected_symbol"],
                str(r["returned_top_5"]),
                pass_fail
            ))
            if r["top_1_hit"]: top_1_accurate += 1
            if r["top_3_hit"]: top_3_accurate += 1
            if r["top_5_hit"]: top_5_accurate += 1

        print("\n--- Summary ---")
        print(f"Total Questions: {total_cases}")
        print(f"Top-1 Accuracy: { (top_1_accurate / total_cases * 100):.2f}% ({top_1_accurate}/{total_cases})")
        print(f"Top-3 Accuracy: { (top_3_accurate / total_cases * 100):.2f}% ({top_3_accurate}/{total_cases})")
        print(f"Top-5 Accuracy: { (top_5_accurate / total_cases * 100):.2f}% ({top_5_accurate}/{total_cases})")

if __name__ == "__main__":
    benchmark = RetrievalBenchmark(REPOSITORY_PATH)
    benchmark.setup_pipeline()
    retrieval_results = benchmark.evaluate_retrieval()
    benchmark.print_report(retrieval_results)
