"""
tests/test_source_code.py
==========================
Verify that source_code fields are correctly extracted and stored in
graph nodes for FUNCTION and METHOD types.

Tests use CodeParser directly (no real git clone) on in-memory Python
source strings written to temporary files.
"""

from __future__ import annotations

import os
import textwrap
import tempfile

import pytest

from app.parsers.code_parser import CodeParser, _truncate_source, _MAX_SOURCE_LINES
from app.graph.graph_builder import GraphBuilder
from app.models.pydantic_models import NodeType


# ===========================================================================
# Helpers
# ===========================================================================

def _parse_source(source: str) -> tuple:
    """
    Write source to a temp file, parse it with CodeParser, and return
    (ParsedFile, CodeParser, temp_path).
    """
    parser = CodeParser()
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", encoding="utf-8", delete=False
    ) as f:
        f.write(source)
        path = f.name
    try:
        parsed = parser.parse_file(path)
    finally:
        os.unlink(path)
    return parsed


def _build_graph_from_source(source: str):
    """Parse source, build graph, and return the RepositoryGraph."""
    parser = CodeParser()
    builder = GraphBuilder()
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", encoding="utf-8", delete=False
    ) as f:
        f.write(source)
        path = f.name
    try:
        pf = parser.parse_file(path)
        from app.models.pydantic_models import ParsedRepository
        repo = ParsedRepository(
            repository_name="test_repo",
            total_python_files=1,
            files=[pf],
        )
        return builder.build_graph(repo, "")
    finally:
        os.unlink(path)


# ===========================================================================
# CodeParser source code extraction
# ===========================================================================

class TestCodeParserSourceCode:

    def test_function_source_code_present(self):
        source = textwrap.dedent("""\
            def hello(name: str) -> str:
                '''Say hello.'''
                return f"Hello, {name}!"
        """)
        parsed = _parse_source(source)
        assert len(parsed.functions) == 1
        fn = parsed.functions[0]
        assert fn.source_code is not None
        assert "def hello" in fn.source_code

    def test_function_source_code_includes_body(self):
        source = textwrap.dedent("""\
            def compute(x, y):
                result = x + y
                return result
        """)
        parsed = _parse_source(source)
        fn = parsed.functions[0]
        assert "result = x + y" in fn.source_code
        assert "return result" in fn.source_code

    def test_function_source_code_includes_signature(self):
        source = textwrap.dedent("""\
            def process(items: list, threshold: int = 10) -> list:
                return [i for i in items if i > threshold]
        """)
        parsed = _parse_source(source)
        fn = parsed.functions[0]
        assert "def process(" in fn.source_code
        assert "threshold" in fn.source_code

    def test_method_source_code_present(self):
        source = textwrap.dedent("""\
            class MyClass:
                def my_method(self, x):
                    return x * 2
        """)
        parsed = _parse_source(source)
        cls = parsed.classes[0]
        method = cls.methods[0]
        assert method.source_code is not None
        assert "def my_method" in method.source_code
        assert "return x * 2" in method.source_code

    def test_class_source_code_is_summary(self):
        source = textwrap.dedent("""\
            class MyService:
                '''A simple service.'''
                def do_something(self):
                    pass
                def do_other(self):
                    pass
        """)
        parsed = _parse_source(source)
        cls = parsed.classes[0]
        # Class source should contain class signature and method signatures
        assert cls.source_code is not None
        assert "class MyService" in cls.source_code
        # Should have method signatures
        assert "do_something" in cls.source_code
        assert "do_other" in cls.source_code

    def test_line_end_populated_for_functions(self):
        source = textwrap.dedent("""\
            def short():
                pass
        """)
        parsed = _parse_source(source)
        fn = parsed.functions[0]
        assert fn.line_end is not None
        assert fn.line_end >= fn.line_number

    def test_line_end_populated_for_methods(self):
        source = textwrap.dedent("""\
            class A:
                def method(self):
                    x = 1
                    y = 2
                    return x + y
        """)
        parsed = _parse_source(source)
        method = parsed.classes[0].methods[0]
        assert method.line_end is not None
        assert method.line_end > method.line_number

    def test_line_end_greater_than_line_number_for_multiline(self):
        source = textwrap.dedent("""\
            def multiline():
                a = 1
                b = 2
                c = 3
                d = 4
                return a + b + c + d
        """)
        parsed = _parse_source(source)
        fn = parsed.functions[0]
        assert fn.line_end > fn.line_number


# ===========================================================================
# Truncation logic
# ===========================================================================

class TestTruncateSource:

    def test_short_source_not_truncated(self):
        lines = [f"line {i}\n" for i in range(10)]
        result = _truncate_source(lines, 1)
        assert "[truncated]" not in result
        assert len(result.splitlines()) == 10

    def test_long_source_is_truncated(self):
        lines = [f"line {i}\n" for i in range(_MAX_SOURCE_LINES + 10)]
        result = _truncate_source(lines, 1)
        assert "truncated" in result.lower()

    def test_truncated_source_has_head_and_tail(self):
        lines = [f"# line {i:03d}\n" for i in range(100)]
        result = _truncate_source(lines, 1)
        # Head lines should be present
        assert "# line 000" in result
        assert "# line 029" in result
        # Tail lines should be present
        assert "# line 099" in result
        assert "# line 095" in result
        # Middle should be absent
        assert "# line 050" not in result

    def test_empty_lines_returns_empty_string(self):
        result = _truncate_source([], 1)
        assert result == ""

    def test_exactly_max_lines_not_truncated(self):
        lines = [f"line {i}\n" for i in range(_MAX_SOURCE_LINES)]
        result = _truncate_source(lines, 1)
        assert "truncated" not in result


# ===========================================================================
# GraphNode source_code field
# ===========================================================================

class TestGraphNodeSourceCode:

    def test_function_node_has_source_code(self):
        source = textwrap.dedent("""\
            def my_function(x):
                return x + 1
        """)
        graph = _build_graph_from_source(source)
        fn_nodes = [n for n in graph.nodes if n.type == NodeType.FUNCTION]
        assert len(fn_nodes) >= 1
        fn = fn_nodes[0]
        assert fn.source_code is not None
        assert "def my_function" in fn.source_code

    def test_method_node_has_source_code(self):
        source = textwrap.dedent("""\
            class Calculator:
                def add(self, a, b):
                    return a + b
        """)
        graph = _build_graph_from_source(source)
        method_nodes = [n for n in graph.nodes if n.type == NodeType.METHOD]
        assert len(method_nodes) >= 1
        method = method_nodes[0]
        assert method.source_code is not None
        assert "def add" in method.source_code

    def test_file_node_has_no_source_code(self):
        source = "x = 1\n"
        graph = _build_graph_from_source(source)
        file_nodes = [n for n in graph.nodes if n.type == NodeType.FILE]
        for fn in file_nodes:
            assert fn.source_code is None

    def test_line_end_in_function_node(self):
        source = textwrap.dedent("""\
            def my_func():
                a = 1
                b = 2
                return a + b
        """)
        graph = _build_graph_from_source(source)
        fn_nodes = [n for n in graph.nodes if n.type == NodeType.FUNCTION]
        assert fn_nodes
        fn = fn_nodes[0]
        assert fn.line_end is not None
        assert fn.line_end > fn.line_number

    def test_source_code_survives_graph_node_creation(self):
        """Ensure source_code is not lost during graph construction."""
        source = textwrap.dedent("""\
            def important_function(data):
                '''Process some data.'''
                result = []
                for item in data:
                    result.append(item * 2)
                return result
        """)
        graph = _build_graph_from_source(source)
        fn_nodes = [n for n in graph.nodes if n.type == NodeType.FUNCTION]
        assert fn_nodes
        fn = fn_nodes[0]
        assert "result.append" in fn.source_code
        assert "return result" in fn.source_code


# ===========================================================================
# LLM context includes source code
# ===========================================================================

class TestLlmContextIncludesSourceCode:

    def test_llm_context_contains_source_for_function(self):
        source = textwrap.dedent("""\
            def my_function(x: int) -> int:
                '''Doubles x.'''
                return x * 2
        """)
        graph = _build_graph_from_source(source)

        from app.retrievers.code_retriever import RepositoryRetriever
        retriever = RepositoryRetriever(graph)
        fn_nodes = [n for n in graph.nodes if n.type == NodeType.FUNCTION]
        if not fn_nodes:
            pytest.skip("No function nodes in graph")

        context = retriever.build_llm_context(fn_nodes[0].id)
        assert "Source:" in context
        assert "def my_function" in context or "return x * 2" in context
