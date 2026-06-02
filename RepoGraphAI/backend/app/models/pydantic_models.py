from pydantic import BaseModel


class RepositoryRequest(BaseModel):
    repo_url: str


class RepositorySummary(BaseModel):

    repository_name: str
    repository_path: str

    repository_type: str
    framework: str | None

    total_files: int
    total_directories: int

    repository_size_bytes: int

    language_distribution: dict[str, int]

    file_extension_distribution: dict[str, int]

    file_category_distribution: dict[str, int]

    top_level_directories: list[str]

    largest_files: list[dict]