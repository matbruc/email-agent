"""
Scheduler for automated email processing.
Uses APScheduler for cron-like job execution with file locking.
"""
import logging
import asyncio
from pathlib import Path
from typing import Optional, Callable, List
from datetime import datetime
from filelock import FileLock

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from config.settings import Settings
from core.email_service import EmailService
from core.llm_service import LLMService
from core.telegram_service import TelegramService, TelegramNotification
from core.storage import Storage
from processors.summarizer import Summarizer


logger = logging.getLogger(__name__)


class JobManager:
    """
    Manages scheduled email processing jobs.
    Prevents concurrent execution via file locking.
    """

    def __init__(
        self,
        email_service: EmailService,
        llm_service: LLMService,
        telegram_service: TelegramService,
        storage: Storage,
        settings: Settings
    ):
        """
        Initialize job manager.

        Args:
            email_service: Email fetching service
            llm_service: LLM service
            telegram_service: Telegram notification service
            storage: Database storage
            settings: Application settings
        """
        self.settings = settings
        self.email_service = email_service
        self.llm_service = llm_service
        self.telegram_service = telegram_service
        self.storage = storage

        # Create summarizer
        self.summarizer = Summarizer(
            settings,
            email_service,
            llm_service,
            storage
        )

        # Scheduler
        self.scheduler = AsyncIOScheduler()

        # File lock for preventing concurrent execution
        self.lock_path = settings.DATA_DIR / ".email_agent.lock"
        self.lock = FileLock(str(self.lock_path))

        # Job tracking
        self._last_run: Optional[datetime] = None
        self._is_processing = False
        self._jobs: List[str] = []

    async def initialize(self) -> None:
        """Initialize scheduler and storage."""
        await self.storage.initialize()
        await self.telegram_service.initialize()

    async def start(self) -> None:
        """Start the scheduler."""
        await self.initialize()

        # Add periodic email processing job
        self._add_email_processing_job()

        # Start scheduler
        self.scheduler.start()
        self._is_processing = True

        logger.info(
            f"Job manager started. Email processing every "
            f"{self.settings.FETCH_INTERVAL_MINUTES} minutes"
        )

    def _add_email_processing_job(self) -> None:
        """Add the periodic email processing job."""
        self.scheduler.add_job(
            self._process_emails_job,
            trigger=IntervalTrigger(
                minutes=self.settings.FETCH_INTERVAL_MINUTES,
                start_date=datetime.now()
            ),
            id="email_processing",
            replace_existing=True,
            name="Periodic Email Processing",
            max_instances=1,
            misfire_grace_time=300  # 5 minutes grace period
        )
        self._jobs.append("email_processing")

    async def _process_emails_job(self) -> None:
        """
        Process emails job handler.
        Uses file lock to prevent concurrent execution.
        """
        if self._is_processing:
            logger.warning("Email processing already in progress, skipping")
            return

        lock_acquired = False
        try:
            # Try to acquire exclusive lock
            lock_acquired = self.lock.acquire(timeout=1)

            if not lock_acquired:
                logger.info("Another instance is running, skipping this cycle")
                return

            self._is_processing = True
            logger.info("Starting email processing cycle")

            # Process emails
            results = await self.summarizer.process_emails()

            # Send notifications for important emails
            notifications_sent = 0
            for result in results:
                if not result.is_skipped and result.classification.value == "important":
                    notification = TelegramNotification(
                        subject=result.email.subject,
                        from_addr=result.email.from_addr,
                        summary=result.summary,
                        classification=result.classification.value,
                        email_id=result.email.message_id
                    )

                    if await self.telegram_service.send_notification(notification):
                        notifications_sent += 1

            self._last_run = datetime.now()
            self.telegram_service._last_run = self._last_run.strftime("%Y-%m-%d %H:%M:%S")

            logger.info(
                f"Processing complete. "
                f"{len(results)} emails processed, "
                f"{notifications_sent} notifications sent"
            )

        except Exception as e:
            logger.error(f"Email processing failed: {e}", exc_info=True)
        finally:
            if lock_acquired:
                self.lock.release()
            self._is_processing = False

    async def run_now(self) -> bool:
        """
        Trigger immediate email processing.
        Waits for any current processing to complete before running.

        Returns:
            True if processing started
        """
        try:
            # Wait for lock with a reasonable timeout (30 seconds)
            # This allows current processing to complete, then runs immediately
            lock_acquired = self.lock.acquire(timeout=30)

            if not lock_acquired:
                logger.warning("Timeout waiting for email processing lock")
                return False

            logger.info("Triggered immediate email processing via /run_now")

            self._is_processing = True

            # Process emails
            results = await self.summarizer.process_emails()

            # Send notifications
            notifications_sent = 0
            for result in results:
                if not result.is_skipped and result.classification.value == "important":
                    notification = TelegramNotification(
                        subject=result.email.subject,
                        from_addr=result.email.from_addr,
                        summary=result.summary,
                        classification=result.classification.value,
                        email_id=result.email.message_id
                    )

                    if await self.telegram_service.send_notification(notification):
                        notifications_sent += 1

            self._last_run = datetime.now()
            self.telegram_service._last_run = self._last_run.strftime("%Y-%m-%d %H:%M:%S")

            logger.info(
                f"Immediate processing complete. "
                f"{len(results)} emails, {notifications_sent} notifications"
            )

            return True

        except Exception as e:
            logger.error(f"Immediate processing failed: {e}", exc_info=True)
            return False
        finally:
            if "lock_acquired" in locals() and lock_acquired:
                self.lock.release()
            self._is_processing = False

    def add_job(
        self,
        func: Callable,
        trigger: IntervalTrigger | DateTrigger,
        name: str,
        **kwargs
    ) -> None:
        """
        Add a custom scheduled job.

        Args:
            func: Async function to call
            trigger: APScheduler trigger
            name: Job name for tracking
            **kwargs: Additional job parameters
        """
        job_id = f"custom_{name}"
        self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            name=name,
            **kwargs
        )
        self._jobs.append(job_id)

    def remove_job(self, job_id: str) -> bool:
        """
        Remove a scheduled job.

        Args:
            job_id: Job ID to remove

        Returns:
            True if job was removed
        """
        try:
            self.scheduler.remove_job(job_id)
            if job_id in self._jobs:
                self._jobs.remove(job_id)
            return True
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}")
            return False

    def get_status(self) -> dict:
        """
        Get scheduler status.

        Returns:
            Status dictionary
        """
        return {
            "is_running": self._is_processing,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "interval_minutes": self.settings.FETCH_INTERVAL_MINUTES,
            "scheduled_jobs": self._jobs.copy(),
            "lock_held": self.lock.is_locked
        }

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._is_processing = False
        self.scheduler.shutdown(wait=False)
        logger.info("Job manager stopped")
