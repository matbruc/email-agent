"""
Gmail IMAP email service for fetching and managing emails.
Supports peek mode (read without marking as seen) and label-based filtering.
"""
import os
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from imapclient import IMAPClient
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

from config.settings import Settings


class EmailFetchError(Exception):
    """Exception raised when email fetching fails."""
    pass


class EmailParseError(Exception):
    """Exception raised when email parsing fails."""
    pass


class Email:
    """Represents a parsed email with metadata."""

    def __init__(
        self,
        message_id: str,
        subject: str,
        from_addr: str,
        timestamp: datetime,
        body_plain: Optional[str] = None,
        body_html: Optional[str] = None,
        labels: Optional[List[str]] = None
    ):
        self.message_id = message_id
        self.subject = subject
        self.from_addr = from_addr
        self.timestamp = timestamp
        self.body_plain = body_plain
        self.body_html = body_html
        self.labels = labels or []

    @property
    def body(self) -> Optional[str]:
        """Return plain text body, fallback to HTML."""
        return self.body_plain or self.body_html

    @property
    def is_marketing(self) -> bool:
        """Check if email appears to be marketing/promotional."""
        marketing_indicators = [
            "unsubscribe", "newsletter", "promotion", "sale",
            "discount", "offer", "coupon", "subscribe"
        ]
        body = (self.body_plain or self.body_html or "").lower()
        return any(indicator in body for indicator in marketing_indicators)

    def to_dict(self) -> Dict[str, Any]:
        """Convert email to dictionary for serialization."""
        return {
            "message_id": self.message_id,
            "subject": self.subject,
            "from_addr": self.from_addr,
            "timestamp": self.timestamp.isoformat(),
            "body_plain": self.body_plain,
            "body_html": self.body_html,
            "labels": self.labels
        }

    def __repr__(self) -> str:
        return f"Email(id={self.message_id}, subject={self.subject!r}, from={self.from_addr})"


class EmailService:
    """
    Service for Gmail IMAP operations.
    Handles connection, authentication, fetching, and parsing of emails.
    """

    def __init__(self, settings: Settings):
        """
        Initialize email service.

        Args:
            settings: Application settings with Gmail credentials
        """
        self.settings = settings
        self._client: Optional[IMAPClient] = None

    async def connect(self) -> None:
        """Establish IMAP connection to Gmail."""
        try:
            self._client = IMAPClient(
                "imap.gmail.com",
                ssl=True,
                validate_certs=True
            )
            self._client.login(
                self.settings.GMAIL_EMAIL,
                self.settings.GMAIL_PASSWORD
            )
        except Exception as e:
            raise EmailFetchError(f"Failed to connect to Gmail: {e}")

    async def disconnect(self) -> None:
        """Close IMAP connection."""
        if self._client:
            try:
                self._client.close()
                self._client.logout()
            except Exception:
                pass
            finally:
                self._client = None

    async def select_folder(
        self,
        folder: str = "INBOX",
        readonly: bool = True
    ) -> None:
        """
        Select a Gmail folder/label.

        Args:
            folder: Folder name (e.g., "INBOX", "[Gmail]/Label/Promotions")
            readonly: Whether to open in read-only mode
        """
        if not self._client:
            raise EmailFetchError("Not connected to Gmail")

        self._client.select_folder(folder, readonly=readonly)

    async def search_emails(
        self,
        criteria: List[str] = ["UNSEEN"],
        folder: str = "INBOX"
    ) -> List[str]:
        """
        Search for emails in a folder.

        Args:
            criteria: Search criteria (e.g., ["UNSEEN"], ["ALL"])
            folder: Folder to search in

        Returns:
            List of message UIDs matching criteria
        """
        if not self._client:
            raise EmailFetchError("Not connected to Gmail")

        try:
            await self.select_folder(folder)
            return self._client.search(criteria)
        except Exception as e:
            raise EmailFetchError(f"Search failed: {e}")

    async def fetch_email(
        self,
        message_uid: str,
        folder: str = "INBOX",
        peek: bool = True
    ) -> Optional[Email]:
        """
        Fetch and parse a single email.

        Args:
            message_uid: Gmail message UID
            folder: Folder where email is located
            peek: Whether to use PEAK (don't mark as read)

        Returns:
            Parsed Email object or None if fetch failed
        """
        if not self._client:
            raise EmailFetchError("Not connected to Gmail")

        try:
            await self.select_folder(folder, readonly=True)

            fetch_tags = ["BODY.PEEK[]" if peek else "BODY[]"]
            response = self._client.fetch([message_uid], fetch_tags)

            if message_uid not in response:
                return None

            data = response[message_uid]
            raw_bytes = data.get(b"BODY[]")

            if not raw_bytes:
                return None

            return self._parse_email_bytes(message_uid, raw_bytes)

        except Exception as e:
            raise EmailParseError(f"Failed to fetch email {message_uid}: {e}")

    async def fetch_emails(
        self,
        count: int = 10,
        folder: str = "INBOX",
        peek: bool = True
    ) -> List[Email]:
        """
        Fetch multiple emails from a folder.

        Args:
            count: Maximum number of emails to fetch
            folder: Folder to fetch from
            peek: Whether to peek (don't mark as read)

        Returns:
            List of parsed Email objects
        """
        uids = await self.search_emails(["UNSEEN"], folder)

        # Limit to requested count
        uids = uids[:count]

        emails = []
        for uid in uids:
            email = await self.fetch_email(uid, folder, peek)
            if email:
                emails.append(email)

        return emails

    async def mark_as_read(self, message_uid: str, folder: str = "INBOX") -> None:
        """
        Mark an email as read.

        Args:
            message_uid: Gmail message UID
            folder: Folder where email is located
        """
        if not self._client:
            raise EmailFetchError("Not connected to Gmail")

        try:
            await self.select_folder(folder, readonly=False)
            self._client.store(message_uid, '+FLAGS', '\\Seen')
        except Exception as e:
            raise EmailFetchError(f"Failed to mark email as read: {e}")

    async def move_to_label(
        self,
        message_uid: str,
        label: str,
        source_folder: str = "INBOX"
    ) -> None:
        """
        Move email to a Gmail label.

        Args:
            message_uid: Gmail message UID
            label: Target label name
            source_folder: Source folder
        """
        if not self._client:
            raise EmailFetchError("Not connected to Gmail")

        try:
            # Gmail labels are applied, not moved
            await self.select_folder(source_folder, readonly=False)
            self._client.add_labels(message_uid, [label])

            # Optionally remove from INBOX
            self._client.remove_labels(message_uid, [r"\Inbox"])
        except Exception as e:
            raise EmailFetchError(f"Failed to apply label: {e}")

    def _parse_email_bytes(
        self,
        message_id: str,
        raw_bytes: bytes
    ) -> Email:
        """
        Parse raw email bytes into Email object.

        Args:
            message_id: Message identifier
            raw_bytes: Raw email content

        Returns:
            Parsed Email object
        """
        try:
            msg = BytesParser(policy=default).parsebytes(raw_bytes)

            # Extract headers
            subject = msg.get("Subject", "No Subject")
            from_addr = msg.get("From", "Unknown")

            # Extract date
            date_str = msg.get("Date")
            try:
                timestamp = datetime.strptime(
                    date_str,
                    "%a, %d %b %Y %H:%M:%S %z"
                )
            except (TypeError, ValueError):
                timestamp = datetime.now()

            # Extract body
            body_plain = None
            body_html = None

            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition") or "")

                    # Skip attachments
                    if "attachment" in content_disposition:
                        continue

                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            text = payload.decode(charset, errors="ignore")

                            if content_type == "text/plain":
                                body_plain = text
                            elif content_type == "text/html":
                                body_html = text
                    except Exception:
                        continue
            else:
                content_type = msg.get_content_type()
                try:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        charset = msg.get_content_charset() or "utf-8"
                        text = payload.decode(charset, errors="ignore")

                        if content_type == "text/plain":
                            body_plain = text
                        elif content_type == "text/html":
                            body_html = text
                except Exception:
                    pass

            # Extract Gmail labels
            labels = []
            x_labels = msg.get("X-GM-THRID")
            if x_labels:
                labels.append("[Gmail]/All Mail")

            return Email(
                message_id=message_id,
                subject=subject,
                from_addr=from_addr,
                timestamp=timestamp,
                body_plain=body_plain,
                body_html=body_html,
                labels=labels
            )

        except Exception as e:
            raise EmailParseError(f"Failed to parse email: {e}")

    async def save_email_to_file(
        self,
        email: Email,
        directory: Optional[Path] = None
    ) -> Path:
        """
        Save email content to a text file.

        Args:
            email: Email to save
            directory: Directory to save in (defaults to EMAILS_DIR from settings)

        Returns:
            Path to saved file
        """
        if directory is None:
            directory = self.settings.EMAILS_DIR

        directory.mkdir(parents=True, exist_ok=True)

        # Sanitize filename
        safe_subject = "".join(
            c if c.isalnum() or c in " _-" else "_"
            for c in email.subject[:50]
        )
        filename = f"{email.message_id}_{safe_subject}.txt"
        filepath = directory / filename

        content = f"""Subject: {email.subject}
From: {email.from_addr}
Date: {email.timestamp.isoformat()}
Message-ID: {email.message_id}
Labels: {", ".join(email.labels)}

--- Body (Plain Text) ---
{email.body_plain or "No plain text body"}

--- Body (HTML) ---
{email.body_html or "No HTML body"}
"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return filepath

    async def get_folders(self) -> List[str]:
        """List all available Gmail folders/labels."""
        if not self._client:
            raise EmailFetchError("Not connected to Gmail")

        try:
            return self._client.list_folders()
        except Exception as e:
            raise EmailFetchError(f"Failed to list folders: {e}")
