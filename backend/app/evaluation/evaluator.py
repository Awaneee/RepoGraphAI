"""
app/evaluation/evaluator.py
============================
Answer-quality evaluation for RepoGraphAI's GraphRAG pipeline.

This module is the *generic, reusable* half of answer-quality evaluation.
It knows nothing about any specific repository, benchmark question set, or
CLI -- that orchestration lives in ``tests/answer_quality_eval.py``, mirroring
how ``app/rag/graphrag_engine.py`` (orchestration-light, generic) is kept
separate from the benchmark scripts that drive it.

What lives here
----------------
- ``BenchmarkQuestion``   -- one ground-truth row: question + expected
  symbol(s) + expected behaviour (no exact-wording answer is ever stored).
- ``JudgeScores`` / ``EvaluationResult`` -- the structured output of judging
  a single generated answer.
- ``AnswerQualityJudge``  -- wraps any ``LLMProvider`` (the same abstract
  interface ``GraphRAGEngine`` already uses -- see ``app/rag/graphrag_engine.py``)
  to act as an LLM-as-judge. The judge is given only the question, the
  expected behaviour, and the generated answer. It is **never** shown the
  retrieved ranking, source nodes, or retrieval metadata, so it cannot
  reward an answer just because retrieval happened to surface the "right"
  nodes -- it can only judge the answer text itself.
- ``EchoJudgeProvider``   -- a dependency-free, deterministic stand-in judge
  (mirrors ``EchoLLMProvider`` in ``graphrag_engine.py``) for dry-running the
  harness without burning API calls or requiring a key.
- Report builders -- turn a list of ``EvaluationResult`` into the Markdown
  and JSON reports the evaluation script writes to disk.

Design principles (mirrors graphrag_engine.py)
-----------------------------------------------
- No retrieval or generation logic lives here. This module only judges
  answers it is handed; it never calls ``ContextBuilder`` or
  ``GraphRAGEngine`` itself.
- The judge LLM is a pluggable boundary via the existing ``LLMProvider``
  interface -- no new provider abstraction is introduced.
- Deterministic everywhere except the judge call itself.
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
from dataclasses import dataclass
from typing import Optional

from app.rag.graphrag_engine import LLMProvider

logger = logging.getLogger("answer_quality_eval.evaluator")


# ===========================================================================
# Quota-efficient execution: rate-limit detection + retrying LLM provider
#
# This is generic infrastructure for *any* ``LLMProvider`` -- it knows
# nothing about answer-quality judging specifically, in the same spirit as
# the rest of this module. It exists so a free-tier API (Gemini's free tier
# is the motivating case) can be driven without manual retries: every call
# through a ``RetryingLLMProvider`` automatically backs off and retries on
# HTTP 429 / quota-exhausted responses instead of bubbling the error straight
# up to the caller after a single attempt.
# ===========================================================================

_RATE_LIMIT_STATUS_CODES = {429}
_RATE_LIMIT_KEYWORDS = (
    "429",
    "resource_exhausted",
    "rate limit",
    "rate_limit",
    "too many requests",
    "quota",
)


def is_rate_limit_error(exc_or_message: "Exception | str") -> bool:
    """
    Best-effort, provider-agnostic detection of a rate-limit / quota error.

    Checks, in order:
    1. A numeric ``code`` or ``status_code`` attribute equal to 429 (this
       covers ``google.genai.errors.APIError`` -- raised by
       ``GeminiLLMProvider`` -- which carries ``.code`` and ``.status``,
       e.g. ``code=429, status="RESOURCE_EXHAUSTED"``).
    2. A ``status`` attribute containing "RESOURCE_EXHAUSTED".
    3. Keyword matching over ``str(exc_or_message)`` for the common phrases
       different providers use for rate limiting (429, quota, "too many
       requests", etc).

    Accepts either an exception instance or a plain string (e.g. an already
    -stringified ``judge_error``), so the same check can be reused both at
    the point an exception is caught and later, when deciding whether a
    cached ``judge_error`` string represents a transient rate limit that
    should be retried rather than recorded permanently.
    """
    if isinstance(exc_or_message, str):
        message = exc_or_message
        code = None
        status = None
    else:
        message = str(exc_or_message)
        code = getattr(exc_or_message, "code", None)
        status = getattr(exc_or_message, "status", None)

    if isinstance(code, int) and code in _RATE_LIMIT_STATUS_CODES:
        return True
    status_code = getattr(exc_or_message, "status_code", None)
    if isinstance(status_code, int) and status_code in _RATE_LIMIT_STATUS_CODES:
        return True
    if isinstance(status, str) and "resource_exhausted" in status.lower():
        return True

    lowered = message.lower()
    return any(keyword in lowered for keyword in _RATE_LIMIT_KEYWORDS)


class RetryingLLMProvider(LLMProvider):
    """
    Wraps any ``LLMProvider`` to make it quota-efficient: automatic
    exponential-backoff retry on rate-limit errors, a minimum delay enforced
    between consecutive requests, and a longer automatic "cooldown" pause if
    several rate-limit errors happen back-to-back (a sign the whole quota
    window is exhausted, not just a single unlucky request).

    This is the *only* place retry/backoff/pacing logic lives -- it has
    nothing to do with judging or report-building, and wraps the existing
    ``LLMProvider`` interface rather than introducing a new one, so it can
    sit in front of ``GeminiLLMProvider`` (or any other provider) with zero
    changes to ``GraphRAGEngine`` or ``AnswerQualityJudge``, both of which
    only ever see the abstract ``LLMProvider.generate`` contract.

    Parameters
    ----------
    inner : LLMProvider
        The real provider to call (e.g. ``GeminiLLMProvider``).
    request_delay_seconds : float
        Minimum time to wait between the start of one request and the next,
        enforced even on the very first call after a long idle period.
        Spaces out requests proactively so free-tier per-minute limits are
        less likely to be hit in the first place.
    max_retries : int
        Maximum number of retry attempts for a single ``generate()`` call
        after a rate-limit error, before giving up and letting the error
        propagate to the caller.
    initial_backoff_seconds : float
        Backoff before the first retry.
    backoff_multiplier : float
        Growth factor applied to the backoff after each retry.
    max_backoff_seconds : float
        Upper bound on a single backoff sleep, however many retries have
        accumulated.
    cooldown_after_consecutive_failures : int
        Number of consecutive rate-limit errors (across calls, not just
        within one call's retries) that triggers a single longer cooldown
        pause -- a signal the whole quota window, not just one request, is
        exhausted.
    cooldown_seconds : float
        Length of that cooldown pause.
    """

    def __init__(
        self,
        inner: LLMProvider,
        *,
        request_delay_seconds: float = 2.0,
        max_retries: int = 5,
        initial_backoff_seconds: float = 5.0,
        backoff_multiplier: float = 2.0,
        max_backoff_seconds: float = 120.0,
        cooldown_after_consecutive_failures: int = 3,
        cooldown_seconds: float = 60.0,
    ) -> None:
        self._inner = inner
        self._request_delay = max(0.0, request_delay_seconds)
        self._max_retries = max(0, max_retries)
        self._initial_backoff = max(0.0, initial_backoff_seconds)
        self._backoff_multiplier = max(1.0, backoff_multiplier)
        self._max_backoff = max(self._initial_backoff, max_backoff_seconds)
        self._cooldown_after = max(1, cooldown_after_consecutive_failures)
        self._cooldown_seconds = max(0.0, cooldown_seconds)

        self._last_call_monotonic: Optional[float] = None
        self._consecutive_rate_limits = 0

    def _wait_for_pacing(self) -> None:
        """Enforce ``request_delay_seconds`` between the start of consecutive calls."""
        if self._last_call_monotonic is None:
            return
        elapsed = time.monotonic() - self._last_call_monotonic
        remaining = self._request_delay - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        self._wait_for_pacing()
        self._last_call_monotonic = time.monotonic()

        attempt = 0
        backoff = self._initial_backoff
        while True:
            try:
                result = self._inner.generate(
                    system_prompt=system_prompt, user_prompt=user_prompt
                )
                self._consecutive_rate_limits = 0
                return result
            except Exception as exc:  # noqa: BLE001 - inspected, re-raised if not rate-limit
                if not is_rate_limit_error(exc):
                    raise

                attempt += 1
                self._consecutive_rate_limits += 1

                if self._consecutive_rate_limits >= self._cooldown_after:
                    logger.warning(
                        "Hit %d consecutive rate-limit errors -- pausing %.0fs "
                        "(quota window is likely fully exhausted, not just one request).",
                        self._consecutive_rate_limits,
                        self._cooldown_seconds,
                    )
                    time.sleep(self._cooldown_seconds)
                    self._consecutive_rate_limits = 0

                if attempt > self._max_retries:
                    logger.error(
                        "Rate-limited %d times in a row; giving up on this request "
                        "(it will be retried on the next run).",
                        attempt - 1,
                    )
                    raise

                sleep_time = min(backoff, self._max_backoff) + random.uniform(0, 1)
                logger.warning(
                    "Rate limited (attempt %d/%d). Backing off %.1fs before retrying. (%s)",
                    attempt,
                    self._max_retries,
                    sleep_time,
                    exc,
                )
                time.sleep(sleep_time)
                backoff *= self._backoff_multiplier
                self._last_call_monotonic = time.monotonic()


# ===========================================================================
# Ground-truth dataset model
# ===========================================================================

@dataclass(frozen=True)
class BenchmarkQuestion:
    """
    One row of the answer-quality ground-truth dataset.

    Deliberately mirrors the shape already used by
    ``tests/retrieval_metrics.py`` (``category``/``question``/
    ``expected_symbols``) plus one new field, ``expected_behaviour`` -- a
    short, human-written description of what a correct answer should say.
    The generated answer is graded against this description, not against
    exact wording, and not against ``expected_symbols`` (those are recorded
    purely as a traceability aid back to the retrieval benchmark).
    """

    repository: str
    category: str
    question: str
    expected_symbols: list[str]
    expected_behaviour: str


# ===========================================================================
# Judge output models
# ===========================================================================

SCORE_FIELDS = ("correctness", "groundedness", "completeness", "hallucination", "overall")


@dataclass
class JudgeScores:
    """1-5 integer scores produced by the LLM judge for one answer."""

    correctness: int
    groundedness: int
    completeness: int
    hallucination: int
    overall: int

    def as_dict(self) -> dict:
        return {f: getattr(self, f) for f in SCORE_FIELDS}


def _fallback_scores() -> JudgeScores:
    """
    Used only when the judge call fails outright or returns something that
    cannot be parsed as the expected JSON shape. Scored at the bottom of the
    scale (1) rather than omitted, so a broken judge call always shows up as
    a clear failure in the aggregate report instead of silently vanishing
    from the averages.
    """
    return JudgeScores(correctness=1, groundedness=1, completeness=1, hallucination=1, overall=1)


@dataclass
class EvaluationResult:
    """Everything recorded for one evaluated question, ready to serialise."""

    question: str
    repository: str
    category: str
    expected_symbols: list[str]
    expected_behaviour: str
    generated_answer: str
    scores: JudgeScores
    reason: str
    passed: bool

    judge_error: Optional[str] = None
    generation_error: Optional[str] = None

    retrieved_node_count: Optional[int] = None
    """
    Recorded for diagnostics / report-building only. Never passed to the
    judge -- see ``AnswerQualityJudge.judge`` for the enforced separation.
    """

    def to_json_dict(self) -> dict:
        return {
            "question": self.question,
            "repository": self.repository,
            "category": self.category,
            "expected_symbols": self.expected_symbols,
            "expected_behaviour": self.expected_behaviour,
            "generated_answer": self.generated_answer,
            "scores": self.scores.as_dict(),
            "reason": self.reason,
            "passed": self.passed,
            "judge_error": self.judge_error,
            "generation_error": self.generation_error,
            "retrieved_node_count": self.retrieved_node_count,
        }


# ===========================================================================
# LLM judge
# ===========================================================================

PASS_THRESHOLD = 4
"""
An answer "passes" when the judge's overall score is >= this value on the
1-5 scale, AND the judge did not flag a hallucination risk worse than the
same threshold. See ``AnswerQualityJudge._passed`` for the exact rule.
"""

JUDGE_SYSTEM_PROMPT = """\
You are a strict, impartial evaluator of an AI coding assistant's answers \
about a software repository.

You will be given:
1. QUESTION -- a natural-language question about the repository.
2. EXPECTED BEHAVIOUR -- a short description, written by a human reviewer, \
of what a correct, complete answer should explain. This is a description \
of behaviour, not a literal answer key -- a correct answer does not need to \
match its wording.
3. GENERATED ANSWER -- the answer actually produced by the system under \
test.

You are NOT shown what the system retrieved or how it ranked anything. \
Judge only the GENERATED ANSWER text against the EXPECTED BEHAVIOUR and \
your own knowledge of how software systems like this typically work.

Score the GENERATED ANSWER on five dimensions, each on a 1-5 integer scale \
(1 = very poor, 5 = excellent):

- correctness: Does the answer accurately describe the behaviour in \
EXPECTED BEHAVIOUR, with no factual errors?
- groundedness: Does the answer sound grounded in real, specific repository \
detail (symbol names, mechanisms, file-level reasoning) rather than vague, \
generic, or templated text?
- completeness: Does the answer cover the important parts of EXPECTED \
BEHAVIOUR, or does it leave out significant pieces?
- hallucination: Rate the ABSENCE of hallucination -- 5 means the answer \
invents nothing, 1 means it confidently states specifics (function names, \
file paths, behaviour) that are very likely fabricated or contradict \
EXPECTED BEHAVIOUR.
- overall: Your holistic judgment of answer quality for a developer relying \
on this answer.

Respond with ONLY a single JSON object and nothing else -- no markdown code \
fences, no preamble, no commentary outside the JSON. The JSON object must \
have exactly this shape:

{
  "correctness": <1-5 integer>,
  "groundedness": <1-5 integer>,
  "completeness": <1-5 integer>,
  "hallucination": <1-5 integer>,
  "overall": <1-5 integer>,
  "reason": "<one or two sentence explanation of the scores>"
}
"""


def _build_judge_user_prompt(question: str, expected_behaviour: str, generated_answer: str) -> str:
    """
    Assembles the judge's user prompt from exactly the three permitted
    fields. Intentionally does not accept a ``ContextPackage``, retrieved
    node list, or retrieval metadata as input -- there is no parameter for
    them, so a caller cannot leak the ranking into the judge even by
    accident.
    """
    return (
        "QUESTION:\n"
        f"{question}\n\n"
        "EXPECTED BEHAVIOUR:\n"
        f"{expected_behaviour}\n\n"
        "GENERATED ANSWER:\n"
        f"{generated_answer}\n"
    )


def _extract_json_object(raw: str) -> Optional[dict]:
    """
    Best-effort extraction of a JSON object from a judge response.

    Handles the common deviations real LLMs produce even when explicitly
    told "JSON only": markdown code fences, leading/trailing commentary.
    Returns ``None`` if no valid JSON object could be recovered.
    """
    if not raw or not raw.strip():
        return None

    text = raw.strip()

    # Strip ```json ... ``` or ``` ... ``` fences if present.
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fall back to grabbing the first {...} span in the text.
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            return None

    return None


def _coerce_score(value: object) -> int:
    """Clamp any numeric-ish value into the valid 1-5 integer score range."""
    try:
        score = int(round(float(value)))
    except (TypeError, ValueError):
        return 1
    return max(1, min(5, score))


class AnswerQualityJudge:
    """
    LLM-as-judge for generated GraphRAG answers.

    Wraps an ``LLMProvider`` (the exact same abstract interface
    ``GraphRAGEngine`` consumes) so the judge can be backed by
    ``GeminiLLMProvider``, ``AnthropicLLMProvider``, ``EchoJudgeProvider``,
    or any other implementation without this class changing.
    """

    def __init__(self, llm_provider: LLMProvider, *, pass_threshold: int = PASS_THRESHOLD) -> None:
        self._llm = llm_provider
        self._pass_threshold = pass_threshold

    def judge(
        self,
        *,
        question: str,
        expected_behaviour: str,
        generated_answer: str,
    ) -> tuple[JudgeScores, str, Optional[str]]:
        """
        Run the judge call for one answer.

        Returns
        -------
        (scores, reason, error)
            ``error`` is ``None`` on success, otherwise a short message
            describing why fallback scores were used (LLM call failure or
            unparseable response). ``scores``/``reason`` are always
            populated -- with conservative fallback values on failure -- so
            callers never need to special-case a missing result.
        """
        user_prompt = _build_judge_user_prompt(question, expected_behaviour, generated_answer)

        try:
            raw = self._llm.generate(system_prompt=JUDGE_SYSTEM_PROMPT, user_prompt=user_prompt)
        except Exception as exc:  # noqa: BLE001 - any provider failure is reported uniformly
            return _fallback_scores(), "Judge LLM call failed; see judge_error.", f"{type(exc).__name__}: {exc}"

        parsed = _extract_json_object(raw)
        if parsed is None:
            return (
                _fallback_scores(),
                "Judge response could not be parsed as JSON; see judge_error.",
                f"Unparseable judge response (first 300 chars): {raw[:300]!r}",
            )

        scores = JudgeScores(
            correctness=_coerce_score(parsed.get("correctness")),
            groundedness=_coerce_score(parsed.get("groundedness")),
            completeness=_coerce_score(parsed.get("completeness")),
            hallucination=_coerce_score(parsed.get("hallucination")),
            overall=_coerce_score(parsed.get("overall")),
        )
        reason = str(parsed.get("reason") or "").strip() or "(judge did not provide a reason)"
        return scores, reason, None

    def _passed(self, scores: JudgeScores, judge_error: Optional[str]) -> bool:
        if judge_error is not None:
            return False
        return scores.overall >= self._pass_threshold and scores.hallucination >= self._pass_threshold

    def evaluate(
        self,
        bq: BenchmarkQuestion,
        generated_answer: str,
        *,
        generation_error: Optional[str] = None,
        retrieved_node_count: Optional[int] = None,
    ) -> EvaluationResult:
        """
        Judge one generated answer against its ``BenchmarkQuestion`` ground
        truth and produce a complete ``EvaluationResult``.

        If ``generation_error`` is set (the GraphRAG pipeline itself failed
        for this question), the judge call is skipped entirely and the
        result is recorded as a failure -- there is nothing meaningful to
        judge.
        """
        if generation_error is not None:
            scores = _fallback_scores()
            return EvaluationResult(
                question=bq.question,
                repository=bq.repository,
                category=bq.category,
                expected_symbols=bq.expected_symbols,
                expected_behaviour=bq.expected_behaviour,
                generated_answer="",
                scores=scores,
                reason="Answer generation failed; question was not sent to the judge.",
                passed=False,
                generation_error=generation_error,
                retrieved_node_count=retrieved_node_count,
            )

        scores, reason, judge_error = self.judge(
            question=bq.question,
            expected_behaviour=bq.expected_behaviour,
            generated_answer=generated_answer,
        )
        return EvaluationResult(
            question=bq.question,
            repository=bq.repository,
            category=bq.category,
            expected_symbols=bq.expected_symbols,
            expected_behaviour=bq.expected_behaviour,
            generated_answer=generated_answer,
            scores=scores,
            reason=reason,
            passed=self._passed(scores, judge_error),
            judge_error=judge_error,
            retrieved_node_count=retrieved_node_count,
        )


class EchoJudgeProvider(LLMProvider):
    """
    Dependency-free, deterministic judge ``LLMProvider``.

    Makes no network calls and requires no API key. It does not actually
    evaluate anything -- it returns a fixed, clearly-labelled placeholder
    JSON response. Mirrors ``EchoLLMProvider`` in ``graphrag_engine.py``:
    useful for dry-running the full eval harness (dataset construction,
    pipeline wiring, report generation) end to end without burning real
    judge API calls, and as a sanity check that the harness's JSON parsing
    and report building work correctly.

    Scores are mid-scale (3) rather than top-of-scale, so a dry run is
    visually distinguishable from a real run that happens to score well.
    """

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        return json.dumps(
            {
                "correctness": 3,
                "groundedness": 3,
                "completeness": 3,
                "hallucination": 3,
                "overall": 3,
                "reason": (
                    "EchoJudgeProvider placeholder score -- no real judging was performed. "
                    "Re-run with a real LLMProvider (e.g. GeminiLLMProvider) for actual scores."
                ),
            }
        )


# ===========================================================================
# Aggregation
# ===========================================================================

def aggregate_results(results: list[EvaluationResult]) -> dict:
    """Compute average scores and pass rate across all evaluated questions."""
    if not results:
        return {
            "count": 0,
            "passed": 0,
            "pass_rate": 0.0,
            "averages": {f: 0.0 for f in SCORE_FIELDS},
        }

    averages = {
        f: round(sum(getattr(r.scores, f) for r in results) / len(results), 2)
        for f in SCORE_FIELDS
    }
    passed = sum(1 for r in results if r.passed)
    return {
        "count": len(results),
        "passed": passed,
        "pass_rate": round(passed / len(results), 4),
        "averages": averages,
    }


def _failure_patterns(results: list[EvaluationResult]) -> list[str]:
    """
    Lightweight, deterministic heuristics over the scored results -- no LLM
    call. Flags the kinds of systematic weaknesses a reviewer would want
    surfaced first.
    """
    patterns: list[str] = []
    if not results:
        return patterns

    n = len(results)
    gen_failures = [r for r in results if r.generation_error]
    judge_failures = [r for r in results if r.judge_error]
    low_hallu = [r for r in results if r.judge_error is None and r.scores.hallucination <= 2]
    low_ground = [r for r in results if r.judge_error is None and r.scores.groundedness <= 2]
    low_complete = [r for r in results if r.judge_error is None and r.scores.completeness <= 2]

    if gen_failures:
        patterns.append(
            f"{len(gen_failures)}/{n} questions failed during answer generation "
            "(GraphRAG/LLM provider errors) before ever reaching the judge."
        )
    if judge_failures:
        patterns.append(
            f"{len(judge_failures)}/{n} questions could not be scored because the judge call "
            "failed or returned unparseable output."
        )
    if low_hallu:
        cats = sorted({r.category for r in low_hallu})
        patterns.append(
            f"{len(low_hallu)}/{n} answers scored low on hallucination risk "
            f"(categories: {', '.join(cats)}) -- the model likely stated specifics not "
            "supported by the retrieved context."
        )
    if low_ground:
        cats = sorted({r.category for r in low_ground})
        patterns.append(
            f"{len(low_ground)}/{n} answers scored low on groundedness "
            f"(categories: {', '.join(cats)}) -- answers leaned generic rather than citing "
            "specific repository detail."
        )
    if low_complete:
        cats = sorted({r.category for r in low_complete})
        patterns.append(
            f"{len(low_complete)}/{n} answers scored low on completeness "
            f"(categories: {', '.join(cats)}) -- important parts of the expected behaviour "
            "were left out."
        )
    if not patterns:
        patterns.append("No systematic failure pattern detected across the evaluated questions.")
    return patterns


def _recommendations(summary: dict, patterns: list[str]) -> list[str]:
    """Templated, deterministic recommendations derived from the aggregate stats."""
    recs: list[str] = []
    avg = summary["averages"]

    if summary["count"] == 0:
        return ["No questions were evaluated; nothing to recommend."]

    if avg["hallucination"] < 4:
        recs.append(
            "Tighten the GraphRAG system prompt's grounding instructions, or reduce "
            "top_k/max_hops noise, to reduce hallucination risk."
        )
    if avg["groundedness"] < 4:
        recs.append(
            "Consider including more concrete code snippets or node-level detail in "
            "ContextBuilder's llm_context so answers can cite specifics."
        )
    if avg["completeness"] < 4:
        recs.append(
            "Investigate whether retrieval (top_k/max_hops) is surfacing enough related "
            "nodes for multi-part questions, since incomplete context limits how complete "
            "an answer can be."
        )
    if summary["pass_rate"] < 0.7:
        recs.append(
            "Pass rate is below 70%% -- re-run this evaluation after any prompt or retrieval "
            "change to confirm answer quality is trending upward, not just retrieval metrics."
        )
    if not recs:
        recs.append(
            "Answer quality looks strong across all judged dimensions; no immediate "
            "changes recommended. Re-run this evaluation whenever prompting or retrieval "
            "changes to catch regressions."
        )
    return recs


# ===========================================================================
# Report builders
# ===========================================================================

def build_json_report(results: list[EvaluationResult], *, generated_at: str) -> dict:
    summary = aggregate_results(results)
    return {
        "generated_at": generated_at,
        "summary": summary,
        "results": [r.to_json_dict() for r in results],
    }


def _format_result_line(r: EvaluationResult) -> str:
    return (
        f"- **[{r.repository} / {r.category}]** {r.question}\n"
        f"  - Overall: {r.scores.overall}/5 "
        f"(correctness={r.scores.correctness}, groundedness={r.scores.groundedness}, "
        f"completeness={r.scores.completeness}, hallucination={r.scores.hallucination})\n"
        f"  - Reason: {r.reason}\n"
    )


def build_markdown_report(results: list[EvaluationResult], *, generated_at: str) -> str:
    summary = aggregate_results(results)
    avg = summary["averages"]
    patterns = _failure_patterns(results)
    recommendations = _recommendations(summary, patterns)

    scored = [r for r in results if r.judge_error is None and r.generation_error is None]
    best = sorted(scored, key=lambda r: r.scores.overall, reverse=True)[:5]
    worst = sorted(scored, key=lambda r: r.scores.overall)[:5]

    lines: list[str] = []
    lines.append("# RepoGraphAI -- Answer Quality Evaluation Report\n\n")
    lines.append(f"Generated: {generated_at}\n\n")

    lines.append("## Summary\n\n")
    lines.append(f"- Evaluated questions: {summary['count']}\n")
    lines.append(
        f"- Passed (overall >= {PASS_THRESHOLD} and hallucination >= {PASS_THRESHOLD}): "
        f"{summary['passed']} ({summary['pass_rate'] * 100:.1f}%)\n"
    )
    lines.append(f"- Average Correctness: {avg['correctness']}/5\n")
    lines.append(f"- Average Groundedness: {avg['groundedness']}/5\n")
    lines.append(f"- Average Completeness: {avg['completeness']}/5\n")
    lines.append(f"- Average Hallucination (absence of): {avg['hallucination']}/5\n")
    lines.append(f"- Average Overall Score: {avg['overall']}/5\n\n")

    by_repo: dict[str, list[EvaluationResult]] = {}
    for r in results:
        by_repo.setdefault(r.repository, []).append(r)

    lines.append("## Per-Repository Breakdown\n\n")
    for repo, repo_results in by_repo.items():
        repo_summary = aggregate_results(repo_results)
        repo_avg = repo_summary["averages"]
        lines.append(
            f"- **{repo}**: {repo_summary['count']} questions, "
            f"overall avg {repo_avg['overall']}/5, "
            f"pass rate {repo_summary['pass_rate'] * 100:.1f}%\n"
        )
    lines.append("\n")

    lines.append("## Best Answers\n\n")
    if best:
        for r in best:
            lines.append(_format_result_line(r))
    else:
        lines.append("_No successfully-judged answers to rank._\n")
    lines.append("\n")

    lines.append("## Weakest Answers\n\n")
    if worst:
        for r in worst:
            lines.append(_format_result_line(r))
    else:
        lines.append("_No successfully-judged answers to rank._\n")
    lines.append("\n")

    lines.append("## Common Failure Patterns\n\n")
    for p in patterns:
        lines.append(f"- {p}\n")
    lines.append("\n")

    lines.append("## Recommendations\n\n")
    for rec in recommendations:
        lines.append(f"- {rec}\n")
    lines.append("\n")

    lines.append("## All Results\n\n")
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"### [{status}] {r.question}\n\n")
        lines.append(f"- Repository: {r.repository}\n")
        lines.append(f"- Category: {r.category}\n")
        lines.append(f"- Expected Symbol(s): {', '.join(r.expected_symbols) or 'N/A'}\n")
        lines.append(f"- Expected Behaviour: {r.expected_behaviour}\n")
        if r.generation_error:
            lines.append(f"- Generation Error: {r.generation_error}\n")
        else:
            lines.append(f"- Generated Answer: {r.generated_answer}\n")
            lines.append(
                f"- Scores: correctness={r.scores.correctness}, "
                f"groundedness={r.scores.groundedness}, "
                f"completeness={r.scores.completeness}, "
                f"hallucination={r.scores.hallucination}, "
                f"overall={r.scores.overall}\n"
            )
            lines.append(f"- Reason: {r.reason}\n")
            if r.judge_error:
                lines.append(f"- Judge Error: {r.judge_error}\n")
        lines.append("\n")

    return "".join(lines)