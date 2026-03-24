"""
Tests for storage layer.
"""
import pytest
from datetime import datetime
from core.storage import Storage, EmailLabel, ProcessedEmail


class TestStorage:
    """Test cases for Storage."""

    @pytest.mark.asyncio
    async def test_initialize_database(self, storage):
        """Test database initialization."""
        await storage.initialize()

        # Should not raise any exceptions
        stats = await storage.get_statistics()
        assert "total" in stats

    @pytest.mark.asyncio
    async def test_mark_processed(self, storage):
        """Test marking email as processed."""
        await storage.initialize()

        await storage.mark_processed(
            message_id="123",
            subject="Test Email",
            from_addr="test@example.com",
            email_timestamp=int(datetime.now().timestamp()),
            label=EmailLabel.IMPORTANT,
            body_preview="Test preview",
            summary="Test summary"
        )

        # Check if email is marked as processed
        is_processed = await storage.is_processed("123")
        assert is_processed is True

    @pytest.mark.asyncio
    async def test_is_processed(self, storage):
        """Test checking if email was processed."""
        await storage.initialize()

        # New email should not be processed
        assert await storage.is_processed("new_email") is False

        # Mark and check
        await storage.mark_processed(
            message_id="new_email",
            subject="Test",
            from_addr="test@example.com",
            email_timestamp=int(datetime.now().timestamp()),
            label=EmailLabel.IMPORTANT
        )

        assert await storage.is_processed("new_email") is True

    @pytest.mark.asyncio
    async def test_get_processed_emails(self, storage):
        """Test retrieving processed emails."""
        await storage.initialize()

        # Add some emails
        for i in range(3):
            await storage.mark_processed(
                message_id=str(i),
                subject=f"Email {i}",
                from_addr=f"test{i}@example.com",
                email_timestamp=int(datetime.now().timestamp()),
                label=EmailLabel.IMPORTANT
            )

        emails = await storage.get_processed_emails()

        assert len(emails) == 3
        assert isinstance(emails[0], ProcessedEmail)
        assert emails[0].subject == "Email 2"  # Should be ordered by timestamp desc

    @pytest.mark.asyncio
    async def test_get_processed_emails_filtered(self, storage):
        """Test filtering processed emails by label."""
        await storage.initialize()

        # Add emails with different labels
        await storage.mark_processed(
            message_id="1",
            subject="Important",
            from_addr="test@example.com",
            email_timestamp=int(datetime.now().timestamp()),
            label=EmailLabel.IMPORTANT
        )
        await storage.mark_processed(
            message_id="2",
            subject="Promo",
            from_addr="promo@example.com",
            email_timestamp=int(datetime.now().timestamp()),
            label=EmailLabel.PROMOTIONS
        )

        important = await storage.get_processed_emails(label=EmailLabel.IMPORTANT)
        promotions = await storage.get_processed_emails(label=EmailLabel.PROMOTIONS)

        assert len(important) == 1
        assert len(promotions) == 1
        assert important[0].message_id == "1"
        assert promotions[0].message_id == "2"

    @pytest.mark.asyncio
    async def test_add_note(self, storage):
        """Test adding notes to emails."""
        await storage.initialize()

        # First mark email as processed
        await storage.mark_processed(
            message_id="123",
            subject="Test",
            from_addr="test@example.com",
            email_timestamp=int(datetime.now().timestamp()),
            label=EmailLabel.IMPORTANT
        )

        # Add note
        note_id = await storage.add_note("123", "This is important!")

        assert note_id > 0

        # Retrieve notes
        notes = await storage.get_notes("123")

        assert len(notes) == 1
        assert notes[0]["content"] == "This is important!"

    @pytest.mark.asyncio
    async def test_get_statistics(self, storage):
        """Test getting processing statistics."""
        await storage.initialize()

        # Add emails
        await storage.mark_processed(
            message_id="1",
            subject="Important",
            from_addr="test@example.com",
            email_timestamp=int(datetime.now().timestamp()),
            label=EmailLabel.IMPORTANT
        )
        await storage.mark_processed(
            message_id="2",
            subject="Promo",
            from_addr="promo@example.com",
            email_timestamp=int(datetime.now().timestamp()),
            label=EmailLabel.PROMOTIONS
        )

        stats = await storage.get_statistics()

        assert stats["total"] == 2
        assert stats["by_label"]["important"] == 1
        assert stats["by_label"]["promotions"] == 1

    @pytest.mark.asyncio
    async def test_clear_processed_emails(self, storage):
        """Test clearing processed emails."""
        await storage.initialize()

        # Add email
        await storage.mark_processed(
            message_id="1",
            subject="Test",
            from_addr="test@example.com",
            email_timestamp=int(datetime.now().timestamp()),
            label=EmailLabel.IMPORTANT
        )

        # Clear
        await storage.clear_processed_emails()

        # Should be empty
        stats = await storage.get_statistics()
        assert stats["total"] == 0
