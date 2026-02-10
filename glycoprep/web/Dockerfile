# Build context should be the glycoprep/ root directory.
# docker compose (from web/) sets context: ..

# Stage 1: Build Svelte frontend
FROM node:20-alpine AS frontend
WORKDIR /build
COPY web/frontend/package.json web/frontend/package-lock.json* ./
RUN npm ci
COPY web/frontend/ .
RUN npm run build

# Stage 2: Python runtime
FROM python:3.12-slim AS runtime
WORKDIR /app

# Install glycoprep library
COPY pyproject.toml README.md /pkg/
COPY src /pkg/src
RUN pip install --no-cache-dir /pkg

# Install web dependencies
RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    python-multipart

# Copy backend code
COPY web/backend/ /app/backend/

# Copy built frontend
COPY --from=frontend /build/dist /app/frontend/dist

# Copy bundled glycan database
COPY data/db/human_colon.xlsx /app/data/db/human_colon.xlsx

# Create tmp directory for sessions
RUN mkdir -p /tmp/glycoprep

EXPOSE 8000

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000", "--root-path", "/glycoprep"]
