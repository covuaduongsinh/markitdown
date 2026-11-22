FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    EXIFTOOL_PATH=/usr/bin/exiftool \
    FFMPEG_PATH=/usr/bin/ffmpeg \
    ORT_DISABLE_TELEMETRY=1 \
    GRADIO_SERVER_NAME="0.0.0.0" \
    GRADIO_SERVER_PORT=7860 \
    PATH="/root/.local/bin:$PATH" \
    DOCKER=1 \
    MID_DATA_DIR=/data \
    MID_KEEP_DAYS=60

# Install runtime & build dependencies + Node.js (for Claude Code) + Google Antigravity CLI (agy)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libimage-exiftool-perl \
    poppler-utils \
    git \
    curl \
    ca-certificates \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && claude --version \
    && curl -fsSL https://antigravity.google/cli/install.sh -o /tmp/agy-install.sh \
    && bash /tmp/agy-install.sh \
    && rm -f /tmp/agy-install.sh \
    && ln -sf /root/.local/bin/agy /usr/local/bin/agy \
    && agy --version \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy application files
COPY . /app

# Install python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    /app/packages/markitdown[all] \
    /app/packages/markitdown-ocr \
    -r /app/requirements-gui.txt

# Dữ liệu công việc nền (jobs.py): gắn volume bền vào /data để không mất khi redeploy (docs/tinh-nang/10, G2.9)
VOLUME /data

EXPOSE 7860

CMD ["python", "markitdown_gui.py"]
