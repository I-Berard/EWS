import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

st.set_page_config(page_title="Study Area", page_icon="🗺️", layout="wide")

st.title("Study Area Definition")

st.markdown("""
Draw a rectangle on the map to define your study area. The bounding box will be saved automatically for data fetching.
""")

config = st.session_state.get('config', {})
if 'study_area' not in config:
    config['study_area'] = {}
    st.session_state.config = config

bbox = config.get("study_area", {}).get("bbox", [-122.5, 37.5, -122.0, 38.0])

# Initialize folium map
# Center map on current bbox or default
center_lat = (bbox[1] + bbox[3]) / 2
center_lon = (bbox[0] + bbox[2]) / 2

m = folium.Map(location=[center_lat, center_lon], zoom_start=10)

# Add draw control
draw = Draw(
    export=False,
    position='topleft',
    draw_options={
        'polyline': False,
        'polygon': False,
        'circle': False,
        'marker': False,
        'circlemarker': False,
        'rectangle': True, # Only allow rectangles for bounding box
    },
    edit_options={'edit': False}
)
m.add_child(draw)

# Display the map and get output
output = st_folium(m, width=1000, height=600)

if output["last_active_drawing"]:
    # The output is a GeoJSON feature
    geometry = output["last_active_drawing"]["geometry"]
    if geometry["type"] == "Polygon":
        coords = geometry["coordinates"][0]
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        
        min_lon, max_lon = min(lons), max(lons)
        min_lat, max_lat = min(lats), max(lats)
        
        new_bbox = [min_lon, min_lat, max_lon, max_lat]
        
        if new_bbox != bbox:
            st.session_state.config["study_area"]["bbox"] = new_bbox
            st.success(f"Study area updated: {new_bbox}")
            # Ensure the config updates trigger a rerun or just display
            st.rerun()

st.markdown("### Current Bounding Box")
st.code(st.session_state.config.get("study_area", {}).get("bbox", []))
