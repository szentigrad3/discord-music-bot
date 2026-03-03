FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Ensure user-local scripts are on PATH
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create data directory
RUN mkdir -p data/sfx

# Signal that the bot is running inside Docker so it skips Lavalink auto-start
ENV BOT_IN_DOCKER=true

# Start bot
CMD ["python", "-m", "bot.main"]
