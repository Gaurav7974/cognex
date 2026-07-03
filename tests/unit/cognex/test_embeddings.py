import sys
import importlib
from unittest.mock import MagicMock, patch
import pytest

def test_embedding_engine_unavailable_without_library():
    with patch.dict(sys.modules, {'sentence_transformers': None}):
        import cognex.embeddings
        importlib.reload(cognex.embeddings)
        assert cognex.embeddings.AVAILABLE is False
        with pytest.raises(ImportError):
            cognex.embeddings.EmbeddingEngine._get_model()

def test_embedding_engine_normalization():
    from cognex.embeddings import EmbeddingEngine
    vec = [3.0, 4.0]
    normalized = EmbeddingEngine._normalize(vec)
    assert normalized == [0.6, 0.8]

def test_embedding_engine_embed_mocked():
    mock_model = MagicMock()
    mock_model.encode.return_value = MagicMock(tolist=lambda: [1.0, 2.0, 2.0])
    with patch('cognex.embeddings.EmbeddingEngine.AVAILABLE', True), patch('cognex.embeddings.SentenceTransformer', return_value=mock_model):
        from cognex.embeddings import EmbeddingEngine
        EmbeddingEngine._model = None
        res = EmbeddingEngine.embed('test query')
        assert res == [1.0 / 3.0, 2.0 / 3.0, 2.0 / 3.0]
        mock_model.encode.assert_called_once_with('test query')
        EmbeddingEngine.embed('another query')
        assert mock_model.encode.call_count == 2