from fastapi import APIRouter

from app.models.pydantic_models import (
    RepositoryRequest,
    RepositorySummary
)

from app.services.repository_service import (
    RepositoryService
)
from app.services.graph_services import (
    GraphService
)

from app.models.pydantic_models import (
    RepositoryGraph
)

router = APIRouter()

repository_service = RepositoryService()
graph_service = GraphService()


@router.post(
    "/analyze",
    response_model=RepositorySummary
)
def analyze_repository(
    request: RepositoryRequest
):

    repo_path = (
        repository_service
        .clone_repository(
            request.repo_url
        )
    )

    summary = (
        repository_service
        .generate_summary(
            repo_path
        )
    )

    return summary
@router.post(
    "/graph",
    response_model=RepositoryGraph
)
def generate_graph(
    request: RepositoryRequest
):

    repo_path = (
        repository_service
        .clone_repository(
            request.repo_url
        )
    )

    return (
        graph_service
        .generate_graph(
            repo_path
        )
    )