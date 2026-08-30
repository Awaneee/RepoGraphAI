"""
app/parsers/typescript_parser.py
===================================
TypeScript/JavaScript code parser using tree-sitter.

Produces ``ParsedFile`` objects in exactly the same schema as
``CodeParser`` (Python), making ``GraphBuilder``, ``QueryResolver``,
``ContextBuilder``, and ``GraphRAGEngine`` language-agnostic — none of
those layers know or care whether the parsed files were Python or TypeScript.

Supported constructs
---------------------
- Classes (including abstract classes and interfaces)
- Methods (instance and static)
- Functions (top-level function declarations and arrow functions assigned
  to const/let/var at the module level)
- Imports (import … from "…" and require("…"))
- Decorators (@decorator on classes and methods)
- Call expressions (direct calls and method calls)
- Inheritance (extends clause)

Limitations (by design — mirrors CodeParser's scope)
------------------------------------------------------
- No type inference (types are syntactic strings only).
- Relative imports are included (unlike CodeParser, which skips them)
  because TypeScript projects use relative imports pervasively.
- Dynamic requires / computed import() paths are not resolved.
- Nested classes / closures are not recursively parsed.

Requires: pip install tree-sitter tree-sitter-typescript
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from app.models.pydantic_models import (
    ParsedClass,
    ParsedDecorator,
    ParsedFile,
    ParsedFunction,
    ParsedRepository,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# tree-sitter setup (lazy — only load when first used)
# ---------------------------------------------------------------------------

_TS_LANGUAGE = None
_TSX_LANGUAGE = None
_PARSER = None


def _get_parser():
    global _TS_LANGUAGE, _TSX_LANGUAGE, _PARSER
    if _PARSER is not None:
        return _PARSER

    try:
        import tree_sitter_typescript as ts_ts
        from tree_sitter import Language, Parser

        _TS_LANGUAGE = Language(ts_ts.language_typescript())
        _TSX_LANGUAGE = Language(ts_ts.language_tsx())
        _PARSER = Parser(_TS_LANGUAGE)
        logger.debug("tree-sitter TypeScript parser initialized.")
        return _PARSER
    except ImportError as exc:
        raise ImportError(
            "TypeScript parsing requires tree-sitter-typescript. "
            "Install with: pip install tree-sitter tree-sitter-typescript"
        ) from exc


def is_available() -> bool:
    """Return True if tree-sitter-typescript is installed."""
    import importlib.util

    return (
        importlib.util.find_spec("tree_sitter") is not None
        and importlib.util.find_spec("tree_sitter_typescript") is not None
    )


# ---------------------------------------------------------------------------
# Node traversal helpers
# ---------------------------------------------------------------------------


def _text(node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _child_by_type(node, *types: str):
    for child in node.children:
        if child.type in types:
            return child
    return None


def _children_by_type(node, *types: str):
    return [c for c in node.children if c.type in types]


def _find_all(node, *types: str):
    """DFS traversal yielding all descendant nodes of given types."""
    for child in node.children:
        if child.type in types:
            yield child
        yield from _find_all(child, *types)


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def _extract_decorators(node, source: bytes) -> list[ParsedDecorator]:
    """Extract @decorators from a class_declaration or method_definition."""
    decorators = []
    for child in node.children:
        if child.type == "decorator":
            name_node = _child_by_type(child, "identifier", "member_expression", "call_expression")
            if name_node:
                if name_node.type == "call_expression":
                    func_node = _child_by_type(name_node, "identifier", "member_expression")
                    raw = _text(func_node, source) if func_node else _text(name_node, source)
                    decorators.append(ParsedDecorator(name=raw, is_call=True))
                else:
                    decorators.append(ParsedDecorator(name=_text(name_node, source), is_call=False))
    return decorators


def _extract_calls(node, source: bytes) -> list[str]:
    """Extract all called function/method names from a function body."""
    seen: set[str] = set()
    for call in _find_all(node, "call_expression"):
        func = _child_by_type(call, "identifier", "member_expression")
        if func is None:
            continue
        if func.type == "identifier":
            seen.add(_text(func, source))
        elif func.type == "member_expression":
            prop = _child_by_type(func, "property_identifier")
            if prop:
                seen.add(_text(prop, source))
    return sorted(seen)


def _method_name(method_node, source: bytes) -> Optional[str]:
    name_node = _child_by_type(
        method_node,
        "property_identifier",
        "computed_property_name",
        "private_property_identifier",
    )
    if name_node:
        return _text(name_node, source)
    # constructor keyword
    if any(c.type == "constructor" for c in method_node.children):
        return "__init__"
    return None


def _extract_methods(class_body, source: bytes) -> list[ParsedFunction]:
    methods = []
    for node in class_body.children:
        if node.type in (
            "method_definition",
            "abstract_method_definition",
            "public_field_definition",
        ):
            name = _method_name(node, source)
            if not name:
                continue
            body = _child_by_type(node, "statement_block")
            calls = _extract_calls(body, source) if body else []
            methods.append(
                ParsedFunction(
                    name=name,
                    line_number=node.start_point[0] + 1,
                    arguments=[],
                    return_type=None,
                    docstring=None,
                    calls=calls,
                    instantiates=[],
                    decorators=_extract_decorators(node, source),
                )
            )
    return methods


def _extract_source_snippet(node, source: bytes, max_lines: int = 50) -> Optional[str]:
    """Extract raw source for a function or class body (bounded)."""
    start = node.start_byte
    end = node.end_byte
    raw = source[start:end].decode("utf-8", errors="replace")
    lines = raw.split("\n")
    if len(lines) > max_lines:
        head = lines[:30]
        tail = lines[-5:]
        return (
            "\n".join(head)
            + f"\n// ... [{len(lines) - 35} lines truncated] ...\n"
            + "\n".join(tail)
        )
    return raw


# ---------------------------------------------------------------------------
# TypeScriptParser
# ---------------------------------------------------------------------------


class TypeScriptParser:
    """
    Parse TypeScript/JavaScript source files into ``ParsedFile`` objects.

    The output schema is identical to ``CodeParser``'s output — both produce
    ``ParsedFile`` objects that ``GraphBuilder`` can process without any
    language-specific logic.

    Usage
    -----
    ::

        parser = TypeScriptParser()
        parsed_file = parser.parse_file("src/utils.ts")
        parsed_repo = parser.parse_repository("./my-ts-project")
    """

    _SKIP_DIRS: frozenset[str] = frozenset(
        {
            ".git",
            "__pycache__",
            "node_modules",
            "dist",
            "build",
            ".venv",
            "venv",
            ".next",
            ".nuxt",
            "out",
            "coverage",
            ".github",
            ".idea",
            ".vscode",
        }
    )

    _TS_EXTENSIONS: frozenset[str] = frozenset(
        {
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".mjs",
            ".cjs",
        }
    )

    def parse_file(self, file_path: str) -> ParsedFile:
        parser = _get_parser()

        with open(file_path, "rb") as fh:
            source = fh.read()

        # Use TSX parser for .tsx/.jsx files
        if file_path.endswith((".tsx", ".jsx")):
            import tree_sitter_typescript as ts_ts
            from tree_sitter import Language, Parser

            tsx_lang = Language(ts_ts.language_tsx())
            tsx_parser = Parser(tsx_lang)
            tree = tsx_parser.parse(source)
        else:
            tree = parser.parse(source)

        root = tree.root_node

        imports: list[str] = []
        classes: list[ParsedClass] = []
        functions: list[ParsedFunction] = []

        # --- Imports ---
        for imp in _find_all(root, "import_statement", "import_declaration"):
            # import ... from "module"
            src_node = _child_by_type(imp, "string")
            if src_node:
                module = _text(src_node, source).strip("'\"")
                imports.append(module)

        for call in _find_all(root, "call_expression"):
            func_node = _child_by_type(call, "identifier")
            if func_node and _text(func_node, source) == "require":
                args = _child_by_type(call, "arguments")
                if args:
                    str_node = _child_by_type(args, "string")
                    if str_node:
                        imports.append(_text(str_node, source).strip("'\""))

        # Deduplicate imports
        seen_imports: set[str] = set()
        deduped_imports = []
        for imp in imports:
            if imp not in seen_imports:
                seen_imports.add(imp)
                deduped_imports.append(imp)
        imports = deduped_imports

        # --- Classes, interfaces ---
        for cls_node in _find_all(
            root,
            "class_declaration",
            "abstract_class_declaration",
            "interface_declaration",
            "class",
        ):
            name_node = _child_by_type(cls_node, "type_identifier", "identifier")
            if name_node is None:
                continue
            name = _text(name_node, source)

            # Inheritance (extends clause)
            parents: list[str] = []
            for clause in _children_by_type(cls_node, "class_heritage", "extends_clause"):
                for ref in _find_all(clause, "identifier", "type_identifier"):
                    parents.append(_text(ref, source))
                    break

            # Methods
            body = _child_by_type(cls_node, "class_body", "interface_body")
            methods = _extract_methods(body, source) if body else []

            # Source snippet for the class header + method signatures
            source_snippet: Optional[str] = None
            if body:
                header_end = body.start_byte
                class_text = source[cls_node.start_byte : header_end].decode(
                    "utf-8", errors="replace"
                )
                method_sigs = "\n".join(f"  {m.name}()" for m in methods)
                source_snippet = class_text + "{\n" + method_sigs + "\n}"

            classes.append(
                ParsedClass(
                    name=name,
                    line_number=cls_node.start_point[0] + 1,
                    inherits_from=parents,
                    docstring=source_snippet,
                    methods=methods,
                    decorators=_extract_decorators(cls_node, source),
                )
            )

        # --- Top-level functions (function declarations + const fn = () => {}) ---
        for fn_node in _find_all(root, "function_declaration", "generator_function_declaration"):
            name_node = _child_by_type(fn_node, "identifier")
            if name_node is None:
                continue
            name = _text(name_node, source)
            body = _child_by_type(fn_node, "statement_block")
            calls = _extract_calls(body, source) if body else []
            src = _extract_source_snippet(fn_node, source) if body else None
            functions.append(
                ParsedFunction(
                    name=name,
                    line_number=fn_node.start_point[0] + 1,
                    arguments=[],
                    return_type=None,
                    docstring=src,
                    calls=calls,
                    instantiates=[],
                    decorators=[],
                )
            )

        # --- const/let/var arrow function or function expression at module scope ---
        for var_decl in _children_by_type(root, "lexical_declaration", "variable_declaration"):
            for declarator in _children_by_type(var_decl, "variable_declarator"):
                name_node = _child_by_type(declarator, "identifier")
                val_node = _child_by_type(
                    declarator,
                    "arrow_function",
                    "function",
                    "function_expression",
                )
                if name_node and val_node:
                    name = _text(name_node, source)
                    body = _child_by_type(val_node, "statement_block")
                    calls = _extract_calls(body, source) if body else []
                    src = _extract_source_snippet(val_node, source) if body else None
                    functions.append(
                        ParsedFunction(
                            name=name,
                            line_number=declarator.start_point[0] + 1,
                            arguments=[],
                            return_type=None,
                            docstring=src,
                            calls=calls,
                            instantiates=[],
                            decorators=[],
                        )
                    )

        return ParsedFile(
            file_path=file_path,
            imports=imports,
            classes=classes,
            functions=functions,
        )

    def parse_repository(self, repository_path: str) -> ParsedRepository:
        parsed_files: list[ParsedFile] = []

        for root_dir, dirs, files in os.walk(repository_path, topdown=True):
            dirs[:] = [d for d in dirs if d not in self._SKIP_DIRS]

            for filename in files:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in self._TS_EXTENSIONS:
                    continue
                if (
                    filename.startswith("test_")
                    or filename.endswith(".test.ts")
                    or filename.endswith(".spec.ts")
                ):
                    continue

                file_path = os.path.join(root_dir, filename)
                try:
                    parsed_files.append(self.parse_file(file_path))
                except Exception as exc:
                    logger.warning("Skipping %s: %s", file_path, exc)
                    continue

        logger.info("Parsed %d TypeScript/JS files from %s", len(parsed_files), repository_path)
        return ParsedRepository(
            repository_name=os.path.basename(repository_path.rstrip("/\\")),
            total_python_files=len(parsed_files),
            files=parsed_files,
        )
