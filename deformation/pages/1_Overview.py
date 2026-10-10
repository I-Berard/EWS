import streamlit as st

st.set_page_config(page_title="Overview", page_icon="📊", layout="wide")

st.title("Overview Dashboard")

st.markdown("### Dataset Summary")
if "metadata" in st.session_state:
    st.success("Data is loaded.")
    st.write("Number of valid pixels: (Processing needed)")
else:
    st.info("No dataset loaded yet. Go to Data Management to load or generate data.")

st.markdown("### Anomaly Summary")
if "anomaly_scores" in st.session_state and "clusters" in st.session_state:
    st.metric("Candidate Anomaly Pixels", len(st.session_state.anomaly_scores[st.session_state.anomaly_scores > 3])) # Example threshold
    st.metric("Candidate Clusters", len(st.session_state.clusters))
else:
    st.info("Run Anomaly Analysis to see results.")
