"""API routes for FeedControl recommendation engine."""

from typing import Any
from fastapi import APIRouter, HTTPException, Query, status

from app.models.post import Post, PostCreate
from app.models.user_preference import UserPreference, UserPreferenceUpdate
from app.services.scoring import (
    calculate_post_score,
    get_post_score_breakdown,
    rank_feed,
    rank_feed_with_scores,
)

router = APIRouter()


class InMemoryStorage:
    """Thread-safe in-memory data store for posts and user preferences."""

    def __init__(self) -> None:
        self.posts: dict[str, Post] = {}
        self.preferences: dict[str, UserPreference] = {}

    def clear(self) -> None:
        """Clear all stored data (useful for test resets)."""
        self.posts.clear()
        self.preferences.clear()


# Shared singleton storage instance
store = InMemoryStorage()


@router.post(
    "/posts",
    response_model=Post,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new post",
    description="Adds a new post to the in-memory repository.",
)
def create_post(payload: PostCreate | Post) -> Post:
    """Store a new post in the in-memory store."""
    if isinstance(payload, Post):
        post = payload
    else:
        # Construct Post from PostCreate
        init_kwargs: dict[str, Any] = {
            "content": payload.content,
            "tags": payload.tags,
            "base_score": payload.base_score,
        }
        if payload.id is not None:
            init_kwargs["id"] = payload.id
        post = Post(**init_kwargs)

    store.posts[post.id] = post
    return post


@router.get(
    "/posts",
    response_model=list[Post],
    summary="List all posts",
    description="Returns all stored posts in insertion order.",
)
def list_posts() -> list[Post]:
    """Retrieve all posts from the in-memory repository."""
    return list(store.posts.values())


@router.get(
    "/posts/{post_id}",
    response_model=Post,
    summary="Get post by ID",
)
def get_post(post_id: str) -> Post:
    """Retrieve a single post by its ID."""
    if post_id not in store.posts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with ID '{post_id}' not found.",
        )
    return store.posts[post_id]


@router.post(
    "/preferences/{user_id}",
    response_model=UserPreference,
    status_code=status.HTTP_200_OK,
    summary="Set or update user preferences",
    description="Updates or sets explicit topic weights for a given user.",
)
def update_preferences(user_id: str, payload: UserPreferenceUpdate) -> UserPreference:
    """Update topic weights for the designated user."""
    user_pref = UserPreference(user_id=user_id, topic_weights=payload.topic_weights)
    store.preferences[user_id] = user_pref
    return user_pref


@router.get(
    "/preferences/{user_id}",
    response_model=UserPreference,
    summary="Get user preferences",
    description="Fetches current topic weights for the user.",
)
def get_preferences(user_id: str) -> UserPreference:
    """Retrieve user topic preferences, defaulting to neutral weights if not found."""
    return store.preferences.get(
        user_id, UserPreference(user_id=user_id, topic_weights={})
    )


@router.get(
    "/feed/{user_id}",
    response_model=list[Post],
    summary="Get ranked feed for user",
    description=(
        "Retrieves personalized, ranked feed for the specified user. "
        "Excludes hard-filtered posts (weight <= -1.0) and posts with score < 0, "
        "and sorts remaining posts by final score descending."
    ),
)
def get_feed(user_id: str) -> list[Post]:
    """Calculate and return the personalized feed for a user."""
    # Retrieve user preference or use empty defaults
    user_pref = store.preferences.get(
        user_id, UserPreference(user_id=user_id, topic_weights={})
    )
    all_posts = list(store.posts.values())
    return rank_feed(all_posts, user_pref)


@router.get(
    "/feed/{user_id}/explained",
    summary="Get ranked feed with score breakdown",
    description="Returns ranked posts alongside scoring breakdown diagnostics.",
)
def get_explained_feed(user_id: str) -> dict[str, Any]:
    """Return ranked posts with detailed score calculations and filtered posts."""
    user_pref = store.preferences.get(
        user_id, UserPreference(user_id=user_id, topic_weights={})
    )
    all_posts = list(store.posts.values())

    ranked_items = rank_feed_with_scores(all_posts, user_pref)

    # Also compute filtered items for debugging
    filtered_items = []
    for post in all_posts:
        score = calculate_post_score(post, user_pref)
        if score < 0.0:
            filtered_items.append(get_post_score_breakdown(post, user_pref))

    return {
        "user_id": user_id,
        "preferences": user_pref.topic_weights,
        "feed": [
            {
                "post": post,
                "score": score,
                "breakdown": breakdown,
            }
            for post, score, breakdown in ranked_items
        ],
        "filtered_posts": filtered_items,
        "total_posts_considered": len(all_posts),
        "total_posts_in_feed": len(ranked_items),
    }
