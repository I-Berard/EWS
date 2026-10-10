import numpy as np
import pandas as pd
from core.models.baseline import calculate_linear_velocity
from core.models.temporal import robust_residual_anomaly, detect_change_points

def test_calculate_linear_velocity():
    dates = pd.date_range("2023-01-01", periods=3, freq="YE").values # 3 years
    # shape: (3 dates, 1 row, 1 col)
    # y = mx + c -> m = 0.05 m/yr -> 5 cm/yr
    timeseries = np.array([[[0.0]], [[0.05]], [[0.10]]])
    
    velocity = calculate_linear_velocity(dates, timeseries)
    
    assert velocity.shape == (1, 1)
    # The time elapsed is actually roughly 1 year between points
    # Let's just check it's positive and close to 0.05
    assert np.isclose(velocity[0, 0], 0.05, atol=0.005)

def test_robust_residual_anomaly_zero_mad():
    # If a pixel has constant velocity, differences are constant, MAD is 0
    # The function should handle this safely and not divide by zero
    timeseries = np.array([[[0.0]], [[0.05]], [[0.10]], [[0.15]], [[0.20]], [[0.25]]])
    scores = robust_residual_anomaly(timeseries)
    assert not np.isnan(scores[0, 0])
    
def test_detect_change_points():
    y = np.concatenate([np.zeros(10), np.ones(10)])
    cps = detect_change_points(y, min_size=5)
    assert len(cps) == 1
    assert cps[0] == 10
