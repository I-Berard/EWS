# Sentinel-1 InSAR Landslide Deformation Anomaly Detection Platform

A complete, working research application for detecting candidate landslide-related ground deformation using Sentinel-1 SAR data, MintPy displacement time series, statistical anomaly detection, and spatial analysis.

## Disclaimer
**This is a research and screening tool. It must not claim to predict landslide failures, establish causality, or issue operational safety warnings.**

## Features
- **Demo Mode:** Interactive dashboard with synthetic deterministic data containing known anomalies.
- **Real-Data Analysis Mode:** Upload and analyze existing MintPy `timeseries.h5` files.
- **Data Acquisition Mode:** Search Copernicus Data Space Ecosystem for Sentinel-1 SLC data.
- **Anomaly Detection:** Configurable robust residual temporal anomaly detection, change point analysis, and spatial clustering.

## Setup Instructions

### Prerequisites
- Python 3.11+
- Virtual environment (recommended)

### Installation
1. Clone the repository.
2. Run the start script:
   ```bash
   ./start.sh
   ```
   *The script will create a virtual environment, install dependencies from `requirements.txt`, and launch the Streamlit app.*

### Usage
- Use the sidebar to navigate between pages.
- Start at **Data Management** to generate demo data or upload a MintPy file.
- Proceed to **Anomaly Analysis** to configure detectors and run analysis.
- Use **Time-Series Explorer** to investigate specific pixels.
- Export results via **Results and Export**.
