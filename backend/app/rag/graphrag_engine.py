"""
app/rag/graphrag_engine.py
===========================
GraphRAG v1 — the final hop from "retrieved graph context" to "answered
question."

This module does **not** introduce a new retrieval mechanism. It is a thin,
generic orchestration layer on top of the existing structural pipeline:

::

    Question
        |
        v
    QueryResolver            (unchanged)
        |
        v
    RepositoryRetriever       (unchanged)
        |
        v
    ContextBuilder            (unchanged)  ->  ContextPackage
        |
        v
    GraphRAGEngine  (this module)
        |  1. build a prompt from ContextPackage.llm_context + question
        |  2. call an abstract LLMProvider
        |  3. shape the result into a GraphRAGResponse
        v
    GraphRAGResponse  (answer + source nodes + retrieval metadata)

Design principles
------------------
- **No retrieval logic lives here.** ``CodeParser``, ``GraphBuilder``,
  ``RepositoryRetriever``, ``QueryResolver``, and ``ContextBuilder`` are used
  exactly as-is, via composition. This module never subclasses or patches
  them.
- **The LLM is a pluggable boundary.** ``LLMProvider`` is an abstract
  interface. Swapping Anthropic, OpenAI, a local model, or a deterministic
  test double requires no changes to ``GraphRAGEngine``.
- **Generic across arbitrary Python repositories.** Nothing in this file
  references RepoGraphAI-specific symbols, file names, or class names.
- **Deterministic everywhere except the LLM call itself.** Prompt
  construction and response shaping have no randomness; only
  ``LLMProvider.generate`` is allowed to vary.
- **Graceful on empty retrieval.** If ``ContextBuilder`` resolves zero nodes,
  the engine returns a clear "no relevant context" answer instead of sending
  an empty prompt to the LLM and risking a hallucinated response.

Future extension point
-----------------------
``ContextBuilder``'s own docstring describes a future hybrid (embedding +
structural) retrieval path. Because ``GraphRAGEngine`` only depends on the
``ContextBuilder.build(question, ...) -> ContextPackage`` contract, swapping
in a future ``GraphRAGBuilder(ContextBuilder, VectorIndex)`` requires zero
changes here — any object exposing that method works.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Iterator, Optional

from app.models.pydantic_models import BaseModel, RepositoryGraph
from app.rag.context_builder import (
    ContextBuilder,
    ContextPackage,
    build_context_builder,
)

# ===========================================================================
# Exceptions
# ===========================================================================

class GraphRAGError(Exception):
    """Base class for all errors raised by the GraphRAG engine."""


class LLMProviderError(GraphRAGError):
    """
    Raised when the configured ``LLMProvider`` fails to produce a usable
    completion — either because it raised an exception internally, or
    because it returned an empty / non-string response.
    """


# ===========================================================================
# Abstract LLM interface
# ===========================================================================

class LLMProvider(ABC):
    """
    Abstract boundary between GraphRAG and any concrete text-generation
    backend.

    Implementations must be synchronous and side-effect-free from the
    engine's point of view: given the same prompts, behaviour should be
    predictable enough to test. Network calls, retries, and API-specific
    error handling belong inside the implementation, not in
    ``GraphRAGEngine``.
    """

    @abstractmethod
    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        """
        Produce a completion for the given prompts.

        Parameters
        ----------
        system_prompt : str
            High-level behavioural instructions (grounding rules, tone,
            citation requirements). Stable across questions.
        user_prompt : str
            The repository context plus the question, assembled by a
            ``PromptBuilder``. Varies per call.

        Returns
        -------
        str
            The model's answer as plain text. Implementations should raise
            on failure rather than returning an empty string or ``None`` —
            ``GraphRAGEngine`` treats both as failures.
        """
        raise NotImplementedError

    def stream(self, *, system_prompt: str, user_prompt: str) -> Iterator[str]:
        """
        Stream a completion for the given prompts, yielding text chunks.

        Default implementation calls ``generate`` and yields the full response
        as a single chunk. Subclasses override this for true token streaming.

        Yields
        ------
        str
            Successive text chunks of the model's answer.
        """
        yield self.generate(system_prompt=system_prompt, user_prompt=user_prompt)


class EchoLLMProvider(LLMProvider):
    """
    Dependency-free, deterministic ``LLMProvider``.

    Makes no network calls and requires no API key. It does not attempt to
    "answer" the question — it simply confirms what context would have been
    sent to a real model. Useful as a zero-setup placeholder while wiring
    the rest of the pipeline, and as a sanity check that prompts are being
    built correctly.
    """

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        return (
            "[EchoLLMProvider — no real LLM configured]\n"
            f"system_prompt length: {len(system_prompt)} chars\n"
            f"user_prompt length: {len(user_prompt)} chars\n"
            "Replace this provider with a real LLMProvider implementation "
            "(e.g. AnthropicLLMProvider) to get an actual answer."
        )


class CallableLLMProvider(LLMProvider):
    """
    Adapts any ``Callable[[str, str], str]`` into an ``LLMProvider`` without
    requiring a subclass. Handy for quick scripts, lambdas, or wrapping a
    function that already exists elsewhere in the codebase.

    Example
    -------
    ::

        provider = CallableLLMProvider(lambda system, user: my_llm_call(system, user))
    """

    def __init__(self, fn: Callable[[str, str], str]) -> None:
        self._fn = fn

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        return self._fn(system_prompt, user_prompt)


class AnthropicLLMProvider(LLMProvider):
    """
    Production ``LLMProvider`` backed by the Anthropic Messages API.

    Requires the ``anthropic`` package (``pip install anthropic``) and a
    valid API key. The model id is deliberately a *required* constructor
    argument with no built-in default: available model names change over
    time independently of this code, so the caller should pass the current
    model id from Anthropic's own documentation
    (https://docs.claude.com) rather than relying on a hardcoded default
    here.

    Parameters
    ----------
    model : str
        The Anthropic model id to use (e.g. whatever the current
        recommended model is per Anthropic's docs at the time you deploy
        this).
    api_key : str | None
        Explicit API key. If omitted, the ``anthropic`` SDK falls back to
        the ``ANTHROPIC_API_KEY`` environment variable.
    max_tokens : int
        Maximum tokens to generate per call.
    client : object | None
        Pre-constructed ``anthropic.Anthropic`` client. Primarily for
        dependency injection in tests; if omitted, a client is constructed
        lazily on first use.
    """

    def __init__(
        self,
        model: str,
        *,
        api_key: Optional[str] = None,
        max_tokens: int = 1024,
        client: Optional[object] = None,
    ) -> None:
        if not model:
            raise ValueError(
                "AnthropicLLMProvider requires an explicit model id — "
                "check https://docs.claude.com for the current model catalog."
            )
        self._model = model
        self._max_tokens = max_tokens
        self._api_key = api_key
        self._client = client

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:
                raise ImportError(
                    "AnthropicLLMProvider requires the 'anthropic' package. "
                    "Install it with `pip install anthropic`."
                ) from exc
            self._client = (
                anthropic.Anthropic(api_key=self._api_key)
                if self._api_key
                else anthropic.Anthropic()
            )
        return self._client

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        client = self._get_client()
        response = client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text_blocks = [
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        ]
        return "".join(text_blocks)

    def stream(self, *, system_prompt: str, user_prompt: str) -> Iterator[str]:
        """Stream using Anthropic's streaming Messages API."""
        client = self._get_client()
        with client.messages.stream(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream_ctx:
            for text in stream_ctx.text_stream:
                yield text


class GeminiLLMProvider(LLMProvider):
    """
    Production ``LLMProvider`` backed by the Google Gemini API.

    Requires the ``google-genai`` package (``pip install google-genai``) and a
    valid API key.

    Parameters
    ----------
    model : str
        The Gemini model id to use (defaults to "gemini-2.5-flash").
    api_key : str | None
        Explicit API key. If omitted, the implementation checks for the
        ``GOOGLE_API_KEY`` environment variable.
    client : object | None
        Pre-constructed ``google.genai.Client``. Primarily for dependency injection
        in tests; if omitted, a client is constructed lazily on first use.
    """

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        *,
        api_key: Optional[str] = None,
        client: Optional[object] = None,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._client = client

    def _get_client(self):
        if self._client is None:
            try:
                from google import genai
            except ImportError as exc:
                raise ImportError(
                    "GeminiLLMProvider requires the 'google-genai' package. "
                    "Install it with `pip install google-genai`."
                ) from exc

            import os
            api_key = self._api_key or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError(
                    "GeminiLLMProvider requires the GOOGLE_API_KEY environment variable "
                    "or an explicit api_key to be set."
                )

            self._client = genai.Client(api_key=api_key)
        return self._client

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        client = self._get_client()
        try:
            from google.genai import types
        except ImportError as exc:
            raise ImportError(
                "GeminiLLMProvider requires the 'google-genai' package. "
                "Install it with `pip install google-genai`."
            ) from exc

        response = client.models.generate_content(
            model=self._model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
            ),
        )
        if response.text is None:
            return ""
        return response.text

    def stream(self, *, system_prompt: str, user_prompt: str) -> Iterator[str]:
        """Stream using Gemini's generate_content_stream API."""
        client = self._get_client()
        try:
            from google.genai import types
        except ImportError as exc:
            raise ImportError(
                "GeminiLLMProvider requires the 'google-genai' package. "
                "Install it with `pip install google-genai`."
            ) from exc

        for chunk in client.models.generate_content_stream(
            model=self._model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
            ),
        ):
            if chunk.text:
                yield chunk.text


# ===========================================================================
# Prompt construction strategy
# ===========================================================================

@dataclass(frozen=True)
class PromptBundle:
    """A fully-assembled pair of prompts ready to hand to an ``LLMProvider``."""

    system_prompt: str
    user_prompt: str


class PromptBuilder(ABC):
    """
    Abstract strategy for turning a ``ContextPackage`` into a ``PromptBundle``.

    Kept as its own interface (rather than inlined into ``GraphRAGEngine``)
    so prompt engineering can evolve — different system instructions, output
    formats, few-shot examples — without touching orchestration logic.
    """

    @abstractmethod
    def build(self, package: ContextPackage) -> PromptBundle:
        raise NotImplementedError


DEFAULT_SYSTEM_PROMPT = """\
You are a senior software engineer answering questions about a specific \
Python codebase. You have access to a structured knowledge graph of the \
repository — it contains nodes (files, classes, functions, methods) and \
typed edges (CALLS, INHERITS, IMPORTS, INSTANTIATES, DECORATES, OVERRIDES).

STRICT GROUNDING RULES
----------------------
1. Ground every statement in the REPOSITORY CONTEXT provided. Do not invent \
function names, class names, file paths, or behaviour not present in the context.
2. If the context is insufficient to answer confidently, say so explicitly: \
"The provided context does not contain enough information to answer this \
question. Try rephrasing or asking about a specific symbol."
3. Never hallucinate. An honest "I don't know" is more valuable than a \
confident wrong answer.

CITATION FORMAT
---------------
When referencing code, always cite the node id from the context, e.g.:
  - Class: `GraphBuilder`
  - Method: `GraphBuilder.build_graph`
  - Function: `build_context_builder`
  - File: `app/graph/graph_builder.py`

ANSWER STYLE
------------
- Be specific and concise. Avoid restating the question.
- Lead with the direct answer, then provide supporting detail.
- If a function calls other functions or a class has relevant subclasses, \
mention them using their node ids.
- Use markdown code formatting for symbol names (`ClassName.method`).

SELF-CHECK (do this silently before answering)
----------------------------------------------
Before writing your answer, identify:
  1. Which nodes in the context are most relevant?
  2. What do the graph edges (CALLS, INHERITS, etc.) tell you about relationships?
  3. Is there enough context to answer confidently?
Then write your answer based only on that evidence."""


# Few-shot examples embedded in the user prompt to demonstrate the
# expected answer format and grounding behaviour.
_FEW_SHOT_EXAMPLES = """\
─────────────────────────────────────────────────────────────────
EXAMPLE QUESTIONS AND EXPECTED ANSWER STYLE (for calibration only)
─────────────────────────────────────────────────────────────────
Example Q: What does `Session.send` do?
Example A: `Session.send` (in `requests/sessions.py`) is the central dispatch
method that all public request methods (`get`, `post`, `put`, etc.) route
through. It resolves the appropriate transport adapter via `get_adapter`,
calls `HTTPAdapter.send` to perform the actual HTTP request, and processes
the response (including redirect following via `SessionRedirectMixin.resolve_redirects`).

Example Q: What calls `build_graph`?
Example A: Based on the context, `GraphService.generate_graph` calls
`GraphBuilder.build_graph`. The CALLS edge in the subgraph confirms this:
`GraphService.generate_graph → GraphBuilder.build_graph`.
─────────────────────────────────────────────────────────────────
END OF EXAMPLES — answer the ACTUAL question below using ONLY the
REPOSITORY CONTEXT provided, not the examples above.
─────────────────────────────────────────────────────────────────
"""


class GraphRAGPromptBuilder(PromptBuilder):
    """
    Default prompt construction strategy for GraphRAG v2.

    Improvements over v1:
    - Stronger system prompt with explicit grounding rules, citation format,
      and a chain-of-thought self-check step.
    - Few-shot examples showing the expected answer style and grounding.
    - Question restated after the context block (improves instruction adherence).
    - Optional few-shot injection (disable with ``include_examples=False``).
    """

    def __init__(
        self,
        system_prompt: Optional[str] = None,
        *,
        include_examples: bool = True,
    ) -> None:
        self._system_prompt    = system_prompt or DEFAULT_SYSTEM_PROMPT
        self._include_examples = include_examples

    def build(self, package: ContextPackage) -> PromptBundle:
        sep = "─" * 60
        examples = _FEW_SHOT_EXAMPLES if self._include_examples else ""
        user_prompt = (
            f"{package.llm_context}\n\n"
            f"{examples}"
            f"{sep}\n"
            "ANSWER INSTRUCTIONS\n"
            f"{sep}\n"
            "Using ONLY the repository context above (not the examples), "
            "answer the following question as specifically as possible. "
            "Cite the relevant node id(s) so the reader can locate the code. "
            "If the context is insufficient, say so honestly.\n\n"
            f"QUESTION: {package.question}"
        )
        return PromptBundle(system_prompt=self._system_prompt, user_prompt=user_prompt)


# ===========================================================================
# Output models
# ===========================================================================

class SourceNode(BaseModel):
    """
    A single graph node that was used as grounding for an answer.

    A flattened, serialisable projection of ``ResolvedNode`` — only the
    fields a caller needs to display "here's where this answer came from"
    or to deep-link into the repository.
    """

    node_id: str
    node_type: str
    label: str
    score: float
    file_path: Optional[str] = None
    line_number: Optional[int] = None


class RetrievalMetadata(BaseModel):
    """
    Diagnostic summary of the retrieval pass that produced an answer.

    Useful for logging, debugging weak answers, and the kind of retrieval
    benchmarking already done in ``retrieval_benchmark.py`` — this is the
    GraphRAG-level equivalent of that diagnostic surface.
    """

    intent_categories: list[str]
    keywords: list[str]
    resolved_node_count: int
    subgraph_node_count: int
    subgraph_edge_count: int

    traversal_strategy: str = "default"
    """
    Name of the ``IntentExpansionPolicy`` that drove subgraph expansion for
    this call.  Logged here so benchmark reports can confirm which policy
    fired — e.g. "routing" for route-registration queries, "analysis" for
    hierarchy questions, "default" for UNKNOWN intent.
    """

    top_k: Optional[int] = None
    """
    The top_k value actually in effect for this call. ``None`` only if it
    could not be determined (e.g. a custom ContextBuilder-like object that
    does not expose a ``_top_k`` attribute and no explicit override was
    passed to ``GraphRAGEngine.answer``).
    """

    max_hops: Optional[int] = None
    """Same caveat as ``top_k``, for subgraph expansion depth."""


class GraphRAGResponse(BaseModel):
    """The complete result of a ``GraphRAGEngine.answer()`` call."""

    question: str
    answer: str
    source_nodes: list[SourceNode]
    retrieval_metadata: RetrievalMetadata


# ===========================================================================
# GraphRAG engine
# ===========================================================================

NO_CONTEXT_ANSWER = (
    "I couldn't find anything in this repository that's clearly relevant to "
    "that question. Try mentioning a specific file, class, or function "
    "name, or rephrasing the question."
)


class GraphRAGEngine:
    """
    Orchestrates ``ContextBuilder`` -> prompt construction -> ``LLMProvider``
    -> ``GraphRAGResponse``.

    This class owns no retrieval logic of its own. It depends only on the
    public ``ContextBuilder.build(question, *, top_k=None, max_hops=None) ->
    ContextPackage`` contract, so any object honouring that contract
    (including a future hybrid/embedding-augmented builder) can be passed in
    unchanged.

    Parameters
    ----------
    context_builder : ContextBuilder
        Pre-constructed builder wrapping the repository's knowledge graph.
    llm_provider : LLMProvider
        The text-generation backend to call.
    prompt_builder : PromptBuilder | None
        Prompt construction strategy. Defaults to ``GraphRAGPromptBuilder()``.
    require_resolved_nodes : bool
        If ``True`` (default), questions that resolve to zero nodes skip the
        LLM call entirely and return ``NO_CONTEXT_ANSWER``. This avoids
        spending a model call on a prompt with no grounding, and avoids the
        model confidently inventing an answer from nothing. Set to ``False``
        to always call the LLM regardless of retrieval results.

    Usage
    -----
    ::

        context_builder = build_context_builder(graph)
        engine = GraphRAGEngine(context_builder, EchoLLMProvider())
        response = engine.answer("How does retrieval work?")
        print(response.answer)
    """

    def __init__(
        self,
        context_builder: ContextBuilder,
        llm_provider: LLMProvider,
        prompt_builder: Optional[PromptBuilder] = None,
        *,
        require_resolved_nodes: bool = True,
    ) -> None:
        self._context_builder = context_builder
        self._llm = llm_provider
        self._prompt_builder = prompt_builder or GraphRAGPromptBuilder()
        self._require_resolved_nodes = require_resolved_nodes

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def answer(
        self,
        question: str,
        *,
        top_k: Optional[int] = None,
        max_hops: Optional[int] = None,
    ) -> GraphRAGResponse:
        """
        Answer a natural-language question about the repository.

        Parameters
        ----------
        question : str
            The natural-language question.
        top_k : int | None
            Override the ``ContextBuilder``'s default top_k for this call.
        max_hops : int | None
            Override the ``ContextBuilder``'s default max_hops for this call.

        Returns
        -------
        GraphRAGResponse

        Raises
        ------
        ValueError
            If ``question`` is empty or whitespace-only.
        LLMProviderError
            If the configured ``LLMProvider`` raises, or returns an empty /
            non-string response.
        """
        if not question or not question.strip():
            raise ValueError("question must be a non-empty string")

        package = self._context_builder.build(question, top_k=top_k, max_hops=max_hops)

        source_nodes = self._build_source_nodes(package)
        metadata = self._build_metadata(package, top_k, max_hops)

        if self._require_resolved_nodes and not package.resolved_nodes:
            return GraphRAGResponse(
                question=question,
                answer=NO_CONTEXT_ANSWER,
                source_nodes=source_nodes,
                retrieval_metadata=metadata,
            )

        prompt = self._prompt_builder.build(package)

        try:
            raw_answer = self._llm.generate(
                system_prompt=prompt.system_prompt,
                user_prompt=prompt.user_prompt,
            )
        except Exception as exc:  # noqa: BLE001 - intentionally broad: any
            # provider failure (network, auth, rate limit, SDK-internal) is
            # surfaced uniformly as an LLMProviderError to callers.
            raise LLMProviderError(
                f"LLM provider failed to generate an answer for question: {question!r}"
            ) from exc

        if not isinstance(raw_answer, str) or not raw_answer.strip():
            raise LLMProviderError(
                "LLM provider returned an empty or non-string response."
            )

        return GraphRAGResponse(
            question=question,
            answer=raw_answer.strip(),
            source_nodes=source_nodes,
            retrieval_metadata=metadata,
        )

    def stream_answer(
        self,
        question: str,
        *,
        top_k: Optional[int] = None,
        max_hops: Optional[int] = None,
    ) -> Iterator[dict]:
        """
        Stream a GraphRAG answer as a sequence of Server-Sent Event payloads.

        Yields a series of dicts that callers should serialise as SSE ``data:``
        lines.  The sequence is:

        1. One ``"metadata"`` event with intent, keywords, and source nodes —
           sent before the first token so the client can render retrieval info
           immediately while the LLM streams.
        2. One or more ``"token"`` events, each carrying a text chunk from the
           LLM provider's streaming API.
        3. One ``"done"`` event with ``full_answer`` (the concatenated tokens)
           and a ``"no_context"`` flag if retrieval was empty.

        If the provider does not implement ``stream()`` (returns a single
        chunk), the caller still sees the same event sequence — only the
        number of ``"token"`` events differs.

        Parameters
        ----------
        question : str
        top_k, max_hops : int | None
            Forwarded to ``ContextBuilder.build``.

        Raises
        ------
        ValueError
            If ``question`` is empty.
        LLMProviderError
            If the LLM provider raises during streaming.

        Example SSE stream
        ------------------
        ::

            data: {"type": "metadata", "intent_categories": [...], ...}
            data: {"type": "token", "text": "The "}
            data: {"type": "token", "text": "function build_graph "}
            data: {"type": "done", "full_answer": "The function build_graph ..."}
        """
        if not question or not question.strip():
            raise ValueError("question must be a non-empty string")

        package  = self._context_builder.build(question, top_k=top_k, max_hops=max_hops)
        metadata = self._build_metadata(package, top_k, max_hops)
        source_nodes = self._build_source_nodes(package)

        # --- Event 1: metadata (retrieval results, before first LLM token) ---
        yield {
            "type": "metadata",
            "intent_categories": metadata.intent_categories,
            "keywords": metadata.keywords,
            "resolved_node_count": metadata.resolved_node_count,
            "subgraph_node_count": metadata.subgraph_node_count,
            "traversal_strategy": metadata.traversal_strategy,
            "source_nodes": [
                {
                    "node_id":   sn.node_id,
                    "node_type": sn.node_type,
                    "label":     sn.label,
                    "score":     sn.score,
                    "file_path": sn.file_path,
                }
                for sn in source_nodes
            ],
        }

        # --- No-context shortcut ---
        if self._require_resolved_nodes and not package.resolved_nodes:
            yield {"type": "token", "text": NO_CONTEXT_ANSWER}
            yield {"type": "done", "full_answer": NO_CONTEXT_ANSWER, "no_context": True}
            return

        prompt      = self._prompt_builder.build(package)
        accumulated = []

        try:
            for chunk in self._llm.stream(
                system_prompt=prompt.system_prompt,
                user_prompt=prompt.user_prompt,
            ):
                if chunk:
                    accumulated.append(chunk)
                    yield {"type": "token", "text": chunk}
        except Exception as exc:
            raise LLMProviderError(
                f"LLM provider failed while streaming answer for question: {question!r}"
            ) from exc

        full_answer = "".join(accumulated).strip()
        if not full_answer:
            raise LLMProviderError("LLM provider streamed an empty response.")

        yield {"type": "done", "full_answer": full_answer, "no_context": False}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_source_nodes(package: ContextPackage) -> list[SourceNode]:
        """Project ``ResolvedNode`` objects down to the public ``SourceNode`` shape."""
        return [
            SourceNode(
                node_id=rn.node_id,
                node_type=rn.node_type,
                label=rn.label,
                score=rn.score,
                file_path=rn.file_path,
                line_number=rn.line_number,
            )
            for rn in package.resolved_nodes
        ]

    def _build_metadata(
        self,
        package: ContextPackage,
        top_k: Optional[int],
        max_hops: Optional[int],
    ) -> RetrievalMetadata:
        return RetrievalMetadata(
            intent_categories=list(package.intent_categories),
            keywords=list(package.keywords),
            resolved_node_count=len(package.resolved_nodes),
            subgraph_node_count=package.subgraph_node_count,
            subgraph_edge_count=package.subgraph_edge_count,
            traversal_strategy=package.traversal_strategy,
            top_k=self._effective_param(top_k, "_top_k"),
            max_hops=self._effective_param(max_hops, "_max_hops"),
        )

    def _effective_param(self, explicit: Optional[int], attr_name: str) -> Optional[int]:
        """
        Best-effort resolution of the parameter value actually used by the
        ``ContextBuilder`` for this call.

        ``ContextPackage`` does not record the effective top_k / max_hops it
        was built with, and ``ContextBuilder`` does not expose its instance
        defaults publicly. Rather than modify ``ContextBuilder`` to add
        public accessors, this reads the private attribute defensively and
        falls back to ``None`` if it is unavailable — e.g. when
        ``context_builder`` is a test double or a future drop-in
        replacement that does not share this internal layout.
        """
        if explicit is not None:
            return explicit
        return getattr(self._context_builder, attr_name, None)


# ===========================================================================
# Factory convenience
# ===========================================================================

def build_graphrag_engine(
    graph: RepositoryGraph,
    llm_provider: LLMProvider,
    *,
    prompt_builder: Optional[PromptBuilder] = None,
    top_k: int = 10,
    max_hops: int = 1,
    max_llm_neighbours: int = 20,
    require_resolved_nodes: bool = True,
) -> GraphRAGEngine:
    """
    One-call factory: build a ``GraphRAGEngine`` directly from a
    ``RepositoryGraph``, mirroring ``build_context_builder``'s ergonomics.

    Parameters
    ----------
    graph : RepositoryGraph
        The master (or filtered) knowledge graph.
    llm_provider : LLMProvider
        The text-generation backend to call.
    prompt_builder : PromptBuilder | None
        Prompt construction strategy. Defaults to ``GraphRAGPromptBuilder()``.
    top_k, max_hops, max_llm_neighbours
        Forwarded to ``build_context_builder``.
    require_resolved_nodes : bool
        Forwarded to ``GraphRAGEngine``.

    Returns
    -------
    GraphRAGEngine
    """
    context_builder = build_context_builder(
        graph,
        top_k=top_k,
        max_hops=max_hops,
        max_llm_neighbours=max_llm_neighbours,
    )
    return GraphRAGEngine(
        context_builder,
        llm_provider,
        prompt_builder,
        require_resolved_nodes=require_resolved_nodes,
    )