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
from typing import Callable, Optional
from app.models.pydantic_models import BaseModel

from app.models.pydantic_models import RepositoryGraph
from app.rag.context_builder import (
    ContextBuilder,
    ContextPackage,
    ResolvedNode,
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
Python codebase.

Ground every statement in the REPOSITORY CONTEXT you are given. Do not \
invent function names, classes, file paths, or behaviour that is not shown \
in the context. If the context is insufficient to answer confidently, say \
so explicitly instead of guessing.

When you reference code, cite the relevant node id (for example \
ClassName.method_name or function_name) so the reader can locate it in the \
repository."""


class GraphRAGPromptBuilder(PromptBuilder):
    """
    Default prompt construction strategy for GraphRAG v1.

    The user prompt is the ``ContextPackage.llm_context`` block (which
    already contains the question, detected intent, keywords, per-node
    context, and subgraph relationships) followed by an explicit
    answer-instruction footer that restates the question. Restating the
    question after a long context block measurably improves instruction
    adherence on most chat models.
    """

    def __init__(self, system_prompt: Optional[str] = None) -> None:
        self._system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    def build(self, package: ContextPackage) -> PromptBundle:
        sep = "─" * 60
        user_prompt = (
            f"{package.llm_context}\n\n"
            f"{sep}\n"
            "ANSWER INSTRUCTIONS\n"
            f"{sep}\n"
            "Using only the repository context above, answer the following "
            "question as specifically as possible, citing the relevant node "
            "id(s) where it helps the reader locate the code:\n\n"
            f"{package.question}"
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