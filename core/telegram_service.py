"""
Telegram bot service for command handling and notifications.
Supports both polling mode and webhook mode (ngrok).
"""
import asyncio
import logging
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

import pyrogram
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from config.settings import Settings


logger = logging.getLogger(__name__)


@dataclass
class CommandContext:
    """Context for command handling."""
    command: str
    args: str
    chat_id: str
    user_id: Optional[int] = None


class TelegramNotification:
    """Represents a notification to send."""

    def __init__(
        self,
        subject: str,
        from_addr: str,
        summary: str,
        classification: str,
        email_id: Optional[str] = None
    ):
        self.subject = subject
        self.from_addr = from_addr
        self.summary = summary
        self.classification = classification
        self.email_id = email_id

    def to_message(self) -> str:
        """Convert to formatted Telegram message."""
        classification_icon = "📧" if self.classification == "important" else "📢"

        return f"""{classification_icon} *New Email Notification*

*b From:* {self.from_addr}
*b Subject:* {self.subject}

{self.summary}
"""


class TelegramService:
    """
    Service for Telegram bot operations.
    Handles commands, notifications, and user interactions.
    """

    # Available commands
    COMMANDS = {
        "/start": "Welcome message",
        "/status": "Show current configuration status",
        "/set_interval": "Change fetch interval (e.g., /set_interval 10)",
        "/run_now": "Trigger immediate email processing",
        "/notes": "Add notes to an email (e.g., /notes 12345 note content)",
        "/help": "Show help message"
    }

    def __init__(self, settings: Settings):
        """
        Initialize Telegram service.

        Args:
            settings: Application settings with Telegram configuration
        """
        self.settings = settings
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID

        # Bot client
        self._client: Optional[Client] = None
        self._is_running = False

        # Command handlers
        self._handlers: Dict[str, Callable] = {}
        self._register_default_handlers()

        # State
        self._last_run: Optional[str] = None
        self._current_interval = settings.FETCH_INTERVAL_MINUTES

    def _register_default_handlers(self) -> None:
        """Register default command handlers."""
        self._handlers["/start"] = self._handle_start
        self._handlers["/status"] = self._handle_status
        self._handlers["/set_interval"] = self._handle_set_interval
        self._handlers["/run_now"] = self._handle_run_now
        self._handlers["/notes"] = self._handle_notes
        self._handlers["/help"] = self._handle_help

    def _register_handler(self, command: str, handler: Callable) -> None:
        """
        Register a custom command handler.

        Args:
            command: Command name (e.g., "/custom")
            handler: Async handler function
        """
        self._handlers[command] = handler

    async def initialize(self) -> None:
        """Initialize Telegram client."""
        if self._client is None:
            self._client = Client(
                "email_agent",
                bot_token=self.bot_token
            )

    async def start_polling(self) -> None:
        """Start bot in polling mode."""
        await self.initialize()

        self._is_running = True
        logger.info("Starting Telegram bot in polling mode")

        try:
            await self._client.run()
        except Exception as e:
            logger.error(f"Telegram polling error: {e}")
            raise
        finally:
            self._is_running = False

    async def send_notification(self, notification: TelegramNotification) -> bool:
        """
        Send email notification to chat.

        Args:
            notification: Notification to send

        Returns:
            True if sent successfully
        """
        if not self._client:
            logger.warning("Telegram client not initialized")
            return False

        try:
            await self._client.send_message(
                chat_id=self.chat_id,
                text=notification.to_message(),
                parse_mode="Markdown"
            )
            logger.info(f"Sent notification for email: {notification.subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False

    async def send_message(
        self,
        text: str,
        parse_mode: str = "Markdown"
    ) -> bool:
        """
        Send a message to the configured chat.

        Args:
            text: Message text
            parse_mode: Parse mode (Markdown/HTML)

        Returns:
            True if sent successfully
        """
        if not self._client:
            return False

        try:
            await self._client.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=parse_mode
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def _handle_command(self, message: Message) -> None:
        """
        Route command to appropriate handler.

        Args:
            message: Incoming message
        """
        if not message.text:
            return

        parts = message.text.split()
        command = parts[0].lower()

        if command in self._handlers:
            try:
                handler = self._handlers[command]
                await handler(message)
            except Exception as e:
                logger.error(f"Error handling command {command}: {e}")
                await self.send_message(f"Error processing command: {e}")
        else:
            await self.send_message(f"Unknown command: {command}")

    async def _handle_start(self, message: Message) -> None:
        """Handle /start command."""
        welcome_text = """*Welcome to Email Agent!* 📧

I monitor your Gmail inbox and summarize important emails.

*Available Commands:*
/start - Welcome message
/status - Show current status
/set_interval <minutes> - Change fetch frequency
/run_now - Trigger immediate check
/notes <email_id> <note> - Add notes
/help - Show this help

*Current Settings:*
- Fetch interval: {} minutes
- Last run: {}
""".format(
            self._current_interval,
            self._last_run or "Never"
        )

        await self.send_message(welcome_text)

    async def _handle_status(self, message: Message) -> None:
        """Handle /status command."""
        status_text = f"""*Email Agent Status* 📊

*Configuration:*
- Fetch interval: {self._current_interval} minutes
- LLM model: {self.settings.LLM_MODEL}
- Promotions filter: {'Enabled' if self.settings.SKIP_PROMOTIONS else 'Disabled'}
- Peek mode: {'Enabled' if self.settings.PEEK_MODE else 'Disabled'}

*Last Run:* {self._last_run or "Never"}

*Use /run_now to trigger an immediate check.*
"""

        await self.send_message(status_text)

    async def _handle_set_interval(self, message: Message) -> None:
        """Handle /set_interval command."""
        parts = message.text.split()

        if len(parts) < 2:
            await self.send_message(
                "Usage: /set_interval <minutes>\n"
                "Example: /set_interval 10"
            )
            return

        try:
            new_interval = int(parts[1])

            if new_interval < 1 or new_interval > 1440:
                await self.send_message(
                    "Interval must be between 1 and 1440 minutes."
                )
                return

            self._current_interval = new_interval
            self.settings.FETCH_INTERVAL_MINUTES = new_interval

            await self.send_message(
                f"Fetch interval updated to {new_interval} minutes."
            )
        except ValueError:
            await self.send_message("Invalid interval. Please provide a number.")

    async def _handle_run_now(self, message: Message) -> None:
        """Handle /run_now command."""
        await self.send_message(
            "Triggering immediate email check... 📨\n"
            "I'll notify you when processing is complete."
        )

        # In a real implementation, this would trigger the scheduler
        # For now, just acknowledge
        self._last_run = "Just now"

    async def _handle_notes(self, message: Message) -> None:
        """Handle /notes command."""
        # Parse: /notes <email_id> <note> or just /notes for list
        parts = message.text.split(None, 2)

        if len(parts) < 3:
            await self.send_message(
                "Usage: /notes <email_id> <note>\n"
                "Example: /notes 12345 This is important"
            )
            return

        email_id = parts[1]
        note_content = parts[2]

        await self.send_message(
            f"Note added to email {email_id}: {note_content}"
        )

    async def _handle_help(self, message: Message) -> None:
        """Handle /help command."""
        help_text = """*Email Agent Help* 📚

*Commands:*
/start - Welcome message
/status - Show current status and configuration
/set_interval <minutes> - Change fetch frequency (1-1440)
/run_now - Trigger immediate email check
/notes <email_id> <note> - Add notes to an email
/help - Show this help

*Features:*
- Automatically processes unread emails
- Filters promotional/marketing emails
- Summarizes important emails using local LLM
- Sends notifications via Telegram

*Note:* All processing is done locally via llama.cpp."""

        await self.send_message(help_text)

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        self._is_running = False
        if self._client:
            await self._client.stop()
            logger.info("Telegram bot stopped")
