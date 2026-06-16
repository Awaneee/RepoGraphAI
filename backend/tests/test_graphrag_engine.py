"""
tests/test_graphrag_engine.py
==============================
Test suite for app.rag.graphrag_engine.

Two layers of testing are used:

1. **Isolated unit tests** against a hand-built ``ContextPackage`` and a
   fake ``ContextBuilder`` double, so engine logic (prompt construction,
   response shaping, error handling) is verified independently of the real
   QueryResolver / RepositoryRetriever scoring behaviour.

2. **Integration tests** against a tiny, real ``RepositoryGraph`` run through
   the actual ``ContextBuilder`` (unmodified), so we also verify the engine
   wires correctly into the real pipeline end-to-end. Only the LLM is faked
   in these tests — never the retrieval stack.
"""

from __future__ import annotations

import pytest

from app.models.pydantic_models import (
    GraphEdge,
    GraphNode,
    NodeType,
    RelationshipType,
    RepositoryGraph,
)
from app.rag.context_builder import ContextPackage, ResolvedNode, SubgraphSummary, build_context_builder
from app.rag.graphrag_engine import (
    NO_CONTEXT_ANSWER,
    AnthropicLLMProvider,
    CallableLLMProvider,
    EchoLLMProvider,
    GraphRAGEngine,
    GraphRAGPromptBuilder,
    GraphRAGResponse,
    LLMProvider,
    LLMProviderError,
    PromptBuilder,
    PromptBundle,
    build_graphrag_engine,
)


# ===========================================================================
# Shared fixtures
# ===========================================================================

def _make_resolved_node(node_id="Retriever.fetch", node_type="Method", score=31.0) -> ResolvedNode:
    return ResolvedNode(
        node_id=node_id,
        node_type=node_type,
        label=node_id.split(".")[-1],
        score=score,
        reason="exact label match",
        file_path="app/utils.py",
        line_number=15,
        docstring="Fetch data from source.",
        outgoing_count=0,
        incoming_count=1,
        neighbour_ids=["Retriever"],
    )


def _make_context_package(question: str, resolved_nodes=None) -> ContextPackage:
    """Hand-build a ContextPackage without touching QueryResolver/RepositoryRetriever."""
    resolved_nodes = resolved_nodes if resolved_nodes is not None else [_make_resolved_node()]
    return ContextPackage(
        question=question,
        intent_categories=["retrieval"],
        keywords=["fetch"],
        resolved_nodes=resolved_nodes,
        subgraph_node_count=2,
        subgraph_edge_count=1,
        subgraph_summary=SubgraphSummary(
            node_count=2, edge_count=1, nodes_by_type={"Method": 1, "Class": 1}, edge_types=["contains"]
        ),
        llm_context=(
            f"QUESTION\n{question}\n\nDETECTED INTENT\nretrieval\n\n"
            "=== METHOD: fetch ===\nID: Retriever.fetch\nFile: app/utils.py\n"
        ),
        raw_resolution=None,
    )


class FakeContextBuilder:
    """
    Minimal test double honouring the ``ContextBuilder.build`` contract.

    Records every call so tests can assert the engine invokes it with the
    right question and parameter overrides, and returns a pre-baked
    ``ContextPackage`` so tests don't depend on real QueryResolver scoring.
    """

    def __init__(self, package: ContextPackage, *, top_k: int = 10, max_hops: int = 1) -> None:
        self._package = package
        self._top_k = top_k       # mirrors real ContextBuilder's private attrs,
        self._max_hops = max_hops  # used by GraphRAGEngine's best-effort introspection
        self.calls: list[dict] = []

    def build(self, question, *, top_k=None, max_hops=None) -> ContextPackage:
        self.calls.append({"question": question, "top_k": top_k, "max_hops": max_hops})
        return self._package


class RecordingLLMProvider(LLMProvider):
    """Captures the prompts it receives and returns a fixed canned answer."""

    def __init__(self, canned_answer: str = "This is the canned answer.") -> None:
        self.canned_answer = canned_answer
        self.received_calls: list[dict] = []

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        self.received_calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        return self.canned_answer


class FailingLLMProvider(LLMProvider):
    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        raise RuntimeError("simulated provider outage")


class EmptyLLMProvider(LLMProvider):
    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        return "   "


# ===========================================================================
# PromptBuilder tests
# ===========================================================================

class TestGraphRAGPromptBuilder:
    def test_prompt_includes_question_and_llm_context(self):
        package = _make_context_package("How does fetch work?")
        bundle = GraphRAGPromptBuilder().build(package)

        assert isinstance(bundle, PromptBundle)
        assert "How does fetch work?" in bundle.user_prompt
        assert "Retriever.fetch" in bundle.user_prompt  # from llm_context
        assert package.llm_context in bundle.user_prompt

    def test_system_prompt_is_grounding_oriented_by_default(self):
        bundle = GraphRAGPromptBuilder().build(_make_context_package("q"))
        assert "REPOSITORY CONTEXT" in bundle.system_prompt or "codebase" in bundle.system_prompt.lower()

    def test_custom_system_prompt_is_respected(self):
        custom = "You are a pirate who only answers in nautical metaphors."
        bundle = GraphRAGPromptBuilder(system_prompt=custom).build(_make_context_package("q"))
        assert bundle.system_prompt == custom


# ===========================================================================
# GraphRAGEngine — isolated unit tests (FakeContextBuilder)
# ===========================================================================

class TestGraphRAGEngineOrchestration:
    def test_context_builder_invoked_with_question(self):
        package = _make_context_package("How does fetch work?")
        fake_builder = FakeContextBuilder(package)
        provider = RecordingLLMProvider()
        engine = GraphRAGEngine(fake_builder, provider)

        engine.answer("How does fetch work?")

        assert len(fake_builder.calls) == 1
        assert fake_builder.calls[0]["question"] == "How does fetch work?"

    def test_top_k_and_max_hops_overrides_are_forwarded(self):
        package = _make_context_package("q")
        fake_builder = FakeContextBuilder(package)
        engine = GraphRAGEngine(fake_builder, RecordingLLMProvider())

        engine.answer("q", top_k=3, max_hops=2)

        assert fake_builder.calls[0]["top_k"] == 3
        assert fake_builder.calls[0]["max_hops"] == 2

    def test_empty_question_raises_value_error(self):
        engine = GraphRAGEngine(FakeContextBuilder(_make_context_package("q")), RecordingLLMProvider())
        with pytest.raises(ValueError):
            engine.answer("   ")

    def test_llm_receives_constructed_prompt(self):
        package = _make_context_package("How does fetch work?")
        provider = RecordingLLMProvider()
        engine = GraphRAGEngine(FakeContextBuilder(package), provider)

        engine.answer("How does fetch work?")

        assert len(provider.received_calls) == 1
        call = provider.received_calls[0]
        assert "How does fetch work?" in call["user_prompt"]
        assert call["system_prompt"]  # non-empty grounding instructions

    def test_custom_prompt_builder_is_used(self):
        package = _make_context_package("q")
        provider = RecordingLLMProvider()

        class StaticPromptBuilder(PromptBuilder):
            def build(self, package: ContextPackage) -> PromptBundle:
                return PromptBundle(system_prompt="SYS", user_prompt="USR")

        engine = GraphRAGEngine(FakeContextBuilder(package), provider, StaticPromptBuilder())
        engine.answer("q")

        assert provider.received_calls[0] == {"system_prompt": "SYS", "user_prompt": "USR"}


# ===========================================================================
# GraphRAGEngine — response shape
# ===========================================================================

class TestGraphRAGResponseStructure:
    def test_response_is_graphrag_response(self):
        package = _make_context_package("How does fetch work?")
        engine = GraphRAGEngine(FakeContextBuilder(package), RecordingLLMProvider("the answer"))

        response = engine.answer("How does fetch work?")

        assert isinstance(response, GraphRAGResponse)
        assert response.question == "How does fetch work?"
        assert response.answer == "the answer"

    def test_source_nodes_mirror_resolved_nodes(self):
        rn = _make_resolved_node(node_id="Retriever.fetch", score=31.0)
        package = _make_context_package("q", resolved_nodes=[rn])
        engine = GraphRAGEngine(FakeContextBuilder(package), RecordingLLMProvider())

        response = engine.answer("q")

        assert len(response.source_nodes) == 1
        source = response.source_nodes[0]
        assert source.node_id == "Retriever.fetch"
        assert source.node_type == "Method"
        assert source.score == 31.0
        assert source.file_path == "app/utils.py"
        assert source.line_number == 15

    def test_retrieval_metadata_reflects_package(self):
        package = _make_context_package("q")
        engine = GraphRAGEngine(FakeContextBuilder(package, top_k=7, max_hops=2), RecordingLLMProvider())

        response = engine.answer("q")
        meta = response.retrieval_metadata

        assert meta.intent_categories == ["retrieval"]
        assert meta.keywords == ["fetch"]
        assert meta.resolved_node_count == 1
        assert meta.subgraph_node_count == 2
        assert meta.subgraph_edge_count == 1
        # No explicit override passed -> falls back to the (fake) builder's defaults
        assert meta.top_k == 7
        assert meta.max_hops == 2

    def test_explicit_overrides_take_precedence_in_metadata(self):
        package = _make_context_package("q")
        engine = GraphRAGEngine(FakeContextBuilder(package, top_k=7, max_hops=2), RecordingLLMProvider())

        response = engine.answer("q", top_k=99, max_hops=4)

        assert response.retrieval_metadata.top_k == 99
        assert response.retrieval_metadata.max_hops == 4

    def test_response_is_json_serialisable(self):
        package = _make_context_package("q")
        engine = GraphRAGEngine(FakeContextBuilder(package), RecordingLLMProvider())
        response = engine.answer("q")

        dumped = response.model_dump_json()
        assert "source_nodes" in dumped
        assert "retrieval_metadata" in dumped


# ===========================================================================
# No-context / empty-retrieval behaviour
# ===========================================================================

class TestNoContextHandling:
    def test_no_resolved_nodes_short_circuits_llm_by_default(self):
        package = _make_context_package("unrelated question", resolved_nodes=[])
        provider = RecordingLLMProvider()
        engine = GraphRAGEngine(FakeContextBuilder(package), provider)

        response = engine.answer("unrelated question")

        assert response.answer == NO_CONTEXT_ANSWER
        assert response.source_nodes == []
        assert len(provider.received_calls) == 0  # LLM never called

    def test_require_resolved_nodes_false_still_calls_llm(self):
        package = _make_context_package("unrelated question", resolved_nodes=[])
        provider = RecordingLLMProvider("answered anyway")
        engine = GraphRAGEngine(
            FakeContextBuilder(package), provider, require_resolved_nodes=False
        )

        response = engine.answer("unrelated question")

        assert response.answer == "answered anyway"
        assert len(provider.received_calls) == 1


# ===========================================================================
# LLM failure handling
# ===========================================================================

class TestLLMFailureHandling:
    def test_llm_exception_is_wrapped_in_llm_provider_error(self):
        package = _make_context_package("q")
        engine = GraphRAGEngine(FakeContextBuilder(package), FailingLLMProvider())

        with pytest.raises(LLMProviderError):
            engine.answer("q")

    def test_empty_llm_response_raises_llm_provider_error(self):
        package = _make_context_package("q")
        engine = GraphRAGEngine(FakeContextBuilder(package), EmptyLLMProvider())

        with pytest.raises(LLMProviderError):
            engine.answer("q")


# ===========================================================================
# LLMProvider implementations
# ===========================================================================

class TestLLMProviderImplementations:
    def test_echo_provider_returns_deterministic_diagnostic_text(self):
        provider = EchoLLMProvider()
        result = provider.generate(system_prompt="sys", user_prompt="usr")
        assert "EchoLLMProvider" in result
        assert isinstance(result, str)

    def test_callable_provider_delegates_to_function(self):
        captured = {}

        def fn(system, user):
            captured["system"] = system
            captured["user"] = user
            return "delegated answer"

        provider = CallableLLMProvider(fn)
        result = provider.generate(system_prompt="sys", user_prompt="usr")

        assert result == "delegated answer"
        assert captured == {"system": "sys", "user": "usr"}

    def test_anthropic_provider_requires_model(self):
        with pytest.raises(ValueError):
            AnthropicLLMProvider(model="")

    def test_anthropic_provider_uses_injected_client(self):
        class FakeTextBlock:
            type = "text"
            text = "anthropic answer"

        class FakeResponse:
            content = [FakeTextBlock()]

        class FakeMessages:
            def create(self, **kwargs):
                self.last_kwargs = kwargs
                return FakeResponse()

        class FakeClient:
            def __init__(self):
                self.messages = FakeMessages()

        fake_client = FakeClient()
        provider = AnthropicLLMProvider(model="some-model-id", client=fake_client)

        result = provider.generate(system_prompt="sys", user_prompt="usr")

        assert result == "anthropic answer"
        assert fake_client.messages.last_kwargs["model"] == "some-model-id"
        assert fake_client.messages.last_kwargs["system"] == "sys"


# ===========================================================================
# Integration tests — real ContextBuilder, real graph, fake LLM only
# ===========================================================================

@pytest.fixture()
def tiny_real_graph() -> RepositoryGraph:
    nodes = [
        GraphNode(id="app/utils.py", type=NodeType.FILE, label="utils.py", file_path="app/utils.py"),
        GraphNode(
            id="Retriever", type=NodeType.CLASS, label="Retriever",
            file_path="app/utils.py", line_number=10, docstring="Retrieves things.",
        ),
        GraphNode(
            id="Retriever.fetch", type=NodeType.METHOD, label="fetch",
            file_path="app/utils.py", line_number=15, docstring="Fetch data from source.",
        ),
    ]
    edges = [
        GraphEdge(source="app/utils.py", target="Retriever", relationship=RelationshipType.CONTAINS),
        GraphEdge(source="Retriever", target="Retriever.fetch", relationship=RelationshipType.CONTAINS),
    ]
    return RepositoryGraph(nodes=nodes, edges=edges)


class TestIntegrationWithRealContextBuilder:
    def test_build_graphrag_engine_runs_end_to_end(self, tiny_real_graph):
        provider = RecordingLLMProvider("real-pipeline answer")
        engine = build_graphrag_engine(tiny_real_graph, provider, top_k=5, max_hops=1)

        response = engine.answer("How does fetch work?")

        assert response.answer == "real-pipeline answer"
        assert any(n.node_id == "Retriever.fetch" for n in response.source_nodes)
        assert "How does fetch work?" in provider.received_calls[0]["user_prompt"]
        assert response.retrieval_metadata.top_k == 5
        assert response.retrieval_metadata.max_hops == 1

    def test_unrelated_question_yields_no_context_answer(self, tiny_real_graph):
        provider = RecordingLLMProvider()
        engine = build_graphrag_engine(tiny_real_graph, provider)

        response = engine.answer("What is the airspeed velocity of an unladen swallow?")

        assert response.answer == NO_CONTEXT_ANSWER
        assert len(provider.received_calls) == 0

    def test_real_context_builder_can_be_used_directly(self, tiny_real_graph):
        """Engine should also accept a real ContextBuilder instance, not just the factory."""
        real_builder = build_context_builder(tiny_real_graph, top_k=5, max_hops=1)
        provider = RecordingLLMProvider("direct construction answer")
        engine = GraphRAGEngine(real_builder, provider)

        response = engine.answer("How does fetch work?")

        assert response.answer == "direct construction answer"
        assert response.retrieval_metadata.resolved_node_count >= 1
