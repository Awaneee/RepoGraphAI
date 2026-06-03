from pprint import pprint

from app.services.repository_service import (
    RepositoryService
)

service = RepositoryService()

summary = service.generate_summary(
    "repos/fastapi"
)

pprint(summary.model_dump())