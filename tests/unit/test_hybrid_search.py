import uuid

from ragcore.retrieval.hybrid import reciprocal_rank_fusion
from ragcore.retrieval.vector_search import ChunkResult


def _make_result(chunk_id: uuid.UUID, score: float = 0.5) -> ChunkResult:
    return ChunkResult(
        chunk_id=chunk_id,
        document_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        content="some content",
        score=score,
        chunk_index=0,
        filename="doc.txt",
        metadata={},
    )


def test_rrf_combines_both_lists():
    ids = [uuid.uuid4() for _ in range(5)]
    vector = [_make_result(ids[0]), _make_result(ids[1]), _make_result(ids[2])]
    bm25 = [_make_result(ids[2]), _make_result(ids[3]), _make_result(ids[4])]
    fused = reciprocal_rank_fusion(vector, bm25)
    result_ids = [r.chunk_id for r in fused]
    assert ids[2] in result_ids  # appears in both — should rank high
    assert set(result_ids) == set(ids)


def test_rrf_top_ranked_appears_in_both():
    ids = [uuid.uuid4() for _ in range(4)]
    shared = ids[0]
    vector = [_make_result(shared), _make_result(ids[1])]
    bm25 = [_make_result(shared), _make_result(ids[2])]
    fused = reciprocal_rank_fusion(vector, bm25)
    assert fused[0].chunk_id == shared


def test_rrf_empty_lists():
    assert reciprocal_rank_fusion([], []) == []


def test_rrf_one_empty_list():
    ids = [uuid.uuid4(), uuid.uuid4()]
    vector = [_make_result(ids[0]), _make_result(ids[1])]
    fused = reciprocal_rank_fusion(vector, [])
    assert len(fused) == 2


def test_rrf_no_duplicates_in_output():
    cid = uuid.uuid4()
    r = _make_result(cid)
    fused = reciprocal_rank_fusion([r], [r])
    ids = [x.chunk_id for x in fused]
    assert len(ids) == len(set(ids))
