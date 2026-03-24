"""
Configuration management using Pydantic for validation and type safety.
All environment variables are loaded from .env file via python-dotenv.
"""
import os
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Gmail Configuration
    GMAIL_EMAIL: str = Field(
        description="Gmail address for IMAP connection"
    )
    GMAIL_PASSWORD: str = Field(
        description="Gmail app password for IMAP authentication"
    )
    PROMOTIONS_LABEL: str = Field(
        default="[Gmail]/Label/Promotions",
        description="Gmail label for promotional emails"
    )

    # Telegram Configuration
    TELEGRAM_BOT_TOKEN: str = Field(
        description="Telegram bot authentication token"
    )
    TELEGRAM_CHAT_ID: str = Field(
        description="Target chat ID for notifications"
    )
    TELEGRAM_WEBHOOK_URL: Optional[str] = Field(
        default=None,
        description="Telegram webhook URL (ngrok tunnel for remote access)"
    )

    # Local LLM Configuration
    LLM_ENDPOINT: str = Field(
        default="http://localhost:8131",
        description="Local LLM server endpoint (llama.cpp)"
    )
    LLM_MODEL: str = Field(
        default="unsloth/Qwen3.5-35B-A3B-GGUF:Q4_K_M",
        description="LLM model identifier for summarization"
    )
    LLM_TIMEOUT_SECONDS: int = Field(
        default=60,
        description="Timeout for LLM API calls in seconds"
    )

    # Scheduler Configuration
    FETCH_INTERVAL_MINUTES: int = Field(
        default=30,
        ge=1,
        le=1440,
        description="Interval between email fetch cycles in minutes"
    )

    # Storage Configuration
    DATA_DIR: Path = Field(
        default=Path("./data"),
        description="Directory for data storage (database, logs)"
    )
    EMAILS_DIR: Path = Field(
        default=Path("./emails"),
        description="Directory for storing email content as text files"
    )
    DATABASE_PATH: Path = Field(
        default=Path("./data/agent.db"),
        description="Path to SQLite database for processed email tracking"
    )

    # Logging Configuration
    LOG_LEVEL: str = Field(
        default="INFO",
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        description="Logging level"
    )
    LOG_FORMAT: str = Field(
        default="json",
        description="Log format: 'json' for structured logging or 'text' for human-readable"
    )

    # Feature Flags
    SKIP_PROMOTIONS: bool = Field(
        default=True,
        description="Whether to skip promotional/marketing emails"
    )
    PEEK_MODE: bool = Field(
        default=True,
        description="Whether to peek at emails without marking as read"
    )
    ENABLE_NOTION_INTEGRATION: bool = Field(
        default=False,
        description="Enable Notion database integration (future feature)"
    )

    # Notion Configuration (for future use)
    NOTION_TOKEN: Optional[str] = Field(
        default=None,
        description="Notion API token"
    )
    NOTION_DATABASE_ID: Optional[str] = Field(
        default=None,
        description="Notion database ID for storing notes"
    )

    @property
    def llm_api_url(self) -> str:
        """Get the full LLM API endpoint URL."""
        return f"{self.LLM_ENDPOINT}/v1/chat/completions"

    def __init__(self, **data):
        super().__init__(**data)
        # Ensure directories exist
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.EMAILS_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> "Settings":
        """
        Create settings from a specific env file.

        Args:
            env_file: Path to env file (defaults to .env in current directory)

        Returns:
            Settings instance
        """
        os.environ["_"] = env_file or ".env"
        return cls()


# Global settings instance
settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance, loading it if necessary."""
    global settings
    if settings is None:
        settings = Settings()
    return settings
