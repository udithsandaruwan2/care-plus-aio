# Care Plus backend — pinned Python 3.11 (host is 3.14, too new for some ML wheels).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps: GEOS/GDAL/PROJ for GeoDjango (PostGIS), plus curl for healthchecks.
# Use HTTPS apt mirrors: some networks filter/break plaintext port-80 mirror
# traffic. ca-certificates ships in the slim image, so HTTPS works out of the box.
# Handles both deb822 (Debian 12+) and classic sources.list layouts.
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true; \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list 2>/dev/null || true; \
    apt-get update && apt-get install -y --no-install-recommends \
        binutils \
        libproj-dev \
        gdal-bin \
        libgdal-dev \
        libgeos-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8000

# Dev default: ASGI server with autoreload. Overridden per-service in compose.
CMD ["uvicorn", "careplus.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--reload"]
