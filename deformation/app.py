import streamlit as st
import yaml
from pathlib import Path

st.set_page_config(
    page_title="InSAR Anomaly Detection Platform",
    page_icon="🛰️",
    layout="wide",
)

def load_config():
    config_path = Path("config.yaml")
    if config_path.exists():
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    return {}

if "config" not in st.session_state:
    st.session_state.config = load_config()

st.title("Sentinel-1 InSAR Landslide Deformation Anomaly Detection Platform")

st.markdown("""
Welcome to the Quality-Aware Spatiotemporal Anomaly Detection platform.
This is a research and screening tool. It does not claim to predict landslide failures, establish causality, or issue operational safety warnings.

Please use the sidebar to navigate through the workflow.
""")


