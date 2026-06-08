# ---------- Stage 1: build frontend ----------
FROM node:20-alpine AS frontend

WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY frontend ./frontend
COPY vite.config.js tailwind.config.js postcss.config.js ./
RUN npm run build

# ---------- Stage 2: Python runtime ----------
FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn openpyxl pypdf pdfplumber

COPY . .
COPY --from=frontend /build/static ./static

# Ensure data dir exists (sqlite will be mounted as volume in production)
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
