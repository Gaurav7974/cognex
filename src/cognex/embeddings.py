
from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)

try:
    import sentence_transformers
    from sentence_transformers import SentenceTransformer
    AVAILABLE = True
except ImportError:
    sentence_transformers = None
    SentenceTransformer = None
    AVAILABLE = False


class EmbeddingEngine:

    AVAILABLE = AVAILABLE
    _model: SentenceTransformer | None = None
    MODEL_NAME = "all-MiniLM-L6-v2"

    @classmethod
    def _get_model(cls) -> SentenceTransformer:
        if not cls.AVAILABLE:
            raise ImportError(
                "sentence-transformers is not installed. Install with 'pip install .[semantic]'"
            )
        if cls._model is None:
            logger.info("Initializing local SentenceTransformer model: %s", cls.MODEL_NAME)
            cls._model = SentenceTransformer(cls.MODEL_NAME)
        return cls._model

    @classmethod
    def embed(cls, text: str) -> list[float]:
        model = cls._get_model()
        vector = model.encode(text).tolist()
        return cls._normalize(vector)

    @classmethod
    def embed_batch(cls, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = cls._get_model()
        vectors = model.encode(texts).tolist()
        return [cls._normalize(v) for v in vectors]

    @classmethod
    def _normalize(cls, vec: list[float]) -> list[float]:
        sq_sum = sum(x * x for x in vec)
        norm = math.sqrt(sq_sum)
        if norm < 1e-9:
            return vec
        return [x / norm for x in vec]
