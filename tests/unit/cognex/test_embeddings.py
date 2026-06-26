import sys
import importlib
from unittest.mock import MagicMock, patch
import pytest


def test_embedding_engine_unavailable_without_library():
    """Verify that the engine gracefully marks itself unavailable if import fails."""
    # Temporarily hide sentence_transformers
    with patch.dict(sys.modules, {"sentence_transformers": None}):
        import cognex.embeddings

        importlib.reload(cognex.embeddings)
        assert cognex.embeddings.AVAILABLE is False

        # Attempting to get model should raise ImportError
        with pytest.raises(ImportError):
            cognex.embeddings.EmbeddingEngine._get_model()


def test_embedding_engine_normalization():
    """Verify L2 vector normalization computes correctly."""
    from cognex.embeddings import EmbeddingEngine

    # 3-4-5 triangle vector, L2 norm is 5.0
    vec = [3.0, 4.0]
    normalized = EmbeddingEngine._normalize(vec)
    assert normalized == [0.6, 0.8]


def test_embedding_engine_embed_mocked():
    """Verify embedding generation and caching with mocked SentenceTransformer."""
    mock_model = MagicMock()
    # Return [1.0, 2.0, 2.0], norm is 3.0 -> [1/3, 2/3, 2/3]
    mock_model.encode.return_value = MagicMock(tolist=lambda: [1.0, 2.0, 2.0])

    with patch("cognex.embeddings.EmbeddingEngine.AVAILABLE", True), patch(
        "cognex.embeddings.SentenceTransformer", return_value=mock_model
    ):
        from cognex.embeddings import EmbeddingEngine

        # Reset cached model
        EmbeddingEngine._model = None

        res = EmbeddingEngine.embed("test query")
        assert res == [1.0 / 3.0, 2.0 / 3.0, 2.0 / 3.0]
        mock_model.encode.assert_called_once_with("test query")

        # Caching check: next call should reuse the model
        EmbeddingEngine.embed("another query")
        assert mock_model.encode.call_count == 2
