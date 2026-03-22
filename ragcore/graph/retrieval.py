from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ragcore.db.models import Chunk, Document, DocumentEntity, Entity, Relation
from ragcore.graph.extraction import normalize_entity_name
from ragcore.retrieval.vector_search import ChunkResult

_GRAPH_DOCUMENT_ID = uuid.UUID(int=0)


@dataclass
class GraphSearchResult:
    chunks: list[ChunkResult]
    entities: list[dict]
    relations: list[dict]


def _pseudo_chunk_id(prefix: str, value: uuid.UUID) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"{prefix}:{value}")


def _entity_score(query_norm: str, entity_name: str, mention_count: int) -> float:
    entity_norm = normalize_entity_name(entity_name)
    if not entity_norm:
        return 0.0
    if entity_norm == query_norm:
        return 8.0 + min(mention_count, 10) * 0.05

    entity_terms = set(entity_norm.split())
    query_terms = set(query_norm.split())
    overlap = len(entity_terms & query_terms)
    if overlap == 0 and entity_norm not in query_norm and query_norm not in entity_norm:
        return 0.0
    return overlap + (2.0 if entity_norm in query_norm else 0.0) + min(mention_count, 10) * 0.05


async def _matched_entities(
    project_id: uuid.UUID,
    query_text: str,
    session: AsyncSession,
    limit: int,
) -> list[tuple[Entity, float]]:
    query_norm = normalize_entity_name(query_text)
    if not query_norm:
        return []

    result = await session.execute(select(Entity).where(Entity.project_id == project_id))
    entities = result.scalars().all()
    scored = [
        (entity, _entity_score(query_norm, entity.name, entity.mention_count))
        for entity in entities
    ]
    scored = [item for item in scored if item[1] > 0]
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:limit]


async def local_graph_search(
    project_id: uuid.UUID,
    query_text: str,
    top_k: int,
    session: AsyncSession,
) -> GraphSearchResult:
    matched_entities = await _matched_entities(project_id, query_text, session, limit=max(5, top_k * 2))
    if not matched_entities:
        return GraphSearchResult(chunks=[], entities=[], relations=[])

    entity_scores = {entity.id: score for entity, score in matched_entities}
    entity_payload = [
        {
            "entity_id": str(entity.id),
            "name": entity.name,
            "score": round(score, 4),
            "mention_count": entity.mention_count,
            "entity_type": entity.entity_type,
        }
        for entity, score in matched_entities
    ]

    entity_ids = [entity.id for entity, _ in matched_entities]
    links = (
        await session.execute(
            select(DocumentEntity).where(DocumentEntity.entity_id.in_(entity_ids))
        )
    ).scalars().all()

    chunk_scores: dict[tuple[uuid.UUID, int], float] = defaultdict(float)
    for link in links:
        base = entity_scores.get(link.entity_id, 0.0) + (link.mention_count * 0.1)
        for chunk_index in link.chunk_indices:
            chunk_scores[(link.document_id, chunk_index)] += base

    if not chunk_scores:
        return GraphSearchResult(chunks=[], entities=entity_payload, relations=[])

    document_ids = sorted({document_id for document_id, _ in chunk_scores})
    rows = (
        await session.execute(
            select(Chunk, Document.filename)
            .join(Document, Chunk.document_id == Document.id)
            .where(Chunk.project_id == project_id, Chunk.document_id.in_(document_ids))
        )
    ).all()

    chunks: list[ChunkResult] = []
    for row in rows:
        score = chunk_scores.get((row.Chunk.document_id, row.Chunk.chunk_index))
        if score is None:
            continue
        chunks.append(
            ChunkResult(
                chunk_id=row.Chunk.id,
                document_id=row.Chunk.document_id,
                project_id=row.Chunk.project_id,
                content=row.Chunk.content,
                score=score,
                chunk_index=row.Chunk.chunk_index,
                filename=row.filename,
                metadata=row.Chunk.meta,
                source_kind="chunk",
                source_label=row.filename,
            )
        )

    chunks.sort(key=lambda item: item.score, reverse=True)
    return GraphSearchResult(chunks=chunks[:top_k], entities=entity_payload, relations=[])


async def global_graph_search(
    project_id: uuid.UUID,
    query_text: str,
    top_k: int,
    session: AsyncSession,
) -> GraphSearchResult:
    matched_entities = await _matched_entities(project_id, query_text, session, limit=max(5, top_k))
    entity_payload = [
        {
            "entity_id": str(entity.id),
            "name": entity.name,
            "score": round(score, 4),
            "mention_count": entity.mention_count,
            "entity_type": entity.entity_type,
        }
        for entity, score in matched_entities
    ]
    if not matched_entities:
        return GraphSearchResult(chunks=[], entities=[], relations=[])

    entity_ids = [entity.id for entity, _ in matched_entities]
    entity_scores = {entity.id: score for entity, score in matched_entities}
    source_entity_alias = aliased(Entity)
    target_entity_alias = aliased(Entity)
    relation_rows = (
        await session.execute(
            select(Relation, source_entity_alias, target_entity_alias)
            .join(source_entity_alias, Relation.source_entity_id == source_entity_alias.id)
            .join(target_entity_alias, Relation.target_entity_id == target_entity_alias.id)
            .where(Relation.project_id == project_id)
        )
    ).all()

    relation_payload: list[dict] = []
    pseudo_chunks: list[ChunkResult] = []
    for relation, source_entity, target_entity in relation_rows:
        if relation.project_id != project_id:
            continue
        if relation.source_entity_id not in entity_ids and relation.target_entity_id not in entity_ids:
            continue
        score = float(relation.weight)
        if relation.source_entity_id in entity_ids:
            score += entity_scores[relation.source_entity_id]
        if relation.target_entity_id in entity_ids:
            score += entity_scores[relation.target_entity_id]
        label = f"{source_entity.name} {relation.relation_type} {target_entity.name}"
        content = label
        if relation.description:
            content = f"{label}. {relation.description}"
        pseudo_chunks.append(
            ChunkResult(
                chunk_id=_pseudo_chunk_id("relation", relation.id),
                document_id=_GRAPH_DOCUMENT_ID,
                project_id=project_id,
                content=content,
                score=score,
                chunk_index=-1,
                filename="graph",
                metadata={
                    "relation_id": str(relation.id),
                    "source_entity_id": str(relation.source_entity_id),
                    "target_entity_id": str(relation.target_entity_id),
                },
                source_kind="relation",
                source_label=label,
            )
        )
        relation_payload.append(
            {
                "relation_id": str(relation.id),
                "source": source_entity.name,
                "target": target_entity.name,
                "relation_type": relation.relation_type,
                "weight": relation.weight,
                "score": round(score, 4),
            }
        )

    for entity, score in matched_entities[:top_k]:
        label = entity.name
        content = f"{entity.name} ({entity.entity_type})"
        if entity.description:
            content = f"{content}. {entity.description}"
        pseudo_chunks.append(
            ChunkResult(
                chunk_id=_pseudo_chunk_id("entity", entity.id),
                document_id=_GRAPH_DOCUMENT_ID,
                project_id=project_id,
                content=content,
                score=score,
                chunk_index=-1,
                filename="graph",
                metadata={"entity_id": str(entity.id)},
                source_kind="entity",
                source_label=label,
            )
        )

    pseudo_chunks.sort(key=lambda item: item.score, reverse=True)
    relation_payload.sort(key=lambda item: item["score"], reverse=True)
    return GraphSearchResult(
        chunks=pseudo_chunks[:top_k],
        entities=entity_payload,
        relations=relation_payload[:top_k],
    )
