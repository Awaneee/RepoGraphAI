"""
tests/retrieval_metrics.py
==========================
Automated retrieval evaluation for RepoGraphAI — Milestone 4.

Two benchmark modes
-------------------
MODE 1 — Internal benchmark
    Runs the 15 questions from retrieval_benchmark.py against the project's
    own codebase (backend/app/).  Each question has one or more expected
    symbols.  The pipeline is driven via the existing
    ``ContextBuilder.build()`` API exactly as retrieval_benchmark.py does it.

MODE 2 — Cross-repository benchmark
    Runs 15 questions (5 per repo) against FastAPI, Typer, and Requests,
    reusing the clone/parse/build pattern from cross_repo_benchmark.py.
    Expected symbols are listed in CROSS_REPO_EXPECTED below.

Metrics computed (per question and aggregated)
----------------------------------------------
Top-1 Accuracy    first expected symbol appears at rank 1
Top-3 Accuracy    any expected symbol appears in top-3
Top-5 Accuracy    any expected symbol appears in top-5
Recall@k          |expected ∩ top-k| / |expected|
Precision@k       |expected ∩ top-k| / k
MRR               1 / rank of the first expected symbol (0 if none found)

All metrics are based on exact node_id matching.  No LLM, no semantic
judging — entirely deterministic.

Outputs
-------
tests/retrieval_metrics_report.md
tests/retrieval_metrics.json

Usage
-----
    cd backend
    python tests/retrieval_metrics.py
"""

from __future__ import annotations

import json
import logging
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Path bootstrap — identical to the existing benchmarks
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.parsers.code_parser import CodeParser
from app.graph.graph_builder import GraphBuilder
from app.rag.context_builder import build_context_builder
from app.rag.graphrag_engine import EchoLLMProvider, GraphRAGEngine, GraphRAGPromptBuilder

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("retrieval_metrics")

# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------

TESTS_DIR          = Path(__file__).resolve().parent
REPORT_PATH        = TESTS_DIR / "retrieval_metrics_report.md"
JSON_REPORT_PATH   = TESTS_DIR / "retrieval_metrics.json"

# ---------------------------------------------------------------------------
# MODE 1 — Internal benchmark questions + expected symbols
#
# Each entry: question, category, and a list of expected node IDs.
# A match is any retrieved node_id that equals one of the expected strings.
# Single-symbol questions (originally one expected_symbol) are wrapped in a
# list so the multi-symbol metrics (Recall, Precision) generalise cleanly.
# ---------------------------------------------------------------------------

INTERNAL_QUESTIONS: list[dict] = [
    {
        "category": "Parsing",
        "question": "How are files parsed?",
        "expected_symbols": ["CodeParser.parse_file"],
    },
    {
        "category": "Parsing",
        "question": "How are imports extracted?",
        "expected_symbols": ["CodeParser._extract_imports"],
    },
    {
        "category": "Parsing",
        "question": "How are classes extracted?",
        "expected_symbols": ["CodeParser._extract_class"],
    },
    {
        "category": "Graph Construction",
        "question": "How is the graph generated?",
        "expected_symbols": ["GraphBuilder.build_graph"],
    },
    {
        "category": "Graph Construction",
        "question": "How are graph nodes created?",
        "expected_symbols": ["GraphBuilder.build_graph"],
    },
    {
        "category": "Graph Construction",
        "question": "How are graph edges created?",
        "expected_symbols": ["GraphBuilder.build_graph"],
    },
    {
        "category": "Graph Construction",
        "question": "How is inheritance represented?",
        "expected_symbols": ["GraphBuilder.build_class_graph"],
    },
    {
        "category": "Analytics",
        "question": "How are hotspots calculated?",
        "expected_symbols": ["GraphBuilder.generate_statistics"],
    },
    {
        "category": "Analytics",
        "question": "How are graph statistics generated?",
        "expected_symbols": ["GraphBuilder.generate_statistics"],
    },
    {
        "category": "Retrieval",
        "question": "How does retrieval work?",
        "expected_symbols": ["RepositoryRetriever.get_node_context"],
    },
    {
        "category": "Retrieval",
        "question": "How are neighbours retrieved?",
        "expected_symbols": ["RepositoryRetriever._collect_neighbours"],
    },
    {
        "category": "Retrieval",
        "question": "How is a subgraph extracted?",
        "expected_symbols": ["RepositoryRetriever.get_subgraph"],
    },
    {
        "category": "Query Resolution",
        "question": "How does query resolution work?",
        "expected_symbols": ["QueryResolver.resolve_query"],
    },
    {
        "category": "Query Resolution",
        "question": "How are symbols ranked?",
        "expected_symbols": ["QueryResolver.rank_candidates"],
    },
    {
        "category": "Context Building",
        "question": "How is LLM context built?",
        "expected_symbols": ["ContextBuilder.build"],
    },
]

# ---------------------------------------------------------------------------
# MODE 2 — Cross-repo questions + expected symbols
#
# Expected symbols are node IDs as they appear in the graph after parsing
# each repository.  Lists with multiple entries reflect that the question
# can reasonably be answered by any of those symbols.
# ---------------------------------------------------------------------------

CROSS_REPO_QUESTIONS: dict[str, list[dict]] = {
    "FastAPI": [
        {
            "question": "How are routes registered?",
            "expected_symbols": [
                "APIRouter.add_api_route",
                "APIRouter.add_route",
                "APIRouter.add_api_websocket_route",
            ],
        },
        {
            "question": "How does dependency injection work?",
            "expected_symbols": [
                "get_dependant",
                "solve_dependencies",
                "add_non_field_param_to_dependency",
            ],
        },
        {
            "question": "How are requests handled?",
            "expected_symbols": [
                "get_request_handler",
                "APIRoute.handle",
                "request_validation_exception_handler",
            ],
        },
        {
            "question": "How are responses generated?",
            "expected_symbols": [
                "ORJSONResponse.render",
                "UJSONResponse.render",
                "serialize_response",
            ],
        },
        {
            "question": "How are middleware components registered?",
            "expected_symbols": [
                "FastAPI.middleware",
                "FastAPI.build_middleware_stack",
                "AsyncExitStackMiddleware.__call__",
            ],
        },
    ],
    "Typer": [
        {
            "question": "How are CLI commands registered?",
            "expected_symbols": [
                "TyperCLIGroup.list_commands",
                "TyperGroup.format_commands",
                "TyperGroup._click_resolve_command",
            ],
        },
        {
            "question": "How are command arguments parsed?",
            "expected_symbols": [
                "Command.parse_args",
                "TyperArgument._parse_decls",
                "_OptionParser.add_argument",
            ],
        },
        {
            "question": "How are options defined?",
            "expected_symbols": [
                "Command.format_options",
                "TyperCommand.format_options",
                "TyperGroup.format_options",
            ],
        },
        {
            "question": "How is help text generated?",
            "expected_symbols": [
                "Command.format_help_text",
                "_get_help_text",
                "_sanitize_help_text",
            ],
        },
        {
            "question": "How are callbacks executed?",
            "expected_symbols": [
                "get_callback",
                "Typer.callback",
                "get_param_callback",
            ],
        },
    ],
    "Requests": [
        {
            "question": "How are HTTP requests executed?",
            "expected_symbols": [
                "HTTPAdapter.send",
                "Session.send",
                "HTTPAdapter.request_url",
            ],
        },
        {
            "question": "How are sessions managed?",
            "expected_symbols": [
                "Session.send",
                "Session.__init__",
                "session",
            ],
        },
        {
            "question": "How are adapters used?",
            "expected_symbols": [
                "HTTPAdapter",
                "BaseAdapter",
                "Session.get_adapter",
            ],
        },
        {
            "question": "How are redirects handled?",
            "expected_symbols": [
                "SessionRedirectMixin.resolve_redirects",
                "HTTPDigestAuth.handle_redirect",
                "Response.is_redirect",
            ],
        },
        {
            "question": "How are responses processed?",
            "expected_symbols": [
                "Response.iter_content",
                "Response.content",
                "stream_decode_response_unicode",
            ],
        },
    ],
}

REPOS_DIR = PROJECT_ROOT / "repos"
REPOSITORIES = {
    "FastAPI":  "https://github.com/fastapi/fastapi.git",
    "Typer":    "https://github.com/fastapi/typer.git",
    "Requests": "https://github.com/psf/requests.git",
}

# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------

def _find_rank(node_ids: list[str], expected: list[str]) -> Optional[int]:
    """
    Return the 1-based rank of the first expected symbol in *node_ids*,
    or None if none of the expected symbols appear.
    """
    for rank, nid in enumerate(node_ids, start=1):
        if nid in expected:
            return rank
    return None


def compute_metrics(
    retrieved: list[str],
    expected: list[str],
    k: int = 5,
) -> dict:
    """
    Compute all retrieval metrics for one question.

    Parameters
    ----------
    retrieved : list[str]
        Retrieved node IDs in rank order (best first).
    expected : list[str]
        Expected node IDs (any match counts).
    k : int
        Maximum rank considered (top-k).

    Returns
    -------
    dict with keys:
        top_1, top_3, top_5            bool
        recall_1, recall_3, recall_5   float  [0, 1]
        precision_1, precision_3, precision_5  float  [0, 1]
        mrr                            float  [0, 1]
        first_hit_rank                 int | None
    """
    expected_set = set(expected)
    top_k = retrieved[:k]

    def hits_at(n: int) -> int:
        return sum(1 for nid in retrieved[:n] if nid in expected_set)

    n_expected = max(len(expected_set), 1)  # guard /0

    recall_at    = lambda n: hits_at(n) / n_expected
    precision_at = lambda n: hits_at(n) / n if n > 0 else 0.0

    first_rank = _find_rank(retrieved, expected)
    mrr = (1.0 / first_rank) if first_rank is not None else 0.0

    return {
        "top_1":       first_rank == 1,
        "top_3":       first_rank is not None and first_rank <= 3,
        "top_5":       first_rank is not None and first_rank <= 5,
        "recall_1":    recall_at(1),
        "recall_3":    recall_at(3),
        "recall_5":    recall_at(5),
        "precision_1": precision_at(1),
        "precision_3": precision_at(3),
        "precision_5": precision_at(5),
        "mrr":         mrr,
        "first_hit_rank": first_rank,
    }


def aggregate_metrics(metric_list: list[dict]) -> dict:
    """Average all scalar metrics over a list of per-question metric dicts."""
    if not metric_list:
        return {}
    keys = [k for k in metric_list[0] if k != "first_hit_rank"]
    return {
        k: round(sum(m[k] for m in metric_list) / len(metric_list), 4)
        for k in keys
    }

# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------

@dataclass
class QuestionMetrics:
    """Full evaluation record for one benchmark question."""
    repository:       str         # "internal", "FastAPI", etc.
    category:         str
    question:         str
    expected_symbols: list[str]
    retrieved_ids:    list[str]   # top-5 node IDs in rank order
    retrieved_labels: list[str]   # matching labels
    retrieved_scores: list[float]
    retrieved_reasons: list[str] = field(default_factory=list)

    # metric fields (populated after compute_metrics)
    top_1:       bool  = False
    top_3:       bool  = False
    top_5:       bool  = False
    recall_1:    float = 0.0
    recall_3:    float = 0.0
    recall_5:    float = 0.0
    precision_1: float = 0.0
    precision_3: float = 0.0
    precision_5: float = 0.0
    mrr:         float = 0.0
    first_hit_rank: Optional[int] = None

    retrieval_time: float = 0.0
    error: Optional[str] = None

    def pass_fail(self) -> str:
        return "PASS" if self.top_5 else "FAIL"

# ---------------------------------------------------------------------------
# Pipeline runner helpers
# ---------------------------------------------------------------------------

def _run_question(context_builder, question: str, top_k: int = 5) -> tuple[list, float]:
    """
    Call context_builder.build() and return (resolved_nodes, elapsed_seconds).
    Uses the same call pattern as retrieval_benchmark.py.
    """
    t0 = time.perf_counter()
    package = context_builder.build(question, top_k=top_k, max_hops=1)
    elapsed = time.perf_counter() - t0
    return package.resolved_nodes, elapsed


def _evaluate_questions(
    context_builder,
    questions: list[dict],
    repository: str,
) -> list[QuestionMetrics]:
    """
    Run every question through the pipeline and compute metrics.
    Failures are captured per-question so the run never aborts early.
    """
    results: list[QuestionMetrics] = []

    for q in questions:
        question         = q["question"]
        expected_symbols = q["expected_symbols"]
        category         = q.get("category", "")
        qm = QuestionMetrics(
            repository=repository,
            category=category,
            question=question,
            expected_symbols=expected_symbols,
            retrieved_ids=[],
            retrieved_labels=[],
            retrieved_scores=[],
            retrieved_reasons=[],
        )

        try:
            resolved_nodes, elapsed = _run_question(context_builder, question)
            qm.retrieval_time = elapsed

            # Collect retrieved info
            qm.retrieved_ids     = [rn.node_id for rn in resolved_nodes]
            qm.retrieved_labels  = [rn.label   for rn in resolved_nodes]
            qm.retrieved_scores  = [rn.score   for rn in resolved_nodes]
            qm.retrieved_reasons = [rn.reason  for rn in resolved_nodes]

            # Compute metrics
            m = compute_metrics(qm.retrieved_ids, expected_symbols, k=5)
            qm.top_1            = m["top_1"]
            qm.top_3            = m["top_3"]
            qm.top_5            = m["top_5"]
            qm.recall_1         = m["recall_1"]
            qm.recall_3         = m["recall_3"]
            qm.recall_5         = m["recall_5"]
            qm.precision_1      = m["precision_1"]
            qm.precision_3      = m["precision_3"]
            qm.precision_5      = m["precision_5"]
            qm.mrr              = m["mrr"]
            qm.first_hit_rank   = m["first_hit_rank"]

        except Exception:
            qm.error = traceback.format_exc()
            logger.error("  Error on question %r:\n%s", question, qm.error)

        results.append(qm)
    return results

def _inject_ablation_toggles(context_builder, graph, ablation_toggles):
    from app.retrievers.query_resolver import _looks_like_dto
    from app.models.pydantic_models import RelationshipType, NodeType
    if ablation_toggles is not None:
        context_builder._resolver.ablation_toggles = ablation_toggles
        # Re-precompute DTO status
        context_builder._resolver._is_dto = {
            node_id: _looks_like_dto(node, graph, dto_fixes=ablation_toggles.get("dto_fixes", False))
            for node_id, node in context_builder._resolver._nodes.items()
        }
        if ablation_toggles.get("dto_fixes", False):
            for edge in graph.edges:
                if (
                    edge.relationship == RelationshipType.CONTAINS
                    and edge.source in context_builder._resolver._is_dto
                    and context_builder._resolver._is_dto[edge.source]
                    and edge.target in context_builder._resolver._nodes
                    and context_builder._resolver._nodes[edge.target].type == NodeType.METHOD
                ):
                    context_builder._resolver._is_dto[edge.target] = True

# ---------------------------------------------------------------------------
# MODE 1 — Internal benchmark
# ---------------------------------------------------------------------------

def run_internal_benchmark(ablation_toggles: Optional[dict[str, bool]] = None, custom_questions: Optional[list[dict]] = None) -> list[QuestionMetrics]:
    repo_path = str(PROJECT_ROOT / "app")
    logger.info("=" * 70)
    logger.info("MODE 1 — Internal benchmark: %s", repo_path)
    logger.info("=" * 70)

    logger.info("Parsing repository...")
    parsed = CodeParser().parse_repository(repo_path)
    logger.info("Building graph...")
    graph = GraphBuilder().build_graph(parsed)
    context_builder = build_context_builder(graph)
    _inject_ablation_toggles(context_builder, graph, ablation_toggles)
    
    questions = custom_questions if custom_questions is not None else INTERNAL_QUESTIONS
    logger.info("Pipeline ready. Running %d questions...", len(questions))

    results = _evaluate_questions(context_builder, questions, "internal")
    for qm in results:
        status = "✓" if qm.top_5 else "✗"
        logger.info("  [%s] %s  (rank=%s, MRR=%.2f)",
                    status, qm.question, qm.first_hit_rank, qm.mrr)
    return results

# ---------------------------------------------------------------------------
# MODE 2 — Cross-repo benchmark
# ---------------------------------------------------------------------------

def _clone_repo(name: str, url: str) -> Path:
    import subprocess
    repo_path = REPOS_DIR / name.lower()
    if repo_path.exists():
        logger.info("  [SKIP] %s already cloned", name)
        return repo_path
    logger.info("  [CLONE] %s from %s", name, url)
    subprocess.run(["git", "clone", url, str(repo_path)], check=True)
    return repo_path


def run_cross_repo_benchmark(ablation_toggles: Optional[dict[str, bool]] = None, custom_questions: Optional[dict[str, list[dict]]] = None) -> dict[str, list[QuestionMetrics]]:
    REPOS_DIR.mkdir(parents=True, exist_ok=True)
    all_results: dict[str, list[QuestionMetrics]] = {}

    for repo_name, repo_url in REPOSITORIES.items():
        logger.info("=" * 70)
        logger.info("MODE 2 — Repository: %s", repo_name)
        logger.info("=" * 70)

        if custom_questions is not None:
            questions = custom_questions.get(repo_name, [])
            if not questions:
                logger.info("  No questions for %s — skipping.", repo_name)
                continue
        else:
            questions = CROSS_REPO_QUESTIONS.get(repo_name, [])

        try:
            repo_path = _clone_repo(repo_name, repo_url)
            logger.info("  Parsing...")
            parsed = CodeParser().parse_repository(str(repo_path))
            logger.info("  Building graph...")
            graph = GraphBuilder().build_graph(parsed)
            context_builder = build_context_builder(graph, top_k=5, max_hops=1)
            _inject_ablation_toggles(context_builder, graph, ablation_toggles)
            logger.info("  Pipeline ready. Running %d questions...",
                        len(questions))
        except Exception:
            logger.exception("  Setup failed for %s — skipping.", repo_name)
            # Record all questions as failed
            failed: list[QuestionMetrics] = []
            for q in questions:
                failed.append(QuestionMetrics(
                    repository=repo_name,
                    category=q.get("category", ""),
                    question=q["question"],
                    expected_symbols=q["expected_symbols"],
                    retrieved_ids=[],
                    retrieved_labels=[],
                    retrieved_scores=[],
                    error=traceback.format_exc(),
                ))
            all_results[repo_name] = failed
            continue

        results = _evaluate_questions(
            context_builder,
            questions,
            repo_name,
        )
        for qm in results:
            status = "✓" if qm.top_5 else "✗"
            logger.info("  [%s] %s  (rank=%s, MRR=%.2f)",
                        status, qm.question, qm.first_hit_rank, qm.mrr)
        all_results[repo_name] = results

    return all_results

# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

SEP_THICK = "=" * 60
SEP_THIN  = "-" * 60


def _metrics_table_row(label: str, m: dict) -> str:
    """One row of the aggregated metrics table."""
    return (
        f"| {label:<28} "
        f"| {m.get('top_1', 0)*100:>6.1f}% "
        f"| {m.get('top_3', 0)*100:>6.1f}% "
        f"| {m.get('top_5', 0)*100:>6.1f}% "
        f"| {m.get('recall_1', 0)*100:>7.1f}% "
        f"| {m.get('recall_3', 0)*100:>7.1f}% "
        f"| {m.get('recall_5', 0)*100:>7.1f}% "
        f"| {m.get('precision_1', 0)*100:>8.1f}% "
        f"| {m.get('precision_3', 0)*100:>8.1f}% "
        f"| {m.get('precision_5', 0)*100:>8.1f}% "
        f"| {m.get('mrr', 0):>5.3f} |"
    )


def _metrics_table_header() -> str:
    h = (
        "| Dataset                      "
        "| Top-1  | Top-3  | Top-5  "
        "| R@1     | R@3     | R@5     "
        "| P@1      | P@3      | P@5      "
        "| MRR   |"
    )
    sep = "|" + "|".join(["-" * (len(c)) for c in h.split("|")[1:-1]]) + "|"
    return h + "\n" + sep


def _per_question_section(qm: QuestionMetrics) -> str:
    lines = []
    lines.append(f"### {qm.question}")
    lines.append("")
    lines.append(f"**Category:** {qm.category}  ")
    lines.append(f"**Repository:** {qm.repository}  ")
    lines.append(f"**Result:** {qm.pass_fail()}  ")
    lines.append(f"**Retrieval time:** {qm.retrieval_time:.4f}s")
    lines.append("")

    lines.append("**Expected symbols:**")
    for sym in qm.expected_symbols:
        lines.append(f"- `{sym}`")
    lines.append("")

    if qm.error:
        lines.append(f"**ERROR:** `{qm.error[:200]}`")
        lines.append("")
        return "\n".join(lines)

    lines.append("**Retrieved symbols (top-5):**")
    for i, (nid, score) in enumerate(
        zip(qm.retrieved_ids[:5], qm.retrieved_scores[:5]), start=1
    ):
        hit = " ✓" if nid in qm.expected_symbols else ""
        lines.append(f"{i}. `{nid}` [score={score:.2f}]{hit}")
    lines.append("")

    rank_str = str(qm.first_hit_rank) if qm.first_hit_rank else "—"
    lines.append(
        f"| Metric | Top-1 | Top-3 | Top-5 | R@1 | R@3 | R@5 | P@1 | P@3 | P@5 | MRR |"
    )
    lines.append("|--------|-------|-------|-------|-----|-----|-----|-----|-----|-----|-----|")
    lines.append(
        f"| Value "
        f"| {'✓' if qm.top_1 else '✗'} "
        f"| {'✓' if qm.top_3 else '✗'} "
        f"| {'✓' if qm.top_5 else '✗'} "
        f"| {qm.recall_1:.2f} "
        f"| {qm.recall_3:.2f} "
        f"| {qm.recall_5:.2f} "
        f"| {qm.precision_1:.2f} "
        f"| {qm.precision_3:.2f} "
        f"| {qm.precision_5:.2f} "
        f"| {qm.mrr:.3f} |"
    )
    lines.append(f"\nFirst hit rank: **{rank_str}**")
    lines.append("")
    return "\n".join(lines)


def build_report(
    internal: list[QuestionMetrics],
    cross_repo: dict[str, list[QuestionMetrics]],
) -> str:
    lines: list[str] = []
    lines.append("# RepoGraphAI — Retrieval Metrics Report")
    lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(SEP_THICK)

    # ------------------------------------------------------------------ #
    # Overall metrics
    # ------------------------------------------------------------------ #
    all_qm = internal + [qm for qs in cross_repo.values() for qm in qs]
    all_metrics = [
        {k: getattr(qm, k) for k in
         ["top_1","top_3","top_5","recall_1","recall_3","recall_5",
          "precision_1","precision_3","precision_5","mrr"]}
        for qm in all_qm if not qm.error
    ]
    overall = aggregate_metrics(all_metrics)

    lines.append("\n## Overall Metrics (All Questions)\n")
    lines.append(_metrics_table_header())
    lines.append(_metrics_table_row("ALL", overall))
    lines.append("")

    # ------------------------------------------------------------------ #
    # Per-dataset summary
    # ------------------------------------------------------------------ #
    lines.append("\n## Per-Dataset Metrics\n")
    lines.append(_metrics_table_header())

    int_metrics = [
        {k: getattr(qm, k) for k in
         ["top_1","top_3","top_5","recall_1","recall_3","recall_5",
          "precision_1","precision_3","precision_5","mrr"]}
        for qm in internal if not qm.error
    ]
    lines.append(_metrics_table_row("Internal (own codebase)", aggregate_metrics(int_metrics)))

    for repo_name, qms in cross_repo.items():
        repo_metrics = [
            {k: getattr(qm, k) for k in
             ["top_1","top_3","top_5","recall_1","recall_3","recall_5",
              "precision_1","precision_3","precision_5","mrr"]}
            for qm in qms if not qm.error
        ]
        lines.append(_metrics_table_row(repo_name, aggregate_metrics(repo_metrics)))
    lines.append("")

    # ------------------------------------------------------------------ #
    # Per-question detail — Internal
    # ------------------------------------------------------------------ #
    lines.append(f"\n{SEP_THICK}")
    lines.append("\n## Mode 1 — Internal Benchmark (Per Question)\n")
    lines.append(SEP_THICK + "\n")
    for qm in internal:
        lines.append(_per_question_section(qm))
        lines.append(SEP_THIN)
        lines.append("")

    # ------------------------------------------------------------------ #
    # Per-question detail — Cross-repo
    # ------------------------------------------------------------------ #
    lines.append(f"\n{SEP_THICK}")
    lines.append("\n## Mode 2 — Cross-Repository Benchmark (Per Question)\n")
    lines.append(SEP_THICK + "\n")

    for repo_name, qms in cross_repo.items():
        lines.append(f"\n### Repository: {repo_name}\n")
        for qm in qms:
            lines.append(_per_question_section(qm))
            lines.append(SEP_THIN)
            lines.append("")

    return "\n".join(lines)


def build_json(
    internal: list[QuestionMetrics],
    cross_repo: dict[str, list[QuestionMetrics]],
) -> dict:
    def qm_to_dict(qm: QuestionMetrics) -> dict:
        return {
            "repository":       qm.repository,
            "category":         qm.category,
            "question":         qm.question,
            "expected_symbols": qm.expected_symbols,
            "retrieved_ids":    qm.retrieved_ids,
            "retrieved_labels": qm.retrieved_labels,
            "retrieved_scores": qm.retrieved_scores,
            "pass_fail":        qm.pass_fail(),
            "first_hit_rank":   qm.first_hit_rank,
            "retrieval_time":   round(qm.retrieval_time, 4),
            "error":            qm.error,
            "metrics": {
                "top_1":       qm.top_1,
                "top_3":       qm.top_3,
                "top_5":       qm.top_5,
                "recall_1":    round(qm.recall_1, 4),
                "recall_3":    round(qm.recall_3, 4),
                "recall_5":    round(qm.recall_5, 4),
                "precision_1": round(qm.precision_1, 4),
                "precision_3": round(qm.precision_3, 4),
                "precision_5": round(qm.precision_5, 4),
                "mrr":         round(qm.mrr, 4),
            },
        }

    all_qm = internal + [qm for qs in cross_repo.values() for qm in qs]
    all_metrics = [
        {k: getattr(qm, k) for k in
         ["top_1","top_3","top_5","recall_1","recall_3","recall_5",
          "precision_1","precision_3","precision_5","mrr"]}
        for qm in all_qm if not qm.error
    ]
    overall = aggregate_metrics(all_metrics)

    per_repo: dict = {}

    int_metrics = [
        {k: getattr(qm, k) for k in
         ["top_1","top_3","top_5","recall_1","recall_3","recall_5",
          "precision_1","precision_3","precision_5","mrr"]}
        for qm in internal if not qm.error
    ]
    per_repo["internal"] = {
        "aggregate": aggregate_metrics(int_metrics),
        "questions": [qm_to_dict(qm) for qm in internal],
    }

    for repo_name, qms in cross_repo.items():
        repo_metrics = [
            {k: getattr(qm, k) for k in
             ["top_1","top_3","top_5","recall_1","recall_3","recall_5",
              "precision_1","precision_3","precision_5","mrr"]}
            for qm in qms if not qm.error
        ]
        per_repo[repo_name] = {
            "aggregate": aggregate_metrics(repo_metrics),
            "questions": [qm_to_dict(qm) for qm in qms],
        }

    return {
        "generated":   datetime.now().isoformat(),
        "overall":     overall,
        "per_dataset": per_repo,
    }

# ---------------------------------------------------------------------------
# Console summary
# ---------------------------------------------------------------------------

def print_console_summary(
    internal: list[QuestionMetrics],
    cross_repo: dict[str, list[QuestionMetrics]],
) -> None:
    all_qm = internal + [qm for qs in cross_repo.values() for qm in qs]
    valid  = [qm for qm in all_qm if not qm.error]

    def pct(attr: str) -> str:
        hits = sum(getattr(qm, attr) for qm in valid)
        return f"{hits}/{len(valid)} ({100*hits/max(len(valid),1):.1f}%)"

    avg_mrr = sum(qm.mrr for qm in valid) / max(len(valid), 1)

    print("\n" + "=" * 60)
    print("  RETRIEVAL METRICS SUMMARY")
    print("=" * 60)
    print(f"  Total questions : {len(all_qm)}  (errors: {len(all_qm)-len(valid)})")
    print(f"  Top-1 Accuracy  : {pct('top_1')}")
    print(f"  Top-3 Accuracy  : {pct('top_3')}")
    print(f"  Top-5 Accuracy  : {pct('top_5')}")
    print(f"  Average MRR     : {avg_mrr:.3f}")
    print("-" * 60)

    for label, qms in [("Internal", internal)] + list(cross_repo.items()):
        v = [qm for qm in qms if not qm.error]
        if not v:
            continue
        t5 = sum(qm.top_5 for qm in v)
        mrr = sum(qm.mrr for qm in v) / len(v)
        print(f"  {label:<14}: Top-5={t5}/{len(v)}  MRR={mrr:.3f}")

    print("=" * 60)
    print(f"  Report : {REPORT_PATH}")
    print(f"  JSON   : {JSON_REPORT_PATH}")
    print("=" * 60 + "\n")

    # Expected vs Actual Diagnostics for Failed Top-1 Cases
    failed_top1 = [qm for qm in valid if not qm.top_1]
    if failed_top1:
        print("=" * 60)
        print("  EXPECTED VS ACTUAL DIAGNOSTICS FOR FAILED TOP-1 CASES")
        print("=" * 60)
        import re
        for qm in failed_top1:
            print(f"\nQuestion : {qm.question}  ({qm.repository})")
            print(f"Expected : {qm.expected_symbols}")
            
            # Print actual top-1 retrieved symbol
            if qm.retrieved_ids:
                actual_top1_id = qm.retrieved_ids[0]
                actual_top1_score = qm.retrieved_scores[0]
                actual_top1_reason = qm.retrieved_reasons[0]
                print(f"Actual Top-1: {actual_top1_id} (Score: {actual_top1_score})")
                print("Breakdown:")
                parts = [p.strip() for p in actual_top1_reason.split(";")]
                for part in parts:
                    match_sign = re.search(r"([-+]\d+(?:\.\d+)?)$", part)
                    if match_sign:
                        val = match_sign.group(1)
                        desc = part[:match_sign.start()].strip()
                        print(f"  {val:>4} {desc}")
                    else:
                        print(f"       {part}")
            else:
                print("Actual Top-1: (None retrieved)")

            # Find the expected symbol in the retrieved list (if present)
            found_expected = False
            for exp in qm.expected_symbols:
                if exp in qm.retrieved_ids:
                    idx = qm.retrieved_ids.index(exp)
                    score = qm.retrieved_scores[idx]
                    reason = qm.retrieved_reasons[idx]
                    print(f"\nExpected symbol: {exp} (Rank: {idx + 1}, Score: {score})")
                    print("Breakdown:")
                    parts = [p.strip() for p in reason.split(";")]
                    for part in parts:
                        match_sign = re.search(r"([-+]\d+(?:\.\d+)?)$", part)
                        if match_sign:
                            val = match_sign.group(1)
                            desc = part[:match_sign.start()].strip()
                            print(f"  {val:>4} {desc}")
                        else:
                            print(f"       {part}")
                    found_expected = True
                    break
            if not found_expected:
                print("\nExpected symbol: (Not in top-5 retrieved list)")
            print("-" * 60)

# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("RepoGraphAI — Retrieval Metrics  (Milestone 4)")
    logger.info("=" * 70)

    # Step 1 & 2: parse + build graphs, run retrieval for both modes
    internal_results  = run_internal_benchmark()
    cross_repo_results = run_cross_repo_benchmark()

    # Steps 3 & 4: already done inside the runners above (metrics computed
    # inline via compute_metrics after each pipeline call).

    # Step 5: console summary
    print_console_summary(internal_results, cross_repo_results)

    # Step 6: write Markdown report
    report_text = build_report(internal_results, cross_repo_results)
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    logger.info("Markdown report written to: %s", REPORT_PATH)

    json_data = build_json(internal_results, cross_repo_results)
    JSON_REPORT_PATH.write_text(
        json.dumps(json_data, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("JSON report written to: %s", JSON_REPORT_PATH)

def _run_ablation_runs():
    TWEAKS = [
        ("dto_fixes", "Restricts Signal 1 DTO check to Class & propagates DTO"),
        ("private_penalties", "Penalizes private methods/classes by -4"),
        ("dunder_penalties", "Penalizes dunder methods by -15"),
        ("generate_build", "Adds generate/generat -> build synonyms"),
        ("resolution_resolve", "Adds resolution/resolu -> resolve synonyms"),
        ("retrieval_synonyms", "Adds retrieval/retriever synonyms"),
        ("symbol_candidate", "Adds symbol -> candidate synonyms"),
        ("file_module_penalty", "Intent-aware file/module penalty (-12)"),
        ("visualization_penalty", "Intent-aware visualization penalty (-4)"),
        ("verb_lexicon_cleanup", "Removes session from authentication verbs"),
    ]

    logger.info("==================================================")
    print("  PRE-BUILDING CODES AND GRAPHS FOR ABLATION RUNS")
    logger.info("==================================================")

    # 1. APP (Internal)
    logger.info("Parsing internal repository...")
    internal_parsed = CodeParser().parse_repository(str(PROJECT_ROOT / "app"))
    logger.info("Building internal graph...")
    internal_graph = GraphBuilder().build_graph(internal_parsed)

    # 2. Cross-repo
    REPOS_DIR.mkdir(parents=True, exist_ok=True)
    repo_graphs = {}
    for repo_name, repo_url in REPOSITORIES.items():
        try:
            repo_path = _clone_repo(repo_name, repo_url)
            logger.info("Parsing %s...", repo_name)
            parsed = CodeParser().parse_repository(str(repo_path))
            logger.info("Building graph for %s...", repo_name)
            graph = GraphBuilder().build_graph(parsed)
            repo_graphs[repo_name] = graph
        except Exception:
            logger.exception("Failed to build graph for %s", repo_name)

    # Run ablation configurations
    configs = []
    
    # Baseline (all False)
    configs.append(("Baseline (All False)", {t[0]: False for t in TWEAKS}))
    
    # Individual Tweaks
    for tweak_name, desc in TWEAKS:
        toggles = {t[0]: False for t in TWEAKS}
        toggles[tweak_name] = True
        configs.append((f"Tweak: {tweak_name}", toggles))
        
    # Combined (All True)
    configs.append(("Combined (All True)", {t[0]: True for t in TWEAKS}))

    results = []
    for label, toggles in configs:
        # Evaluate internal
        cb_internal = build_context_builder(internal_graph)
        _inject_ablation_toggles(cb_internal, internal_graph, toggles)
        metrics_internal = _evaluate_questions(cb_internal, INTERNAL_QUESTIONS, "internal")

        # Evaluate cross-repo
        metrics_cross = []
        for repo_name, graph in repo_graphs.items():
            cb_cross = build_context_builder(graph, top_k=5, max_hops=1)
            _inject_ablation_toggles(cb_cross, graph, toggles)
            metrics_cross.extend(_evaluate_questions(cb_cross, CROSS_REPO_QUESTIONS[repo_name], repo_name))

        # Aggregate metrics
        all_qm = metrics_internal + metrics_cross
        valid = [qm for qm in all_qm if not qm.error]
        
        all_metrics = [
            {k: getattr(qm, k) for k in ["top_1", "top_3", "top_5", "mrr"]}
            for qm in valid
        ]
        agg = aggregate_metrics(all_metrics)
        results.append((label, agg))

    # Print markdown table
    print("\n" + "=" * 60)
    print("  ABLATION STUDY RESULTS")
    print("=" * 60)
    print("| Configuration | Top-1 | Top-3 | Top-5 | MRR |")
    print("|---|---|---|---|---|")
    for label, agg in results:
        print(f"| {label:<35} | {agg.get('top_1', 0)*100:>5.1f}% | {agg.get('top_3', 0)*100:>5.1f}% | {agg.get('top_5', 0)*100:>5.1f}% | {agg.get('mrr', 0):>5.3f} |")
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="RepoGraphAI Retrieval Metrics & Ablation Runner")
    parser.add_argument("--ablation", action="store_true", help="Run ablation study across all tweaks")
    parser.add_argument("--benchmark", type=str, default=None, help="Path to custom benchmark JSON file")
    args = parser.parse_args()

    if args.ablation:
        _run_ablation_runs()
        return

    logger.info("RepoGraphAI — Retrieval Metrics  (Milestone 4)")
    logger.info("=" * 70)

    custom_internal = None
    custom_cross = None

    if args.benchmark:
        benchmark_path = Path(args.benchmark)
        if not benchmark_path.exists():
            logger.error("Benchmark file not found: %s", benchmark_path)
            sys.exit(1)
        
        with open(benchmark_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        logger.info("Loaded %d questions from custom benchmark %s", len(data), benchmark_path)
        
        custom_internal = []
        custom_cross = {}
        for item in data:
            q_mapped = {
                "question": item["question"],
                "expected_symbols": [item["expected_symbol"]],
                "category": item["category"]
            }
            repo = item["repository"]
            if repo in ("RepoGraphAI", "internal"):
                custom_internal.append(q_mapped)
            else:
                custom_cross.setdefault(repo, []).append(q_mapped)

    # Step 1 & 2: parse + build graphs, run retrieval for both modes
    internal_results  = run_internal_benchmark(custom_questions=custom_internal)
    cross_repo_results = run_cross_repo_benchmark(custom_questions=custom_cross)

    # Step 5: console summary
    print_console_summary(internal_results, cross_repo_results)

    # Step 6: write Markdown report
    report_text = build_report(internal_results, cross_repo_results)
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    logger.info("Markdown report written to: %s", REPORT_PATH)

    # Step 7: write JSON report
    json_data = build_json(internal_results, cross_repo_results)
    JSON_REPORT_PATH.write_text(
        json.dumps(json_data, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("JSON report written to: %s", JSON_REPORT_PATH)


if __name__ == "__main__":
    main()
