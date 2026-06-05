import ast
import os

from app.models.pydantic_models import (
    ParsedFile,
    ParsedClass,
    ParsedFunction,
    ParsedRepository
)


class CodeParser:

    BUILTINS = {
        "len",
        "list",
        "dict",
        "set",
        "tuple",
        "sorted",
        "print",
        "str",
        "int",
        "float",
        "bool",
        "range",
        "enumerate",
        "open",
        "min",
        "max",
        "sum",
        "any",
        "all",
        "zip"
    }

    def extract_function(
        self,
        node: ast.FunctionDef
    ) -> ParsedFunction:

        arguments = [
            arg.arg
            for arg in node.args.args
        ]

        calls = []

        for child in ast.walk(node):

            if isinstance(
                child,
                ast.Call
            ):

                function_name = None

                if isinstance(
                    child.func,
                    ast.Name
                ):

                    function_name = (
                        child.func.id
                    )

                elif isinstance(
                    child.func,
                    ast.Attribute
                ):

                    function_name = (
                        child.func.attr
                    )

                if (
                    function_name
                    and function_name
                    not in self.BUILTINS
                ):

                    calls.append(
                        function_name
                    )

        return_type = None

        if node.returns:

            try:

                return_type = ast.unparse(
                    node.returns
                )

            except Exception:

                return_type = None

        return ParsedFunction(
            name=node.name,
            line_number=node.lineno,
            arguments=arguments,
            return_type=return_type,
            docstring=ast.get_docstring(
                node
            ),
            calls=sorted(
                list(
                    set(calls)
                )
            )
        )

    def parse_file(
        self,
        file_path: str
    ) -> ParsedFile:

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as file:

            source_code = file.read()

        tree = ast.parse(
            source_code
        )

        imports = []
        classes = []
        functions = []

        for node in tree.body:

            if isinstance(
                node,
                ast.Import
            ):

                for alias in node.names:

                    imports.append(
                        alias.name
                    )

            elif isinstance(
                node,
                ast.ImportFrom
            ):

                if node.module:

                    imports.append(
                        node.module
                    )

            elif isinstance(
                node,
                ast.ClassDef
            ):
                base_classes = []

                for base in node.bases:

                    try:

                        if isinstance(
                           base,
                           ast.Name
                         ):

                         base_classes.append(
                             base.id
                         )

                        elif isinstance(
                          base,
                        ast.Attribute
                        ):

                           base_classes.append(
                             base.attr
                            )

                    except Exception:

                      continue

                methods = []


                for class_node in node.body:

                    if isinstance(
                        class_node,
                        ast.FunctionDef
                    ):

                        methods.append(
                            self.extract_function(
                                class_node
                            )
                        )

                classes.append(
                    ParsedClass(
                        name=node.name,
                        line_number=node.lineno,
                        inherits_from=base_classes,
                        methods=methods
                    )
                )

            elif isinstance(
                node,
                ast.FunctionDef
            ):

                functions.append(
                    self.extract_function(
                        node
                    )
                )

        return ParsedFile(
            file_path=file_path,
            imports=sorted(
                list(
                    set(imports)
                )
            ),
            classes=classes,
            functions=functions
        )

    def parse_repository(
        self,
        repository_path: str
    ) -> ParsedRepository:

        parsed_files = []

        for root, dirs, files in os.walk(
            repository_path
        ):

            dirs[:] = [
                d
                for d in dirs
                if d not in {
                    ".git",
                    "__pycache__",
                    ".venv",
                    "venv",
                    "env",
                    "node_modules",
                    "dist",
                    "build",

                    # Documentation
                    "docs",
                    "docs_src",

                    # Examples
                    "examples",
                    "example",

                    # Tests
                    "tests",
                    "test",

                    # IDE / CI
                    ".github",
                    ".idea",
                    ".vscode"
                }
            ]

            for file in files:

                if not file.endswith(
                    ".py"
                ):
                    continue

                if (
                    file.startswith(
                        "test_"
                    )
                    or file.endswith(
                        "_test.py"
                    )
                ):
                    continue

                file_path = os.path.join(
                    root,
                    file
                )

                try:

                    parsed_files.append(
                        self.parse_file(
                            file_path
                        )
                    )

                except Exception as e:

                    print(
                        f"Failed to parse {file_path}: {e}"
                    )

                    continue

        print(
            f"Parsed {len(parsed_files)} Python files"
        )

        return ParsedRepository(
            repository_name=os.path.basename(
                repository_path
            ),
            total_python_files=len(
                parsed_files
            ),
            files=parsed_files
        )