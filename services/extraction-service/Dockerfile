# Build context must be the repo root -- this service's attribute vocabulary
# comes from dataset/submittals/equipment_master.json. See infra/docker-compose.yml:
#   build: {context: .., dockerfile: services/extraction-service/Dockerfile}
FROM python:3.12-slim

WORKDIR /app

COPY services/extraction-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/extraction-service/app ./app
COPY dataset/submittals/equipment_master.json /data/equipment_master.json

ENV PYTHONPATH=/app
ENV EQUIPMENT_MASTER_PATH=/data/equipment_master.json

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
