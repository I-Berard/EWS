import streamlit as st
import os
import numpy as np
from core.utils.export import export_geotiff

st.set_page_config(page_title="Results and Export", page_icon="💾")

st.title("Results and Export")

if "metadata" not in st.session_state or "velocity" not in st.session_state:
    st.warning("Please run Anomaly Analysis first to generate results.")
    st.stop()

st.markdown("### Export Maps as GeoTIFF")

export_dir = "exports"
os.makedirs(export_dir, exist_ok=True)

if st.button("Export Velocity Map"):
    filepath = os.path.join(export_dir, "velocity.tif")
    export_geotiff(filepath, st.session_state.velocity, st.session_state.metadata)
    st.success(f"Exported to {filepath}")
    
if st.button("Export Anomaly Score Map"):
    filepath = os.path.join(export_dir, "anomaly_scores.tif")
    export_geotiff(filepath, st.session_state.anomaly_scores, st.session_state.metadata)
    st.success(f"Exported to {filepath}")

if st.button("Export Clusters Map"):
    filepath = os.path.join(export_dir, "clusters.tif")
    # Convert clusters to float for geotiff
    export_geotiff(filepath, st.session_state.clusters.astype(np.float32), st.session_state.metadata)
    st.success(f"Exported to {filepath}")

st.info("Additional exports (GeoJSON, KML, HTML report) would be implemented here in a full production system.")
