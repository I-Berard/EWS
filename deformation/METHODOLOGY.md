# Methodology

## 1. Data Ingestion
The platform expects a MintPy-compatible `timeseries.h5` file containing:
- 3D displacement array (`timeseries`).
- 1D date array (`date`).
- Geocoding metadata attributes (`X_FIRST`, `Y_FIRST`, `X_STEP`, `Y_STEP`, `UNIT`).

## 2. Baseline Velocity
Calculated pixel-wise using a linear fit over the exact elapsed time (in years) between acquisitions, rather than assuming constant index spacing.

## 3. Temporal Anomaly Detection
Uses a robust standardized residual score:
$z(t) = \frac{r(t) - \text{median}(r)}{1.4826 \times \text{MAD}(r)}$
Where $r$ represents the first-order differences in the displacement time series. This highlights periods where the displacement rate deviates significantly from the median rate.

## 4. Spatial Clustering
Binary masks are generated based on the anomaly score threshold. Connected components are identified using 8-connectivity. Clusters smaller than a configurable minimum pixel size are rejected as noise.

## 5. Interpreting Results
- **LOS Displacement**: The measured phase change mapped to displacement along the sensor's line of sight. Not equivalent to vertical or slope-parallel movement.
- **Statistical Anomaly**: A pixel exhibiting unusual temporal behavior compared to its own history.
- **Candidate Deformation**: Spatially contiguous anomalies.
