from fastapi import FastAPI

from app.api.endpoints import router

app = FastAPI(
    title="RepoGraphAI",
    description=(
        "GraphRAG-based Repository "
        "Architecture Analysis Platform"
    ),
    version="0.1.0"
)

app.include_router(router)