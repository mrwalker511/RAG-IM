import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from ragcore.config import settings
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    documents: Mapped[list["Document"]] = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    api_keys: Mapped[list["APIKey"]] = relationship("APIKey", back_populates="project", cascade="all, delete-orphan")
    bm25_indexes: Mapped[list["BM25Index"]] = relationship("BM25Index", back_populates="project", cascade="all, delete-orphan")
    query_logs: Mapped[list["QueryLog"]] = relationship("QueryLog", back_populates="project", cascade="all, delete-orphan")
    entities: Mapped[list["Entity"]] = relationship("Entity", back_populates="project", cascade="all, delete-orphan")
    relations: Mapped[list["Relation"]] = relationship("Relation", back_populates="project", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")  # pending|processing|complete|failed
    meta: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship("Project", back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    entity_links: Mapped[list["DocumentEntity"]] = relationship("DocumentEntity", back_populates="document", cascade="all, delete-orphan")
    relation_links: Mapped[list["DocumentRelation"]] = relationship("DocumentRelation", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.EMBEDDING_DIM), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")


class BM25Index(Base):
    __tablename__ = "bm25_indexes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    index_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project: Mapped["Project"] = relationship("Project", back_populates="bm25_indexes")


class QueryLog(Base):
    __tablename__ = "query_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    query_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="hybrid")
    latency_ms: Mapped[int] = mapped_column(BigInteger, nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=True)
    top_scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    retrieval_trace: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    eval_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship("Project", back_populates="query_logs")


class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="api_keys")


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, default="named_entity")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    meta: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship("Project", back_populates="entities")
    source_relations: Mapped[list["Relation"]] = relationship(
        "Relation",
        back_populates="source_entity",
        cascade="all, delete-orphan",
        foreign_keys="Relation.source_entity_id",
    )
    target_relations: Mapped[list["Relation"]] = relationship(
        "Relation",
        back_populates="target_entity",
        cascade="all, delete-orphan",
        foreign_keys="Relation.target_entity_id",
    )
    document_links: Mapped[list["DocumentEntity"]] = relationship(
        "DocumentEntity",
        back_populates="entity",
        cascade="all, delete-orphan",
    )


class Relation(Base):
    __tablename__ = "relations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    source_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    target_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False, default="related_to")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    meta: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship("Project", back_populates="relations")
    source_entity: Mapped["Entity"] = relationship(
        "Entity",
        back_populates="source_relations",
        foreign_keys=[source_entity_id],
    )
    target_entity: Mapped["Entity"] = relationship(
        "Entity",
        back_populates="target_relations",
        foreign_keys=[target_entity_id],
    )
    document_links: Mapped[list["DocumentRelation"]] = relationship(
        "DocumentRelation",
        back_populates="relation",
        cascade="all, delete-orphan",
    )


class DocumentEntity(Base):
    __tablename__ = "document_entities"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    chunk_indices: Mapped[list[int]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["Document"] = relationship("Document", back_populates="entity_links")
    entity: Mapped["Entity"] = relationship("Entity", back_populates="document_links")


class DocumentRelation(Base):
    __tablename__ = "document_relations"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    relation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("relations.id", ondelete="CASCADE"), primary_key=True)
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    chunk_indices: Mapped[list[int]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["Document"] = relationship("Document", back_populates="relation_links")
    relation: Mapped["Relation"] = relationship("Relation", back_populates="document_links")
