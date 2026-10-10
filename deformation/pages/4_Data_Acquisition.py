import streamlit as st
import os
from core.acquisition import get_data_source

st.set_page_config(page_title="Data Acquisition", page_icon="📡")

st.title("Data Acquisition")

st.markdown("""
Use this page to search and download satellite acquisitions.
The data source is fully modular. Currently using: **Copernicus Data Space Ecosystem (CDSE)**.
""")

# Initialize modular data source
try:
    data_source = get_data_source("copernicus")
except Exception as e:
    st.error(f"Failed to initialize data source: {e}")
    st.stop()

bbox = st.session_state.get('config', {}).get("study_area", {}).get("bbox", [-122.5, 37.5, -122.0, 38.0])

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date")
with col2:
    end_date = st.date_input("End Date")

if st.button("Search Sentinel-1 SLC"):
    with st.spinner(f"Searching using {data_source.__class__.__name__}..."):
        try:
            results = data_source.search(bbox, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            st.session_state.search_results = results
            st.success(f"Found {len(results)} acquisitions.")
        except Exception as e:
            st.error(f"Search failed: {str(e)}")
            
if "search_results" in st.session_state and st.session_state.search_results:
    st.markdown("### Search Results")
    results = st.session_state.search_results
    
    for i, item in enumerate(results[:10]): # Show first 10
        product_id = item.get("Id")
        product_name = item.get("Name")
        
        with st.expander(f"{product_name} ({item.get('ContentDate', {}).get('Start')})"):
            st.json(item)
            if st.button(f"Download {product_name}", key=f"dl_btn_{i}"):
                with st.spinner(f"Downloading {product_name}... This may take a while."):
                    try:
                        output_dir = "data/raw"
                        filepath = data_source.download(product_id, output_dir=output_dir, name=product_name)
                        st.success(f"Successfully downloaded to: {filepath}")
                    except Exception as e:
                        st.error(f"Download failed: {str(e)}")
                        
    if len(results) > 10:
        st.write("... and more results.")
