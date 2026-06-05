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


class ParsedFunction(BaseModel):

    name: str

    line_number: int

    arguments: list[str]

    return_type: str | None

    docstring: str | None

    calls: list[str]

class ParsedClass(BaseModel):

    name: str

    line_number: int

    inherits_from: list[str] = []

    methods: list[ParsedFunction]


class ParsedFile(BaseModel):

    file_path: str

    imports: list[str]

    classes: list[ParsedClass]

    functions: list[ParsedFunction]

class ParsedRepository(BaseModel):

    repository_name: str

    total_python_files: int

    files: list[ParsedFile]
class GraphEdge(BaseModel):

    source: str

    target: str

    relationship: str


class RepositoryGraph(BaseModel):

    nodes: list[str]

    edges: list[GraphEdge]
class ImportEdge(BaseModel):
    source_file: str
    imported_module: str
class GraphStatistics(BaseModel):

    total_nodes: int

    total_edges: int

    contains_edges: int

    calls_edges: int

    imports_edges: int

    inherits_edges: int

    most_connected_nodes: list[str]



