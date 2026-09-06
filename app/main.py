"""Main entrypoint for FeedControl / FeedCraft FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agent_routes import router as agent_router
from app.api.routes import router as api_router

app = FastAPI(
    title="FeedCraft Recommendation Engine",
    description=(
        "An AI-driven social media recommendation engine prototype (Phases 1, 2 & 3). "
        "Provides real-time personalized feed ranking and natural language preference control via LLM Agent."
    ),
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for local frontends / testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(api_router, tags=["Recommendation Engine"])
app.include_router(agent_router, tags=["LLM Agent"])


@app.get("/", tags=["System"])
def root():
    """Service status and meta information."""
    return {
        "service": "FeedCraft Recommendation Engine",
        "status": "online",
        "version": "1.1.0",
        "phases_active": [1, 2, 3],
        "endpoints": {
            "docs": "/docs",
            "feed": "/feed/{user_id}",
            "agent_chat": "/agent/chat",
        },
    }


@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
