from ragcore.config import settings
from ragcore.embeddings.base import BaseEmbedder
from ragcore.generation.base import BaseLLMGenerator


def make_embedder() -> BaseEmbedder:
    if settings.EMBEDDING_PROVIDER == "sentence_transformer":
        from ragcore.embeddings.sentence_transformer_embedder import SentenceTransformerEmbedder

        return SentenceTransformerEmbedder(model_name=settings.EMBEDDING_MODEL)
    if settings.EMBEDDING_PROVIDER == "openai":
        from ragcore.embeddings.openai_embedder import OpenAIEmbedder

        return OpenAIEmbedder()
    raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {settings.EMBEDDING_PROVIDER}")


def make_generator() -> BaseLLMGenerator:
    if settings.LLM_PROVIDER == "litellm":
        from ragcore.generation.litellm_generator import LiteLLMGenerator

        return LiteLLMGenerator()
    if settings.LLM_PROVIDER == "openai":
        from ragcore.generation.openai_generator import OpenAIGenerator

        return OpenAIGenerator()
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}")
