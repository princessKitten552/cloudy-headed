# Multi-arch (linux/amd64, linux/arm64): only pure-Python code and wheels published for both.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Default non-root user. docker-compose overrides it with PUID/PGID to match the bind mounts.
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin savesync \
    && mkdir -p /data /db \
    && chown savesync:savesync /data /db

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

USER savesync
EXPOSE 8000

# Dependency-free healthcheck: urlopen raises on any non-2xx answer.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]

# Single worker on purpose: SQLite + one process is plenty for a single user.
# FORWARDED_ALLOW_IPS (read by uvicorn) must list the reverse proxy's IP.
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
