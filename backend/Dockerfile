# Care Plus backend — pinned Python 3.11 (host is 3.14, too new for some ML wheels).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps: GEOS/GDAL/PROJ for GeoDjango (PostGIS), plus curl for healthchecks.
RUN apt-get update && apt-get install -y --no-install-recommends \
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
