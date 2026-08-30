"""
app/core/config.py
==================
Application settings via pydantic-settings BaseSettings.

All settings can be overridden via environment variables (or a .env file).
See backend/.env.example for the full list of supported variables.

Usage
-----
    from app.core.config import settings

    if settings.ANTHROPIC_API_KEY:
        ...
"""

from __future__ import annotations

from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    RepoGraphAI application settings.

    Environment variable names match field names (case-insensitive).
    A .env file in the working directory is loaded automatically.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # LLM provider configuration
    # -------------------------------------------------------------------------

    ANTHROPIC_API_KEY: Optional[str] = None
    """Anthropic Messages API key. If set, the /qa endpoint uses Claude."""

    GOOGLE_API_KEY: Optional[str] = None
    """Google Gemini API key. Used when DEFAULT_LLM_PROVIDER=gemini."""

    DEFAULT_LLM_PROVIDER: str = "anthropic"
    """
    Which LLM provider to use when both ANTHROPIC_API_KEY and GOOGLE_API_KEY
    are set. One of: "anthropic", "gemini". Defaults to "anthropic".
    """

    ANTHROPIC_MODEL: str = "claude-sonnet-4-5"
    """
    Anthropic model ID to use. Check https://docs.anthropic.com for the
    current model catalog. Defaults to claude-sonnet-4-5.
    """

    # -------------------------------------------------------------------------
    # Repository / storage directories
    # -------------------------------------------------------------------------

    REPOS_DIR: str = "repos"
    """
    Directory where cloned repositories are stored.
    Relative paths are resolved from the process working directory.
    """

    CACHE_DIR: str = ".cache"
    """
    Directory for RepositoryCache fingerprint and graph pickle files.
    Relative paths are resolved from the process working directory.
    """

    # -------------------------------------------------------------------------
    # Clone security limits
    # -------------------------------------------------------------------------

    MAX_REPO_SIZE_MB: int = 500
    """
    Maximum repository size (in megabytes) allowed after cloning.
    Repositories larger than this are rejected and deleted.
    Prevents disk exhaustion from unexpectedly large repositories.
    """

    CLONE_TIMEOUT_SECONDS: int = 60
    """
    Maximum time (in seconds) allowed for a git clone operation.
    Prevents hung clones from blocking request threads indefinitely.
    Only enforced on Unix (uses SIGALRM).
    """

    ALLOWED_CLONE_HOSTS: list[str] = ["github.com", "gitlab.com", "bitbucket.org"]
    """
    Allowlist of git host domains. Only HTTPS URLs to these hosts are
    accepted by clone_repository(). This prevents SSRF attacks against
    internal services (e.g., http://169.254.169.254/...).

    Note: Redis, Kubernetes, Kafka, Neo4j are NOT used in this project.
    """

    # -------------------------------------------------------------------------
    # Private repository access
    # -------------------------------------------------------------------------

    GITHUB_TOKEN: Optional[str] = None
    """
    GitHub Personal Access Token (classic or fine-grained) for cloning
    private repositories. When set, the token is injected into HTTPS clone
    URLs (https://<token>@github.com/owner/repo).

    The token is NEVER logged or returned in API responses.
    Grant it only the minimum required scope: repo (for private repos) or
    read:packages if needed.

    Example:
        export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
    """

    GITLAB_TOKEN: Optional[str] = None
    """GitLab Personal Access Token for private GitLab repositories."""

    BITBUCKET_TOKEN: Optional[str] = None
    """Bitbucket App Password (username:token) for private Bitbucket repos."""

    # -------------------------------------------------------------------------
    # Auth & rate limiting
    # -------------------------------------------------------------------------

    API_KEY: Optional[str] = None
    """
    Optional API key for protecting the /qa, /qa/async, and /qa/stream
    endpoints. When set, requests must include the header:
        X-API-Key: <value>
    Requests without a valid key receive HTTP 401.

    Leave unset (default) for open access — suitable for local/internal use.
    """

    RATE_LIMIT_REQUESTS: int = 20
    """
    Maximum number of requests per window per client IP for the /qa* endpoints.
    Requests exceeding this limit receive HTTP 429.
    Default: 20 requests per minute.
    """

    RATE_LIMIT_WINDOW_SECONDS: int = 60
    """
    Sliding-window duration for rate limiting, in seconds. Default: 60 (1 minute).
    """

    # -------------------------------------------------------------------------
    # Validators
    # -------------------------------------------------------------------------

    @field_validator("DEFAULT_LLM_PROVIDER")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        allowed = {"anthropic", "gemini"}
        if v.lower() not in allowed:
            raise ValueError(
                f"DEFAULT_LLM_PROVIDER must be one of {sorted(allowed)}, got {v!r}"
            )
        return v.lower()


# Module-level singleton — import this in application code.
settings = Settings()
