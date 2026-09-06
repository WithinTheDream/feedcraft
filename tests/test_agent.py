"""Unit and integration tests for LLM Agent parser and natural language feed control."""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.api.routes import store
from app.main import app
from app.core.config import Settings, settings
from app.models.agent import AgentParseResult, TopicUpdate
from app.models.post import Post
from app.models.user_preference import UserPreference
from app.services.agent import (
    _rule_based_fallback_parser,
    call_llm_parser,
    process_user_message,
)


@pytest.fixture(autouse=True)
def clean_in_memory_store():
    """Reset the in-memory store before and after each test."""
    store.clear()
    yield
    store.clear()


client = TestClient(app)


# ============================================================================
# 1. Tests for Rule-Based Fallback Parser (Offline / Zero-Key Guarantees)
# ============================================================================


def test_fallback_parser_indonesian_prompt():
    """Correctly parses Indonesian natural language input with multiple topics."""
    prompt = "Bro, kurangi politik dan perbanyak tutorial Python"
    result = _rule_based_fallback_parser(prompt)

    assert isinstance(result, AgentParseResult)
    topics = {u.topic: u.weight for u in result.updates}

    assert "politics" in topics
    assert topics["politics"] <= -0.5  # reduced or blocked
    assert "python" in topics
    assert topics["python"] >= 0.8  # boosted
    assert len(result.reply_message) > 0


def test_fallback_parser_english_block_and_focus():
    """Correctly parses English request with hard block (-1.0) and focus."""
    prompt = "I'm sick of politics, hide it completely. Focus on Python and Tech news."
    result = _rule_based_fallback_parser(prompt)

    topics = {u.topic: u.weight for u in result.updates}
    assert topics.get("politics") == -1.0  # Hard block
    assert topics.get("python") >= 0.8  # Boosted
    assert "tech" in topics


def test_fallback_parser_reset_to_neutral():
    """Correctly parses reset command to neutral 0.0 weight."""
    prompt = "Reset food preferences to neutral"
    result = _rule_based_fallback_parser(prompt)

    topics = {u.topic: u.weight for u in result.updates}
    assert topics.get("food") == 0.0


# ============================================================================
# 2. Tests for process_user_message & Preference Merging
# ============================================================================


def test_process_user_message_merges_existing_preferences():
    """New topic updates merge into existing topic weights without wiping unrelated topics."""
    user_id = "user_merge_test"
    # Seed pre-existing preferences
    store.preferences[user_id] = UserPreference(
        user_id=user_id,
        topic_weights={"cooking": 0.6, "politics": 0.2},
    )

    # Process message to mute politics and boost python
    result = process_user_message(
        user_id, "hide politics completely and perbanyak python"
    )

    updated_weights = store.preferences[user_id].topic_weights
    # Politics should be updated to -1.0
    assert updated_weights["politics"] == -1.0
    # Python should be added with positive boost
    assert updated_weights["python"] >= 0.8
    # Cooking should remain intact!
    assert updated_weights["cooking"] == 0.6


# ============================================================================
# 3. Tests for Mocking LiteLLM Completions
# ============================================================================


def test_call_llm_parser_with_mocked_litellm():
    """Tests LLM parser execution with a mocked litellm.completion structured output."""
    mock_payload = {
        "updates": [
            {
                "topic": "crypto",
                "weight": -1.0,
                "reason": "User explicitly asked to block crypto content.",
            },
            {
                "topic": "ai",
                "weight": 0.9,
                "reason": "User requested heavy focus on AI developments.",
            },
        ],
        "reply_message": "Done! Blocked crypto completely (-1.0) and prioritized AI (+0.9).",
    }

    # Simulate litellm response format
    mock_choice = MagicMock()
    mock_choice.message.content = AgentParseResult.model_validate(
        mock_payload
    ).model_dump_json()
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch("litellm.completion", return_value=mock_response):
        with patch("app.services.agent.settings") as mock_settings:
            mock_settings.mock_llm_mode = False
            mock_settings.has_active_api_key.return_value = True
            mock_settings.llm_model = "gemini/gemini-1.5-flash"
            mock_settings.gemini_api_key = "test-key"
            mock_settings.openai_api_key = None
            mock_settings.anthropic_api_key = None
            mock_settings.groq_api_key = None

            result = call_llm_parser(
                "Block all crypto and give me maximum AI news",
                current_weights={},
            )

            assert result.updates[0].topic == "crypto"
            assert result.updates[0].weight == -1.0
            assert result.updates[1].topic == "ai"
            assert result.updates[1].weight == 0.9
            assert "Blocked crypto" in result.reply_message


# ============================================================================
# 4. Integration Tests for POST /agent/chat
# ============================================================================


def test_post_agent_chat_endpoint():
    """Tests the /agent/chat API endpoint end-to-end, validating feed preview ranking."""
    # 1. Seed candidate posts in store
    store.posts["p_py"] = Post(
        id="p_py",
        content="Learn FastAPI with Python 3.11",
        tags=["python", "tech"],
        base_score=0.7,
    )
    store.posts["p_pol"] = Post(
        id="p_pol",
        content="Breaking election updates",
        tags=["politics"],
        base_score=0.9,
    )
    store.posts["p_food"] = Post(
        id="p_food",
        content="Italian pasta recipe",
        tags=["food"],
        base_score=0.5,
    )

    # 2. Invoke /agent/chat endpoint
    payload = {
        "user_id": "user_api_tester",
        "message": "Bro, kurangi politik dan perbanyak tutorial Python",
    }
    response = client.post("/agent/chat", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "reply" in data
    assert "updated_preferences" in data
    assert "feed_preview" in data

    # Verify preferences updated
    prefs = data["updated_preferences"]
    assert "python" in prefs
    assert "politics" in prefs

    # Verify feed preview filtered out politics and ranked Python top
    feed_ids = [p["id"] for p in data["feed_preview"]]
    assert "p_pol" not in feed_ids  # Politics must be excluded
    assert "p_py" in feed_ids
    assert feed_ids[0] == "p_py"  # Python post ranks #1
