FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-chi-sim \
        tesseract-ocr-chi-tra \
        tesseract-ocr-ara \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts ./scripts
COPY src ./src
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
ENV PYTHONPATH=/app/src

EXPOSE 8000
CMD ["uvicorn", "observatory.api:app", "--host", "0.0.0.0", "--port", "8000"]
