# One image: the React console is built, then served by the same FastAPI process
# that serves the API. No nginx, no CORS configuration, no second container.

# --- stage 1: build the console -----------------------------------------
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci --include=dev
COPY frontend/ ./
RUN npm run build

# --- stage 2: the API, with the built console inside it ------------------
FROM python:3.12-slim
WORKDIR /app

# psycopg needs libpq at runtime; curl is used by the container healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt "psycopg[binary]"

COPY backend/ ./backend/
COPY --from=web /web/dist ./frontend/dist

# Run as a non-root user - nothing here needs privileges. /app/data must exist
# in the image so the named volume inherits its ownership instead of root's.
RUN mkdir -p /app/data \
    && useradd --create-home --uid 10001 sentinel \
    && chown -R sentinel /app
USER sentinel

ENV PYTHONUNBUFFERED=1 MODEL_PATH=/app/data/model.joblib EMBEDDER_PATH=/app/data/embedder.joblib
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=90s --retries=5 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
