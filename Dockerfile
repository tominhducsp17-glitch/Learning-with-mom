FROM node:20-bookworm-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    MATH_EXAM_STORAGE_ROOT=/app/storage \
    MATH_EXAM_DATABASE_PATH=/app/storage/math_exam.sqlite3 \
    MATH_EXAM_CUSTOM_FONT_DIR=/usr/local/share/fonts/mathexam \
    MAX_UPLOAD_MB=25 \
    MAGICK_BINARY=convert

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        fontconfig \
        fonts-dejavu-core \
        fonts-liberation2 \
        fonts-opensymbol \
        fonts-urw-base35 \
        imagemagick \
        libmagickcore-6.q16-6-extra \
        libreoffice-writer \
        libwmf-0.2-7 \
        libwmf-bin \
        xfonts-base \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
COPY fonts /usr/local/share/fonts/mathexam

RUN mkdir -p /app/storage/uploads /app/storage/extracted-assets /app/storage/previews

EXPOSE 8000

CMD sh -c "fc-cache -f /usr/local/share/fonts/mathexam || true; uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
