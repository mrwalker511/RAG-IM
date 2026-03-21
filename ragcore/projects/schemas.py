import uuid
from datetime import datetime

from pydantic import BaseModel


class ProjectConfig(BaseModel):
    chunk_size: int = 512
    chunk_overlap: int = 64
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4o-mini"
    top_k: int = 5


class ProjectCreate(BaseModel):
    name: str
    config: ProjectConfig = ProjectConfig()


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    config: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectList(BaseModel):
    projects: list[ProjectResponse]
    total: int
