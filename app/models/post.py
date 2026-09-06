"""Post data model using Pydantic v2."""

from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    """Schema for creating a new post."""

    id: str | None = Field(
        default=None,
        description="Optional unique identifier. A UUID is generated if omitted.",
    )
    content: str = Field(..., min_length=1, description="Post text or description.")
    tags: list[str] = Field(
        default_factory=list,
        description="List of topic tags associated with the post (e.g. ['python', 'tech']).",
    )
    base_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Baseline engagement score or quality metric between 0.0 and 1.0.",
    )


class Post(BaseModel):
    """Complete Post model representing a social media item."""

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the post.",
    )
    content: str = Field(..., description="Post text or description.")
    tags: list[str] = Field(
        default_factory=list,
        description="List of topic tags associated with the post.",
    )
    base_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Baseline engagement score or quality metric between 0.0 and 1.0.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the post was created.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "post-1",
                "content": "Deep dive into Python 3.12 performance improvements!",
                "tags": ["python", "tech", "programming"],
                "base_score": 0.85,
                "created_at": "2026-09-06T12:00:00Z",
            }
        }
    }
