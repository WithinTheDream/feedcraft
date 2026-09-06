"""Unit and integration tests for scoring service and API endpoints."""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.api.routes import store
from app.main import app
from app.models.post import Post, PostCreate
from app.models.user_preference import UserPreference, UserPreferenceUpdate
from app.services.scoring import (
    FILTERED_POST_SCORE,
    HARD_FILTER_THRESHOLD,
    calculate_post_score,
    get_post_score_breakdown,
    rank_feed,
)


# ============================================================================
# Unit Tests: calculate_post_score & Hard Filtering
# ============================================================================


def test_calculate_post_score_neutral():
    """Posts with no matching preference tags retain their base score."""
    post = Post(
        id="p1",
        content="General news update",
        tags=["news", "general"],
        base_score=0.6,
    )
    pref = UserPreference(user_id="u1", topic_weights={"python": 0.8})

    score = calculate_post_score(post, pref)
    assert score == 0.6


def test_calculate_post_score_single_positive_topic():
    """Score increases correctly with a single matching topic."""
    post = Post(
        id="p2",
        content="Awesome Python 3.12 tips!",
        tags=["python"],
        base_score=0.5,
    )
    pref = UserPreference(user_id="u1", topic_weights={"python": 0.8})

    # Final = 0.5 * (1 + 0.8) = 0.5 * 1.8 = 0.9
    score = calculate_post_score(post, pref)
    assert score == 0.9


def test_calculate_post_score_multiple_positive_topics():
    """Topic weights are summed for all matching tags."""
    post = Post(
        id="p3",
        content="Building FastAPI microservices in Python",
        tags=["python", "tech", "cloud"],
        base_score=0.5,
    )
    pref = UserPreference(
        user_id="u1",
        topic_weights={"python": 0.5, "tech": 0.3},  # 'cloud' not in preferences
    )

    # Multiplier = 1 + (0.5 + 0.3) = 1.8
    # Final = 0.5 * 1.8 = 0.9
    score = calculate_post_score(post, pref)
    assert score == 0.9


def test_hard_filter_trigger_at_threshold():
    """Tag matching weight exactly <= -1.0 triggers hard filter (-999.0)."""
    post = Post(
        id="p4",
        content="Controversial political election debate",
        tags=["politics", "news"],
        base_score=0.9,
    )
    pref = UserPreference(user_id="u1", topic_weights={"politics": -1.0})

    score = calculate_post_score(post, pref)
    assert score == FILTERED_POST_SCORE


def test_hard_filter_trigger_below_threshold():
    """Tag matching weight < -1.0 triggers hard filter (-999.0)."""
    post = Post(
        id="p5",
        content="Extreme controversy",
        tags=["spam"],
        base_score=0.9,
    )
    pref = UserPreference(user_id="u1", topic_weights={"spam": -1.5})

    score = calculate_post_score(post, pref)
    assert score == FILTERED_POST_SCORE


def test_hard_filter_overrides_positive_topics():
    """Hard filter tag excludes post even if other tags have high positive weights."""
    post = Post(
        id="p6",
        content="Political bill about AI technology in Python",
        tags=["python", "ai", "politics"],
        base_score=0.9,
    )
    pref = UserPreference(
        user_id="u1",
        topic_weights={"python": 1.0, "ai": 0.8, "politics": -1.0},
    )

    score = calculate_post_score(post, pref)
    assert score == FILTERED_POST_SCORE


def test_soft_negative_weight_does_not_hard_filter():
    """Negative weight between -1.0 and 0.0 reduces score without hard filter."""
    post = Post(
        id="p7",
        content="Celebrity gossip article",
        tags=["celebrity"],
        base_score=0.8,
    )
    pref = UserPreference(user_id="u1", topic_weights={"celebrity": -0.5})

    # Multiplier = 1 + (-0.5) = 0.5
    # Final = 0.8 * 0.5 = 0.4
    score = calculate_post_score(post, pref)
    assert score == 0.4


def test_case_insensitivity_and_whitespace():
    """Tag matching handles mixed case and whitespace robustly."""
    post = Post(
        id="p8",
        content="Python case study",
        tags=["  PyThOn  "],
        base_score=0.5,
    )
    pref = UserPreference(user_id="u1", topic_weights={"python": 0.8})

    score = calculate_post_score(post, pref)
    assert score == 0.9


# ============================================================================
# Unit Tests: rank_feed
# ============================================================================


def test_rank_feed_filtering_and_ordering():
    """rank_feed filters out hard-filtered posts and sorts remaining descending."""
    posts = [
        Post(id="p_pol", content="Politics News", tags=["politics"], base_score=0.95),
        Post(id="p_food", content="Pasta Recipe", tags=["food"], base_score=0.5),
        Post(
            id="p_py",
            content="Python Asyncio Tutorial",
            tags=["python"],
            base_score=0.6,
        ),
        Post(id="p_tech", content="GPU Architecture", tags=["tech"], base_score=0.7),
    ]

    pref = UserPreference(
        user_id="u_dev",
        topic_weights={"python": 0.9, "tech": 0.4, "politics": -1.0},
    )

    ranked = rank_feed(posts, pref)

    # Expected:
    # - p_pol: hard filtered (-999.0) -> EXCLUDED
    # - p_py: 0.6 * (1 + 0.9) = 1.14
    # - p_tech: 0.7 * (1 + 0.4) = 0.98
    # - p_food: 0.5 * 1 = 0.50
    # Expected order: p_py, p_tech, p_food
    assert len(ranked) == 3
    assert [p.id for p in ranked] == ["p_py", "p_tech", "p_food"]


def test_rank_feed_excludes_negative_final_score():
    """Posts whose score drops strictly below 0 are filtered out."""
    post_neg = Post(
        id="p_bad",
        content="Sub-zero interest content",
        tags=["crypto", "ads"],
        base_score=0.5,
    )
    post_good = Post(
        id="p_good",
        content="Great cooking tips",
        tags=["cooking"],
        base_score=0.4,
    )

    # Multiplier: 1 + (-0.6 + -0.6) = 1 - 1.2 = -0.2 -> Final: -0.1 < 0
    pref = UserPreference(
        user_id="u1",
        topic_weights={"crypto": -0.6, "ads": -0.6},
    )

    ranked = rank_feed([post_neg, post_good], pref)
    assert len(ranked) == 1
    assert ranked[0].id == "p_good"


def test_rank_feed_empty_posts():
    """Empty post list returns empty feed."""
    pref = UserPreference(user_id="u1", topic_weights={"python": 0.8})
    assert rank_feed([], pref) == []


# ============================================================================
# Integration Tests: FastAPI Endpoints
# ============================================================================


@pytest.fixture(autouse=True)
def clean_in_memory_store():
    """Ensure in-memory store is clean before and after every test."""
    store.clear()
    yield
    store.clear()


client = TestClient(app)


def test_create_post_api():
    """POST /posts creates and stores a post."""
    payload = {
        "id": "post-api-1",
        "content": "Exploring Pydantic v2",
        "tags": ["python", "pydantic"],
        "base_score": 0.75,
    }
    response = client.post("/posts", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "post-api-1"
    assert data["content"] == "Exploring Pydantic v2"
    assert data["tags"] == ["python", "pydantic"]
    assert data["base_score"] == 0.75
    assert "created_at" in data


def test_update_preferences_api():
    """POST /preferences/{user_id} sets user topic weights."""
    weights = {"python": 0.85, "politics": -1.0}
    response = client.post("/preferences/user-99", json={"topic_weights": weights})
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "user-99"
    assert data["topic_weights"] == weights


def test_get_ranked_feed_api():
    """GET /feed/{user_id} returns correctly ranked and filtered feed."""
    # Seed posts
    client.post(
        "/posts",
        json={
            "id": "p1",
            "content": "Python is fast in 3.12",
            "tags": ["python"],
            "base_score": 0.6,
        },
    )
    client.post(
        "/posts",
        json={
            "id": "p2",
            "content": "Breaking election results",
            "tags": ["politics"],
            "base_score": 0.9,
        },
    )
    client.post(
        "/posts",
        json={
            "id": "p3",
            "content": "Delicious taco recipe",
            "tags": ["food"],
            "base_score": 0.5,
        },
    )

    # Set user preference
    client.post(
        "/preferences/user-alex",
        json={"topic_weights": {"python": 0.9, "politics": -1.0}},
    )

    # Fetch feed
    response = client.get("/feed/user-alex")
    assert response.status_code == 200
    feed = response.json()

    # Verify politics is excluded, and python is ranked above food
    assert len(feed) == 2
    assert feed[0]["id"] == "p1"
    assert feed[1]["id"] == "p3"


def test_get_explained_feed_api():
    """GET /feed/{user_id}/explained provides complete scoring diagnostics."""
    client.post(
        "/posts",
        json={
            "id": "p1",
            "content": "Python Tutorial",
            "tags": ["python"],
            "base_score": 0.5,
        },
    )
    client.post(
        "/posts",
        json={
            "id": "p2",
            "content": "Political Debate",
            "tags": ["politics"],
            "base_score": 0.8,
        },
    )

    client.post(
        "/preferences/user-sam",
        json={"topic_weights": {"python": 0.8, "politics": -1.0}},
    )

    response = client.get("/feed/user-sam/explained")
    assert response.status_code == 200
    data = response.json()

    assert data["total_posts_considered"] == 2
    assert data["total_posts_in_feed"] == 1
    assert data["feed"][0]["post"]["id"] == "p1"
    assert data["feed"][0]["score"] == 0.9
    assert len(data["filtered_posts"]) == 1
    assert data["filtered_posts"][0]["post_id"] == "p2"
    assert data["filtered_posts"][0]["is_filtered"] is True
