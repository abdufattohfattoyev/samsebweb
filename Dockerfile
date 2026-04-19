FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

RUN chmod +x /app/entrypoint.sh
RUN mkdir -p /app/media /app/staticfiles /app/logs

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
