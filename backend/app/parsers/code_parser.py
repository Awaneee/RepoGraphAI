import ast
import os
import sys

from app.models.pydantic_models import (
    ParsedDecorator,
    ParsedFile,
    ParsedClass,
    ParsedFunction,
    ParsedRepository,
)


# ---------------------------------------------------------------------------
# Stdlib module names (top-level only; sufficient for origin classification)
# ---------------------------------------------------------------------------

_STDLIB_TOP_LEVEL: frozenset[str] = frozenset(sys.stdlib_module_names)  # Python 3.10+


def _is_stdlib(module_name: str) -> bool:
    top = module_name.split(".")[0]
    return top in _STDLIB_TOP_LEVEL


# ---------------------------------------------------------------------------
# CodeParser
# ---------------------------------------------------------------------------

class CodeParser:
    """
    Parses Python source files into structured AST representations.

    Design principles
    -----------------
    - All extraction is purely syntactic (no runtime imports, no type inference).
    - The parser is intentionally liberal: it captures more than GraphBuilder
      needs, so GraphBuilder can apply semantic filtering with a complete
      symbol table rather than requiring multiple parse passes.
    - Every new field added here has a corresponding edge type in
      RelationshipType; nothing is extracted "speculatively".
    """

    BUILTINS: frozenset[str] = frozenset({
        "len", "list", "dict", "set", "tuple", "sorted", "print",
        "str", "int", "float", "bool", "range", "enumerate", "open",
        "min", "max", "sum", "any", "all", "zip", "map", "filter",
        "isinstance", "issubclass", "getattr", "setattr", "hasattr",
        "type", "id", "repr", "hash", "iter", "next", "reversed",
        "abs", "round", "pow", "divmod", "hex", "oct", "bin",
        "callable", "vars", "dir", "super", "object",
    })

    # ------------------------------------------------------------------
    # Decorator extraction
    # ------------------------------------------------------------------

    def _extract_decorator(self, decorator_node: ast.expr) -> ParsedDecorator:
        """
        Convert a decorator AST node to a ParsedDecorator.

        Handles three forms:
          @name                 → Name node
          @a.b.c                → Attribute chain
          @name(args)           → Call node (is_call=True)
          @a.b(args)            → Call node on Attribute (is_call=True)
        """

        is_call = isinstance(decorator_node, ast.Call)

        # Unwrap the call to get the underlying reference
        ref = decorator_node.func if is_call else decorator_node

        name = self._unparse_decorator_ref(ref)

        return ParsedDecorator(name=name, is_call=is_call)

    @staticmethod
    def _unparse_decorator_ref(node: ast.expr) -> str:
        """Flatten a Name or Attribute chain into a dotted string."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = CodeParser._unparse_decorator_ref(node.value)
            return f"{parent}.{node.attr}"
        # Fallback for exotic decorator expressions
        try:
            return ast.unparse(node)
        except Exception:
            return "<unknown>"

    # ------------------------------------------------------------------
    # Call / instantiation extraction
    # ------------------------------------------------------------------

    def _extract_calls_from_body(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[str]:
        """
        Walk the function body and collect all called names.

        Returns a sorted, deduplicated list of callee name strings.
        Builtins are filtered out here for efficiency.

        Note: GraphBuilder is responsible for splitting this list into
        CALLS edges (callee is a Function/Method) and INSTANTIATES edges
        (callee is a Class), because the full symbol table only exists
        after parsing the entire repository.
        """

        seen: set[str] = set()

        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue

            name: str | None = None

            if isinstance(child.func, ast.Name):
                name = child.func.id

            elif isinstance(child.func, ast.Attribute):
                # Capture the method name; GraphBuilder resolves the receiver.
                name = child.func.attr

            if name and name not in self.BUILTINS:
                seen.add(name)

        return sorted(seen)

    # ------------------------------------------------------------------
    # Function / method extraction
    # ------------------------------------------------------------------

    def extract_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> ParsedFunction:
        """
        Extract a ParsedFunction from a function or async function def node.

        Captures:
          - arguments (positional + keyword, excluding *args/**kwargs names
            for now to keep the schema clean)
          - return type annotation (unparsed string)
          - docstring
          - all non-builtin call names (split into CALLS / INSTANTIATES by
            GraphBuilder)
          - decorators
        """

        arguments = [
            arg.arg
            for arg in node.args.args
        ]

        calls = self._extract_calls_from_body(node)

        return_type: str | None = None
        if node.returns:
            try:
                return_type = ast.unparse(node.returns)
            except Exception:
                return_type = None

        decorators = [
            self._extract_decorator(d)
            for d in node.decorator_list
        ]

        return ParsedFunction(
            name=node.name,
            line_number=node.lineno,
            arguments=arguments,
            return_type=return_type,
            docstring=ast.get_docstring(node),
            calls=calls,
            instantiates=[],   # GraphBuilder fills this in second pass
            decorators=decorators,
        )

    # ------------------------------------------------------------------
    # Class extraction
    # ------------------------------------------------------------------

    def _extract_bases(self, node: ast.ClassDef) -> list[str]:
        bases: list[str] = []
        for base in node.bases:
            try:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(base.attr)
                else:
                    # Generic subscript bases like Generic[T]
                    bases.append(ast.unparse(base))
            except Exception:
                continue
        return bases

    def _extract_class(self, node: ast.ClassDef) -> ParsedClass:

        bases = self._extract_bases(node)

        methods: list[ParsedFunction] = []
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(self.extract_function(child))

        decorators = [
            self._extract_decorator(d)
            for d in node.decorator_list
        ]

        return ParsedClass(
            name=node.name,
            line_number=node.lineno,
            inherits_from=bases,
            docstring=ast.get_docstring(node),
            methods=methods,
            decorators=decorators,
        )

    # ------------------------------------------------------------------
    # Import extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_imports(tree: ast.Module) -> list[str]:
        """
        Extract all imported module paths from the top level of a module.

        `import os.path`             → "os.path"
        `from fastapi import APIRouter` → "fastapi"
        `from .utils import helper`  → relative imports are skipped
                                       (they resolve to internal modules but
                                        require package context we may not
                                        have; GraphBuilder handles them via
                                        file path matching)

        Returns a sorted, deduplicated list.
        """

        seen: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    seen.add(alias.name)

            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    # Absolute import only
                    seen.add(node.module)
                # Relative imports (node.level > 0) are skipped intentionally

        return sorted(seen)

    # ------------------------------------------------------------------
    # File parsing
    # ------------------------------------------------------------------

    def parse_file(self, file_path: str) -> ParsedFile:

        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            source_code = fh.read()

        try:
            tree = ast.parse(source_code, filename=file_path)
        except SyntaxError as exc:
            raise ValueError(f"Syntax error in {file_path}: {exc}") from exc

        imports = self._extract_imports(tree)

        classes: list[ParsedClass] = []
        functions: list[ParsedFunction] = []

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                classes.append(self._extract_class(node))

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(self.extract_function(node))

        return ParsedFile(
            file_path=file_path,
            imports=imports,
            classes=classes,
            functions=functions,
        )

    # ------------------------------------------------------------------
    # Repository parsing
    # ------------------------------------------------------------------

    _SKIP_DIRS: frozenset[str] = frozenset({
        ".git", "__pycache__", ".venv", "venv", "env",
        "node_modules", "dist", "build",
        "docs", "docs_src",
        "examples", "example",
        "tests", "test",
        ".github", ".idea", ".vscode",
        ".mypy_cache", ".pytest_cache", ".ruff_cache",
    })

    def parse_repository(self, repository_path: str) -> ParsedRepository:

        parsed_files: list[ParsedFile] = []

        for root, dirs, files in os.walk(repository_path, topdown=True):
            dirs[:] = [d for d in dirs if d not in self._SKIP_DIRS]

            for filename in files:
                if not filename.endswith(".py"):
                    continue
                if filename.startswith("test_") or filename.endswith("_test.py"):
                    continue

                file_path = os.path.join(root, filename)

                try:
                    parsed_files.append(self.parse_file(file_path))
                except Exception as exc:
                    print(f"[CodeParser] Skipping {file_path}: {exc}")
                    continue

        print(f"[CodeParser] Parsed {len(parsed_files)} Python files")

        return ParsedRepository(
            repository_name=os.path.basename(repository_path.rstrip("/\\")),
            total_python_files=len(parsed_files),
            files=parsed_files,
        )