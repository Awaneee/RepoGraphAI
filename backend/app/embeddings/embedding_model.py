"""
app/embeddings/embedding_model.py
===================================
Lightweight wrapper around sentence-transformers for node-level embeddings.

Design
------
- Lazy import: ``sentence_transformers`` is only imported on first use.
  The module loads cleanly even when the package is not installed.
- Single model instance per ``EmbeddingModel`` object (cached after first call).
- Batch encoding for efficiency; single-text helper for convenience.
- CPU-only by default (no GPU required, keeps dependencies minimal).

Default model: ``all-MiniLM-L6-v2``
  - 80 MB download, 384-dimensional output.
  - Runs on CPU in < 5ms per node on a laptop.
  - Strong quality/speed tradeoff for code-level retrieval tasks.

Usage
-----
::

    from app.embeddings.embedding_model import EmbeddingModel

    model = EmbeddingModel()                     # default: all-MiniLM-L6-v2
    vecs  = model.encode(["def foo(): ...", "class Bar: ..."])   # list[list[float]]
    vec   = model.encode_one("def foo(): ...")                   # list[float]

    # Check availability without triggering an import error:
    if EmbeddingModel.is_available():
        model = EmbeddingModel()
"""

from __future__ import annotations

from typing import Optional


class EmbeddingModel:
    """
    Thin wrapper over a ``SentenceTransformer`` model.

    Parameters
    ----------
    model_name : str
        Any model name accepted by ``sentence_transformers.SentenceTransformer``.
        Defaults to ``"all-MiniLM-L6-v2"``.
    device : str | None
        PyTorch device string (``"cpu"``, ``"cuda"``, ``"mps"``).
        Defaults to ``"cpu"`` for reproducibility on all machines.
    """

    DEFAULT_MODEL = "all-MiniLM-L6-v2"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: Optional[str] = "cpu",
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._model = None  # lazy-loaded on first encode call

    # ------------------------------------------------------------------
    # Availability check (no import side-effects)
    # ------------------------------------------------------------------

    @staticmethod
    def is_available() -> bool:
        """Return True if ``sentence_transformers`` is installed."""
        import importlib.util

        return importlib.util.find_spec("sentence_transformers") is not None

    # ------------------------------------------------------------------
    # Encoding
    # ------------------------------------------------------------------

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise ImportError(
                    "sentence-transformers is required for embedding support. "
                    "Install it with: pip install sentence-transformers"
                ) from exc
            self._model = SentenceTransformer(self._model_name, device=self._device)
        return self._model

    def encode(self, texts: list[str], *, show_progress: bool = False) -> list[list[float]]:
        """
        Encode a batch of texts and return their embeddings.

        Parameters
        ----------
        texts : list[str]
            Texts to encode.  Empty list returns [].
        show_progress : bool
            Show a tqdm progress bar during encoding.

        Returns
        -------
        list[list[float]]
            One embedding vector per input text.
        """
        if not texts:
            return []
        model = self._get_model()
        embeddings = model.encode(
            texts,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
        )
        return embeddings.tolist()

    def encode_one(self, text: str) -> list[float]:
        """Encode a single text string and return its embedding."""
        return self.encode([text])[0]

    @property
    def model_name(self) -> str:
        return self._model_name
