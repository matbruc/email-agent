#!/usr/bin/env python3
"""
Email Agent - Main Entry Point

Monitors Gmail inbox, processes emails using local LLM,
summarizes important content, and sends notifications via Telegram.
"""
import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Settings, get_settings
from core.email_service import EmailService
from core.llm_service import LLMService
from core.telegram_service import TelegramService
from core.storage import Storage
from scheduler.job_manager import JobManager
from utils.logging_config import configure_logging, get_logger


logger = get_logger(__name__)


async def main() -> None:
    """Main entry point for Email Agent."""
    # Load settings
    settings = get_settings()

    # Configure logging
    configure_logging(
        level=settings.LOG_LEVEL,
        format_type=settings.LOG_FORMAT,
        log_dir=settings.DATA_DIR
    )

    logger.info(
        "Email Agent starting",
        config={
            "interval_minutes": settings.FETCH_INTERVAL_MINUTES,
            "skip_promotions": settings.SKIP_PROMOTIONS,
            "peek_mode": settings.PEEK_MODE
        }
    )

    # Initialize services
    storage = Storage(settings.DATABASE_PATH)
    email_service = EmailService(settings)
    llm_service = LLMService(settings)

    # Create job manager first (without telegram_service initially)
    job_manager = JobManager(
        email_service,
        llm_service,
        None,  # telegram_service will be set after initialization
        storage,
        settings
    )

    # Now create telegram service with job_manager reference
    telegram_service = TelegramService(settings, job_manager)

    # Set telegram_service on job_manager for notification sending
    job_manager.telegram_service = telegram_service

  
    # Setup signal handlers
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(shutdown(job_manager, telegram_service))

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        # Start scheduler in background
        scheduler_task = asyncio.create_task(job_manager.start())

        # Start Telegram bot in polling mode
        telegram_task = asyncio.create_task(telegram_service.start_polling())

        logger.info("Email Agent is running. Press Ctrl+C to stop.")

        # Wait for shutdown signal
        await asyncio.Event().wait()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await shutdown(job_manager, telegram_service)


async def shutdown(job_manager: JobManager, telegram_service: TelegramService) -> None:
    """Graceful shutdown."""
    logger.info("Shutting down...")

    # Stop Telegram service
    await telegram_service.stop()

    # Stop scheduler
    await job_manager.stop()

    logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nEmail Agent stopped.")
