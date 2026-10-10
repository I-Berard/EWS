import streamlit as st
import plotly.express as px
import pandas as pd
import numpy as np

st.set_page_config(page_title="Time-Series Explorer", page_icon="📈")

st.title("Time-Series Explorer")

if "timeseries" not in st.session_state:
    st.warning("No data loaded. Please go to Data Management.")
    st.stop()
    
dates = st.session_state.dates
timeseries = st.session_state.timeseries

n_dates, n_rows, n_cols = timeseries.shape

st.markdown("### Select Pixel")
col1, col2 = st.columns(2)
with col1:
    r = st.number_input("Row index", min_value=0, max_value=n_rows-1, value=n_rows//2)
with col2:
    c = st.number_input("Column index", min_value=0, max_value=n_cols-1, value=n_cols//2)

pixel_ts = timeseries[:, r, c]

# Create DataFrame for plotting
df = pd.DataFrame({
    'Date': dates,
    'Displacement (m)': pixel_ts
})

# Drop NaNs
df_valid = df.dropna()

if len(df_valid) == 0:
    st.warning("Selected pixel has no valid data.")
else:
    st.write(f"Valid observations: {len(df_valid)} / {len(df)}")
    
    # Plotting with Plotly
    fig = px.scatter(df_valid, x='Date', y='Displacement (m)', title=f'LOS Displacement for Pixel (row={r}, col={c})')
    
    # Optional: add trend line
    if len(df_valid) > 2:
        # Simple linear fit on timestamp
        df_valid['days'] = (df_valid['Date'] - df_valid['Date'].min()).dt.days
        m, b = np.polyfit(df_valid['days'], df_valid['Displacement (m)'], 1)
        df_valid['Trend'] = m * df_valid['days'] + b
        fig.add_scatter(x=df_valid['Date'], y=df_valid['Trend'], mode='lines', name='Linear Trend')
        
        st.metric("Estimated Velocity (mm/yr)", f"{m * 365.25 * 1000:.2f}")

    st.plotly_chart(fig, use_container_width=True)
    
    # Provide CSV download
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "Download Time Series as CSV",
        csv,
        "pixel_timeseries.csv",
        "text/csv"
    )
