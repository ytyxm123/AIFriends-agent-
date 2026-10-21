from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MemoryOperation(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    action: Literal['upsert', 'forget']
    key: str = Field(min_length=1, max_length=100, pattern=r'^[a-z0-9_.:-]+$')
    category: Literal['profile', 'preference', 'event', 'relationship']
    content: str = Field(min_length=1, max_length=500)
    importance: float = Field(default=0.5, ge=0, le=1)
    confidence: float = Field(default=1.0, ge=0, le=1)
    source_message_id: int = Field(gt=0)
    evidence: str = Field(min_length=1, max_length=500)
    expires_at: datetime | None = None

    @field_validator('expires_at')
    @classmethod
    def aware_expiration(cls, value):
        if value is not None and value.utcoffset() is None:
            raise ValueError('expires_at must include a timezone')
        return value


class MemoryExtraction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    summary: str = Field(min_length=1, max_length=1500)
    operations: list[MemoryOperation] = Field(default_factory=list, max_length=30)
