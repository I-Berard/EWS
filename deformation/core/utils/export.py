import rasterio
import numpy as np
from typing import Optional
from core.utils.geospatial import get_transform_from_mintpy, get_crs_from_mintpy

def export_geotiff(filepath: str, data: np.ndarray, metadata: dict, nodata: Optional[float] = np.nan):
    """
    Exports a 2D numpy array to a GeoTIFF using metadata from MintPy.
    """
    transform = get_transform_from_mintpy(metadata)
    crs = get_crs_from_mintpy(metadata)
    
    height, width = data.shape
    
    with rasterio.open(
        filepath,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=1,
        dtype=data.dtype,
        crs=crs,
        transform=transform,
        nodata=nodata
    ) as dst:
        dst.write(data, 1)
