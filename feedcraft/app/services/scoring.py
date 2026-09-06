"""Scoring and recommendation ranking engine for FeedControl."""

from app.models.post import Post
from app.models.user_preference import UserPreference

# Constants for scoring policy
HARD_FILTER_THRESHOLD: float = -1.0
FILTERED_POST_SCORE: float = -999.0


def calculate_post_score(post: Post, user_pref: UserPreference) -> float:
    """Calculate the personalized ranking score for a single post.

    Rules:
    1. Hard Filter: If ANY tag of the post matches a topic in `topic_weights`
       with a value <= -1.0, return -999.0 immediately (post is excluded).
    2. Formula:
       Final Score = Base Score * (1 + Sum(topic_weights[tag] for tag in post.tags if tag in topic_weights))

    Tag matching is case-insensitive and ignores leading/trailing whitespace.
    """
    # Normalize preference topics for robust lookup
    normalized_weights = {
        topic.strip().lower(): weight
        for topic, weight in user_pref.topic_weights.items()
    }

    # Step 1: Check for hard filter condition
    for tag in post.tags:
        normalized_tag = tag.strip().lower()
        if normalized_tag in normalized_weights:
            if normalized_weights[normalized_tag] <= HARD_FILTER_THRESHOLD:
                return FILTERED_POST_SCORE

    # Step 2: Sum matching topic weights
    topic_boost = sum(
        normalized_weights[tag.strip().lower()]
        for tag in post.tags
        if tag.strip().lower() in normalized_weights
    )

    # Step 3: Compute final score using multiplier formula
    final_score = post.base_score * (1.0 + topic_boost)

    return round(final_score, 4)


def get_post_score_breakdown(post: Post, user_pref: UserPreference) -> dict:
    """Provide a detailed diagnostic breakdown of the scoring process for a post.

    Useful for explainability, debugging, and user transparency.
    """
    normalized_weights = {
        topic.strip().lower(): weight
        for topic, weight in user_pref.topic_weights.items()
    }

    is_hard_filtered = False
    filtering_reasons = []
    matched_weights = {}

    for tag in post.tags:
        normalized_tag = tag.strip().lower()
        if normalized_tag in normalized_weights:
            weight = normalized_weights[normalized_tag]
            matched_weights[tag] = weight
            if weight <= HARD_FILTER_THRESHOLD:
                is_hard_filtered = True
                filtering_reasons.append(
                    f"Tag '{tag}' matches topic weight {weight} (<= {HARD_FILTER_THRESHOLD})"
                )

    if is_hard_filtered:
        return {
            "post_id": post.id,
            "base_score": post.base_score,
            "final_score": FILTERED_POST_SCORE,
            "is_filtered": True,
            "reason": "; ".join(filtering_reasons),
            "matched_weights": matched_weights,
            "multiplier": 0.0,
        }

    topic_boost = sum(matched_weights.values())
    multiplier = 1.0 + topic_boost
    final_score = round(post.base_score * multiplier, 4)
    is_negative = final_score < 0.0

    return {
        "post_id": post.id,
        "base_score": post.base_score,
        "final_score": final_score,
        "is_filtered": is_negative,
        "reason": "Final score < 0" if is_negative else "Passed filters",
        "matched_weights": matched_weights,
        "multiplier": round(multiplier, 4),
    }


def rank_feed(posts: list[Post], user_pref: UserPreference) -> list[Post]:
    """Rank a collection of posts for a user based on their topic preferences.

    Process:
    1. Computes the personalized score for each post.
    2. Filters out posts with a score < 0.
    3. Sorts remaining posts by Final Score descending (with created_at as tiebreaker).
    """
    scored_posts: list[tuple[Post, float]] = []

    for post in posts:
        score = calculate_post_score(post, user_pref)
        if score >= 0.0:
            scored_posts.append((post, score))

    # Sort primarily by score descending, secondarily by created_at descending
    scored_posts.sort(key=lambda item: (item[1], item[0].created_at), reverse=True)

    return [post for post, _ in scored_posts]


def rank_feed_with_scores(
    posts: list[Post], user_pref: UserPreference
) -> list[tuple[Post, float, dict]]:
    """Rank posts and return detailed tuples of (Post, Final Score, Score Breakdown).

    Excludes posts with score < 0.0, sorted descending by final score.
    """
    ranked_items: list[tuple[Post, float, dict]] = []

    for post in posts:
        breakdown = get_post_score_breakdown(post, user_pref)
        score = breakdown["final_score"]
        if score >= 0.0:
            ranked_items.append((post, score, breakdown))

    ranked_items.sort(key=lambda item: (item[1], item[0].created_at), reverse=True)
    return ranked_items
