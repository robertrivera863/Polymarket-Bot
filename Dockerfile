FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

# Default to safe paper mode. Override CMD or env vars for live trading.
CMD ["python", "-m", "polymarket_bot.cli", "paper"]
