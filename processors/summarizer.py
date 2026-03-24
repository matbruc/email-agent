"""
Email summarizer for generating LLM-powered summaries.
Coordinates the classification and summarization pipeline.
"""
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path

from config.settings import Settings
from core.email_service import Email, EmailService
from core.llm_service import LLMService, ClassificationResult
from core.storage import Storage, EmailLabel, ProcessedEmail
from processors.email_classifier import EmailClassifier, ClassificationScore


logger = logging.getLogger(__name__)


class SummaryResult:
    """Result of email summarization."""

    def __init__(
        self,
        email: Email,
        summary: str,
        classification: ClassificationResult,
        is_skipped: bool = False,
        skip_reason: Optional[str] = None
    ):
        self.email = email
        self.summary = summary
        self.classification = classification
        self.is_skipped = is_skipped
        self.skip_reason = skip_reason

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "email_id": self.email.message_id,
            "subject": self.email.subject,
            "from": self.email.from_addr,
            "timestamp": self.email.timestamp.isoformat(),
            "summary": self.summary,
            "classification": self.classification.value,
            "is_skipped": self.is_skipped,
            "skip_reason": self.skip_reason
        }

    def __repr__(self) -> str:
        status = "skipped" if self.is_skipped else "summarized"
        return f"SummaryResult(email={self.email.subject}, status={status})"


class Summarizer:
    """
    Orchestrates email processing pipeline.
    Handles classification, summarization, and storage.
    """

    def __init__(
        self,
        settings: Settings,
        email_service: EmailService,
        llm_service: LLMService,
        storage: Storage
    ):
        """
        Initialize summarizer.

        Args:
            settings: Application settings
            email_service: Email fetching service
            llm_service: LLM service for processing
            storage: Database storage
        """
        self.settings = settings
        self.email_service = email_service
        self.llm_service = llm_service
        self.storage = storage

        # Classifier with LLM support
        self.classifier = EmailClassifier(settings, llm_service)

    async def process_emails(self) -> List[SummaryResult]:
        """
        Process all unread emails.

        Returns:
            List of SummaryResult objects
        """
        logger.info(f"Starting email processing cycle (interval: {self.settings.FETCH_INTERVAL_MINUTES}min)")

        try:
            # Connect to Gmail
            await self.email_service.connect()

            # Fetch unread emails from INBOX
            emails = await self.email_service.fetch_emails(
                count=10,
                folder="INBOX",
                peek=self.settings.PEEK_MODE
            )

            logger.info(f"Found {len(emails)} unread emails")

            results = []
            for email in emails:
                result = await self._process_single_email(email)
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Email processing failed: {e}")
            raise
        finally:
            await self.email_service.disconnect()

    async def _process_single_email(
        self,
        email: Email
    ) -> SummaryResult:
        """
        Process a single email through the pipeline.

        Args:
            email: Email to process

        Returns:
            SummaryResult
        """
        # Check if already processed
        if await self.storage.is_processed(email.message_id):
            logger.debug(f"Email {email.message_id} already processed, skipping")
            return SummaryResult(
                email=email,
                summary="",
                classification=ClassificationResult.UNCERTAIN,
                is_skipped=True,
                skip_reason="already processed"
            )

        try:
            # Step 1: Classify email
            classification, score = await self.classifier.classify(email)

            logger.info(
                f"Classified email from {email.from_addr} as "
                f"{classification.value} (confidence: {score.confidence:.2f})"
            )

            # Step 2: Handle promotional emails
            if classification == ClassificationResult.PROMOTIONS:
                if self.settings.SKIP_PROMOTIONS:
                    logger.info(f"Skipping promotional email: {email.subject}")

                    # Still mark as processed but don't summarize
                    await self._save_email(
                        email,
                        EmailLabel.PROMOTIONS,
                        is_read=not self.settings.PEEK_MODE
                    )

                    return SummaryResult(
                        email=email,
                        summary="",
                        classification=classification,
                        is_skipped=True,
                        skip_reason="promotional content filtered"
                    )

            # Step 3: Summarize important emails
            summary = await self.llm_service.summarize_email(email)

            logger.info(f"Generated summary for: {email.subject}")

            # Step 4: Save to storage
            await self._save_email(
                email,
                EmailLabel.IMPORTANT,
                summary=summary,
                is_read=not self.settings.PEEK_MODE
            )

            # Step 5: Save email content to file
            await self.email_service.save_email_to_file(email)

            return SummaryResult(
                email=email,
                summary=summary,
                classification=classification,
                is_skipped=False
            )

        except Exception as e:
            logger.error(f"Error processing email {email.message_id}: {e}")

            # Still mark as processed to avoid infinite retry
            await self._save_email(
                email,
                EmailLabel.UNCLASSIFIED,
                is_read=not self.settings.PEEK_MODE
            )

            return SummaryResult(
                email=email,
                summary=f"Error processing: {e}",
                classification=ClassificationResult.UNCERTAIN,
                is_skipped=True,
                skip_reason=str(e)
            )

    async def _save_email(
        self,
        email: Email,
        label: EmailLabel,
        summary: Optional[str] = None,
        is_read: bool = False
    ) -> None:
        """
        Save email to storage.

        Args:
            email: Email to save
            label: Classification label
            summary: Generated summary
            is_read: Whether to mark as read
        """
        preview = (email.body_plain or email.body_html or "")[:200]

        await self.storage.mark_processed(
            message_id=email.message_id,
            subject=email.subject,
            from_addr=email.from_addr,
            email_timestamp=int(email.timestamp.timestamp()),
            label=label,
            body_preview=preview,
            summary=summary,
            is_read=is_read
        )

    async def process_specific_email(
        self,
        message_uid: str,
        folder: str = "INBOX"
    ) -> Optional[SummaryResult]:
        """
        Process a specific email by UID.

        Args:
            message_uid: Gmail message UID
            folder: Folder containing email

        Returns:
            SummaryResult or None
        """
        await self.email_service.connect()

        try:
            email = await self.email_service.fetch_email(
                message_uid,
                folder=folder,
                peek=self.settings.PEEK_MODE
            )

            if not email:
                logger.warning(f"Could not fetch email {message_uid}")
                return None

            return await self._process_single_email(email)

        finally:
            await self.email_service.disconnect()
