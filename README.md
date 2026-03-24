# Email Agent

A professional email monitoring agent that uses a local LLM to classify and summarize important emails, filtering out promotional content, and sends notifications via Telegram.

## Features

- **Gmail Integration**: Connects via IMAP to fetch unread emails
- **Smart Classification**: Uses heuristics and local LLM to distinguish promotional vs important emails
- **Local LLM Processing**: Summarizes emails using Qwen3.5-35B via llama.cpp
- **Telegram Notifications**: Sends summaries with configurable polling or webhook support
- **Scheduled Processing**: Configurable fetch intervals (10/30/60 minutes)
- **Email Storage**: SQLite database tracks processed emails and stores user notes
- **Docker Support**: Containerized deployment with ngrok tunnel support

## Requirements

- Python 3.12+
- Gmail App Password (with 2FA enabled)
- Telegram Bot Token
- Local LLM server (llama.cpp) running on port 8131

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# .venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```env
GMAIL_EMAIL=your.gmail.address@gmail.com
GMAIL_PASSWORD=your-app-password
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
FETCH_INTERVAL_MINUTES=30
```

### 3. Run the Agent

```bash
python main.py
```

### 4. Telegram Commands

Once running, send these commands to your Telegram bot:

- `/start` - Welcome message
- `/status` - Show current configuration
- `/set_interval <minutes>` - Change fetch frequency
- `/run_now` - Trigger immediate email check
- `/notes <email_id> <note>` - Add notes to an email
- `/help` - Show help

## Docker Deployment

### Local Development

```bash
docker-compose build
docker-compose up
```

### With ngrok Webhook

For remote Telegram webhook support:

1. Get ngrok authtoken from [ngrok.com](https://ngrok.com)
2. Add to `.env`:
   ```env
   NGROK_AUTHTOKEN=your-ngrok-token
   ```
3. Run:
   ```bash
   docker-compose up
   ```

## Architecture

```
email-agent/
├── config/
│   └── settings.py        # Pydantic configuration
├── core/
│   ├── email_service.py   # Gmail IMAP operations
│   ├── llm_service.py     # Local LLM wrapper
│   ├── telegram_service.py # Telegram bot handler
│   └── storage.py         # SQLite database
├── processors/
│   ├── email_classifier.py # Marketing detection
│   └── summarizer.py       # Processing pipeline
├── scheduler/
│   └── job_manager.py      # APScheduler orchestration
├── utils/
│   └── logging_config.py   # Structured logging
├── tests/
│   └── ...                 # Unit tests
├── main.py                 # Entry point
├── requirements.txt
├── docker-compose.yml
└── .env
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=core --cov=processors

# Run specific test file
pytest tests/test_email_classifier.py -v
```

## Email Processing Pipeline

1. **Fetch**: EmailService retrieves unread emails from Gmail
2. **Classify**: EmailClassifier determines if promotional or important
3. **Filter**: Promotional emails are skipped (configurable)
4. **Summarize**: LLMService generates summary of important emails
5. **Store**: Processed emails saved to SQLite database
6. **Notify**: TelegramService sends notification with summary

## Configuration Options

| Setting | Description | Default |
|---------|-------------|---------|
| `FETCH_INTERVAL_MINUTES` | Time between email checks | 30 |
| `SKIP_PROMOTIONS` | Filter out marketing emails | true |
| `PEEK_MODE` | Don't mark emails as read | true |
| `LOG_LEVEL` | Logging verbosity | INFO |
| `LOG_FORMAT` | JSON or text output | json |

## Troubleshooting

### Gmail Connection Issues

- Ensure 2FA is enabled on your Google account
- Generate a new App Password in Google Account settings
- Check that IMAP is enabled in Gmail settings

### LLM Connection Issues

- Verify llama.cpp is running: `curl http://localhost:8131/v1/models`
- Check the model name matches your loaded model
- Increase `LLM_TIMEOUT_SECONDS` if processing is slow

### Telegram Issues

- Verify bot token is correct
- Get your chat ID by messaging @userinfobot on Telegram
- For webhook mode, ensure ngrok tunnel is active

## License

MIT
