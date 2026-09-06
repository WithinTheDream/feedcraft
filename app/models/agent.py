"""Pydantic schemas for LLM Agent parser and natural language control."""

from pydantic import BaseModel, Field, field_validator


class TopicUpdate(BaseModel):
    """Structured extraction of a single topic preference change."""

    topic: str = Field(
        ...,
        description="Topic tag in lowercase (e.g. 'python', 'politics', 'tech').",
    )
    weight: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description=(
            "Weight value on a -1.0 to +1.0 scale: "
            "-1.0 (block/hard filter), -0.3 to -0.6 (reduce), "
            "+0.4 to +0.8 (boost), +0.9 to +1.0 (heavy focus), 0.0 (reset/neutral)."
        ),
    )
    reason: str = Field(
        ...,
        description="Brief rationale for this extracted weight assignment.",
    )

    @field_validator("topic")
    @classmethod
    def normalize_topic(cls, v: str) -> str:
        return v.strip().lower()

    model_config = {
        "json_schema_extra": {
            "example": {
                "topic": "politics",
                "weight": -1.0,
                "reason": "User expressed extreme fatigue and explicitly requested to hide politics completely.",
            }
        }
    }


class AgentParseResult(BaseModel):
    """Structured response returned by the LLM agent parser."""

    updates: list[TopicUpdate] = Field(
        default_factory=list,
        description="List of topic updates extracted from the user message.",
    )
    reply_message: str = Field(
        ...,
        description="Friendly, conversational confirmation response explaining the changes made to the user's feed.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "updates": [
                    {
                        "topic": "politics",
                        "weight": -1.0,
                        "reason": "Mute politics completely per user instruction.",
                    },
                    {
                        "topic": "python",
                        "weight": 0.9,
                        "reason": "Boost Python tutorials and development content.",
                    },
                ],
                "reply_message": "Sip! Aku sudah blokir konten politik sepenuhnya (-1.0) dan naikin prioritas tutorial Python kamu (+0.9). Feed kamu sekarang jauh lebih fokus ke coding!",
            }
        }
    }


class AgentChatRequest(BaseModel):
    """Payload for POST /agent/chat."""

    user_id: str = Field(..., description="Unique user identifier.")
    message: str = Field(
        ..., min_length=1, description="Natural language feedback or command."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "user_developer_01",
                "message": "Bro, kurangi politik dan perbanyak tutorial Python ya!",
            }
        }
    }
