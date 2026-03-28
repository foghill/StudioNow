FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default data directory (override with DATA_DIR env var to use a Railway volume)
RUN mkdir -p /app/scraper/data/raw /app/scraper/data/normalized

EXPOSE 8000

CMD ["sh", "-c", "python -m uvicorn scraper.server:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info"]
