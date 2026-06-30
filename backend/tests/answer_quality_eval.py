# tests/answer_quality_eval.py
"""
RepoGraphAI -- Answer Quality Evaluation
==========================================

Evaluates the quality of the final natural-language ANSWERS produced by the
full GraphRAG pipeline:

    Question
        |
        v
    QueryResolver            (unchanged -- via ContextBuilder)
        |
        v
    RepositoryRetriever       (unchanged -- via ContextBuilder)
        |
        v
    ContextBuilder            (unchanged)        -> ContextPackage
        |
        v
    GeminiLLMProvider         (unchanged)         -> generated answer
        |
        v
    LLM Judge (AnswerQualityJudge, app/evaluation/evaluator.py)
        |
        v
    answer_quality.json + answer_quality_report.md

This script is a pure *consumer* of the existing pipeline, in the same spirit
as ``tests/retrieval_benchmark.py``, ``tests/retrieval_metrics.py``, and
``tests/cross_repo_benchmark.py``:

- ``CodeParser``, ``GraphBuilder``, ``RepositoryCache``, ``build_context_builder``,
  ``GraphRAGEngine`` and ``GeminiLLMProvider`` are used exactly as-is.
- No retrieval logic, prompt logic, or ContextBuilder logic is touched.
- The benchmark *dataset* (questions + expected symbols) is imported directly
  from ``tests/retrieval_metrics.py`` -- the existing, already-measured
  retrieval benchmark -- rather than redefined. This script adds exactly one
  new piece of ground truth per question: ``expected_behaviour``, a short
  human-written description of what a correct answer should explain (see
  ``EXPECTED_BEHAVIOURS`` below). Nothing in ``tests/retrieval_metrics.py`` or
  ``tests/retrieval_benchmark.py`` is modified.
- The judge (a second Gemini call, via ``AnswerQualityJudge`` in
  ``app/evaluation/evaluator.py``) is shown ONLY the question, the expected
  behaviour, and the generated answer -- never the retrieved ranking,
  source nodes, or retrieval metadata. This keeps answer-quality evaluation
  independent of retrieval evaluation: a question could retrieve the "right"
  node and still get a bad answer (or vice versa), and the judge has no way
  to infer one from the other.

Dataset
-------
30 questions total, reusing the exact question set already used to produce
RepoGraphAI's retrieval metrics:

- 15 "internal" questions against RepoGraphAI's own ``app/`` package
  (categories: Parsing, Graph Construction, Analytics, Retrieval,
  Query Resolution, Context Building).
- 15 cross-repository questions, 5 each against FastAPI, Typer, and Requests
  (already cloned under ``repos/`` by the existing benchmark scripts).

Quota-efficient execution
--------------------------
Every question costs up to two Gemini calls (generate + judge). On the
Gemini free tier that is enough to start returning HTTP 429 after only
8-10 questions. This script is built to survive that:

- Every LLM call (generation AND judging) goes through
  ``RetryingLLMProvider`` (``app/evaluation/evaluator.py``), which retries
  on 429 with exponential backoff, paces requests with a configurable
  delay, and pauses for a longer cooldown after repeated consecutive
  rate-limit hits.
- Every completed answer/judgment is written to a checkpoint file
  (``tests/answer_quality_cache.json``) immediately, not just at the end.
  Re-running the script resumes from whatever is already cached --
  nothing already done is repeated unless ``--force`` is passed, and
  nothing in progress is lost if the process is killed or rate limited.
- Generation and judging can be run as two separate invocations
  (``--generate`` / ``--judge``), so a 30-question run can be spread over
  as many sessions as the free tier requires.
- A single failed question (generation or judging) never aborts the run --
  it's logged, skipped, and retried automatically on a later invocation.

Usage
-----
    cd backend
    python tests/answer_quality_eval.py                       # generate + judge everything not yet cached
    python tests/answer_quality_eval.py --generate             # answers only, cached for later judging
    python tests/answer_quality_eval.py --judge                # judge whatever has been generated so far
    python tests/answer_quality_eval.py --gemini-model gemini-2.5-flash
    python tests/answer_quality_eval.py --judge-model gemini-2.5-pro
    python tests/answer_quality_eval.py --echo                 # dry run, no API calls
    python tests/answer_quality_eval.py --limit 5               # first 5 questions of the (filtered) dataset
    python tests/answer_quality_eval.py --repository FastAPI    # only FastAPI questions
    python tests/answer_quality_eval.py --start 10 --end 20     # questions [10, 20) of the (filtered) dataset
    python tests/answer_quality_eval.py --force                 # ignore the cache, regenerate/rejudge
    python tests/answer_quality_eval.py --no-cache               # ignore cached repository graphs (unrelated to --force)
    python tests/answer_quality_eval.py --delay 5 --max-retries 8 --cooldown-seconds 90   # tune for a stricter quota

Requires the ``GOOGLE_API_KEY`` environment variable (or ``--api-key``) to be
set when not running with ``--echo``, since both answer generation and
judging go through ``GeminiLLMProvider`` by default.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.cache.repository_cache import RepositoryCache
from app.evaluation.evaluator import (
    AnswerQualityJudge,
    BenchmarkQuestion,
    EchoJudgeProvider,
    EvaluationResult,
    JudgeScores,
    RetryingLLMProvider,
    build_json_report,
    build_markdown_report,
    is_rate_limit_error,
)
from app.graph.graph_builder import GraphBuilder
from app.parsers.code_parser import CodeParser
from app.rag.context_builder import build_context_builder
from app.rag.graphrag_engine import (
    EchoLLMProvider,
    GeminiLLMProvider,
    GraphRAGEngine,
    GraphRAGPromptBuilder,
    LLMProvider,
)

# Reuse the existing, already-measured benchmark dataset -- no new questions
# are invented, and these files are never modified.
from tests.retrieval_metrics import (
    CROSS_REPO_QUESTIONS,
    INTERNAL_QUESTIONS,
    REPOS_DIR,
    REPOSITORIES,
)

# Reuse the existing repo-cloning helper rather than duplicating it.
from tests.cross_repo_benchmark import clone_repo

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("answer_quality_eval")

# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------

TESTS_DIR = Path(__file__).resolve().parent
JSON_REPORT_PATH = TESTS_DIR / "answer_quality.json"
MD_REPORT_PATH = TESTS_DIR / "answer_quality_report.md"
CHECKPOINT_PATH = TESTS_DIR / "answer_quality_cache.json"

INTERNAL_REPOSITORY_NAME = "RepoGraphAI"

# A non-rate-limit generation/judging failure is retried this many times
# (across separate script invocations) before being recorded permanently in
# the report as a real failure. Rate-limit failures never count against this
# -- they are always retried, since they say nothing about whether the
# question itself is answerable/judgeable.
MAX_NON_RATE_LIMIT_ATTEMPTS = 3

# ---------------------------------------------------------------------------
# Ground truth: expected behaviour per question
#
# This is the one new piece of ground truth this script adds on top of the
# existing retrieval benchmark. Each entry is a short, human-written
# description -- grounded in the actual implementation of the referenced
# symbol(s) -- of what a *correct* answer should explain. The LLM judge
# grades the generated answer against this description, never against exact
# wording, and never against expected_symbols (which are carried along only
# for traceability back to the retrieval benchmark).
#
# Keyed by the exact question text, which is unique across the full 30
# question dataset (verified against INTERNAL_QUESTIONS / CROSS_REPO_QUESTIONS
# below at import time).
# ---------------------------------------------------------------------------

EXPECTED_BEHAVIOURS: dict[str, str] = {
    # --- Internal: Parsing ---
    "How are files parsed?": (
        "CodeParser.parse_file reads a single Python file as UTF-8 text, parses it into an "
        "AST via ast.parse (raising a clear ValueError on a syntax error rather than crashing "
        "silently), and walks that AST to extract the file's classes, functions, and imports "
        "into a ParsedFile."
    ),
    "How are imports extracted?": (
        "CodeParser._extract_imports walks the top level of a module's AST collecting `import` "
        "and `from X import Y` statements into dotted module paths (e.g. \"os.path\"). Relative "
        "imports (`from .x import y`) are deliberately skipped because resolving them requires "
        "package context the parser does not have at this stage."
    ),
    "How are classes extracted?": (
        "CodeParser._extract_class takes an ast.ClassDef node, extracts its base classes, and "
        "walks the class body collecting any FunctionDef/AsyncFunctionDef children as methods "
        "(via extract_function), producing a ParsedClass with a name, base list, and method list."
    ),
    # --- Internal: Graph Construction ---
    "How is the graph generated?": (
        "GraphBuilder.build_graph takes a ParsedRepository and builds the master RepositoryGraph: "
        "it creates a node for every file, class, and function, and edges for the relationships "
        "between them (e.g. containment, calls, imports, inheritance)."
    ),
    "How are graph nodes created?": (
        "Node creation is done by an internal helper (nested inside build_graph) that adds a "
        "node -- representing a file, class, or function -- to the graph, keyed by a unique node "
        "id and deduplicated so the same symbol is never added twice."
    ),
    "How are graph edges created?": (
        "Edge creation is done by an internal helper (nested inside build_graph) that records a "
        "typed relationship (e.g. CALLS, IMPORTS, CONTAINS, INHERITS) between two node ids that "
        "already exist in the graph."
    ),
    "How is inheritance represented?": (
        "GraphBuilder.build_class_graph derives a class-only view of the master graph by "
        "connecting class nodes with INHERITS edges (plus INSTANTIATES/DECORATES), so class "
        "hierarchies can be queried or visualised independently of functions and files."
    ),
    # --- Internal: Analytics ---
    "How are hotspots calculated?": (
        "GraphBuilder.generate_statistics computes the most-connected nodes in the graph (ranked "
        "by edge degree) as part of its statistics output; these high-degree nodes act as a proxy "
        "for \"hotspots\" -- symbols that are heavily depended upon or tightly coupled to many "
        "others."
    ),
    "How are graph statistics generated?": (
        "GraphBuilder.generate_statistics computes total node/edge counts, counts broken down by "
        "node type and edge type, and the most-connected nodes, returning a GraphStatistics object "
        "summarising the whole graph."
    ),
    # --- Internal: Retrieval ---
    "How does retrieval work?": (
        "RepositoryRetriever.get_node_context is the universal entry point for retrieving context "
        "about a single node id: it returns a RetrievalResult bundling that node together with its "
        "relevant neighbours and relationships, used as the building block for answering questions "
        "about any node type."
    ),
    "How are neighbours retrieved?": (
        "RepositoryRetriever._collect_neighbours returns the deduplicated one-hop neighbours of a "
        "node by walking both the outgoing and incoming edge indexes, so callers get every directly "
        "connected node regardless of edge direction."
    ),
    "How is a subgraph extracted?": (
        "RepositoryRetriever.get_subgraph takes a set of node ids plus a max_hops limit and returns "
        "a new RepositoryGraph containing those nodes plus everything reachable within max_hops -- "
        "this is the focused slice of the graph that ultimately becomes the LLM's context."
    ),
    # --- Internal: Query Resolution ---
    "How does query resolution work?": (
        "QueryResolver.resolve_query is the main entry point: it takes a natural-language question, "
        "extracts keywords and detects intent, ranks candidate graph nodes against them, and returns "
        "a QueryResolutionResult containing the ranked list of matching nodes."
    ),
    "How are symbols ranked?": (
        "QueryResolver.rank_candidates scores candidate nodes against the question's extracted "
        "keywords and detected intent, producing an ordered list of QueryMatch objects (best match "
        "first) that downstream code uses to select the top_k nodes."
    ),
    # --- Internal: Context Building ---
    "How is LLM context built?": (
        "ContextBuilder.build(question, top_k, max_hops) resolves the question via QueryResolver, "
        "retrieves a subgraph around the resolved nodes via RepositoryRetriever, and assembles all "
        "of that into a ContextPackage -- including an llm_context string -- ready to be handed to "
        "an LLM provider."
    ),
    # --- FastAPI ---
    "How are routes registered?": (
        "Routes are registered on an APIRouter (or on a FastAPI app, which delegates to its own "
        "router) via add_api_route, which builds an APIRoute object from the path, endpoint "
        "function, HTTP methods, and dependencies, and appends it to the router's route list. "
        "add_route and add_api_websocket_route are the equivalent entry points for plain ASGI "
        "routes and websocket routes respectively."
    ),
    "How does dependency injection work?": (
        "FastAPI inspects a path operation function's signature via get_dependant to build a "
        "Dependant tree describing its parameters and any nested sub-dependencies. At request time, "
        "solve_dependencies recursively walks that tree -- calling sub-dependency callables and "
        "validating/injecting parameter values -- to produce the arguments ultimately passed into "
        "the endpoint function."
    ),
    "How are requests handled?": (
        "get_request_handler builds the ASGI callable used for a given route: it validates the "
        "incoming request, solves dependencies, calls the endpoint function, and serialises the "
        "result into a response. APIRoute.handle is the per-route ASGI entry point that this "
        "handler is wired into, and request_validation_exception_handler formats the 422 response "
        "returned when request validation fails."
    ),
    "How are responses generated?": (
        "serialize_response converts an endpoint's return value (respecting any declared "
        "response_model) into a JSON-serialisable structure; response classes such as "
        "ORJSONResponse and UJSONResponse then render that structure into the raw response bytes "
        "using their respective fast JSON encoders."
    ),
    "How are middleware components registered?": (
        "Middleware is registered either declaratively (the middleware list passed when "
        "constructing FastAPI) or imperatively via the FastAPI.middleware decorator / "
        "add_middleware. FastAPI.build_middleware_stack then assembles all registered middleware "
        "-- including the built-in AsyncExitStackMiddleware, which manages dependency cleanup -- "
        "into the final ASGI call chain."
    ),
    # --- Typer ---
    "How are CLI commands registered?": (
        "Commands are registered on a Typer app via the @app.command() decorator, which wraps the "
        "decorated function into a Click Command and adds it to the app's underlying Click Group. "
        "TyperGroup/TyperCLIGroup then expose listing (list_commands), formatting (format_commands), "
        "and resolution (_click_resolve_command) of those registered commands at runtime."
    ),
    "How are command arguments parsed?": (
        "Typer builds Click Arguments and Options from a function's type-annotated parameters -- "
        "TyperArgument._parse_decls determines an argument's declaration/name -- and registers them "
        "with an internal option parser (_OptionParser.add_argument). At invocation time, Click's "
        "Command.parse_args drives the actual parsing of sys.argv into resolved parameter values."
    ),
    "How are options defined?": (
        "Options are defined by converting typed function parameters that have defaults into Click "
        "Option objects. format_options (overridden by TyperCommand/TyperGroup) is responsible for "
        "rendering those options' listing/help text whenever --help is invoked."
    ),
    "How is help text generated?": (
        "Help text is derived primarily from a command's docstring. _get_help_text and "
        "_sanitize_help_text clean and format that docstring (handling whitespace and Click's tag "
        "stripping), and Command.format_help_text renders the final formatted text into the --help "
        "output."
    ),
    "How are callbacks executed?": (
        "Typer.callback() registers a function that runs before any of a Typer app's subcommands "
        "(typically for shared options or setup). get_callback wraps a function into the "
        "Click-compatible callable that Click actually invokes, and get_param_callback does the "
        "equivalent for individual parameter-level callbacks such as validation callbacks."
    ),
    # --- Requests ---
    "How are HTTP requests executed?": (
        "A Session prepares a PreparedRequest and passes it to Session.send, which looks up the "
        "appropriate transport adapter for the request's URL and calls HTTPAdapter.send to actually "
        "perform the HTTP request over urllib3 (using request_url to build the final request URL), "
        "wrapping the raw response into a Response object."
    ),
    "How are sessions managed?": (
        "Session.__init__ sets up persistent state -- cookies, default headers, mounted adapters, "
        "auth -- that is reused across multiple requests. The module-level session() factory "
        "function creates a Session for one-off use, and Session.send is the shared internal call "
        "that every public method (get/post/put/etc.) ultimately funnels through."
    ),
    "How are adapters used?": (
        "HTTPAdapter (implementing the abstract BaseAdapter interface) provides the actual HTTP "
        "transport -- connection pooling, retries, SSL handling -- and is mounted on a Session "
        "against a URL prefix. Session.get_adapter looks up the correct mounted adapter for a given "
        "request URL before the request is sent."
    ),
    "How are redirects handled?": (
        "After a response is received, Response.is_redirect checks the status code and Location "
        "header to detect a redirect. If one is found, SessionRedirectMixin.resolve_redirects "
        "generates each subsequent request needed to follow the redirect chain -- re-applying auth "
        "via hooks such as HTTPDigestAuth.handle_redirect -- up to the configured redirect limit."
    ),
    "How are responses processed?": (
        "Response.content lazily reads and caches the full response body in memory. "
        "Response.iter_content streams the body in chunks instead of loading it all at once, and "
        "stream_decode_response_unicode decodes those raw byte chunks into text using the "
        "response's detected or declared encoding."
    ),
}


# ---------------------------------------------------------------------------
# Dataset construction (reuses tests/retrieval_metrics.py question lists)
# ---------------------------------------------------------------------------

def build_dataset() -> list[BenchmarkQuestion]:
    """
    Build the full 30-question answer-quality dataset by combining:

      - ``INTERNAL_QUESTIONS`` (15 questions against RepoGraphAI's own code)
      - ``CROSS_REPO_QUESTIONS`` (15 questions, 5 each against FastAPI,
        Typer, Requests)

    both imported unmodified from ``tests/retrieval_metrics.py``, with
    ``expected_behaviour`` looked up from ``EXPECTED_BEHAVIOURS`` above.

    Raises
    ------
    KeyError
        If a question from the imported benchmark lists has no matching
        entry in ``EXPECTED_BEHAVIOURS`` -- fails loudly at startup rather
        than silently evaluating with missing ground truth.
    """
    dataset: list[BenchmarkQuestion] = []

    for item in INTERNAL_QUESTIONS:
        question = item["question"]
        dataset.append(
            BenchmarkQuestion(
                repository=INTERNAL_REPOSITORY_NAME,
                category=item["category"],
                question=question,
                expected_symbols=list(item["expected_symbols"]),
                expected_behaviour=EXPECTED_BEHAVIOURS[question],
            )
        )

    for repo_name, items in CROSS_REPO_QUESTIONS.items():
        for item in items:
            question = item["question"]
            dataset.append(
                BenchmarkQuestion(
                    repository=repo_name,
                    category=repo_name,
                    question=question,
                    expected_symbols=list(item["expected_symbols"]),
                    expected_behaviour=EXPECTED_BEHAVIOURS[question],
                )
            )

    return dataset


def filter_dataset(
    dataset: list[BenchmarkQuestion],
    *,
    repository: Optional[str] = None,
    start: Optional[int] = None,
    end: Optional[int] = None,
    limit: Optional[int] = None,
) -> list[BenchmarkQuestion]:
    """
    Apply the CLI's subset-selection flags to *dataset*, in a fixed order:

    1. ``--repository`` -- keep only questions for one repository
       (case-insensitive match against ``BenchmarkQuestion.repository``,
       e.g. "fastapi" matches "FastAPI").
    2. ``--start`` / ``--end`` -- a plain Python slice, ``dataset[start:end]``,
       applied to whatever the repository filter left.
    3. ``--limit`` -- keep only the first N questions of whatever is left
       after the above.

    Every flag is optional and independent -- e.g. ``--repository FastAPI
    --limit 2`` runs only the first 2 FastAPI questions.
    """
    result = dataset

    if repository is not None:
        wanted = repository.strip().lower()
        result = [bq for bq in result if bq.repository.strip().lower() == wanted]
        if not result:
            known = sorted({bq.repository for bq in dataset})
            raise ValueError(
                f"--repository {repository!r} matched no questions. "
                f"Known repositories: {', '.join(known)}"
            )

    if start is not None or end is not None:
        result = result[start:end]

    if limit is not None:
        result = result[:limit]

    return result


# ---------------------------------------------------------------------------
# Checkpointing / caching
#
# Every completed answer and every completed judgment is written to
# CHECKPOINT_PATH immediately (i.e. after every single question, not just at
# the end of the run). Re-running the script -- whether because it was
# interrupted, rate limited, or simply because the user is splitting a
# 30-question run across several free-tier sessions -- reads this file back
# in and skips anything already cached, so nothing is ever regenerated or
# re-judged unless --force is passed.
# ---------------------------------------------------------------------------

def _checkpoint_key(repository: str, question: str) -> str:
    """Stable per-question cache key. Includes repository to be extra-safe
    even though question text is already unique dataset-wide (see
    ``EXPECTED_BEHAVIOURS`` docstring)."""
    return f"{repository}::{question}"


@dataclass
class CheckpointStore:
    """
    Disk-backed cache of generated answers and judge results, keyed per
    question. Saves itself to disk on every mutation (``set_answer`` /
    ``set_judgment``) so progress is never lost -- this *is* the
    checkpointing mechanism requirement 4 asks for.

    File format (``answer_quality_cache.json``)::

        {
          "answers": {
            "<repository>::<question>": {
              "status": "done" | "pending" | "failed",
              "attempts": <int>,
              "repository": ..., "category": ..., "question": ...,
              "expected_symbols": [...], "expected_behaviour": ...,
              "generated_answer": ..., "retrieved_node_count": ...,
              "last_error": ..., "updated_at": "..."
            }, ...
          },
          "judgments": {
            "<repository>::<question>": {
              "status": "done" | "pending",
              "attempts": <int>,
              "scores": {...}, "reason": ..., "passed": ...,
              "judge_error": ..., "generation_error": ...,
              "retrieved_node_count": ..., "updated_at": "..."
            }, ...
          }
        }

    "done" means usable as-is in the final report. "pending" means a
    previous attempt failed (often a rate limit) and should be retried.
    "failed" (answers only) means it failed repeatedly for a *non*
    rate-limit reason and is now recorded permanently, so the report still
    completes instead of retrying a genuinely broken question forever.
    """

    path: Path
    answers: dict = field(default_factory=dict)
    judgments: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "CheckpointStore":
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                return cls(
                    path=path,
                    answers=raw.get("answers", {}),
                    judgments=raw.get("judgments", {}),
                )
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "Could not read checkpoint file %s (%s) -- starting fresh.", path, exc
                )
        return cls(path=path)

    def save(self) -> None:
        """Atomic write: write to a temp file, then rename over the real
        path, so a crash mid-write never corrupts the checkpoint."""
        payload = {"answers": self.answers, "judgments": self.judgments}
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        tmp_path.replace(self.path)

    # -- answers ----------------------------------------------------------

    def get_answer(self, repository: str, question: str) -> Optional[dict]:
        return self.answers.get(_checkpoint_key(repository, question))

    def set_answer(self, repository: str, question: str, entry: dict) -> None:
        entry["updated_at"] = datetime.now().isoformat()
        self.answers[_checkpoint_key(repository, question)] = entry
        self.save()

    # -- judgments ----------------------------------------------------------

    def get_judgment(self, repository: str, question: str) -> Optional[dict]:
        return self.judgments.get(_checkpoint_key(repository, question))

    def set_judgment(self, repository: str, question: str, entry: dict) -> None:
        entry["updated_at"] = datetime.now().isoformat()
        self.judgments[_checkpoint_key(repository, question)] = entry
        self.save()


# ---------------------------------------------------------------------------
# Engine construction -- mirrors tests/cross_repo_benchmark.py build_engine
# ---------------------------------------------------------------------------

def repository_path_for(repository: str) -> Path:
    if repository == INTERNAL_REPOSITORY_NAME:
        return PROJECT_ROOT / "app"

    repo_path = REPOS_DIR / repository.lower()
    if not repo_path.exists():
        url = REPOSITORIES[repository]
        repo_path = clone_repo(repository, url)
    return repo_path


def build_engine(
    repo_path: Path,
    llm_provider: LLMProvider,
    *,
    no_cache: bool = False,
) -> GraphRAGEngine:
    """
    Parse (or load from cache) *repo_path* and wire up a GraphRAGEngine.

    Identical pipeline to ``app/examples/graphrag_example_usage.py`` and
    ``tests/cross_repo_benchmark.py``: RepositoryCache -> CodeParser ->
    GraphBuilder -> build_context_builder -> GraphRAGEngine. No retrieval
    parameters are changed from those scripts' defaults (top_k=5, max_hops=1).
    """
    cache = RepositoryCache(str(repo_path))
    graph = None

    if not no_cache:
        fingerprint = cache.compute_fingerprint()
        validation = cache.is_cache_valid(fingerprint)
        if validation.is_valid:
            graph = cache.load()
            logger.info("[Cache] Loaded repository graph for %s", repo_path)

    if graph is None:
        logger.info("Parsing repository: %s", repo_path)
        parsed_repository = CodeParser().parse_repository(str(repo_path))
        logger.info("Building knowledge graph...")
        graph = GraphBuilder().build_graph(parsed_repository)
        if not no_cache:
            cache.save(graph, cache.compute_fingerprint())
            logger.info("[Cache] Graph cached for %s", repo_path)

    context_builder = build_context_builder(graph, top_k=5, max_hops=1)
    engine = GraphRAGEngine(context_builder, llm_provider, GraphRAGPromptBuilder())
    return engine


# ---------------------------------------------------------------------------
# Generation phase -- "python tests/answer_quality_eval.py --generate"
#
# Calls the real GraphRAG pipeline (engine.answer()) for every selected
# question that is not already cached as "done", and writes each result to
# the checkpoint immediately. Never makes a judge call.
# ---------------------------------------------------------------------------

def run_generation(
    dataset: list[BenchmarkQuestion],
    *,
    answer_provider: LLMProvider,
    checkpoint: CheckpointStore,
    no_cache: bool = False,
    force: bool = False,
) -> None:
    by_repo: dict[str, list[BenchmarkQuestion]] = {}
    for bq in dataset:
        by_repo.setdefault(bq.repository, []).append(bq)

    for repository, questions in by_repo.items():
        pending = [
            bq
            for bq in questions
            if force
            or (checkpoint.get_answer(bq.repository, bq.question) or {}).get("status") != "done"
        ]
        if not pending:
            logger.info("[%s] All %d questions already have cached answers -- skipping.", repository, len(questions))
            continue

        logger.info("=" * 70)
        logger.info("Repository: %s (%d/%d questions need answers)", repository, len(pending), len(questions))
        logger.info("=" * 70)

        try:
            repo_path = repository_path_for(repository)
            engine = build_engine(repo_path, answer_provider, no_cache=no_cache)
        except Exception:
            err = str(sys.exc_info()[1])
            logger.exception(
                "Setup failed for %s -- its questions stay unanswered and will be retried on the next run.",
                repository,
            )
            continue

        for bq in pending:
            existing = checkpoint.get_answer(bq.repository, bq.question) or {}
            attempts = existing.get("attempts", 0)

            logger.info("Q [%s]: %s", repository, bq.question)
            t0 = time.perf_counter()
            try:
                response = engine.answer(bq.question)
                elapsed = time.perf_counter() - t0
                logger.info("  -> answered in %.2fs (%d source nodes)", elapsed, len(response.source_nodes))
                checkpoint.set_answer(
                    bq.repository,
                    bq.question,
                    {
                        "status": "done",
                        "attempts": attempts + 1,
                        "repository": bq.repository,
                        "category": bq.category,
                        "question": bq.question,
                        "expected_symbols": bq.expected_symbols,
                        "expected_behaviour": bq.expected_behaviour,
                        "generated_answer": response.answer,
                        "retrieved_node_count": len(response.source_nodes),
                        "last_error": None,
                    },
                )
            except Exception as exc:
                attempts += 1
                rate_limited = is_rate_limit_error(exc)
                if rate_limited:
                    logger.error("  -> rate limited; will retry on a later run: %s", exc)
                    status = "pending"
                elif attempts < MAX_NON_RATE_LIMIT_ATTEMPTS:
                    logger.error(
                        "  -> generation failed (attempt %d/%d); will retry on a later run: %s",
                        attempts, MAX_NON_RATE_LIMIT_ATTEMPTS, exc,
                    )
                    status = "pending"
                else:
                    logger.error(
                        "  -> generation failed %d times; recording as a permanent failure: %s",
                        attempts, exc,
                    )
                    status = "failed"
                checkpoint.set_answer(
                    bq.repository,
                    bq.question,
                    {
                        "status": status,
                        "attempts": attempts,
                        "repository": bq.repository,
                        "category": bq.category,
                        "question": bq.question,
                        "expected_symbols": bq.expected_symbols,
                        "expected_behaviour": bq.expected_behaviour,
                        "generated_answer": "",
                        "retrieved_node_count": None,
                        "last_error": str(exc),
                    },
                )
                # Never abort the whole run because of one question -- continue.
                continue


# ---------------------------------------------------------------------------
# Judging phase -- "python tests/answer_quality_eval.py --judge"
#
# Judges every selected question whose answer is already cached ("done" or
# permanently "failed"), skipping anything not yet generated. Never calls
# engine.answer() / the GraphRAG pipeline.
# ---------------------------------------------------------------------------

def run_judging(
    dataset: list[BenchmarkQuestion],
    *,
    judge: AnswerQualityJudge,
    checkpoint: CheckpointStore,
    force: bool = False,
) -> None:
    for bq in dataset:
        answer_entry = checkpoint.get_answer(bq.repository, bq.question)
        if answer_entry is None or answer_entry.get("status") not in ("done", "failed"):
            logger.warning(
                "[%s] No generated answer cached yet for %r -- run with --generate first. Skipping.",
                bq.repository, bq.question,
            )
            continue

        judgment_entry = checkpoint.get_judgment(bq.repository, bq.question)
        if judgment_entry is not None and judgment_entry.get("status") == "done" and not force:
            continue  # already judged

        if answer_entry["status"] == "failed":
            # Permanent generation failure -- judge.evaluate() skips the LLM
            # call entirely for these (nothing to judge), so this is free.
            result = judge.evaluate(bq, "", generation_error=answer_entry.get("last_error") or "Answer generation failed.")
            checkpoint.set_judgment(
                bq.repository,
                bq.question,
                {
                    "status": "done",
                    "attempts": (judgment_entry or {}).get("attempts", 0) + 1,
                    "scores": result.scores.as_dict(),
                    "reason": result.reason,
                    "passed": result.passed,
                    "judge_error": result.judge_error,
                    "generation_error": result.generation_error,
                    "retrieved_node_count": result.retrieved_node_count,
                },
            )
            continue

        attempts = (judgment_entry or {}).get("attempts", 0)
        logger.info("Judging [%s]: %s", bq.repository, bq.question)
        result = judge.evaluate(
            bq,
            answer_entry.get("generated_answer", ""),
            retrieved_node_count=answer_entry.get("retrieved_node_count"),
        )

        if result.judge_error and is_rate_limit_error(result.judge_error):
            attempts += 1
            logger.error("  -> judge call rate limited; will retry on a later run.")
            checkpoint.set_judgment(
                bq.repository,
                bq.question,
                {"status": "pending", "attempts": attempts},
            )
            continue

        logger.info("  -> overall=%d/5 passed=%s", result.scores.overall, result.passed)
        checkpoint.set_judgment(
            bq.repository,
            bq.question,
            {
                "status": "done",
                "attempts": attempts + 1,
                "scores": result.scores.as_dict(),
                "reason": result.reason,
                "passed": result.passed,
                "judge_error": result.judge_error,
                "generation_error": result.generation_error,
                "retrieved_node_count": result.retrieved_node_count,
            },
        )


# ---------------------------------------------------------------------------
# Report assembly -- turns whatever is currently in the checkpoint into the
# same EvaluationResult shape run_evaluation() used to build directly, so
# build_json_report()/build_markdown_report() (unchanged) produce exactly
# the same report format as before. Questions not yet judged are omitted
# and counted separately, so a partial run produces a partial-but-correctly
# -shaped report rather than crashing or inventing placeholder scores.
# ---------------------------------------------------------------------------

def collect_results(
    dataset: list[BenchmarkQuestion],
    checkpoint: CheckpointStore,
) -> tuple[list[EvaluationResult], int]:
    results: list[EvaluationResult] = []
    incomplete = 0

    for bq in dataset:
        judgment_entry = checkpoint.get_judgment(bq.repository, bq.question)
        if judgment_entry is None or judgment_entry.get("status") != "done":
            incomplete += 1
            continue

        answer_entry = checkpoint.get_answer(bq.repository, bq.question) or {}
        scores_dict = judgment_entry.get("scores") or {}
        results.append(
            EvaluationResult(
                question=bq.question,
                repository=bq.repository,
                category=bq.category,
                expected_symbols=bq.expected_symbols,
                expected_behaviour=bq.expected_behaviour,
                generated_answer=answer_entry.get("generated_answer", ""),
                scores=JudgeScores(
                    correctness=scores_dict.get("correctness", 1),
                    groundedness=scores_dict.get("groundedness", 1),
                    completeness=scores_dict.get("completeness", 1),
                    hallucination=scores_dict.get("hallucination", 1),
                    overall=scores_dict.get("overall", 1),
                ),
                reason=judgment_entry.get("reason", ""),
                passed=bool(judgment_entry.get("passed", False)),
                judge_error=judgment_entry.get("judge_error"),
                generation_error=judgment_entry.get("generation_error"),
                retrieved_node_count=judgment_entry.get("retrieved_node_count"),
            )
        )

    return results, incomplete


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="RepoGraphAI answer-quality evaluation.")
    parser.add_argument("--gemini-model", default="gemini-2.5-flash", help="Gemini model used to GENERATE answers.")
    parser.add_argument(
        "--judge-model",
        default=None,
        help="Gemini model used to JUDGE answers. Defaults to --gemini-model if omitted.",
    )
    parser.add_argument("--api-key", default=None, help="Explicit GOOGLE_API_KEY override.")
    parser.add_argument(
        "--echo",
        action="store_true",
        help="Dry run: use EchoLLMProvider for generation and EchoJudgeProvider for judging. "
        "No network calls, no API key required. Produces correctly-shaped reports with "
        "clearly-labelled placeholder scores, for testing the harness itself.",
    )
    parser.add_argument("--no-cache", action="store_true", help="Ignore any cached repository graphs.")

    parser.add_argument(
        "--generate", action="store_true", help="Only generate answers (and cache them). Skips judging.",
    )
    parser.add_argument(
        "--judge", action="store_true", help="Only judge previously generated answers. Skips generation.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Ignore the answer/judgment cache: regenerate and/or rejudge everything selected.",
    )
    parser.add_argument(
        "--cache-file", type=Path, default=None,
        help=f"Checkpoint file path (default: {CHECKPOINT_PATH}).",
    )

    parser.add_argument("--limit", type=int, default=None, help="Keep only the first N questions of the (filtered) dataset.")
    parser.add_argument("--repository", default=None, help="Keep only questions for one repository, e.g. FastAPI.")
    parser.add_argument("--start", type=int, default=None, help="Start index (inclusive) of the dataset slice.")
    parser.add_argument("--end", type=int, default=None, help="End index (exclusive) of the dataset slice.")

    parser.add_argument("--delay", type=float, default=2.0, help="Minimum seconds between consecutive LLM requests.")
    parser.add_argument("--max-retries", type=int, default=5, help="Max retries per request after a rate-limit error.")
    parser.add_argument("--initial-backoff", type=float, default=5.0, help="Initial backoff (seconds) before the first retry.")
    parser.add_argument("--max-backoff", type=float, default=120.0, help="Upper bound (seconds) on a single backoff sleep.")
    parser.add_argument(
        "--cooldown-after", type=int, default=3,
        help="Consecutive rate-limit errors that trigger one longer cooldown pause.",
    )
    parser.add_argument("--cooldown-seconds", type=float, default=60.0, help="Length of that cooldown pause, in seconds.")

    args = parser.parse_args()

    full_dataset = build_dataset()
    try:
        dataset = filter_dataset(
            full_dataset, repository=args.repository, start=args.start, end=args.end, limit=args.limit,
        )
    except ValueError as exc:
        logger.error(str(exc))
        sys.exit(2)

    logger.info("RepoGraphAI -- Answer Quality Evaluation")
    logger.info("Questions selected: %d (of %d total)", len(dataset), len(full_dataset))

    checkpoint = CheckpointStore.load(args.cache_file or CHECKPOINT_PATH)
    logger.info("Checkpoint file: %s", checkpoint.path)

    do_generate = args.generate or not args.judge
    do_judge = args.judge or not args.generate

    if args.echo:
        logger.info("Running in --echo dry-run mode: no real LLM calls will be made.")
        answer_provider: LLMProvider = EchoLLMProvider()
        judge_provider: LLMProvider = EchoJudgeProvider()
    else:
        judge_model = args.judge_model or args.gemini_model
        logger.info("Answer generation model: %s", args.gemini_model)
        logger.info("Judge model: %s", judge_model)
        retry_kwargs = dict(
            request_delay_seconds=args.delay,
            max_retries=args.max_retries,
            initial_backoff_seconds=args.initial_backoff,
            max_backoff_seconds=args.max_backoff,
            cooldown_after_consecutive_failures=args.cooldown_after,
            cooldown_seconds=args.cooldown_seconds,
        )
        # Each provider gets its own RetryingLLMProvider instance so the two
        # request streams (generation vs. judging) are paced/retried
        # independently of each other.
        answer_provider = RetryingLLMProvider(
            GeminiLLMProvider(model=args.gemini_model, api_key=args.api_key), **retry_kwargs,
        )
        judge_provider = RetryingLLMProvider(
            GeminiLLMProvider(model=judge_model, api_key=args.api_key), **retry_kwargs,
        )

    judge = AnswerQualityJudge(judge_provider)

    if do_generate:
        run_generation(
            dataset, answer_provider=answer_provider, checkpoint=checkpoint,
            no_cache=args.no_cache, force=args.force,
        )
    if do_judge:
        run_judging(dataset, judge=judge, checkpoint=checkpoint, force=args.force)

    results, incomplete = collect_results(dataset, checkpoint)
    if incomplete:
        logger.warning(
            "%d/%d selected questions are not yet fully generated+judged -- "
            "this report only reflects the %d that are complete. Re-run to pick up where you left off.",
            incomplete, len(dataset), len(results),
        )

    generated_at = datetime.now().isoformat()

    json_report = build_json_report(results, generated_at=generated_at)
    JSON_REPORT_PATH.write_text(json.dumps(json_report, indent=2, default=str), encoding="utf-8")
    logger.info("JSON report written to: %s", JSON_REPORT_PATH)

    md_report = build_markdown_report(results, generated_at=generated_at)
    MD_REPORT_PATH.write_text(md_report, encoding="utf-8")
    logger.info("Markdown report written to: %s", MD_REPORT_PATH)

    summary = json_report["summary"]
    logger.info(
        "Summary: count=%d passed=%d pass_rate=%.1f%% "
        "avg_correctness=%.2f avg_groundedness=%.2f avg_completeness=%.2f "
        "avg_hallucination=%.2f avg_overall=%.2f",
        summary["count"],
        summary["passed"],
        summary["pass_rate"] * 100,
        summary["averages"]["correctness"],
        summary["averages"]["groundedness"],
        summary["averages"]["completeness"],
        summary["averages"]["hallucination"],
        summary["averages"]["overall"],
    )

    if incomplete == 0 and summary["count"] > 0 and summary["passed"] == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()