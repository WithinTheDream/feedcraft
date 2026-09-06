"""LLM Agent Service for extracting topic weight preferences and updating user feed settings."""

import json
import logging
import os
import re
from typing import Any

import litellm

from app.api.routes import store
from app.core.config import settings
from app.models.agent import AgentParseResult, TopicUpdate
from app.models.user_preference import UserPreference

logger = logging.getLogger("feedcraft.agent")

AGENT_SYSTEM_PROMPT = """You are the FeedCraft Algorithm Agent. Your job is to listen to the user's preferences regarding their feed content, extract topics and their corresponding weight changes (-1.0 to +1.0 scale), update their settings, and reply naturally.

Weight Guidelines:
- Hard Block / Mute / Stop seeing: -1.0
- Less / Reduce: -0.3 to -0.6
- More / Boost / Like: +0.4 to +0.8
- Heavy Focus / Priority: +0.9 to +1.0
- Reset / Neutral: 0.0

Instructions:
1. Identify all mentioned topics/categories (convert to lowercase single words or standard tags like 'python', 'politics', 'tech', 'food', 'ai', 'crypto', etc.).
2. Assign each topic a weight based on the guidelines above.
3. Formulate a friendly, conversational response explaining what changed in their feed. Reply in the same language the user used (e.g. Indonesian or English).
4. Output must strictly conform to the JSON schema for AgentParseResult.
"""


def _rule_based_fallback_parser(message: str) -> AgentParseResult:
    """Intelligent fallback parser when running offline or without active LLM keys.

    Handles common Indonesian and English intent patterns.
    """
    msg_lower = message.lower()
    updates: list[TopicUpdate] = []

    # Dictionary of topic aliases
    known_topics = {
        "python": ["python", "py"],
        "politics": ["politik", "politics", "political", "pemilu", "pilpres"],
        "tech": ["tech", "teknologi", "technology", "gadget", "software"],
        "food": ["food", "makanan", "kuliner", "cooking", "pizza", "baking"],
        "ai": ["ai", "artificial intelligence", "machine learning", "ml", "llm"],
        "crypto": ["crypto", "kripto", "bitcoin", "btc"],
        "news": ["news", "berita"],
    }

    # Detect topics mentioned
    found_topics: dict[str, str] = {}
    for canonical, aliases in known_topics.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", msg_lower):
                found_topics[canonical] = alias
                break

    # If no known topics found, attempt to extract nouns after action words
    if not found_topics:
        custom_matches = re.findall(
            r"(?:kurangi|perbanyak|fokus|blokir|tambah|more|less|block|hide|focus on)\s+([a-zA-Z]+)",
            msg_lower,
        )
        for custom_word in custom_matches:
            found_topics[custom_word.strip().lower()] = custom_word

    reply_parts = []

    for canonical, alias in found_topics.items():
        # Pattern matching helper
        def has_intent(prefixes: list[str], suffixes: list[str] | None = None) -> bool:
            prefix_pattern = r"(?:" + "|".join(prefixes) + r")\b(?:\s+\w+){0,3}\s+" + re.escape(alias)
            if re.search(prefix_pattern, msg_lower):
                return True
            if suffixes:
                suffix_pattern = re.escape(alias) + r"\b(?:\s+\w+){0,3}\s+(?:" + "|".join(suffixes) + r")"
                if re.search(suffix_pattern, msg_lower):
                    return True
            return False

        # 1. Reset / Neutral (0.0)
        if has_intent(["reset", "normalkan", "netralkan"], ["ke normal", "ke netral", "neutral", "normal"]):
            weight = 0.0
            reason = f"Reset topic '{canonical}' to neutral."
            reply_parts.append(f"mengembalikan topik {canonical} ke netral (0.0)")

        # 2. Hard block (-1.0)
        elif has_intent(
            ["blokir", "hide", "block", "mute", "stop", "hilangkan", "sick of", "hate", "tanpa", "jangan ada"],
            ["completely", "sama sekali", "sepenuhnya"],
        ) or (
            ("politik" in alias or "politics" in alias)
            and any(b in msg_lower for b in ["kurangi", "hide", "block", "stop", "sick of", "hilangkan", "jangan ada"])
        ):
            weight = -1.0
            reason = f"Hard block topic '{canonical}' per user request."
            reply_parts.append(f"memblokir konten {canonical} (-1.0)")

        # 3. Reduce / Less (-0.5)
        elif has_intent(["kurangi", "less", "reduce", "dikit"]):
            weight = -0.5
            reason = f"Reduced topic '{canonical}' per user preference."
            reply_parts.append(f"mengurangi konten {canonical} (-0.5)")

        # 4. Heavy focus / Priority (+0.9)
        elif has_intent(["fokus", "focus", "focus on", "prioritaskan", "priority", "utamakan"]):
            weight = 0.9
            reason = f"Heavy priority focus on topic '{canonical}'."
            reply_parts.append(f"memprioritaskan konten {canonical} (+0.9)")

        # 5. Boost / More (+0.8)
        elif has_intent(["perbanyak", "more", "boost", "tambah", "suka", "like"]) or (
            canonical == "python" and not any(neg in msg_lower for neg in ["kurangi", "block", "hide", "reset"])
        ):
            weight = 0.8
            reason = f"Boosted topic '{canonical}' per user interest."
            reply_parts.append(f"memperbanyak tutorial & artikel {canonical} (+0.8)")

        else:
            weight = 0.5
            reason = f"Adjusted interest for '{canonical}'."
            reply_parts.append(f"menyesuaikan topik {canonical} (+0.5)")

        updates.append(TopicUpdate(topic=canonical, weight=weight, reason=reason))

    # Generate friendly conversational reply
    is_indonesian = any(
        w in msg_lower
        for w in ["bro", "kurangi", "perbanyak", "dan", "ya", "tolong", "aku", "saya", "dong"]
    )

    if updates:
        if is_indonesian:
            changes_str = ", lalu ".join(reply_parts)
            reply = f"Siap! Aku sudah {changes_str}. Feed kamu sudah diperbarui dengan kurasi terbaru!"
        else:
            changes_str = "; ".join(f"{u.topic} ({u.weight:+.1f})" for u in updates)
            reply = f"Got it! I've updated your feed preferences: {changes_str}. Your feed ranking has been adjusted accordingly."
    else:
        if is_indonesian:
            reply = "Halo! Beritahu topik apa yang ingin kamu perbanyak, kurangi, atau blokir (misal: 'perbanyak Python, blokir politik')."
        else:
            reply = "Hello! Let me know what topics you'd like to see more or less of (e.g. 'boost tech, mute politics')."

    return AgentParseResult(updates=updates, reply_message=reply)


def call_llm_parser(
    message: str, current_weights: dict[str, float]
) -> AgentParseResult:
    """Invoke LiteLLM to extract structured preference updates from user input."""
    # Check if mock mode is forced or no API keys are present
    if settings.mock_llm_mode or not settings.has_active_api_key():
        logger.info("Using rule-based fallback parser (MOCK_LLM_MODE or no API keys).")
        return _rule_based_fallback_parser(message)

    # Prepare provider API keys in environment for LiteLLM
    if settings.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
    if settings.groq_api_key:
        os.environ["GROQ_API_KEY"] = settings.groq_api_key

    try:
        user_prompt = (
            f"Current User Topic Weights: {json.dumps(current_weights)}\n"
            f"User Input: \"{message}\"\n\n"
            "Extract structured topic weight updates and provide a conversational confirmation reply."
        )

        response = litellm.completion(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format=AgentParseResult,
            temperature=0.1,
        )

        content = response.choices[0].message.content

        if isinstance(content, str):
            return AgentParseResult.model_validate_json(content)
        elif isinstance(content, dict):
            return AgentParseResult.model_validate(content)
        elif isinstance(content, AgentParseResult):
            return content
        else:
            raise ValueError(f"Unexpected completion response type: {type(content)}")

    except Exception as exc:
        logger.warning(
            "LiteLLM call failed (%s). Falling back to rule-based parser.",
            exc,
            exc_info=True,
        )
        return _rule_based_fallback_parser(message)


def process_user_message(user_id: str, message: str) -> AgentParseResult:
    """Process natural language feed feedback from a user.

    1. Retrieves existing user preferences.
    2. Parses the message into structured TopicUpdate list and conversational reply.
    3. Merges topic updates into the in-memory preference store.
    4. Returns AgentParseResult.
    """
    # 1. Retrieve existing preferences
    user_pref = store.preferences.get(
        user_id, UserPreference(user_id=user_id, topic_weights={})
    )
    current_weights = dict(user_pref.topic_weights)

    # 2. Extract structured updates via LLM (or fallback)
    parse_result = call_llm_parser(message, current_weights)

    # 3. Merge extracted weights into user preference store
    for update in parse_result.updates:
        topic_key = update.topic.strip().lower()
        if update.weight == 0.0 and topic_key in current_weights:
            current_weights[topic_key] = 0.0
        else:
            current_weights[topic_key] = update.weight

    # Save back to in-memory store
    store.preferences[user_id] = UserPreference(
        user_id=user_id, topic_weights=current_weights
    )

    return parse_result
