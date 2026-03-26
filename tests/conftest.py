"""
Pytest configuration and fixtures.
"""
import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure event loop exists before any imports that may trigger pyrogram
# This is needed for Python 3.14+ compatibility
asyncio.set_event_loop(asyncio.new_event_loop())

from config.settings import Settings
from core.email_service import Email, EmailService
from core.llm_service import LLMService, ClassificationResult
from core.storage import Storage
from processors.email_classifier import EmailClassifier
from processors.summarizer import Summarizer

# Lazy import TelegramService to avoid pyrogram import issues
@pytest.fixture
def telegram_service(settings: Settings):
    """Create Telegram service with mocked client."""
    from core.telegram_service import TelegramService

    service = TelegramService(settings)
    service._client = AsyncMock()
    service.send_message = AsyncMock()
    return service


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Create settings with test paths."""
    with patch.dict("os.environ", {
        "GMAIL_EMAIL": "test@example.com",
        "GMAIL_PASSWORD": "test-password",
        "TELEGRAM_BOT_TOKEN": "test-token",
        "TELEGRAM_CHAT_ID": "123456",
        "DATA_DIR": str(tmp_path / "data"),
        "EMAILS_DIR": str(tmp_path / "emails"),
        "DATABASE_PATH": str(tmp_path / "test.db"),
        "LOG_LEVEL": "DEBUG"
    }):
        settings = Settings()
        # Create directories
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        settings.EMAILS_DIR.mkdir(parents=True, exist_ok=True)
        return settings


@pytest.fixture
def sample_email() -> Email:
    """Create a sample email for testing."""
    from datetime import datetime
    return Email(
        message_id="12345",
        subject="Meeting Tomorrow",
        from_addr="colleague@example.com",
        timestamp=datetime.now(),
        body_plain="Hi, let's meet tomorrow at 10am to discuss the project.",
        body_html="<p>Hi, let's meet tomorrow at 10am to discuss the project.</p>",
        labels=[]
    )


@pytest.fixture
def marketing_email() -> Email:
    """Create a marketing email for testing."""
    from datetime import datetime
    return Email(
        message_id="67890",
        subject="50% Off - Limited Time Only!",
        from_addr="noreply@marketing.com",
        timestamp=datetime.now(),
        body_plain="""
            Don't miss out! Get 50% off all items today only.
            Use code SAVE50 at checkout. Unsubscribe here.
        """,
        body_html="""
            <html><body>
                <h1>50% OFF!</h1>
                <p>Don't miss out!</p>
                <a href="#">Shop Now</a>
                <a href="#">Unsubscribe</a>
            </body></html>
        """,
        labels=[]
    )


@pytest.fixture
def email_service(settings: Settings) -> EmailService:
    """Create email service with mocked IMAP client."""
    service = EmailService(settings)
    mock_client = MagicMock()
    mock_client.login = MagicMock(return_value=None)
    mock_client.logout = MagicMock(return_value=None)
    service._client = mock_client
    return service


@pytest.fixture
def llm_service(settings: Settings) -> LLMService:
    """Create LLM service."""
    return LLMService(settings)


@pytest.fixture
def storage(settings: Settings) -> Storage:
    """Create storage with test database."""
    return Storage(settings.DATABASE_PATH)


@pytest.fixture
def classifier(settings: Settings, llm_service: LLMService) -> EmailClassifier:
    """Create email classifier."""
    return EmailClassifier(settings, llm_service)


@pytest.fixture
def summarizer(
    settings: Settings,
    email_service: EmailService,
    llm_service: LLMService,
    storage: Storage
) -> Summarizer:
    """Create summarizer."""
    return Summarizer(settings, email_service, llm_service, storage)


