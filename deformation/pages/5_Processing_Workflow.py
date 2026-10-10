import streamlit as st

st.set_page_config(page_title="Processing Workflow", page_icon="⚙️")

st.title("Processing Workflow")

st.markdown("""
This workflow explains the path from raw Sentinel-1 SLC data to MintPy displacement time series.
""")

st.header("Path 1: Existing MintPy products")
st.write("If you already have a `timeseries.h5` file, you can upload it via the **Data Management** page and proceed directly to **Anomaly Analysis**.")

st.header("Path 2: Raw Sentinel-1 acquisitions")
st.markdown("""
To process raw SLCs into a time series:
1.  **Interferogram Formation:** Use an upstream processor like ISCE2 (`stackSentinel.py`) or SNAP.
2.  **Unwrapping:** Unwrap the interferograms using SNAPHU.
3.  **Time-Series Inversion:** Run MintPy (`smallbaselineApp.py`) on the unwrapped interferograms to generate `timeseries.h5`.

*Note: This platform currently assumes you have completed upstream processing or are using Demo mode.*
""")
