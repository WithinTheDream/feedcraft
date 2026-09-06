"""Main entrypoint for FeedControl FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as api_router

app = FastAPI(
    title="FeedControl Recommendation Engine",
    description=(
        "An AI-driven social media recommendation engine prototype (Phase 1 & 2). "
        "Provides real-time personalized feed ranking based on explicit user topic weights."
    ),
    version="1.0.0",
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

# Mount API router
app.include_router(api_router, tags=["Recommendation Engine"])


@app.get("/", tags=["System"])
def root():
    """Service status and meta information."""
    return {
        "service": "FeedControl Recommendation Engine",
        "status": "online",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
