import streamlit as st
import os
from core.data.validation import validate_h5_structure
from core.data.ingest import load_mintpy_timeseries

st.set_page_config(page_title="Data Management", page_icon="📁")

st.title("Data Management")

st.markdown("### Load MintPy Dataset")
uploaded_file = st.file_uploader("Upload MintPy HDF5 file (e.g. timeseries.h5)", type=["h5", "hdf5"])

filepath_to_load = None
if uploaded_file is not None:
    # Save uploaded file temporarily
    os.makedirs("data", exist_ok=True)
    filepath_to_load = os.path.join("data", uploaded_file.name)
    with open(filepath_to_load, "wb") as f:
        f.write(uploaded_file.getbuffer())
elif "filepath" in st.session_state and os.path.exists(st.session_state.filepath):
    filepath_to_load = st.session_state.filepath

if filepath_to_load:
    st.write(f"Selected file: `{filepath_to_load}`")
    if st.button("Validate and Load"):
        is_valid, msg = validate_h5_structure(filepath_to_load)
        if is_valid:
            st.success("File structure is valid.")
            with st.spinner("Loading data into memory..."):
                dates, timeseries, metadata = load_mintpy_timeseries(filepath_to_load)
                st.session_state.dates = dates
                st.session_state.timeseries = timeseries
                st.session_state.metadata = metadata
            st.success("Data loaded successfully.")
            st.write(f"Shape: {timeseries.shape} (Dates, Rows, Cols)")
            st.write(f"Number of dates: {len(dates)}")
        else:
            st.error(f"Validation failed: {msg}")
