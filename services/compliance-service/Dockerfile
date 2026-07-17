# Build context must be the repo root, not this directory -- this service's
# spec-requirement seed data lives in dataset/submittals/equipment_master.json
# and needs to be reachable from the build context. See infra/docker-compose.yml:
#   build: {context: .., dockerfile: services/compliance-service/Dockerfile}
FROM python:3.12-slim

WORKDIR /app

COPY services/compliance-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/compliance-service/app ./app
COPY dataset/submittals/equipment_master.json /data/equipment_master.json

ENV PYTHONPATH=/app
ENV EQUIPMENT_MASTER_PATH=/data/equipment_master.json

EXPOSE 8002

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
