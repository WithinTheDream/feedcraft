"""Standalone demonstration script for FeedControl recommendation engine.

Demonstrates:
1. Creating mock posts covering tech, politics, food, and python.
2. Creating a mock user with topic preferences: {"python": 0.9, "politics": -1.0}.
3. Executing `rank_feed` and outputting ordered feed with clear score breakdowns.
"""

from datetime import datetime, timezone
import os
import sys

# Ensure feedcraft root is in python path regardless of where script is invoked
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from app.models.post import Post
from app.models.user_preference import UserPreference
from app.services.scoring import (
    calculate_post_score,
    get_post_score_breakdown,
    rank_feed,
)


def create_mock_posts() -> list[Post]:
    """Generate a realistic set of mock posts spanning various topics."""
    return [
        Post(
            id="post-101",
            content="Mastering Python Concurrency & Asyncio in Modern Microservices",
            tags=["python", "tech"],
            base_score=0.75,
            created_at=datetime(2026, 9, 6, 10, 0, tzinfo=timezone.utc),
        ),
        Post(
            id="post-102",
            content="Heated Parliamentary Debate Over Global Trade Tariffs",
            tags=["politics", "news"],
            base_score=0.90,
            created_at=datetime(2026, 9, 6, 11, 30, tzinfo=timezone.utc),
        ),
        Post(
            id="post-103",
            content="Authentic Neapolitan Pizza: The Science of Fermentation & Crust",
            tags=["food", "lifestyle"],
            base_score=0.65,
            created_at=datetime(2026, 9, 6, 12, 15, tzinfo=timezone.utc),
        ),
        Post(
            id="post-104",
            content="Breakthrough in Quantum Computing Chip Architecture Unveiled",
            tags=["tech", "science"],
            base_score=0.70,
            created_at=datetime(2026, 9, 6, 13, 45, tzinfo=timezone.utc),
        ),
        Post(
            id="post-105",
            content="Government Debates Open Source Regulations for Python Software",
            tags=["python", "politics"],
            base_score=0.85,
            created_at=datetime(2026, 9, 6, 14, 0, tzinfo=timezone.utc),
        ),
        Post(
            id="post-106",
            content="Top 10 Sourdough Bread Recipes for Weekend Bakers",
            tags=["food"],
            base_score=0.55,
            created_at=datetime(2026, 9, 6, 14, 30, tzinfo=timezone.utc),
        ),
    ]


def run_demo() -> None:
    """Run interactive recommendation demonstration."""
    print("=" * 80)
    print("  FEEDCONTROL RECOMMENDATION ENGINE - PHASE 1 & 2 PROTOTYPE DEMO")
    print("=" * 80)

    # 1. Initialize Mock User Preferences
    user_pref = UserPreference(
        user_id="user_developer_01",
        topic_weights={
            "python": 0.9,      # Strong positive affinity (+90% boost)
            "politics": -1.0,   # Strict hard filter (excluded entirely)
        },
    )

    print("\n[1] MOCK USER PROFILE")
    print(f"  User ID: {user_pref.user_id}")
    print("  Explicit Topic Weights:")
    for topic, weight in user_pref.topic_weights.items():
        weight_desc = (
            "HARD FILTER (Blocked)"
            if weight <= -1.0
            else f"+{weight * 100:.0f}% Boost"
        )
        print(f"    - {topic:<12} : {weight:>5.1f} ({weight_desc})")

    # 2. Initialize Mock Posts
    all_posts = create_mock_posts()
    print(f"\n[2] CANDIDATE POST POOL ({len(all_posts)} posts loaded):")
    for post in all_posts:
        print(
            f"  - [{post.id}] (base: {post.base_score:.2f}) "
            f"Tags: {post.tags!s:<24} | {post.content[:45]}..."
        )

    # 3. Execute rank_feed
    print("\n[3] EXECUTING RANKING PIPELINE (`rank_feed`)...")
    ranked_posts = rank_feed(all_posts, user_pref)

    # 4. Display Ranked Feed with Score Breakdowns
    print("\n" + "=" * 80)
    print(f"  FINAL PERSONALIZED FEED ({len(ranked_posts)} posts displayed)")
    print("=" * 80)

    ranked_ids = {p.id for p in ranked_posts}

    for rank, post in enumerate(ranked_posts, start=1):
        breakdown = get_post_score_breakdown(post, user_pref)
        base = breakdown["base_score"]
        multiplier = breakdown["multiplier"]
        final_score = breakdown["final_score"]
        weights = breakdown["matched_weights"]

        matched_str = (
            ", ".join(f"'{k}': {v:+.1f}" for k, v in weights.items())
            if weights
            else "None (Neutral 1.0x)"
        )

        print(f"\n  Rank #{rank} | Post ID: {post.id} | Final Score: {final_score:.4f}")
        print(f"  Content    : {post.content}")
        print(f"  Tags       : {post.tags}")
        print(
            f"  Formula    : Base ({base:.2f}) * Multiplier ({multiplier:.2f}) "
            f"[1 + Sum({matched_str})] = {final_score:.4f}"
        )

    # 5. Display Filtered / Excluded Posts
    filtered_posts = [p for p in all_posts if p.id not in ranked_ids]
    print("\n" + "-" * 80)
    print(f"  EXCLUDED / FILTERED POSTS ({len(filtered_posts)} posts filtered)")
    print("-" * 80)

    for post in filtered_posts:
        score = calculate_post_score(post, user_pref)
        breakdown = get_post_score_breakdown(post, user_pref)
        print(f"\n  [EXCLUDED] Post ID: {post.id} (Raw Score: {score})")
        print(f"  Content   : {post.content}")
        print(f"  Tags      : {post.tags}")
        print(f"  Filter Reason : {breakdown['reason']}")

    print("\n" + "=" * 80)
    print("  DEMO COMPLETED SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    run_demo()
