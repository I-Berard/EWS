import numpy as np
import pandas as pd
from typing import Tuple

def calculate_linear_velocity(dates: np.ndarray, timeseries: np.ndarray) -> np.ndarray:
    """
    Calculates linear LOS velocity in meters/year for each pixel using actual elapsed time.
    dates: 1D array of datetime64
    timeseries: 3D array (dates, rows, cols)
    Returns: 2D array of velocity (rows, cols)
    """
    n_dates, n_rows, n_cols = timeseries.shape
    
    # Convert dates to years elapsed since first date
    t = (dates - dates[0]).astype('timedelta64[D]').astype(float) / 365.25
    
    velocity = np.zeros((n_rows, n_cols), dtype=np.float32)
    velocity[:] = np.nan
    
    # We can do this efficiently using numpy polyfit if there are no NaNs,
    # but we must handle NaNs safely.
    
    # Pre-compute for speed using least squares formula
    # y = mx + c -> m = cov(x,y)/var(x)
    
    for r in range(n_rows):
        for c in range(n_cols):
            y = timeseries[:, r, c]
            valid = ~np.isnan(y)
            if np.sum(valid) > 2: # At least 3 points
                x_valid = t[valid]
                y_valid = y[valid]
                # Mean centered
                x_c = x_valid - np.mean(x_valid)
                y_c = y_valid - np.mean(y_valid)
                
                var_x = np.sum(x_c**2)
                if var_x > 0:
                    m = np.sum(x_c * y_c) / var_x
                    velocity[r, c] = m
                    
    return velocity
