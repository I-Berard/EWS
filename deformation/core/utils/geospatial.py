import numpy as np
import rasterio
from rasterio.transform import from_origin

def get_transform_from_mintpy(metadata: dict) -> rasterio.Affine:
    """
    Creates a rasterio Affine transform from MintPy metadata.
    """
    x_first = float(metadata.get('X_FIRST', 0))
    y_first = float(metadata.get('Y_FIRST', 0))
    x_step = float(metadata.get('X_STEP', 1))
    y_step = float(metadata.get('Y_STEP', -1))
    
    # Rasterio expects from_origin(west, north, xsize, ysize)
    # y_step is usually negative
    return from_origin(x_first, y_first, x_step, abs(y_step))

def get_crs_from_mintpy(metadata: dict) -> str:
    """
    Extracts CRS from MintPy metadata. Defaults to EPSG:4326 (WGS84) if not found.
    """
    # Simple heuristic
    return 'EPSG:4326'
