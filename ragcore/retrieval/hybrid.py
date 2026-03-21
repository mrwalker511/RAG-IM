import uuid
from collections import defaultdict

from ragcore.retrieval.vector_search import ChunkResult


def reciprocal_rank_fusion(
    vector_results: list[ChunkResult],
    bm25_results: list[ChunkResult],
    k: int = 60,
) -> list[ChunkResult]:
    """Merge two ranked lists using Reciprocal Rank Fusion."""
    scores: dict[uuid.UUID, float] = defaultdict(float)
    by_id: dict[uuid.UUID, ChunkResult] = {}

    for rank, result in enumerate(vector_results):
        scores[result.chunk_id] += 1.0 / (k + rank + 1)
        by_id[result.chunk_id] = result

    for rank, result in enumerate(bm25_results):
        scores[result.chunk_id] += 1.0 / (k + rank + 1)
        by_id[result.chunk_id] = result

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [by_id[chunk_id] for chunk_id, _ in ranked]
