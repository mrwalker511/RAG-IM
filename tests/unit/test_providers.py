from unittest.mock import patch

import pytest

from ragcore.providers import make_embedder, make_generator


def test_make_embedder_returns_sentence_transformer():
    with patch("ragcore.providers.settings.EMBEDDING_PROVIDER", "sentence_transformer"):
        with patch("ragcore.embeddings.sentence_transformer_embedder.SentenceTransformerEmbedder") as mock_cls:
            mock_instance = mock_cls.return_value
            result = make_embedder()

    assert result is mock_instance


def test_make_embedder_returns_openai():
    with patch("ragcore.providers.settings.EMBEDDING_PROVIDER", "openai"):
        with patch("ragcore.embeddings.openai_embedder.OpenAIEmbedder") as mock_cls:
            mock_instance = mock_cls.return_value
            result = make_embedder()

    assert result is mock_instance


def test_make_embedder_raises_on_unknown_provider():
    with patch("ragcore.providers.settings.EMBEDDING_PROVIDER", "unknown"):
        with pytest.raises(ValueError, match="Unsupported EMBEDDING_PROVIDER"):
            make_embedder()


def test_make_generator_returns_litellm():
    with patch("ragcore.providers.settings.LLM_PROVIDER", "litellm"):
        with patch("ragcore.generation.litellm_generator.LiteLLMGenerator") as mock_cls:
            mock_instance = mock_cls.return_value
            result = make_generator()

    assert result is mock_instance


def test_make_generator_returns_openai():
    with patch("ragcore.providers.settings.LLM_PROVIDER", "openai"):
        with patch("ragcore.generation.openai_generator.OpenAIGenerator") as mock_cls:
            mock_instance = mock_cls.return_value
            result = make_generator()

    assert result is mock_instance


def test_make_generator_raises_on_unknown_provider():
    with patch("ragcore.providers.settings.LLM_PROVIDER", "unknown"):
        with pytest.raises(ValueError, match="Unsupported LLM_PROVIDER"):
            make_generator()
