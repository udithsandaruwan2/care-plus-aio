# Care Plus backend — pinned Python 3.11 (host is 3.14, too new for some ML wheels).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps: GEOS/GDAL/PROJ for GeoDjango (PostGIS), curl for healthchecks,
# ffmpeg for faster-whisper ASR (webm → wav).
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true; \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list 2>/dev/null || true; \
    apt-get update && apt-get install -y --no-install-recommends \
        binutils \
        libproj-dev \
        gdal-bin \
        libgdal-dev \
        libgeos-dev \
        curl \
        ffmpeg \
        espeak-ng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
# Dev default: ASGI server with autoreload. Overridden per-service in compose.
CMD ["uvicorn", "careplus.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--reload"]
