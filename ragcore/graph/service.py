from __future__ import annotations

import uuid

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ragcore.db.models import DocumentEntity, DocumentRelation, Entity, Relation
from ragcore.graph.extraction import GraphExtraction


async def purge_document_graph(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    entity_links = (
        await session.execute(
            select(DocumentEntity).where(DocumentEntity.document_id == document_id)
        )
    ).scalars().all()
    relation_links = (
        await session.execute(
            select(DocumentRelation).where(DocumentRelation.document_id == document_id)
        )
    ).scalars().all()

    for link in relation_links:
        relation = await session.get(Relation, link.relation_id)
        if relation:
            relation.weight = max(0, relation.weight - link.mention_count)
        await session.delete(link)

    for link in entity_links:
        entity = await session.get(Entity, link.entity_id)
        if entity:
            entity.mention_count = max(0, entity.mention_count - link.mention_count)
        await session.delete(link)

    await session.flush()

    orphan_relations = (
        await session.execute(
            select(Relation)
            .where(Relation.project_id == project_id)
            .outerjoin(DocumentRelation, DocumentRelation.relation_id == Relation.id)
            .where(DocumentRelation.relation_id.is_(None))
        )
    ).scalars().all()
    for relation in orphan_relations:
        await session.delete(relation)

    await session.flush()

    orphan_entities = (
        await session.execute(
            select(Entity)
            .where(Entity.project_id == project_id)
            .outerjoin(DocumentEntity, DocumentEntity.entity_id == Entity.id)
            .where(DocumentEntity.entity_id.is_(None))
        )
    ).scalars().all()
    for entity in orphan_entities:
        await session.delete(entity)

    await session.flush()


async def _upsert_entity(
    project_id: uuid.UUID,
    extracted_entity,
    session: AsyncSession,
) -> Entity:
    result = await session.execute(
        select(Entity).where(
            Entity.project_id == project_id,
            Entity.normalized_name == extracted_entity.normalized_name,
        )
    )
    entity = result.scalar_one_or_none()
    if entity is None:
        entity = Entity(
            project_id=project_id,
            name=extracted_entity.name,
            normalized_name=extracted_entity.normalized_name,
            entity_type=extracted_entity.entity_type,
            description=extracted_entity.description,
            mention_count=extracted_entity.mention_count,
            meta={},
        )
        session.add(entity)
        await session.flush()
        return entity

    entity.name = entity.name if len(entity.name) >= len(extracted_entity.name) else extracted_entity.name
    entity.entity_type = extracted_entity.entity_type or entity.entity_type
    if extracted_entity.description and not entity.description:
        entity.description = extracted_entity.description
    entity.mention_count += extracted_entity.mention_count
    await session.flush()
    return entity


async def _upsert_relation(
    project_id: uuid.UUID,
    source_entity_id: uuid.UUID,
    target_entity_id: uuid.UUID,
    extracted_relation,
    session: AsyncSession,
) -> Relation:
    result = await session.execute(
        select(Relation).where(
            Relation.project_id == project_id,
            Relation.source_entity_id == source_entity_id,
            Relation.target_entity_id == target_entity_id,
            Relation.relation_type == extracted_relation.relation_type,
        )
    )
    relation = result.scalar_one_or_none()
    if relation is None:
        relation = Relation(
            project_id=project_id,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relation_type=extracted_relation.relation_type,
            description=extracted_relation.description,
            weight=extracted_relation.mention_count,
            meta={},
        )
        session.add(relation)
        await session.flush()
        return relation

    if extracted_relation.description and not relation.description:
        relation.description = extracted_relation.description
    relation.weight += extracted_relation.mention_count
    await session.flush()
    return relation


async def upsert_document_graph(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    extraction: GraphExtraction,
    session: AsyncSession,
) -> dict[str, int]:
    entity_ids_by_name: dict[str, uuid.UUID] = {}

    for extracted_entity in extraction.entities:
        entity = await _upsert_entity(project_id, extracted_entity, session)
        entity_ids_by_name[extracted_entity.normalized_name] = entity.id
        session.add(
            DocumentEntity(
                document_id=document_id,
                entity_id=entity.id,
                mention_count=extracted_entity.mention_count,
                chunk_indices=extracted_entity.chunk_indices,
            )
        )

    await session.flush()

    for extracted_relation in extraction.relations:
        source_entity_id = entity_ids_by_name.get(extracted_relation.source_normalized_name)
        target_entity_id = entity_ids_by_name.get(extracted_relation.target_normalized_name)
        if not source_entity_id or not target_entity_id or source_entity_id == target_entity_id:
            continue
        relation = await _upsert_relation(
            project_id=project_id,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            extracted_relation=extracted_relation,
            session=session,
        )
        session.add(
            DocumentRelation(
                document_id=document_id,
                relation_id=relation.id,
                mention_count=extracted_relation.mention_count,
                chunk_indices=extracted_relation.chunk_indices,
            )
        )

    await session.flush()
    return {
        "entities": len(extraction.entities),
        "relations": len(extraction.relations),
    }
