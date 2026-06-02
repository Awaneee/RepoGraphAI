from pprint import pprint

from app.services.repository_service import (
    RepositoryService
)

service = RepositoryService()

result = service.scan_repository(
    "repos/fastapi"
)

pprint(result)