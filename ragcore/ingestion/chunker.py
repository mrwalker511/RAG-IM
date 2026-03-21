from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from ragcore.config import settings

# Max tokens for supported embedding models
_MODEL_MAX_TOKENS: dict[str, int] = {
    "text-embedding-3-small": 8191,
    "text-embedding-3-large": 8191,
    "text-embedding-ada-002": 8191,
}


class ConfigError(ValueError):
    pass


def _validate_chunk_size(chunk_size: int, model: str) -> None:
    max_tokens = _MODEL_MAX_TOKENS.get(model, 8191)
    if chunk_size > max_tokens:
        raise ConfigError(
            f"chunk_size={chunk_size} exceeds max tokens for model '{model}' ({max_tokens})"
        )


@dataclass
class ChunkResult:
    content: str
    chunk_index: int


def chunk_texts(
    sections: list[str],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    embedding_model: str | None = None,
    strategy: str = "recursive",
) -> list[ChunkResult]:
    size = chunk_size or settings.DEFAULT_CHUNK_SIZE
    overlap = chunk_overlap or settings.DEFAULT_CHUNK_OVERLAP
    model = embedding_model or settings.EMBEDDING_MODEL

    _validate_chunk_size(size, model)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        length_function=len,
    )

    chunks: list[ChunkResult] = []
    for section in sections:
        split = splitter.split_text(section)
        for text in split:
            if text.strip():
                chunks.append(ChunkResult(content=text.strip(), chunk_index=len(chunks)))

    return chunks
