# Data Guide

## Obtaining Sentinel-1 Data
1. Register at the [Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu/).
2. Navigate to the **Data Acquisition** page in this application to search for Level-1 SLC (Single Look Complex) products over your study area.
3. *Note:* GRD products do not contain the phase information required for InSAR time-series analysis.

## Processing to MintPy Format
This platform does not process raw SLC data natively. You must use an upstream processor:
1. **ISCE2**: Use `stackSentinel.py` to generate interferograms.
2. **SNAP**: Use the S1 Toolbox for coregistration and interferogram generation.
3. **SNAPHU**: Unwrap the phase.
4. **MintPy**: Use `smallbaselineApp.py` to invert the interferometric network and generate a `timeseries.h5` file.

Upload the resulting `timeseries.h5` via the **Data Management** page.
