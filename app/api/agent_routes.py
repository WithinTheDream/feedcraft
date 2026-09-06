"""API route for natural language feed control via LLM Agent."""

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.api.routes import store
from app.models.agent import AgentChatRequest, TopicUpdate
from app.models.post import Post
from app.services.agent import process_user_message
from app.services.scoring import rank_feed

router = APIRouter()


class AgentChatResponse(BaseModel):
    """Response returned by the /agent/chat endpoint."""

    reply: str = Field(
        ...,
        description="Conversational confirmation response from the algorithm agent.",
    )
    updated_preferences: dict[str, float] = Field(
        ...,
        description="Updated dictionary of user topic weights.",
    )
    feed_preview: list[Post] = Field(
        ...,
        description="Top 3 ranked posts in the user's feed after preference adjustment.",
    )
    updates: list[TopicUpdate] = Field(
        default_factory=list,
        description="List of structured topic weight changes parsed from the message.",
    )


@router.post(
    "/agent/chat",
    response_model=AgentChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Chat with FeedCraft Algorithm Agent",
    description=(
        "Processes natural language feed feedback (e.g. 'kurangi politik dan perbanyak python'), "
        "extracts topic weight adjustments, updates user preferences in-memory, "
        "and returns a conversational reply along with a top-3 feed preview."
    ),
)
def chat_with_agent(payload: AgentChatRequest) -> AgentChatResponse:
    """Natural language interface for adjusting feed topic weights."""
    # 1. Process message through LLM agent service (updates in-memory store)
    parse_result = process_user_message(
        user_id=payload.user_id, message=payload.message
    )

    # 2. Retrieve updated user preferences
    user_pref = store.preferences.get(payload.user_id)
    updated_weights = user_pref.topic_weights if user_pref else {}

    # 3. Calculate immediate feed preview (top 3 posts)
    all_posts = list(store.posts.values())
    ranked_posts = rank_feed(all_posts, user_pref)
    feed_preview = ranked_posts[:3]

    return AgentChatResponse(
        reply=parse_result.reply_message,
        updated_preferences=updated_weights,
        feed_preview=feed_preview,
        updates=parse_result.updates,
    )
