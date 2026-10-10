import h5py
import numpy as np
import pandas as pd

def validate_h5_structure(filepath: str):
    """Validates if the HDF5 file has the required MintPy structure."""
    try:
        with h5py.File(filepath, 'r') as f:
            if 'date' not in f or 'timeseries' not in f:
                return False, "Missing 'date' or 'timeseries' dataset."
            if 'UNIT' not in f.attrs:
                return False, "Missing 'UNIT' attribute."
            if 'X_FIRST' not in f.attrs or 'Y_FIRST' not in f.attrs:
                return False, "Missing geocoding attributes (X_FIRST, Y_FIRST)."
        return True, "Valid"
    except Exception as e:
        return False, str(e)
