"""
Tests for Telegram service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from core.telegram_service import TelegramService, TelegramNotification


class TestTelegramNotification:
    """Test cases for TelegramNotification."""

    def test_to_message_format(self):
        """Test notification message formatting."""
        notification = TelegramNotification(
            subject="Test Subject",
            from_addr="test@example.com",
            summary="This is a test summary",
            classification="important"
        )

        message = notification.to_message()

        assert "Test Subject" in message
        assert "test@example.com" in message
        assert "This is a test summary" in message
        assert "important" in message

    def test_markdown_formatting(self):
        """Test that message uses Markdown formatting."""
        notification = TelegramNotification(
            subject="Bold Subject",
            from_addr="test@example.com",
            summary="Normal summary",
            classification="important"
        )

        message = notification.to_message()

        assert "*" in message  # Markdown bold markers


class TestTelegramService:
    """Test cases for TelegramService."""

    def test_command_handlers_registered(self, telegram_service):
        """Test that default command handlers are registered."""
        assert "/start" in telegram_service._handlers
        assert "/status" in telegram_service._handlers
        assert "/set_interval" in telegram_service._handlers
        assert "/run_now" in telegram_service._handlers

    def test_handle_start_message(self, telegram_service):
        """Test /start command handler."""
        message = MagicMock()
        message.text = "/start"

        # Should send welcome message
        asyncio.run(telegram_service._handle_start(message))

        telegram_service.send_message.assert_called_once()

    def test_handle_status_message(self, telegram_service):
        """Test /status command handler."""
        message = MagicMock()
        message.text = "/status"

        asyncio.run(telegram_service._handle_status(message))

        call_args = telegram_service.send_message.call_args[0][0]
        assert "Email Agent Status" in call_args
        assert str(telegram_service._current_interval) in call_args

    def test_handle_set_interval_valid(self, telegram_service):
        """Test /set_interval with valid value."""
        message = MagicMock()
        message.text = "/set_interval 15"

        asyncio.run(telegram_service._handle_set_interval(message))

        assert telegram_service._current_interval == 15

    def test_handle_set_interval_invalid(self, telegram_service):
        """Test /set_interval with invalid value."""
        message = MagicMock()
        message.text = "/set_interval abc"

        asyncio.run(telegram_service._handle_set_interval(message))

        # Should show usage error
        assert telegram_service.send_message.called

    def test_send_notification_success(self, telegram_service):
        """Test successful notification send."""
        notification = TelegramNotification(
            subject="Test",
            from_addr="test@example.com",
            summary="Summary",
            classification="important"
        )

        result = asyncio.run(telegram_service.send_notification(notification))

        assert result is True
        telegram_service._client.send_message.assert_called_once()

    def test_send_notification_no_client(self, telegram_service):
        """Test notification send without client."""
        telegram_service._client = None

        notification = TelegramNotification(
            subject="Test",
            from_addr="test@example.com",
            summary="Summary",
            classification="important"
        )

        result = asyncio.run(telegram_service.send_notification(notification))

        assert result is False
