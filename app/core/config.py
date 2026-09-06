"""Application configuration and environment settings using pydantic-settings."""

import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration class supporting .env loading and model swapping."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application settings
    app_name: str = "FeedCraft Recommendation Engine"
    app_env: str = Field(default="development", alias="APP_ENV")
    app_port: int = Field(default=8000, alias="PORT")

    # LLM Model Configuration
    # Supported: gemini/gemini-1.5-flash, gemini/gemini-1.5-pro, gpt-4o, gpt-4o-mini,
    # claude-3-5-sonnet-20240620, groq/llama-3.1-70b-versatile, etc.
    llm_model: str = Field(
        default="gemini/gemini-1.5-flash",
        alias="DEFAULT_LLM_MODEL",
        description="Model name recognized by LiteLLM.",
    )

    # API Keys for various LLM providers
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")

    # Simulation / offline mode
    mock_llm_mode: bool = Field(
        default=False,
        alias="MOCK_LLM_MODE",
        description="If True or no keys provided, uses intelligent rule-based parsing.",
    )

    def has_active_api_key(self) -> bool:
        """Check if any LLM provider API key is configured."""
        return any(
            [
                bool(self.gemini_api_key or os.getenv("GEMINI_API_KEY")),
                bool(self.openai_api_key or os.getenv("OPENAI_API_KEY")),
                bool(self.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")),
                bool(self.groq_api_key or os.getenv("GROQ_API_KEY")),
            ]
        )


settings = Settings()
