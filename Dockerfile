FROM python:3.12-slim

# system user
RUN groupadd -r scraper && useradd -r -g scraper scraper

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATA_DIR=/app/data

WORKDIR /app

# deps first for cache
COPY --chown=scraper:scraper requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# code
COPY --chown=scraper:scraper tg_chat_scrape.py .

# data dir
RUN mkdir -p /app/data

USER scraper

# optionally:
# VOLUME ["/app/data"]
# HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
#   CMD pgrep -f "tg_chat_scrape.py" >/dev/null || exit 1

CMD ["python", "/app/tg_chat_scrape.py"]