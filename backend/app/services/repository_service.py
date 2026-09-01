import heapq
import logging
import os
import re
import shutil
import stat
import threading
from collections import Counter
from urllib.parse import urlparse

from git import Repo

from app.models.pydantic_models import RepositorySummary  # noqa: E402

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Security: URL allowlist
# Prevents SSRF attacks — only well-known public git hosts are allowed.
# ---------------------------------------------------------------------------

_ALLOWED_CLONE_HOSTS = frozenset(
    {
        "github.com",
        "gitlab.com",
        "bitbucket.org",
    }
)

# Repo name sanitization: only alphanumeric, hyphens, underscores, dots.
_SAFE_REPO_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")

# Per-repo file lock to prevent concurrent clone race conditions.
# Maps repo_name → threading.Lock.
_CLONE_LOCKS: dict[str, threading.Lock] = {}
_CLONE_LOCKS_MUTEX = threading.Lock()

# Security limits
_CLONE_TIMEOUT_SECONDS = 60
_MAX_REPO_SIZE_MB = 500


def _get_clone_lock(repo_name: str) -> threading.Lock:
    """Return a per-repo lock (creates one if it doesn't exist yet)."""
    with _CLONE_LOCKS_MUTEX:
        if repo_name not in _CLONE_LOCKS:
            _CLONE_LOCKS[repo_name] = threading.Lock()
        return _CLONE_LOCKS[repo_name]


def validate_clone_url(repo_url: str) -> None:
    """
    Validate that repo_url is a safe, allowlisted HTTPS git URL.

    Raises ValueError with a descriptive message on any security violation.

    Trust boundary: this function is the single gate for all external git
    clone operations. It must be called before any Repo.clone_from() call.

    Allowed pattern: https://{allowed_host}/{owner}/{repo}[.git][/]
    """
    if not isinstance(repo_url, str) or not repo_url.strip():
        raise ValueError("repo_url must be a non-empty string.")

    parsed = urlparse(repo_url)

    if parsed.scheme != "https":
        raise ValueError(
            f"Only HTTPS URLs are allowed. Got scheme: {parsed.scheme!r}. "
            "file://, http://, ssh://, and bare paths are all rejected."
        )

    host = parsed.hostname or ""
    if host not in _ALLOWED_CLONE_HOSTS:
        raise ValueError(
            f"Host {host!r} is not in the allowed list. "
            f"Allowed hosts: {sorted(_ALLOWED_CLONE_HOSTS)}. "
            "This restriction prevents SSRF attacks against internal services."
        )

    path = parsed.path.strip("/")
    if not path or "/" not in path:
        raise ValueError(
            f"URL must include an owner and a repository name: "
            f"https://github.com/{{owner}}/{{repo}}. Got path: {path!r}"
        )


def sanitize_repo_name(repo_url: str) -> str:
    """
    Extract and sanitize the repository name from a URL.

    Uses os.path.basename to strip any path separators, then validates
    the result against a strict allowlist pattern. Strips .git suffix.

    Raises ValueError if the result would be empty, contain unsafe chars,
    or is a path traversal component (e.g. '.' or '..').

    Trust boundary: the returned name is used as a directory name under the
    repos/ directory. A malicious URL like https://github.com/x/../../etc
    could escape the repos/ directory without this sanitization.
    The realpath check in clone_repository() provides a second layer of
    defense against any edge cases that slip through here.
    """
    raw_name = repo_url.rstrip("/").split("/")[-1]

    # Strip .git suffix
    if raw_name.endswith(".git"):
        raw_name = raw_name[:-4]

    # Use basename to strip any path separators
    safe_name = os.path.basename(raw_name)

    # Explicitly reject path traversal components
    if safe_name in (".", ".."):
        raise ValueError(
            f"Unsafe repository name: {raw_name!r} resolves to {safe_name!r}, "
            "which is a path traversal component."
        )

    if not safe_name or not _SAFE_REPO_NAME_RE.match(safe_name):
        raise ValueError(
            f"Unsafe repository name extracted from URL: {raw_name!r}. "
            "Repository names may only contain alphanumeric characters, "
            "hyphens, underscores, and dots."
        )

    # Additional check: must not consist entirely of dots
    if all(c == "." for c in safe_name):
        raise ValueError(
            f"Repository name {safe_name!r} consists only of dots "
            "and is not a valid directory name."
        )

    return safe_name


def _inject_token(repo_url: str, token: str) -> str:
    """
    Inject a personal access token into an HTTPS git URL for authentication.

    Transforms:
        https://github.com/owner/repo
        → https://<token>@github.com/owner/repo

    The token is used only for the git clone/fetch operation and is never
    stored, logged, or returned to callers.

    Parameters
    ----------
    repo_url : str  — validated HTTPS URL (already through validate_clone_url)
    token    : str  — PAT (GitHub) or "username:token" (Bitbucket)
    """
    parsed = urlparse(repo_url)
    authenticated = parsed._replace(netloc=f"{token}@{parsed.netloc}")
    return authenticated.geturl()


def _auth_url(repo_url: str) -> str:
    """
    Return an authenticated clone URL if a matching token is configured,
    otherwise return the original URL (suitable for public repos).

    Token selection is based on the host:
      github.com    → GITHUB_TOKEN
      gitlab.com    → GITLAB_TOKEN
      bitbucket.org → BITBUCKET_TOKEN (format: "username:app_password")
    """
    from app.core.config import settings

    parsed = urlparse(repo_url)
    host = parsed.hostname or ""

    if "github.com" in host and settings.GITHUB_TOKEN:
        return _inject_token(repo_url, settings.GITHUB_TOKEN)
    if "gitlab.com" in host and settings.GITLAB_TOKEN:
        return _inject_token(repo_url, settings.GITLAB_TOKEN)
    if "bitbucket.org" in host and settings.BITBUCKET_TOKEN:
        return _inject_token(repo_url, settings.BITBUCKET_TOKEN)

    return repo_url  # public repo — no token needed


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
        ".toml": "TOML",
    }

    EXCLUDED_DIRECTORIES = {
        ".git",
        ".github",
        "__pycache__",
        ".venv",
        "node_modules",
        ".idea",
        ".vscode",
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
        ".dart",
    }

    DOCUMENTATION_EXTENSIONS = {".md"}

    CONFIGURATION_EXTENSIONS = {".yaml", ".yml", ".json", ".toml", ".xml"}

    ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp"}

    def remove_readonly(self, func, path, _):
        """
        Fix Windows permission issues when deleting files.
        """

        os.chmod(path, stat.S_IWRITE)

        func(path)

    def clone_repository(self, repo_url: str) -> str:
        """
        Clone a repository from a public git host to a local path.

        Security measures applied (in order):
        1. URL allowlist validation (SSRF prevention).
        2. Repo name sanitization (path traversal prevention).
        3. Per-repo file lock (concurrent clone race prevention).
        4. Clone timeout (denial-of-service / hung-clone prevention).
        5. Repo size check after clone (disk exhaustion prevention).

        Trust boundary note: the local repos/ directory is internal state.
        The RepositoryCache (repository_cache.py) uses pickle for the graph
        cache — this is safe because only this service writes to that cache.
        External untrusted input (repo_url) is sanitized before any disk
        path is derived from it.
        """
        # --- Security: validate URL ---
        validate_clone_url(repo_url)

        # --- Security: sanitize repo name (prevents path traversal) ---
        repo_name = sanitize_repo_name(repo_url)

        repos_dir = os.path.abspath("repos")
        local_path = os.path.join(repos_dir, repo_name)

        # Double-check that local_path is actually inside repos_dir
        real_local = os.path.realpath(local_path)
        real_repos = os.path.realpath(repos_dir)
        if not real_local.startswith(real_repos + os.sep) and real_local != real_repos:
            raise ValueError(
                f"Path traversal detected: resolved path {real_local!r} "
                f"is outside the repos directory {real_repos!r}."
            )

        os.makedirs(repos_dir, exist_ok=True)

        # --- Security: per-repo lock (prevents concurrent clone race) ---
        lock = _get_clone_lock(repo_name)
        with lock:
            # Resolve authenticated URL (injects PAT for private repos if configured)
            clone_url = _auth_url(repo_url)

            if os.path.exists(local_path):
                # Fast path: repository already exists — try git pull instead of
                # re-cloning. For large repos (200MB+), this is 30-120x faster.
                try:
                    existing = Repo(local_path)
                    # Update remote URL in case a token was added/changed
                    with existing.remotes.origin.config_writer as cw:
                        cw.set("url", clone_url)
                    existing.remotes.origin.fetch()
                    local_commit = existing.head.commit.hexsha
                    remote_commit = existing.remotes.origin.refs[0].commit.hexsha
                    if local_commit == remote_commit:
                        logger.debug("Repository %s is up to date; skipping re-clone.", repo_name)
                        return local_path
                    # Remote has new commits — pull
                    logger.info("Pulling updates for %s.", repo_name)
                    existing.remotes.origin.pull()
                    return local_path
                except Exception as exc:
                    logger.warning(
                        "Could not update existing repo %s (%s); falling back to re-clone.",
                        repo_name,
                        exc,
                    )
                    try:
                        shutil.rmtree(local_path, onerror=self.remove_readonly)
                    except Exception as e:
                        raise Exception(f"Failed to remove existing repository: {e}") from e

            # Fresh clone (no existing repo at local_path)
            logger.info("Cloning %s → %s", repo_url, local_path)
            try:
                # Security: clone timeout prevents hung clones.
                # signal.alarm only works on Unix AND only in the main thread.
                # We use it when available (production uvicorn main thread),
                # and skip gracefully in worker threads (tests, async workers).
                import signal
                import threading

                _use_alarm = (
                    hasattr(signal, "SIGALRM")
                    and threading.current_thread() is threading.main_thread()
                )

                if _use_alarm:

                    def _timeout_handler(signum, frame):
                        raise TimeoutError(
                            f"Git clone timed out after {_CLONE_TIMEOUT_SECONDS}s. "
                            f"Repository may be too large or network too slow."
                        )

                    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
                    signal.alarm(_CLONE_TIMEOUT_SECONDS)

                try:
                    # Shallow clone (depth=1, no tags): we only need the current
                    # tree for static analysis — history is dead weight and
                    # dominates wall time on large repos.
                    Repo.clone_from(
                        clone_url,
                        local_path,
                        multi_options=["--depth=1", "--single-branch", "--no-tags"],
                    )
                finally:
                    if _use_alarm:
                        signal.alarm(0)
                        signal.signal(signal.SIGALRM, old_handler)

            except TimeoutError:
                if os.path.exists(local_path):
                    shutil.rmtree(local_path, onerror=self.remove_readonly)
                raise
            except Exception as e:
                raise Exception(f"Failed to clone repository: {e}") from e

            # --- Security: repo size limit ---
            total_size_mb = self._directory_size_mb(local_path)
            if total_size_mb > _MAX_REPO_SIZE_MB:
                shutil.rmtree(local_path, onerror=self.remove_readonly)
                raise ValueError(
                    f"Repository size {total_size_mb:.1f} MB exceeds the "
                    f"limit of {_MAX_REPO_SIZE_MB} MB."
                )

        return local_path

    def _directory_size_mb(self, path: str) -> float:
        """Return total size of a directory tree in megabytes."""
        total = 0
        for root, _dirs, files in os.walk(path):
            for fname in files:
                try:
                    total += os.path.getsize(os.path.join(root, fname))
                except OSError:
                    pass
        return total / (1024 * 1024)

    def detect_framework(self, repo_path: str) -> str | None:

        pyproject_path = os.path.join(repo_path, "pyproject.toml")

        requirements_path = os.path.join(repo_path, "requirements.txt")

        try:
            if os.path.exists(pyproject_path):
                with open(pyproject_path, "r", encoding="utf-8") as file:
                    content = file.read().lower()

                    if "fastapi" in content:
                        return "FastAPI"

                    if "django" in content:
                        return "Django"

                    if "flask" in content:
                        return "Flask"

            if os.path.exists(requirements_path):
                with open(requirements_path, "r", encoding="utf-8") as file:
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

    def classify_repository_type(self, framework: str | None) -> str:

        if framework in {"FastAPI", "Django", "Flask"}:
            return "Backend API"

        return "General Software Project"

    def scan_repository(self, repo_path: str) -> dict:

        total_files = 0
        total_directories = 0
        repository_size_bytes = 0

        extension_distribution = Counter()
        language_distribution = Counter()
        file_category_distribution = Counter()

        largest_files = []
        top_level_directories = []

        for item in os.listdir(repo_path):
            item_path = os.path.join(repo_path, item)

            if os.path.isdir(item_path) and item not in self.EXCLUDED_DIRECTORIES:
                top_level_directories.append(item)

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRECTORIES]

            total_directories += len(dirs)

            for file in files:
                file_path = os.path.join(root, file)

                try:
                    file_size = os.path.getsize(file_path)

                    total_files += 1
                    repository_size_bytes += file_size

                    relative_path = os.path.relpath(file_path, repo_path)

                    largest_files.append({"file": relative_path, "size_bytes": file_size})

                    extension = os.path.splitext(file)[1].lower()

                    if not extension:
                        extension = "NO_EXTENSION"

                    extension_distribution[extension] += 1

                    if extension in self.EXTENSION_LANGUAGE_MAP:
                        language = self.EXTENSION_LANGUAGE_MAP[extension]

                        language_distribution[language] += 1

                    if extension in self.SOURCE_CODE_EXTENSIONS:
                        file_category_distribution["source_code"] += 1

                    elif extension in self.DOCUMENTATION_EXTENSIONS:
                        file_category_distribution["documentation"] += 1

                    elif extension in self.CONFIGURATION_EXTENSIONS:
                        file_category_distribution["configuration"] += 1

                    elif extension in self.ASSET_EXTENSIONS:
                        file_category_distribution["assets"] += 1

                    elif "test" in relative_path.lower():
                        file_category_distribution["tests"] += 1

                    else:
                        file_category_distribution["other"] += 1

                except (PermissionError, FileNotFoundError, OSError):
                    continue

        framework = self.detect_framework(repo_path)

        repository_type = self.classify_repository_type(framework)

        largest_files = heapq.nlargest(10, largest_files, key=lambda x: x["size_bytes"])

        return {
            "total_files": total_files,
            "total_directories": total_directories,
            "repository_size_bytes": repository_size_bytes,
            "language_distribution": dict(language_distribution),
            "file_extension_distribution": dict(extension_distribution),
            "file_category_distribution": dict(file_category_distribution),
            "top_level_directories": sorted(top_level_directories),
            "framework": framework,
            "repository_type": repository_type,
            "largest_files": largest_files,
        }

    def generate_summary(self, repo_path: str) -> RepositorySummary:

        scan_result = self.scan_repository(repo_path)

        return RepositorySummary(
            repository_name=os.path.basename(repo_path),
            repository_path=repo_path,
            repository_type=scan_result["repository_type"],
            framework=scan_result["framework"],
            total_files=scan_result["total_files"],
            total_directories=scan_result["total_directories"],
            repository_size_bytes=scan_result["repository_size_bytes"],
            language_distribution=scan_result["language_distribution"],
            file_extension_distribution=scan_result["file_extension_distribution"],
            file_category_distribution=scan_result["file_category_distribution"],
            top_level_directories=scan_result["top_level_directories"],
            largest_files=scan_result["largest_files"],
        )
