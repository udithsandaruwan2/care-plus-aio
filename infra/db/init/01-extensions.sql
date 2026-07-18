-- Enable required extensions on the Care Plus database.
-- TimescaleDB-HA auto-creates the timescaledb extension, but we make it explicit
-- and add PostGIS (geospatial) + pgcrypto (AES-256 encryption at rest).
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
