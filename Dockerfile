# Build the React frontend
FROM node:24-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Python API that also serves the built frontend
FROM python:3.12-slim
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=web /web/dist /app/frontend/dist
ENV BO_DATA_DIR=/data
VOLUME /data
EXPOSE 8000
# First boot downloads data and trains (~1 min); later boots reuse /data.
CMD ["sh", "-c", "[ -f /data/bettorsoracle.db ] || python -m app.cli refresh; uvicorn app.main:app --host 0.0.0.0 --port 8000"]
