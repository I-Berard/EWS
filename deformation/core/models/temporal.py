import numpy as np
import pandas as pd
import ruptures as rpt
from typing import Tuple

def robust_residual_anomaly(timeseries: np.ndarray) -> np.ndarray:
    """
    Calculates a standardized residual anomaly score for each pixel.
    z(t) = (r(t) - median(r)) / (1.4826 * MAD(r))
    timeseries: 3D array (dates, rows, cols)
    Returns: 2D array of max anomaly scores (rows, cols)
    """
    n_dates, n_rows, n_cols = timeseries.shape
    anomaly_scores = np.zeros((n_rows, n_cols), dtype=np.float32)
    
    for r in range(n_rows):
        for c in range(n_cols):
            y = timeseries[:, r, c]
            valid = ~np.isnan(y)
            if np.sum(valid) > 5:
                y_valid = y[valid]
                # Simple detrend: differences or just median if assumed stationary
                # For anomaly in displacement, we might look at rate changes or residuals from linear trend
                
                # Let's use simple median absolute deviation of differences (velocity proxies)
                dy = np.diff(y_valid)
                med_dy = np.median(dy)
                mad = np.median(np.abs(dy - med_dy))
                
                if mad == 0:
                    mad = 1e-6 # Minimum noise safeguard
                    
                z_scores = (dy - med_dy) / (1.4826 * mad)
                
                # Take the max absolute z-score as the anomaly score for this pixel
                anomaly_scores[r, c] = np.max(np.abs(z_scores))
                
    return anomaly_scores

def detect_change_points(y: np.ndarray, min_size: int = 5) -> list:
    """
    Detects change points using ruptures (Pelt search method).
    """
    valid = ~np.isnan(y)
    if np.sum(valid) < min_size * 2:
        return []
        
    y_valid = y[valid]
    algo = rpt.Pelt(model="l2", min_size=min_size).fit(y_valid)
    # penalty based on variance
    penalty = np.var(y_valid) * np.log(len(y_valid)) * 2 
    result = algo.predict(pen=penalty)
    
    # Ruptures returns the index *after* the change point, and includes the end of array
    if len(result) > 0 and result[-1] == len(y_valid):
        result = result[:-1]
        
    # Map valid indices back to original array indices
    valid_indices = np.where(valid)[0]
    original_cps = [valid_indices[i] for i in result if i < len(valid_indices)]
    
    return original_cps
