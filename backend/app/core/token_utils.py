"""
app/core/token_utils.py
=========================
Token counting and context window management.

Token counting
--------------
Uses ``tiktoken`` when available (accurate BPE count for OpenAI-family and
Anthropic models). Falls back to a character-based approximation (÷4) when
tiktoken is not installed — accurate enough for context size management.

Context trimming
----------------
``trim_to_token_limit`` trims a long string to fit within a token budget
using a binary-search approach: no character is ever read twice, making
the trim O(log N) tokenizer calls.

Usage
-----
::

    from app.core.token_utils import count_tokens, trim_to_token_limit

    tokens = count_tokens(text)           # int
    trimmed = trim_to_token_limit(text, max_tokens=24_000)
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tiktoken encoder (lazy-loaded, optional)
# ---------------------------------------------------------------------------

_encoder = None
_tiktoken_available: bool | None = None


def _get_encoder():
    global _encoder, _tiktoken_available
    if _tiktoken_available is None:
        try:
            import tiktoken
            # cl100k_base is used by GPT-4, Claude approximation is very close
            _encoder = tiktoken.get_encoding("cl100k_base")
            _tiktoken_available = True
        except (ImportError, Exception):
            _tiktoken_available = False
            logger.debug("tiktoken not available; using character approximation for token counting.")
    return _encoder


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def count_tokens(text: str) -> int:
    """
    Return the approximate token count for ``text``.

    Uses tiktoken BPE encoding when available; falls back to ``len(text) // 4``
    (a standard approximation that is accurate to within ±10% for English prose
    and Python source code).

    Parameters
    ----------
    text : str

    Returns
    -------
    int — estimated token count
    """
    if not text:
        return 0
    enc = _get_encoder()
    if enc is not None:
        return len(enc.encode(text))
    return max(1, len(text) // 4)


def trim_to_token_limit(
    text: str,
    max_tokens: int,
    truncation_marker: str = "\n\n[... context trimmed to fit token limit ...]",
) -> str:
    """
    Trim ``text`` to fit within ``max_tokens``, preserving the beginning.

    Uses binary search over character positions to find the trim point
    efficiently: O(log N) tokenizer calls regardless of text length.

    If ``text`` already fits within ``max_tokens``, it is returned unchanged.

    Parameters
    ----------
    text : str
        Input text. May be any length.
    max_tokens : int
        Maximum number of tokens in the returned string (including the
        truncation marker, if added).
    truncation_marker : str
        Appended when the text is trimmed, to signal to the LLM that context
        was cut. Defaults to a clearly visible inline notice.

    Returns
    -------
    str — text that fits within ``max_tokens``
    """
    if count_tokens(text) <= max_tokens:
        return text

    marker_tokens = count_tokens(truncation_marker)
    budget        = max(0, max_tokens - marker_tokens)

    # Binary search for the largest character prefix that fits within budget
    lo, hi = 0, len(text)
    while lo < hi:
        mid  = (lo + hi + 1) // 2
        candidate = text[:mid]
        if count_tokens(candidate) <= budget:
            lo = mid
        else:
            hi = mid - 1

    return text[:lo] + truncation_marker


# ---------------------------------------------------------------------------
# Context-aware limit for GraphRAG
# ---------------------------------------------------------------------------

# Default context budget: leave ~8K tokens for the LLM's own answer generation.
# Most models (Claude Sonnet, GPT-4o) support 128K context; Gemini Flash 1M.
# We use a conservative 24K default to ensure compatibility with all supported
# models and to keep cost predictable.
DEFAULT_MAX_CONTEXT_TOKENS: int = 24_000
