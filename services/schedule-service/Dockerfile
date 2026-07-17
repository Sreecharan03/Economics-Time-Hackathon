# Build context must be the repo root, not this directory -- this service's
# baseline CPM network lives in dataset/schedule/schedule.csv and needs to be
# reachable from the build context. See infra/docker-compose.yml:
#   build: {context: .., dockerfile: services/schedule-service/Dockerfile}
FROM python:3.12-slim

WORKDIR /app

COPY services/schedule-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/schedule-service/app ./app
COPY dataset/schedule/schedule.csv /data/schedule.csv

ENV PYTHONPATH=/app
ENV SCHEDULE_CSV_PATH=/data/schedule.csv

EXPOSE 8003

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
