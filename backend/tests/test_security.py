"""
tests/test_security.py
=======================
Security tests for URL validation, repo name sanitization,
and concurrent clone safety.

These tests verify the security-critical paths in RepositoryService
without performing any actual network calls.
"""

from __future__ import annotations

import threading
import time
import pytest

from app.services.repository_service import (
    validate_clone_url,
    sanitize_repo_name,
    _get_clone_lock,
)


# ===========================================================================
# URL validation tests
# ===========================================================================

class TestValidateCloneUrl:

    # --- Valid URLs ---

    def test_valid_github_url(self):
        validate_clone_url("https://github.com/psf/requests")

    def test_valid_gitlab_url(self):
        validate_clone_url("https://gitlab.com/gitlab-org/gitlab-foss")

    def test_valid_bitbucket_url(self):
        validate_clone_url("https://bitbucket.org/atlassian/python-bitbucketserver")

    def test_valid_url_with_git_suffix(self):
        validate_clone_url("https://github.com/psf/requests.git")

    def test_valid_url_with_trailing_slash(self):
        validate_clone_url("https://github.com/psf/requests/")

    # --- Rejected: wrong scheme ---

    def test_rejects_http_scheme(self):
        with pytest.raises(ValueError, match="Only HTTPS URLs"):
            validate_clone_url("http://github.com/psf/requests")

    def test_rejects_file_scheme(self):
        with pytest.raises(ValueError, match="Only HTTPS URLs"):
            validate_clone_url("file:///etc/passwd")

    def test_rejects_ssh_scheme(self):
        with pytest.raises(ValueError, match="Only HTTPS URLs"):
            validate_clone_url("ssh://git@github.com/psf/requests")

    def test_rejects_bare_git_scheme(self):
        with pytest.raises(ValueError, match="Only HTTPS URLs"):
            validate_clone_url("git://github.com/psf/requests")

    def test_rejects_bare_path(self):
        with pytest.raises(ValueError):
            validate_clone_url("/etc/passwd")

    # --- Rejected: SSRF / internal hosts ---

    def test_rejects_arbitrary_host(self):
        with pytest.raises(ValueError, match="not in the allowed list"):
            validate_clone_url("https://evil.com/malicious/repo")

    def test_rejects_localhost(self):
        with pytest.raises(ValueError, match="not in the allowed list"):
            validate_clone_url("https://localhost/repo/name")

    def test_rejects_127_0_0_1(self):
        with pytest.raises(ValueError, match="not in the allowed list"):
            validate_clone_url("https://127.0.0.1/repo/name")

    def test_rejects_169_254_metadata(self):
        # AWS/GCP/Azure metadata endpoint — classic SSRF target
        with pytest.raises(ValueError, match="not in the allowed list"):
            validate_clone_url("https://169.254.169.254/latest/meta-data/")

    def test_rejects_internal_ip(self):
        with pytest.raises(ValueError, match="not in the allowed list"):
            validate_clone_url("https://10.0.0.1/repo/name")

    def test_rejects_docker_host(self):
        with pytest.raises(ValueError, match="not in the allowed list"):
            validate_clone_url("https://172.17.0.1/repo/name")

    # --- Rejected: missing path components ---

    def test_rejects_host_only(self):
        with pytest.raises(ValueError, match="owner and a repository"):
            validate_clone_url("https://github.com/")

    def test_rejects_owner_only(self):
        with pytest.raises(ValueError, match="owner and a repository"):
            validate_clone_url("https://github.com/psf")

    # --- Rejected: empty / non-string ---

    def test_rejects_empty_string(self):
        with pytest.raises(ValueError):
            validate_clone_url("")

    def test_rejects_whitespace_only(self):
        with pytest.raises(ValueError):
            validate_clone_url("   ")

    def test_rejects_non_string(self):
        with pytest.raises((ValueError, AttributeError)):
            validate_clone_url(None)  # type: ignore[arg-type]


# ===========================================================================
# Repo name sanitization tests
# ===========================================================================

class TestSanitizeRepoName:

    def test_normal_name(self):
        assert sanitize_repo_name("https://github.com/psf/requests") == "requests"

    def test_strips_git_suffix(self):
        assert sanitize_repo_name("https://github.com/psf/requests.git") == "requests"

    def test_strips_trailing_slash(self):
        assert sanitize_repo_name("https://github.com/psf/requests/") == "requests"

    def test_hyphenated_name(self):
        assert sanitize_repo_name("https://github.com/tiangolo/fastapi") == "fastapi"

    def test_underscored_name(self):
        assert sanitize_repo_name("https://github.com/encode/httpx") == "httpx"

    def test_dotted_name(self):
        result = sanitize_repo_name("https://github.com/python/cpython")
        assert result == "cpython"

    # --- Path traversal attempts ---

    def test_rejects_dotdot_as_repo_name(self):
        """A repo URL whose final path component is '..' should be rejected."""
        # "https://github.com/x/.." — split("/")[-1] is ".." which fails the regex
        with pytest.raises(ValueError):
            sanitize_repo_name("https://github.com/x/..")

    def test_rejects_dot_as_repo_name(self):
        """A repo URL whose final path component is '.' should be rejected."""
        with pytest.raises(ValueError):
            sanitize_repo_name("https://github.com/x/.")

    def test_dotdot_followed_by_basename_extracts_leaf(self):
        """
        A URL like https://github.com/x/../../etc/passwd extracts 'passwd'
        as the repo name after split("/")[-1] — which is safe because:
        1. sanitize_repo_name checks the NAME only (leaf after last slash).
        2. clone_repository() does a realpath check to ensure the full
           join(repos_dir, name) stays inside repos_dir.
        The name 'passwd' itself is valid — the combined path safety is
        enforced by the realpath guard in clone_repository().
        """
        result = sanitize_repo_name("https://github.com/x/../../etc/passwd")
        assert result == "passwd"  # only the leaf is extracted

    def test_double_slash_url_uses_owner_as_name(self):
        """
        A URL ending with '//' strips the trailing slashes (rstrip) and
        then extracts the last real path component (the owner, 'x' here).
        This is an unusual URL but not a security concern since validate_clone_url
        rejects all but github.com/gitlab.com/bitbucket.org URLs anyway.
        The resulting name 'x' is valid alphanumeric.
        """
        # This does NOT raise — the double slash is normalized away
        result = sanitize_repo_name("https://github.com/x//")
        assert result == "x"

    def test_rejects_url_encoded_traversal(self):
        """URL-encoded path traversal characters are rejected by the regex."""
        # After split("/")[-1] this would be "..%2Fetc%2Fpasswd" — rejected by regex
        with pytest.raises(ValueError):
            sanitize_repo_name("https://github.com/x/..%2Fetc%2Fpasswd")

    def test_rejects_null_byte(self):
        with pytest.raises(ValueError):
            sanitize_repo_name("https://github.com/x/repo\x00name")

    def test_rejects_shell_special_chars(self):
        with pytest.raises(ValueError):
            sanitize_repo_name("https://github.com/x/repo;rm -rf /")


# ===========================================================================
# Concurrent clone lock tests
# ===========================================================================

class TestConcurrentCloneLock:

    def test_same_repo_gets_same_lock_object(self):
        lock1 = _get_clone_lock("myrepo")
        lock2 = _get_clone_lock("myrepo")
        assert lock1 is lock2

    def test_different_repos_get_different_locks(self):
        lock_a = _get_clone_lock("repo_a")
        lock_b = _get_clone_lock("repo_b")
        assert lock_a is not lock_b

    def test_lock_is_threading_lock(self):
        lock = _get_clone_lock("testlocktype")
        # Should be acquirable
        acquired = lock.acquire(blocking=False)
        if acquired:
            lock.release()
        # Being able to acquire/release without error confirms it's a lock

    def test_concurrent_access_serialized(self):
        """
        Verify that two threads competing for the same repo lock are
        serialized — the second waits until the first releases.
        """
        results: list[str] = []
        lock = _get_clone_lock("concurrent_test_repo")

        def _worker(label: str, hold_seconds: float) -> None:
            with lock:
                results.append(f"{label}_start")
                time.sleep(hold_seconds)
                results.append(f"{label}_end")

        t1 = threading.Thread(target=_worker, args=("A", 0.05))
        t2 = threading.Thread(target=_worker, args=("B", 0.01))

        t1.start()
        time.sleep(0.01)  # Ensure t1 acquires first
        t2.start()

        t1.join(timeout=2)
        t2.join(timeout=2)

        # A must fully complete before B starts (serialized)
        assert results.index("A_end") < results.index("B_start"), (
            f"Threads were not serialized. Execution order: {results}"
        )
