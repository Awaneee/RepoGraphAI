from fastapi import APIRouter

from app.models.pydantic_models import (
    RepositoryRequest,
    RepositorySummary
)

from app.services.repository_service import (
    RepositoryService
)

router = APIRouter()

repository_service = RepositoryService()


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