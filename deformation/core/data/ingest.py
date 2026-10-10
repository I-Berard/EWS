import h5py
import numpy as np
import pandas as pd
from typing import Tuple, Dict, Any

def load_mintpy_timeseries(filepath: str) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Loads timeseries data, dates, and attributes from a MintPy HDF5 file.
    Returns:
        dates: Array of pandas datetime objects
        timeseries: 3D numpy array (dates, rows, cols) in meters
        metadata: Dictionary of attributes
    """
    with h5py.File(filepath, 'r') as f:
        # Load dates
        date_strs = f['date'][:]
        dates = pd.to_datetime([d.decode('ascii') if isinstance(d, bytes) else str(d) for d in date_strs])
        
        # Load timeseries
        timeseries = f['timeseries'][:]
        
        # Convert units to meters if necessary
        unit = f.attrs.get('UNIT', 'm')
        if isinstance(unit, bytes):
            unit = unit.decode('ascii')
            
        if unit == 'cm':
            timeseries = timeseries / 100.0
        elif unit == 'mm':
            timeseries = timeseries / 1000.0
            
        # Load metadata
        metadata = {k: v.decode('ascii') if isinstance(v, bytes) else v for k, v in f.attrs.items()}
        
    return dates.values, timeseries, metadata
