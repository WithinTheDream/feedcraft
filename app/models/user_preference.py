"""UserPreference data model using Pydantic v2."""

from pydantic import BaseModel, Field


class UserPreferenceUpdate(BaseModel):
    """Schema for updating topic weights for a user."""

    topic_weights: dict[str, float] = Field(
        default_factory=dict,
        description="Mapping of topic tag to user preference weight (e.g. {'python': 0.8, 'politics': -1.0}).",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "topic_weights": {
                    "python": 0.9,
                    "tech": 0.4,
                    "politics": -1.0,
                }
            }
        }
    }


class UserPreference(BaseModel):
    """User preference model storing explicit topic weights."""

    user_id: str = Field(..., description="Unique user identifier.")
    topic_weights: dict[str, float] = Field(
        default_factory=dict,
        description="Mapping of topic tag to weight multiplier.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "user-123",
                "topic_weights": {
                    "python": 0.8,
                    "politics": -1.0,
                },
            }
        }
    }
