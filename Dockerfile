FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATA_DIR=/app/data

RUN groupadd -r scraper && useradd -r -g scraper scraper

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY tg_chat_scrape.py .

RUN mkdir -p /app/data

CMD ["python", "/app/tg_chat_scrape.py"]