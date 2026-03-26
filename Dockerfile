# Email Agent Dockerfile
# Optimized for M4 Pro Mac Mini with local LLM

FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies (required for tgcrypto and other packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies (use --only-binary for tgcrypto if available)
RUN pip install --no-cache-dir -r requirements.txt || pip install --no-cache-dir --only-binary=:all: -r requirements.txt

# Copy project files
COPY --chown=root:root . .

# Create data directories
RUN mkdir -p data emails logs

# Set permissions
RUN chown -R root:root /app

# Expose port for ngrok (if using webhook mode)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from config.settings import get_settings; print(get_settings())" || exit 1

# Default command
CMD ["python", "main.py"]
