# Architecture

The platform follows a modular, Python-first architecture.

## UI Layer (Streamlit)
- `app.py`: Main entry point and configuration loading.
- `pages/`: Individual dashboard pages (Overview, Study Area, Data Management, Data Acquisition, Processing Workflow, Time-Series Explorer, Anomaly Analysis, Results and Export).

## Core Logic (`core/`)
- **`data/`**: Ingestion (`ingest.py`) and validation (`validation.py`) of MintPy HDF5 formats.
- **`models/`**: 
  - `baseline.py`: Linear velocity calculation.
  - `temporal.py`: Robust residual scoring and ruptures-based change point detection.
  - `spatial.py`: Scipy-based connected component clustering.
- **`synthetic/`**: `generator.py` for reproducible synthetic HDF5 datasets with spatial noise and simulated deformation patches.
- **`acquisition/`**: `copernicus.py` for REST API interactions with Copernicus Data Space Ecosystem.
- **`utils/`**: Geospatial transformations and GeoTIFF export (`export.py`, `geospatial.py`) using rasterio.

## Testing (`tests/`)
Pytest suite for validation, model integrity, and synthetic data reproducibility.
