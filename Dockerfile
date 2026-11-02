# The whole app in one image: the React app is built first, then served by FastAPI with the API.
# Render builds this on every push to main (see render.yaml).

# --- 1. Build the React app ---
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- 2. The Python app ---
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv
WORKDIR /app/backend
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
# Dependencies first, in their own layer, so a code change doesn't reinstall them all.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/app ./app
COPY --from=frontend /app/frontend/dist ./static

# Run as an ordinary user, not root.
RUN useradd --create-home app && chown -R app /app
USER app

# Render tells the app which port to use in $PORT. --proxy-headers: Render's proxy passes the
# visitor's address in X-Forwarded-For, which the per-visitor split limit needs.
ENV PORT=8000
CMD ["sh", "-c", "exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'"]
