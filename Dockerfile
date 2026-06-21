# Stage 1: Build React frontend
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend + built frontend
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev

COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist/ ./frontend/dist/

EXPOSE 8000
CMD ["uv", "run", "python", "-m", "backend.main"]
