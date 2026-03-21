import asyncio
import functools

from ragcore.embeddings.base import BaseEmbedder

_DEFAULT_MODEL = "all-MiniLM-L6-v2"
_DEFAULT_DIM = 384


class SentenceTransformerEmbedder(BaseEmbedder):
    """Local embedding fallback — no API key required."""

    def __init__(self, model_name: str = _DEFAULT_MODEL) -> None:
        self._model_name = model_name
        self._model = None  # Lazy-loaded

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
        return self._model

    @property
    def dimension(self) -> int:
        return _DEFAULT_DIM

    async def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load_model()
        loop = asyncio.get_event_loop()
        encode = functools.partial(model.encode, texts, show_progress_bar=False)
        embeddings = await loop.run_in_executor(None, encode)
        return [emb.tolist() for emb in embeddings]
