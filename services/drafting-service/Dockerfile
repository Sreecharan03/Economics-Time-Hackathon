# Build context must be the repo root. See infra/docker-compose.yml:
#   build: {context: .., dockerfile: services/drafting-service/Dockerfile}
FROM python:3.12-slim

WORKDIR /app

COPY services/drafting-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/drafting-service/app ./app

ENV PYTHONPATH=/app

EXPOSE 8005

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]
