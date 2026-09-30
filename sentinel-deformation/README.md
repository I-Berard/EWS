# Sentinel Deformation Monitor

A web platform that automatically downloads and processes Sentinel-1 SAR data to detect and visualize ground deformation.

## Features (MVP)
* Fetch Sentinel-1 data via Copernicus STAC API
* Asynchronous processing with Celery & Redis
* Store InSAR products in PostgreSQL & MinIO
* Interactive MapLibre GL map
* Displacement time series charts
* Period movement analysis: overlays the stack of Sentinel-1 visits taken in a
  selected date range, estimates per-pixel movement, and highlights the areas
  that moved the most in that period (magenta heatmap + ranked hotspots)

## Architecture
- **Frontend**: React, TypeScript, Vite, MapLibre GL, Recharts, TanStack Query
- **Backend**: FastAPI, Celery, Redis, SQLAlchemy, Pydantic
- **Database**: PostgreSQL with PostGIS
- **Storage**: MinIO
- **Processing**: Python (GDAL, Rasterio, MintPy, ISCE3)

## Prerequisites
- Docker and Docker Compose
- Node.js (for local frontend development)
- Python 3.10+ (for local backend development)

## Setup

1. Copy `.env.example` to `.env` and fill in your details:
   ```bash
   cp .env.example .env
   ```
2. Start the infrastructure:
   ```bash
   docker-compose up -d
   ```
3. Run the FastAPI backend:
   ```bash
   make api
   ```
4. Run the React frontend:
   ```bash
   make frontend
   ```

## Demo Mode
The application includes a demo mode with synthetic data for testing the UI without downloading massive Sentinel-1 images. Access this from the dashboard.

## Development Phases
Refer to the documentation for development progress.
