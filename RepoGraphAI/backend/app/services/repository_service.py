import os
import shutil
import heapq

from collections import Counter
from git import Repo

from app.models.pydantic_models import RepositorySummary


class RepositoryService:

    EXTENSION_LANGUAGE_MAP = {
        ".py": "Python",
        ".java": "Java",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".cpp": "C++",
        ".c": "C",
        ".cs": "C#",
        ".go": "Go",
        ".rs": "Rust",
        ".kt": "Kotlin",
        ".swift": "Swift",
        ".php": "PHP",
        ".rb": "Ruby",
        ".scala": "Scala",
        ".dart": "Dart",
        ".html": "HTML",
        ".css": "CSS",
        ".sh": "Shell",
        ".yaml": "YAML",
        ".yml": "YAML",
        ".json": "JSON",
        ".xml": "XML",
        ".md": "Markdown",
        ".toml": "TOML"
    }

    EXCLUDED_DIRECTORIES = {
        ".git",
        ".github",
        "__pycache__",
        ".venv",
        "node_modules",
        ".idea",
        ".vscode"
    }

    SOURCE_CODE_EXTENSIONS = {
        ".py",
        ".java",
        ".js",
        ".ts",
        ".cpp",
        ".c",
        ".cs",
        ".go",
        ".rs",
        ".kt",
        ".swift",
        ".php",
        ".rb",
        ".scala",
        ".dart"
    }

    DOCUMENTATION_EXTENSIONS = {
        ".md"
    }

    CONFIGURATION_EXTENSIONS = {
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".xml"
    }

    ASSET_EXTENSIONS = {
        ".png",
        ".jpg",
        ".jpeg",
        ".svg",
        ".gif",
        ".webp"
    }

    def clone_repository(
        self,
        repo_url: str
    ) -> str:

        repo_name = (
            repo_url
            .rstrip("/")
            .split("/")[-1]
        )

        local_path = os.path.join(
            "repos",
            repo_name
        )

        if os.path.exists(local_path):
            shutil.rmtree(local_path)

        Repo.clone_from(
            repo_url,
            local_path
        )

        return local_path

    def detect_framework(
        self,
        repo_path: str
    ) -> str | None:

        pyproject_path = os.path.join(
            repo_path,
            "pyproject.toml"
        )

        requirements_path = os.path.join(
            repo_path,
            "requirements.txt"
        )

        try:

            if os.path.exists(pyproject_path):

                with open(
                    pyproject_path,
                    "r",
                    encoding="utf-8"
                ) as file:

                    content = file.read().lower()

                    if "fastapi" in content:
                        return "FastAPI"

                    if "django" in content:
                        return "Django"

                    if "flask" in content:
                        return "Flask"

            if os.path.exists(requirements_path):

                with open(
                    requirements_path,
                    "r",
                    encoding="utf-8"
                ) as file:

                    content = file.read().lower()

                    if "fastapi" in content:
                        return "FastAPI"

                    if "django" in content:
                        return "Django"

                    if "flask" in content:
                        return "Flask"

        except Exception:
            pass

        return None

    def classify_repository_type(
        self,
        framework: str | None
    ) -> str:

        if framework in {
            "FastAPI",
            "Django",
            "Flask"
        }:
            return "Backend API"

        return "General Software Project"

    def scan_repository(
        self,
        repo_path: str
    ) -> dict:

        total_files = 0
        total_directories = 0
        repository_size_bytes = 0

        extension_distribution = Counter()
        language_distribution = Counter()
        file_category_distribution = Counter()

        largest_files = []

        top_level_directories = []

        # Collect top-level directories
        for item in os.listdir(repo_path):

            item_path = os.path.join(
                repo_path,
                item
            )

            if (
                os.path.isdir(item_path)
                and item not in self.EXCLUDED_DIRECTORIES
            ):
                top_level_directories.append(item)

        for root, dirs, files in os.walk(repo_path):

            dirs[:] = [
                d
                for d in dirs
                if d not in self.EXCLUDED_DIRECTORIES
            ]

            total_directories += len(dirs)

            for file in files:

                file_path = os.path.join(
                    root,
                    file
                )

                try:

                    file_size = os.path.getsize(
                        file_path
                    )

                    total_files += 1

                    repository_size_bytes += file_size

                    relative_path = os.path.relpath(
                        file_path,
                        repo_path
                    )

                    largest_files.append(
                        {
                            "file": relative_path,
                            "size_bytes": file_size
                        }
                    )

                    extension = (
                        os.path.splitext(file)[1]
                        .lower()
                    )

                    if not extension:
                        extension = "NO_EXTENSION"

                    extension_distribution[
                        extension
                    ] += 1

                    if (
                        extension
                        in self.EXTENSION_LANGUAGE_MAP
                    ):
                        language = (
                            self
                            .EXTENSION_LANGUAGE_MAP[
                                extension
                            ]
                        )

                        language_distribution[
                            language
                        ] += 1

                    if (
                        extension
                        in self.SOURCE_CODE_EXTENSIONS
                    ):
                        file_category_distribution[
                            "source_code"
                        ] += 1

                    elif (
                        extension
                        in self.DOCUMENTATION_EXTENSIONS
                    ):
                        file_category_distribution[
                            "documentation"
                        ] += 1

                    elif (
                        extension
                        in self.CONFIGURATION_EXTENSIONS
                    ):
                        file_category_distribution[
                            "configuration"
                        ] += 1

                    elif (
                        extension
                        in self.ASSET_EXTENSIONS
                    ):
                        file_category_distribution[
                            "assets"
                        ] += 1

                    elif "test" in relative_path.lower():

                        file_category_distribution[
                            "tests"
                        ] += 1

                    else:

                        file_category_distribution[
                            "other"
                        ] += 1

                except (
                    PermissionError,
                    FileNotFoundError,
                    OSError
                ):
                    continue

        framework = self.detect_framework(
            repo_path
        )

        repository_type = (
            self.classify_repository_type(
                framework
            )
        )

        largest_files = heapq.nlargest(
            10,
            largest_files,
            key=lambda x: x["size_bytes"]
        )

        return {
            "total_files": total_files,
            "total_directories": total_directories,
            "repository_size_bytes": repository_size_bytes,
            "language_distribution": dict(
                language_distribution
            ),
            "file_extension_distribution": dict(
                extension_distribution
            ),
            "file_category_distribution": dict(
                file_category_distribution
            ),
            "top_level_directories": sorted(
                top_level_directories
            ),
            "framework": framework,
            "repository_type": repository_type,
            "largest_files": largest_files
        }

    def generate_summary(
        self,
        repo_path: str
    ) -> RepositorySummary:

        scan_result = self.scan_repository(
            repo_path
        )

        return RepositorySummary(
            repository_name=os.path.basename(
                repo_path
            ),
            repository_path=repo_path,
            repository_type=scan_result[
                "repository_type"
            ],
            framework=scan_result[
                "framework"
            ],
            total_files=scan_result[
                "total_files"
            ],
            total_directories=scan_result[
                "total_directories"
            ],
            repository_size_bytes=scan_result[
                "repository_size_bytes"
            ],
            language_distribution=scan_result[
                "language_distribution"
            ],
            file_extension_distribution=scan_result[
                "file_extension_distribution"
            ],
            file_category_distribution=scan_result[
                "file_category_distribution"
            ],
            top_level_directories=scan_result[
                "top_level_directories"
            ],
            largest_files=scan_result[
                "largest_files"
            ]
        )