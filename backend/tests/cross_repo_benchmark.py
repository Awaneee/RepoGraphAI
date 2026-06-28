# tests/cross_repo_benchmark.py
"""
Robust cross-repository benchmark for RepoGraphAI's GraphRAG pipeline.

This script reuses the exact pipeline demonstrated in
``app/examples/graphrag_example_usage.py`` end to end:

    CodeParser.parse_repository()
        -> GraphBuilder.build_graph()
        -> build_context_builder()  (app.rag.context_builder)
        -> GraphRAGEngine(...)      (app.rag.graphrag_engine)
        -> engine.answer(question)

No application code is modified or re-implemented. The only thing this file
adds on top of the existing pipeline is *instrumentation*: timing, structured
result records, exception capture (with full tracebacks), and a final
aggregate summary.

Timing methodology
-------------------
``GraphRAGEngine.answer()`` does not expose separate retrieval/generation
timings — it is a single call that internally builds a ``ContextPackage``
(retrieval) and then calls the configured ``LLMProvider`` (generation).
Rather than reach into ``GraphRAGEngine``'s private attributes, this script:

  1. Calls the SAME ``ContextBuilder`` instance's public ``build(question)``
     method directly (this is exactly the call ``engine.answer()`` makes
     internally) and times it -> ``retrieval_time_seconds``.
  2. Calls ``engine.answer(question)`` (the unmodified, real pipeline call
     that produces the actual answer) and times the whole thing.
  3. Derives ``generation_time_seconds`` as
     ``total_time - retrieval_time_seconds`` (clamped at 0). Because graph
     retrieval is deterministic, in-memory, and side-effect free, the
     redundant retrieval pass inside ``engine.answer()`` costs the same as
     the one measured in step 1, so the subtraction isolates the LLM call.

This keeps the benchmark a pure *consumer* of the public API
(``ContextBuilder.build``, ``GraphRAGEngine.answer``) with zero reliance on
private internals and zero duplication of application logic.

Usage
-----
    python tests/cross_repo_benchmark.py
    python tests/cross_repo_benchmark.py --gemini
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import json
import logging
import subprocess
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional

from app.cache.repository_cache import RepositoryCache
from app.parsers.code_parser import CodeParser
from app.graph.graph_builder import GraphBuilder
from app.rag.context_builder import build_context_builder
from app.rag.graphrag_engine import (
    EchoLLMProvider,
    GeminiLLMProvider,
    GraphRAGEngine,
    GraphRAGPromptBuilder,
)

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------

logger = logging.getLogger("cross_repo_benchmark")


def _configure_logging() -> None:
    """
    Configure logging once. Uses a timestamped, leveled format so failures
    are easy to spot in long benchmark runs, and ensures uncaught exceptions
    inside our own try/except blocks are logged with their full traceback
    via logger.exception(...).
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------

REPOS_DIR = Path("repos")
REPORT_PATH = Path("tests/cross_repo_report.md")
JSON_REPORT_PATH = Path("tests/cross_repo_report.json")

REPOSITORIES = {
    "FastAPI": "https://github.com/fastapi/fastapi.git",
    "Typer": "https://github.com/fastapi/typer.git",
    "Requests": "https://github.com/psf/requests.git",
}

QUESTIONS = {
    "FastAPI": [
        "How are routes registered?",
        "How does dependency injection work?",
        "How are requests handled?",
        "How are responses generated?",
        "How are middleware components registered?",
    ],
    "Typer": [
        "How are CLI commands registered?",
        "How are command arguments parsed?",
        "How are options defined?",
        "How is help text generated?",
        "How are callbacks executed?",
    ],
    "Requests": [
        "How are HTTP requests executed?",
        "How are sessions managed?",
        "How are adapters used?",
        "How are redirects handled?",
        "How are responses processed?",
    ],
}


# ------------------------------------------------------------------
# Result data models
# ------------------------------------------------------------------

@dataclass
class QuestionResult:
    """Everything recorded for a single benchmark question."""

    repository: str
    question: str
    success: bool = False

    error: Optional[str] = None
    traceback: Optional[str] = None

    retrieval_time_seconds: Optional[float] = None
    generation_time_seconds: Optional[float] = None
    total_time_seconds: Optional[float] = None

    graph_nodes: Optional[int] = None
    graph_edges: Optional[int] = None
    resolved_node_count: Optional[int] = None
    subgraph_node_count: Optional[int] = None
    subgraph_edge_count: Optional[int] = None

    answer: Optional[str] = None


@dataclass
class RepositoryResult:
    """Everything recorded for one repository's benchmark run."""

    name: str

    graph_nodes: Optional[int] = None
    graph_edges: Optional[int] = None
    total_python_files: Optional[int] = None

    setup_error: Optional[str] = None
    setup_traceback: Optional[str] = None

    questions: list[QuestionResult] = field(default_factory=list)


# ------------------------------------------------------------------
# Repo Management
# ------------------------------------------------------------------

def clone_repo(name: str, url: str) -> Path:
    repo_path = REPOS_DIR / name.lower()

    if repo_path.exists():
        logger.info("[SKIP] %s already cloned", name)
        return repo_path

    logger.info("[CLONE] %s", name)

    subprocess.run(
        ["git", "clone", url, str(repo_path)],
        check=True,
    )

    return repo_path


# ------------------------------------------------------------------
# Engine Builder
#
# Mirrors app/examples/graphrag_example_usage.py exactly:
#   CodeParser -> GraphBuilder -> build_context_builder -> GraphRAGEngine
#
# We construct the ContextBuilder ourselves (instead of going through the
# build_graphrag_engine() convenience factory) purely so we can keep a
# reference to it for retrieval-only timing in ask_question(). The
# parameters passed (top_k=5, max_hops=1) are identical to what
# build_graphrag_engine() would use internally, so the resulting engine
# behaves identically.
# ------------------------------------------------------------------

@dataclass
class _CachedRepoStats:
    """
    Minimal stand-in for a ``ParsedRepository`` on the cache-hit path,
    where re-parsing was skipped entirely. Only ``total_python_files``
    is read by callers (for the report's "Python Files" stat), so that
    is all this carries.
    """
    total_python_files: int


def build_engine(repo_path: str, use_gemini: bool, no_cache: bool = False):
    startup_start = time.perf_counter()

    parsing_time = 0.0
    graph_build_time = 0.0
    cache_load_time = 0.0

    cache = RepositoryCache(repo_path)
    graph = None
    fingerprint = None
    parsed_repository = None

    if not no_cache:
        fingerprint = cache.compute_fingerprint()
        validation = cache.is_cache_valid(fingerprint)

        if validation.is_valid:
            t0 = time.perf_counter()
            graph = cache.load()
            cache_load_time = time.perf_counter() - t0
            logger.info("[Cache] Loaded repository graph.")
            print("[Cache] Loaded repository graph.")
            parsed_repository = _CachedRepoStats(
                total_python_files=fingerprint["file_count"]
            )

    if graph is None:
        logger.info("Parsing repository: %s", repo_path)

        t0 = time.perf_counter()
        parsed_repository = CodeParser().parse_repository(repo_path)
        parsing_time = time.perf_counter() - t0

        logger.info("Building graph...")

        t0 = time.perf_counter()
        graph = GraphBuilder().build_graph(parsed_repository)
        graph_build_time = time.perf_counter() - t0

        if not no_cache:
            cache.save(graph, fingerprint or cache.compute_fingerprint())
            logger.info("[Cache] Graph cached.")
            print("[Cache] Graph cached.")

    total_startup_time = time.perf_counter() - startup_start

    logger.info(
        "Startup benchmark for %s — parsing=%.4fs build=%.4fs cache_load=%.4fs total=%.4fs",
        repo_path, parsing_time, graph_build_time, cache_load_time, total_startup_time,
    )
    print(f"Repository parsing time: {parsing_time:.4f}s")
    print(f"Graph build time: {graph_build_time:.4f}s")
    print(f"Cache load time: {cache_load_time:.4f}s")
    print(f"Total startup time: {total_startup_time:.4f}s")

    provider = (
        GeminiLLMProvider()
        if use_gemini
        else EchoLLMProvider()
    )

    context_builder = build_context_builder(graph, top_k=5, max_hops=1)

    engine = GraphRAGEngine(
        context_builder,
        provider,
        GraphRAGPromptBuilder(),
    )

    return engine, context_builder, graph, parsed_repository


# ------------------------------------------------------------------
# Question execution (timed, exact pipeline)
# ------------------------------------------------------------------

def ask_question(engine: GraphRAGEngine, context_builder, question: str) -> dict:
    """
    Run *question* through the real, unmodified GraphRAG pipeline and time
    the retrieval and generation phases separately.

    See the module docstring ("Timing methodology") for why generation time
    is derived rather than measured directly.

    Raises whatever exception the underlying pipeline raises; the caller is
    responsible for catching it so the benchmark can continue.
    """
    t0 = time.perf_counter()
    context_builder.build(question)
    retrieval_time = time.perf_counter() - t0

    t1 = time.perf_counter()
    response = engine.answer(question)
    total_time = time.perf_counter() - t1

    generation_time = max(total_time - retrieval_time, 0.0)

    meta = response.retrieval_metadata

    return {
        "response": response,
        "retrieval_time": retrieval_time,
        "generation_time": generation_time,
        "total_time": retrieval_time + generation_time,
        "resolved_node_count": meta.resolved_node_count,
        "subgraph_node_count": meta.subgraph_node_count,
        "subgraph_edge_count": meta.subgraph_edge_count,
    }


# ------------------------------------------------------------------
# Markdown Helpers
# ------------------------------------------------------------------

def source_nodes_markdown(nodes) -> str:
    if not nodes:
        return "_No source nodes retrieved._\n"

    lines = []

    for node in nodes:
        lines.append(
            f"- **{node.node_id}** "
            f"({node.node_type}) "
            f"[score={node.score:.2f}] "
            f"{node.file_path or 'N/A'}"
            + (
                f":{node.line_number}"
                if node.line_number
                else ""
            )
        )

    return "\n".join(lines)


def metadata_markdown(meta) -> str:
    return (
        f"- Intent Categories: {meta.intent_categories}\n"
        f"- Keywords: {meta.keywords}\n"
        f"- Resolved Nodes: {meta.resolved_node_count}\n"
        f"- Subgraph Nodes: {meta.subgraph_node_count}\n"
        f"- Subgraph Edges: {meta.subgraph_edge_count}\n"
        f"- top_k: {meta.top_k}\n"
        f"- max_hops: {meta.max_hops}\n"
    )


def timing_markdown(qr: QuestionResult) -> str:
    return (
        f"- Retrieval time: {qr.retrieval_time_seconds:.4f}s\n"
        f"- Generation time: {qr.generation_time_seconds:.4f}s\n"
        f"- Total time: {qr.total_time_seconds:.4f}s\n"
    )


def summary_markdown(summary: dict) -> str:
    return (
        "# Summary\n\n"
        f"- Total Questions: {summary['total_questions']}\n"
        f"- Successful Questions: {summary['successful_questions']}\n"
        f"- Failed Questions: {summary['failed_questions']}\n"
        f"- Average Retrieval Time: {summary['average_retrieval_time_seconds']:.4f}s\n"
        f"- Average Generation Time: {summary['average_generation_time_seconds']:.4f}s\n"
    )


# ------------------------------------------------------------------
# Summary computation
# ------------------------------------------------------------------

def build_summary(results: list[RepositoryResult]) -> dict:
    all_questions = [q for r in results for q in r.questions]
    successful = [q for q in all_questions if q.success]
    failed = [q for q in all_questions if not q.success]

    retrieval_times = [
        q.retrieval_time_seconds
        for q in successful
        if q.retrieval_time_seconds is not None
    ]
    generation_times = [
        q.generation_time_seconds
        for q in successful
        if q.generation_time_seconds is not None
    ]

    avg_retrieval = (
        sum(retrieval_times) / len(retrieval_times) if retrieval_times else 0.0
    )
    avg_generation = (
        sum(generation_times) / len(generation_times) if generation_times else 0.0
    )

    return {
        "total_questions": len(all_questions),
        "successful_questions": len(successful),
        "failed_questions": len(failed),
        "average_retrieval_time_seconds": round(avg_retrieval, 4),
        "average_generation_time_seconds": round(avg_generation, 4),
    }


# ------------------------------------------------------------------
# Benchmark Runner
# ------------------------------------------------------------------

def run_benchmark(
    use_gemini: bool,
    *,
    report_path: Path = REPORT_PATH,
    json_report_path: Path = JSON_REPORT_PATH,
    no_cache: bool = False,
) -> list[RepositoryResult]:

    report_path.parent.mkdir(parents=True, exist_ok=True)

    results: list[RepositoryResult] = []
    report: list[str] = []

    report.append(
        f"# Cross Repository Benchmark\n\n"
        f"Generated: {datetime.now()}\n\n"
    )

    for repo_name, repo_url in REPOSITORIES.items():

        logger.info("=" * 80)
        logger.info("Repository: %s", repo_name)
        logger.info("=" * 80)

        repo_result = RepositoryResult(name=repo_name)
        results.append(repo_result)

        report.append(f"# {repo_name}\n\n")

        # --------------------------------------------------------------
        # Repo-level setup (clone + parse + build graph). If this fails,
        # log it with a full traceback, record every question for this
        # repository as failed (so the summary stays accurate), and move
        # on to the next repository instead of aborting the whole run.
        # --------------------------------------------------------------
        try:
            repo_path = clone_repo(repo_name, repo_url)
            engine, context_builder, graph, parsed_repo = build_engine(
                str(repo_path), use_gemini, no_cache
            )
        except Exception:
            tb = traceback.format_exc()
            err = str(sys.exc_info()[1])
            logger.exception(
                "Repository setup failed for %s — skipping its questions.",
                repo_name,
            )

            repo_result.setup_error = err
            repo_result.setup_traceback = tb

            report.append(
                "## Setup Error\n\n"
                f"Failed to clone/parse/build graph for **{repo_name}**.\n\n"
                f"```text\n{err}\n```\n\n"
                "### Traceback\n\n"
                f"```text\n{tb}\n```\n\n---\n\n"
            )

            for question in QUESTIONS.get(repo_name, []):
                repo_result.questions.append(
                    QuestionResult(
                        repository=repo_name,
                        question=question,
                        success=False,
                        error="Repository setup failed; question was not attempted.",
                        traceback=tb,
                    )
                )

            continue  # next repository

        repo_result.graph_nodes = len(graph.nodes)
        repo_result.graph_edges = len(graph.edges)
        repo_result.total_python_files = parsed_repo.total_python_files

        report.append("## Graph Statistics\n\n")
        report.append(f"- Python Files: {parsed_repo.total_python_files}\n")
        report.append(f"- Graph Nodes: {repo_result.graph_nodes}\n")
        report.append(f"- Graph Edges: {repo_result.graph_edges}\n\n")

        # --------------------------------------------------------------
        # Per-question execution. Each question is fully isolated: a
        # failure here is logged with a full traceback and recorded, but
        # never stops the benchmark from moving on to the next question.
        # --------------------------------------------------------------
        for question in QUESTIONS.get(repo_name, []):

            logger.info("Q: %s", question)

            qr = QuestionResult(
                repository=repo_name,
                question=question,
                graph_nodes=repo_result.graph_nodes,
                graph_edges=repo_result.graph_edges,
            )

            try:
                result = ask_question(engine, context_builder, question)
            except Exception:
                tb = traceback.format_exc()
                err = str(sys.exc_info()[1])
                logger.exception(
                    "Question failed for %s: %r", repo_name, question
                )

                qr.success = False
                qr.error = err
                qr.traceback = tb
                repo_result.questions.append(qr)

                report.append(
                    f"## Question\n\n{question}\n\n"
                    f"### ERROR\n\n```text\n{err}\n```\n\n"
                    f"### Traceback\n\n```text\n{tb}\n```\n\n---\n\n"
                )
                continue  # next question

            response = result["response"]

            qr.success = True
            qr.retrieval_time_seconds = result["retrieval_time"]
            qr.generation_time_seconds = result["generation_time"]
            qr.total_time_seconds = result["total_time"]
            qr.resolved_node_count = result["resolved_node_count"]
            qr.subgraph_node_count = result["subgraph_node_count"]
            qr.subgraph_edge_count = result["subgraph_edge_count"]
            qr.answer = response.answer
            repo_result.questions.append(qr)

            report.append(f"## Question\n\n{question}\n\n")

            report.append("### Timing\n\n")
            report.append(timing_markdown(qr))
            report.append("\n")

            report.append("### Retrieved Nodes\n\n")
            report.append(source_nodes_markdown(response.source_nodes))
            report.append("\n\n")

            report.append("### Retrieval Metadata\n\n")
            report.append(metadata_markdown(response.retrieval_metadata))
            report.append("\n")

            report.append("### Answer\n\n")
            report.append(response.answer)
            report.append("\n\n---\n\n")

    summary = build_summary(results)
    report.append(summary_markdown(summary))

    report_path.write_text("".join(report), encoding="utf-8")
    logger.info("Benchmark report written to: %s", report_path)

    json_report_path.write_text(
        json.dumps(
            {
                "generated": datetime.now().isoformat(),
                "summary": summary,
                "repositories": [asdict(r) for r in results],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    logger.info("JSON report written to: %s", json_report_path)

    logger.info(
        "Summary: total=%d success=%d failed=%d "
        "avg_retrieval=%.4fs avg_generation=%.4fs",
        summary["total_questions"],
        summary["successful_questions"],
        summary["failed_questions"],
        summary["average_retrieval_time_seconds"],
        summary["average_generation_time_seconds"],
    )

    return results


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    _configure_logging()

    parser = argparse.ArgumentParser(
        description="Robust cross-repository GraphRAG benchmark."
    )

    parser.add_argument(
        "--gemini",
        action="store_true",
        help="Use Gemini instead of Echo provider",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=REPORT_PATH,
        help="Path to write the Markdown report (default: tests/cross_repo_report.md)",
    )
    parser.add_argument(
        "--json-report",
        type=Path,
        default=JSON_REPORT_PATH,
        help="Path to write the JSON report (default: tests/cross_repo_report.json)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Force re-parsing and rebuilding each repository's graph, ignoring any cached graph.",
    )

    args = parser.parse_args()

    REPOS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        results = run_benchmark(
            use_gemini=args.gemini,
            report_path=args.report,
            json_report_path=args.json_report,
            no_cache=args.no_cache,
        )
    except Exception:
        # Last-resort safety net: even a bug in the benchmark harness itself
        # should be logged with a full traceback rather than producing a
        # bare Python stack trace with no context.
        logger.exception("Benchmark run aborted due to an unhandled error.")
        sys.exit(1)

    summary = build_summary(results)

    # Non-zero exit only when literally nothing succeeded — useful as a CI
    # signal — but never raised mid-run, since individual failures are
    # already captured and the benchmark always finishes and writes reports.
    if summary["total_questions"] > 0 and summary["successful_questions"] == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()