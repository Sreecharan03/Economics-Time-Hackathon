# Build context must be the repo root -- this service's seed data lives in
# dataset/rfis/rfis.json. See infra/docker-compose.yml:
#   build: {context: .., dockerfile: services/retrieval-service/Dockerfile}
FROM python:3.12-slim

WORKDIR /app

COPY services/retrieval-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/retrieval-service/app ./app
COPY services/retrieval-service/seed_rfis.py .
COPY dataset/rfis/rfis.json /data/rfis.json

ENV PYTHONPATH=/app

EXPOSE 8004

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
