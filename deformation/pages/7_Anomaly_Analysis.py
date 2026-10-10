import streamlit as st
import numpy as np
import plotly.express as px
from core.models.baseline import calculate_linear_velocity
from core.models.temporal import robust_residual_anomaly
from core.models.spatial import spatial_clustering

st.set_page_config(page_title="Anomaly Analysis", page_icon="🔍")

st.title("Anomaly Analysis")

if "timeseries" not in st.session_state:
    st.warning("No data loaded. Please go to Data Management.")
    st.stop()

dates = st.session_state.dates
timeseries = st.session_state.timeseries

st.sidebar.header("Configuration")
config = st.session_state.get("config", {}).get("anomaly_detection", {})
vel_threshold = st.sidebar.number_input("Velocity Threshold (mm/yr)", value=config.get("velocity_threshold_mm_yr", 10.0))
z_threshold = st.sidebar.number_input("Residual Z-Score Threshold", value=config.get("residual_z_score_threshold", 3.0))
min_cluster = st.sidebar.number_input("Min Cluster Size (pixels)", value=config.get("min_cluster_size_pixels", 5), min_value=1)

if st.button("Run Analysis"):
    with st.spinner("Calculating Baseline Velocity..."):
        velocity = calculate_linear_velocity(dates, timeseries)
        st.session_state.velocity = velocity
        
    with st.spinner("Calculating Temporal Anomalies..."):
        anomaly_scores = robust_residual_anomaly(timeseries)
        st.session_state.anomaly_scores = anomaly_scores
        
    with st.spinner("Performing Spatial Clustering..."):
        clusters, cluster_props = spatial_clustering(anomaly_scores, z_threshold, int(min_cluster))
        st.session_state.clusters = clusters
        st.session_state.cluster_props = cluster_props
        
    st.success("Analysis complete.")

if "velocity" in st.session_state:
    st.markdown("### Velocity Map (mm/yr)")
    vel_mm = st.session_state.velocity * 1000
    fig1 = px.imshow(vel_mm, color_continuous_scale='RdBu_r', title='Linear Velocity')
    st.plotly_chart(fig1, use_container_width=True)

if "anomaly_scores" in st.session_state:
    st.markdown("### Temporal Anomaly Scores (Max absolute Z-score)")
    fig2 = px.imshow(st.session_state.anomaly_scores, color_continuous_scale='Viridis', title='Anomaly Score Map')
    st.plotly_chart(fig2, use_container_width=True)
    
if "clusters" in st.session_state:
    st.markdown(f"### Candidate Spatial Clusters (Threshold: Z > {z_threshold}, Size >= {min_cluster})")
    n_clusters = len(st.session_state.cluster_props)
    st.write(f"Found {n_clusters} clusters.")
    # Plot clusters with distinct colors
    fig3 = px.imshow(st.session_state.clusters, color_continuous_scale='Set3', title='Candidate Clusters')
    st.plotly_chart(fig3, use_container_width=True)
