FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY ride_connector ./ride_connector

RUN pip install --no-cache-dir .

CMD ["python", "-m", "ride_connector.jobs.daily_push"]

