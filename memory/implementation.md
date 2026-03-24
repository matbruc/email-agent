# Email Agent Implementation Notes

## Architecture Overview

The Email Agent has been refactored from a single-file script into a professional, modular application following these key principles:

### Core Architecture Patterns

1. **Configuration-First Design**
   - All settings loaded via Pydantic from `.env` file
   - Type-safe configuration with validation
   - Global settings singleton pattern

2. **Service-Based Architecture**
   - `EmailService`: Gmail IMAP operations
   - `LLMService`: Local LLM API wrapper
   - `TelegramService`: Bot commands and notifications
   - `Storage`: SQLite persistence layer

3. **Processor Pipeline**
   - `EmailClassifier`: Marketing detection (heuristics + LLM)
   - `Summarizer`: End-to-end email processing orchestration

4. **Scheduler Orchestration**
   - APScheduler for cron-like job execution
   - File locking to prevent concurrent runs

## File Structure

```
email-agent/
├── config/
│   └── settings.py           # Pydantic configuration
├── core/
│   ├── email_service.py      # Gmail IMAP operations
│   ├── llm_service.py        # LLM API wrapper
│   ├── telegram_service.py   # Telegram bot
│   └── storage.py            # SQLite database
├── processors/
│   ├── email_classifier.py   # Marketing detection
│   └── summarizer.py         # Processing pipeline
├── scheduler/
│   └── job_manager.py        # APScheduler
├── utils/
│   └── logging_config.py     # Structured logging
├── tests/
│   ├── conftest.py           # Test fixtures
│   ├── test_email_service.py
│   ├── test_llm_service.py
│   ├── test_telegram_service.py
│   ├── test_email_classifier.py
│   └── test_storage.py
├── data/                     # SQLite database
├── emails/                   # Saved email content
├── logs/                     # Application logs
├── main.py                   # Entry point
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## Key Implementation Details

### Email Service (`core/email_service.py`)

- Connects to Gmail IMAP with SSL
- Supports PEAK mode (read without marking as seen)
- Parses multipart emails (plain text + HTML)
- Saves email content to `.txt` files
- Handles Gmail labels (Promotions, etc.)

### LLM Service (`core/llm_service.py`)

- Wraps llama.cpp HTTP API
- Classification prompts: PROMOTIONS vs IMPORTANT
- Summarization prompts with focus areas
- Heuristic fallback when LLM unavailable
- Timeout handling with configurable limits

### Email Classifier (`processors/email_classifier.py`)

- **Heuristic Detection**:
  - Marketing keywords (sale, discount, promo)
  - Suspicious sender domains (noreply, newsletter)
  - HTML density threshold (>70% = suspicious)
  - Marketing HTML patterns (unsubscribe, shop now)

- **Classification Score**:
  - Range: -1 (promotional) to 1 (important)
  - Confidence: absolute value of score
  - Threshold: < -0.1 = promotional

### Storage (`core/storage.py`)

- **Table: processed_emails**
  - message_id (PK), subject, from_addr
  - email_timestamp, label, processed_at
  - body_preview, summary, is_read

- **Table: user_notes**
  - email_id (FK), note_content, created_at

- Async operations via aiosqlite
- File locking for thread safety

### Telegram Service (`core/telegram_service.py`)

- **Commands**:
  - `/start` - Welcome message
  - `/status` - Current configuration
  - `/set_interval <minutes>` - Change frequency
  - `/run_now` - Trigger immediate check
  - `/notes <email_id> <note>` - Add notes
  - `/help` - Help message

- Supports polling mode (default)
- Webhook mode via ngrok (future)

### Scheduler (`scheduler/job_manager.py`)

- APScheduler with IntervalTrigger
- FileLock prevents concurrent execution
- Graceful shutdown handling
- Job tracking and status reporting

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| GMAIL_EMAIL | Yes | - | Gmail address |
| GMAIL_PASSWORD | Yes | - | App password |
| TELEGRAM_BOT_TOKEN | Yes | - | Bot token |
| TELEGRAM_CHAT_ID | Yes | - | Target chat |
| FETCH_INTERVAL_MINUTES | No | 30 | Check frequency |
| SKIP_PROMOTIONS | No | true | Filter marketing |
| PEEK_MODE | No | true | Don't mark read |
| LLM_ENDPOINT | No | localhost:8131 | LLM server URL |
| LOG_LEVEL | No | INFO | DEBUG/INFO/WARN |

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=core --cov=processors

# Run specific test
pytest tests/test_email_classifier.py -v

# Validate setup
python validate_setup.py
```

## Docker Deployment

```bash
# Build
docker-compose build

# Run
docker-compose up

# View logs
docker-compose logs -f email-agent

# With ngrok webhook
# Add NGROK_AUTHTOKEN to .env
docker-compose up
```

## Migration from Original main.py

The original monolithic `main.py` has been replaced with:

1. **Entry Point** (`main.py`): Minimal orchestration, signal handling
2. **Settings** (`config/settings.py`): Centralized configuration
3. **Services**: Decoupled, testable components
4. **Processors**: Business logic separated from infrastructure

### Key Improvements

- **Modularity**: Each component can be tested independently
- **Type Safety**: Pydantic validation, type hints throughout
- **Error Handling**: Try/except with proper logging
- **Async Support**: aiosqlite, async Telegram bot
- **Logging**: Structured JSON logs with rotation
- **Concurrency**: File locking prevents duplicate runs
- **Extensibility**: Easy to add new features

## Future Enhancements

1. **Webhook Mode**: Replace polling with ngrok webhook
2. **Notion Integration**: Store summaries in Notion database
3. **Email Reply**: Support replying via Telegram
4. **Multiple Chats**: Support different configs per chat
5. **Analytics**: Track processing statistics over time
6. **Rules Engine**: User-defined email filtering rules
7. **Attachment Handling**: Process email attachments
