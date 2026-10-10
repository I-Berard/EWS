#!/bin/bash
echo "Starting Sentinel-1 InSAR Landslide Deformation Anomaly Detection Platform..."
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating one..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --prefer-binary -r requirements.txt
else
    source venv/bin/activate
fi

export PYTHONPATH=$(pwd)
streamlit run app.py
