FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py scraper.py exporter.py main.py ./

RUN mkdir -p /app/output /app/logs

ENV SCRAPER_MAX_CONCURRENT=5 \
    SCRAPER_REQUEST_DELAY=0.2

CMD ["python", "main.py", "--max-pages", "0"]
