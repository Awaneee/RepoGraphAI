from app.services.repository_service import RepositoryService


service = RepositoryService()

path = service.clone_repository(
    "https://github.com/fastapi/fastapi"
)

print(path)