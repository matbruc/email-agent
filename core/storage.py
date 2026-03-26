"""
SQLite database layer for tracking processed emails and storing user notes.
Uses aiosqlite for async database operations.
"""
import asyncio
import aiosqlite
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum


class EmailLabel(Enum):
    """Email classification labels."""
    PROMOTIONS = "promotions"
    IMPORTANT = "important"
    UNCLASSIFIED = "unclassified"


@dataclass
class ProcessedEmail:
    """Represents a processed email record."""
    message_id: str
    subject: str
    from_addr: str
    timestamp: datetime
    label: EmailLabel
    processed_at: datetime
    body_preview: Optional[str] = None
    summary: Optional[str] = None
    is_read: bool = False


class Storage:
    """
    SQLite storage layer for email agent.
    Handles persistence of processed emails, classifications, and user notes.
    """

    def __init__(self, database_path: Path):
        """
        Initialize storage with database path.

        Args:
            database_path: Path to SQLite database file
        """
        self.database_path = database_path
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Create database tables if they don't exist."""
        async with aiosqlite.connect(str(self.database_path)) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS processed_emails (
                    message_id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    from_addr TEXT NOT NULL,
                    email_timestamp INTEGER NOT NULL,
                    label TEXT NOT NULL,
                    processed_at INTEGER NOT NULL,
                    body_preview TEXT,
                    summary TEXT,
                    is_read BOOLEAN DEFAULT 0
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email_id TEXT NOT NULL,
                    note_content TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY (email_id) REFERENCES processed_emails(message_id)
                )
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_processed_emails_label
                ON processed_emails(label)
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_processed_emails_timestamp
                ON processed_emails(email_timestamp)
            """)

            await db.commit()

    async def mark_processed(
        self,
        message_id: str,
        subject: str,
        from_addr: str,
        email_timestamp: int,
        label: EmailLabel,
        body_preview: Optional[str] = None,
        summary: Optional[str] = None,
        is_read: bool = False
    ) -> None:
        """
        Mark an email as processed and store its metadata.

        Args:
            message_id: Unique Gmail message ID
            subject: Email subject
            from_addr: Sender email address
            email_timestamp: Unix timestamp of email
            label: Classification label (promotions/important)
            body_preview: First ~200 chars of email body
            summary: LLM-generated summary
            is_read: Whether email should be marked as read
        """
        async with self._lock:
            async with aiosqlite.connect(str(self.database_path)) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO processed_emails
                    (message_id, subject, from_addr, email_timestamp, label,
                     processed_at, body_preview, summary, is_read)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        message_id,
                        subject,
                        from_addr,
                        email_timestamp,
                        label.value,
                        int(datetime.now().timestamp()),
                        body_preview,
                        summary,
                        1 if is_read else 0
                    )
                )
                await db.commit()

    async def is_processed(self, message_id: str) -> bool:
        """
        Check if an email has already been processed.

        Args:
            message_id: Gmail message ID to check

        Returns:
            True if email was already processed
        """
        async with aiosqlite.connect(str(self.database_path)) as db:
            cursor = await db.execute(
                "SELECT 1 FROM processed_emails WHERE message_id = ?",
                (message_id,)
            )
            row = await cursor.fetchone()
            return row is not None

    async def get_unprocessed_count(self) -> int:
        """Get count of emails that haven't been classified yet."""
        async with aiosqlite.connect(str(self.database_path)) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM processed_emails WHERE label = 'unclassified'"
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_processed_emails(
        self,
        label: Optional[EmailLabel] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ProcessedEmail]:
        """
        Retrieve processed emails with optional filtering.

        Args:
            label: Filter by label (promotions/important/unclassified)
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of ProcessedEmail objects
        """
        async with aiosqlite.connect(str(self.database_path)) as db:
            query = """
                SELECT message_id, subject, from_addr, email_timestamp,
                       label, processed_at, body_preview, summary, is_read
                FROM processed_emails
            """
            params = []

            if label:
                query += " WHERE label = ?"
                params.append(label.value)

            query += " ORDER BY email_timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

            return [
                ProcessedEmail(
                    message_id=row[0],
                    subject=row[1],
                    from_addr=row[2],
                    timestamp=datetime.fromtimestamp(row[3]),
                    label=EmailLabel(row[4]),
                    processed_at=datetime.fromtimestamp(row[5]),
                    body_preview=row[6],
                    summary=row[7],
                    is_read=bool(row[8])
                )
                for row in rows
            ]

    async def add_note(
        self,
        email_id: str,
        note_content: str
    ) -> int:
        """
        Add a user note to a processed email.

        Args:
            email_id: Message ID of the email
            note_content: Note text from user

        Returns:
            ID of the created note
        """
        async with self._lock:
            async with aiosqlite.connect(str(self.database_path)) as db:
                cursor = await db.execute(
                    """
                    INSERT INTO user_notes (email_id, note_content, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (email_id, note_content, int(datetime.now().timestamp()))
                )
                await db.commit()
                return cursor.lastrowid

    async def get_notes(self, email_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all notes for a specific email.

        Args:
            email_id: Message ID of the email

        Returns:
            List of note dictionaries with id, content, and created_at
        """
        async with aiosqlite.connect(str(self.database_path)) as db:
            cursor = await db.execute(
                """
                SELECT id, note_content, created_at
                FROM user_notes
                WHERE email_id = ?
                ORDER BY created_at DESC
                """,
                (email_id,)
            )
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "content": row[1],
                    "created_at": datetime.fromtimestamp(row[2])
                }
                for row in rows
            ]

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get processing statistics.

        Returns:
            Dictionary with counts of processed emails by label
        """
        async with aiosqlite.connect(str(self.database_path)) as db:
            cursor = await db.execute("""
                SELECT label, COUNT(*)
                FROM processed_emails
                GROUP BY label
            """)
            rows = await cursor.fetchall()

            stats = {"total": 0, "by_label": {}}
            for label, count in rows:
                stats["by_label"][label] = count
                stats["total"] += count

            return stats

    async def clear_processed_emails(self) -> None:
        """Clear all processed email records (useful for testing)."""
        async with self._lock:
            async with aiosqlite.connect(str(self.database_path)) as db:
                await db.execute("DELETE FROM processed_emails")
                await db.execute("DELETE FROM user_notes")
                await db.commit()
