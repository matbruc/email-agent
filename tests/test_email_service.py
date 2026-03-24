"""
Tests for email service.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from core.email_service import EmailService, Email, EmailFetchError, EmailParseError


class TestEmail:
    """Test cases for Email data class."""

    def test_email_creation(self):
        """Test basic email creation."""
        from datetime import datetime
        email = Email(
            message_id="123",
            subject="Test Subject",
            from_addr="test@example.com",
            timestamp=datetime.now()
        )

        assert email.message_id == "123"
        assert email.subject == "Test Subject"
        assert email.from_addr == "test@example.com"
        assert email.is_marketing is False

    def test_email_body_fallback(self):
        """Test body fallback from HTML to plain."""
        from datetime import datetime
        email = Email(
            message_id="123",
            subject="Test",
            from_addr="test@example.com",
            timestamp=datetime.now(),
            body_plain=None,
            body_html="<p>HTML content</p>"
        )

        assert email.body == "<p>HTML content</p>"

    def test_email_is_marketing(self):
        """Test marketing detection."""
        from datetime import datetime
        email = Email(
            message_id="123",
            subject="Sale!",
            from_addr="deals@store.com",
            timestamp=datetime.now(),
            body_plain="Get 50% off today! Unsubscribe here."
        )

        assert email.is_marketing is True

    def test_email_to_dict(self):
        """Test email serialization."""
        from datetime import datetime
        email = Email(
            message_id="123",
            subject="Test",
            from_addr="test@example.com",
            timestamp=datetime.now(),
            body_plain="Body text",
            labels=["INBOX"]
        )

        data = email.to_dict()

        assert data["message_id"] == "123"
        assert data["subject"] == "Test"
        assert data["body_plain"] == "Body text"


class TestEmailService:
    """Test cases for EmailService."""

    def test_service_initialization(self, settings):
        """Test service initialization."""
        service = EmailService(settings)
        assert service.settings == settings
        assert service._client is None

    @pytest.mark.asyncio
    async def test_connect(self, email_service):
        """Test IMAP connection."""
        await email_service.connect()
        assert email_service._client is not None

    @pytest.mark.asyncio
    async def test_disconnect(self, email_service):
        """Test IMAP disconnection."""
        await email_service.connect()
        await email_service.disconnect()
        assert email_service._client is None

    def test_select_folder(self, email_service):
        """Test folder selection."""
        # Mock the select_folder method
        email_service._client.select_folder = MagicMock()

        asyncio.run(email_service.select_folder("INBOX"))

        email_service._client.select_folder.assert_called_once()

    def test_parse_email_bytes(self, settings):
        """Test email parsing."""
        service = EmailService(settings)

        # Create raw email bytes
        raw_email = b"""From: sender@example.com
To: recipient@example.com
Subject: Test Email
Date: Mon, 1 Jan 2024 12:00:00 +0000

This is the email body.
"""

        email = service._parse_email_bytes("123", raw_email)

        assert email.message_id == "123"
        assert email.subject == "Test Email"
        assert email.from_addr == "sender@example.com"
        assert "This is the email body" in email.body_plain

    def test_parse_email_multipart(self, settings):
        """Test parsing multipart email."""
        service = EmailService(settings)

        raw_email = b"""From: sender@example.com
Subject: Multipart Email
Date: Mon, 1 Jan 2024 12:00:00 +0000
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="boundary"

--boundary
Content-Type: text/plain

Plain text body
--boundary
Content-Type: text/html

<html><body>HTML body</body></html>
--boundary--
"""

        email = service._parse_email_bytes("123", raw_email)

        assert "Plain text body" in email.body_plain
        assert "HTML body" in email.body_html

    def test_save_email_to_file(self, settings, tmp_path):
        """Test saving email to file."""
        service = EmailService(settings)
        service.EMAILS_DIR = tmp_path / "emails"

        from datetime import datetime
        email = Email(
            message_id="123",
            subject="Test Subject",
            from_addr="test@example.com",
            timestamp=datetime.now(),
            body_plain="Body content"
        )

        filepath = asyncio.run(service.save_email_to_file(email))

        assert filepath.exists()
        content = filepath.read_text()
        assert "Test Subject" in content
        assert "Body content" in content

    def test_marketing_email_detection(self, settings):
        """Test marketing email detection patterns."""
        service = EmailService(settings)

        email = Email(
            message_id="123",
            subject="50% Off Sale!",
            from_addr="noreply@deals.com",
            timestamp=datetime.now(),
            body_plain="Limited time offer! Unsubscribe here."
        )

        assert email.is_marketing is True
