# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Email Agent is a professional email monitoring system that uses a local LLM (Qwen3.5-35B via llama.cpp) to classify and summarize important emails, filtering out promotional content, and sends notifications via Telegram.

## Development Setup

**Activate virtual environment:**
```bash
source .venv/bin/activate
```

**Run the agent:**
```bash
python main.py
```

**Run validation:**
```bash
python validate_setup.py
```

**Run tests:**
```bash
pytest
```

## Dependencies

The project uses `requirements.txt`:
- `requests` - HTTP client for Telegram and LLM API
- `python-dotenv` - Environment variable management
- `imapclient` - IMAP protocol for Gmail access
- `pyrogram` - Telegram bot framework
- `pydantic` + `pydantic-settings` - Configuration management
- `APScheduler` - Scheduled task execution
- `structlog` - Structured JSON logging
- `aiosqlite` - Async SQLite database
- `filelock` - Prevent concurrent execution
- `notion-client` - Notion API (future feature)

## Architecture

### Directory Structure
```
email-agent/
├── config/           # Pydantic settings
├── core/             # Services (email, llm, telegram, storage)
├── processors/       # Business logic (classifier, summarizer)
├── scheduler/        # APScheduler job management
├── utils/            # Logging configuration
├── tests/            # Unit tests
├── data/             # SQLite database
├── emails/           # Saved email content
├── logs/             # Application logs
├── main.py           # Entry point
├── Dockerfile
├── docker-compose.yml
├── .env
└── README.md
```

### Core Services

| Service | File | Purpose |
|---------|------|---------|
| EmailService | `core/email_service.py` | Gmail IMAP operations, email fetching/parsing |
| LLMService | `core/llm_service.py` | Local LLM API wrapper for classification/summarization |
| TelegramService | `core/telegram_service.py` | Bot commands, notifications, user interactions |
| Storage | `core/storage.py` | SQLite database for processed emails and notes |

### Processors

| Processor | File | Purpose |
|-----------|------|---------|
| EmailClassifier | `processors/email_classifier.py` | Marketing detection via heuristics + LLM |
| Summarizer | `processors/summarizer.py` | End-to-end email processing pipeline |

### Environment Variables (`.env`)

**Required:**
- `GMAIL_EMAIL` - Gmail address
- `GMAIL_PASSWORD` - Gmail app password (2FA required)
- `TELEGRAM_BOT_TOKEN` - Telegram bot token
- `TELEGRAM_CHAT_ID` - Target chat ID

**Optional:**
- `FETCH_INTERVAL_MINUTES` - Check frequency (default: 30)
- `SKIP_PROMOTIONS` - Filter marketing emails (default: true)
- `PEEK_MODE` - Don't mark emails as read (default: true)
- `LLM_ENDPOINT` - llama.cpp URL (default: http://localhost:8131)
- `LOG_LEVEL` - DEBUG/INFO/WARNING/ERROR (default: INFO)

## Email Processing Pipeline

1. **Fetch**: EmailService retrieves unread emails via IMAP
2. **Classify**: EmailClassifier determines promotional vs important
3. **Filter**: Promotional emails skipped (configurable)
4. **Summarize**: LLMService generates summary
5. **Store**: Saved to SQLite database
6. **Notify**: TelegramService sends notification

## Key Features

- **Promotional Filtering**: Heuristic + LLM-based detection
- **Peek Mode**: Read emails without marking as seen
- **Configurable Interval**: 1-1440 minutes via `/set_interval`
- **Telegram Commands**: `/start`, `/status`, `/run_now`, `/notes`, `/help`
- **File Locking**: Prevents concurrent execution
- **Structured Logging**: JSON logs with rotation
- **Docker Support**: Containerized with ngrok webhook option

## Development Patterns

When modifying email processing logic:

1. **Add new feature**: Create in appropriate service/processor module
2. **Update settings**: Add to `config/settings.py` if configurable
3. **Add tests**: Create tests in `tests/` directory
4. **Update README**: Document new features in `README.md`

### Common Modifications

**Change fetch interval:**
- Update `FETCH_INTERVAL_MINUTES` in `.env` or via `/set_interval` command

**Add email filtering rules:**
- Modify `processors/email_classifier.py` heuristic patterns

**Add new Telegram command:**
- Add handler in `core/telegram_service.py` `_register_default_handlers()`

**Change LLM model:**
- Update `LLM_MODEL` in `.env` or `config/settings.py`

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=core --cov=processors

# Run specific test file
pytest tests/test_email_classifier.py -v
```

## Docker Deployment

```bash
# Build and run
docker-compose build
docker-compose up

# View logs
docker-compose logs -f email-agent
```

For ngrok webhook support, add `NGROK_AUTHTOKEN` to `.env`.
