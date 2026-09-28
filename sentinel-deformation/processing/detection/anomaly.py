import os
import rasterio
import numpy as np
import geopandas as gpd
from scipy import ndimage
from shapely.geometry import shape
import rasterio.features

def detect_deformation_anomalies(
    velocity_tif: str,
    coherence_tif: str,
    output_geojson: str,
    velocity_threshold: float = 0.015, # 15 mm/yr, for example
    coherence_threshold: float = 0.4,
    min_area_pixels: int = 10
):
    """
    Detects deformation anomalies based on velocity and coherence thresholds,
    performs morphological cleanup, and extracts polygons.
    """
    if not os.path.exists(velocity_tif) or not os.path.exists(coherence_tif):
        raise FileNotFoundError("Input rasters for anomaly detection not found.")

    with rasterio.open(velocity_tif) as vel_src, rasterio.open(coherence_tif) as coh_src:
        velocity = vel_src.read(1)
        coherence = coh_src.read(1)
        transform = vel_src.transform
        crs = vel_src.crs

    # 1. Base thresholding
    # Candidate = High velocity magnitude AND acceptable coherence
    candidate_mask = (np.abs(velocity) > velocity_threshold) & (coherence > coherence_threshold)

    # 2. Morphological cleanup (Remove isolated pixels, fill small holes)
    # Opening removes small objects, closing fills small holes
    opened_mask = ndimage.binary_opening(candidate_mask, structure=np.ones((3,3)))
    cleaned_mask = ndimage.binary_closing(opened_mask, structure=np.ones((3,3)))

    # 3. Identify connected components and filter by minimum area
    labeled_array, num_features = ndimage.label(cleaned_mask)
    if num_features == 0:
        print("No deformation anomalies found matching the criteria.")
        # Write empty geojson
        gpd.GeoDataFrame(columns=['geometry'], crs=crs).to_file(output_geojson, driver='GeoJSON')
        return output_geojson

    # Filter regions by size
    sizes = ndimage.sum(cleaned_mask, labeled_array, range(num_features + 1))
    mask_size = sizes < min_area_pixels
    remove_pixel = mask_size[labeled_array]
    labeled_array[remove_pixel] = 0
    final_mask = labeled_array > 0

    if not np.any(final_mask):
        print("All anomalies were smaller than the minimum area threshold.")
        gpd.GeoDataFrame(columns=['geometry'], crs=crs).to_file(output_geojson, driver='GeoJSON')
        return output_geojson

    # 4. Polygonize candidate regions
    shapes = rasterio.features.shapes(final_mask.astype(np.uint8), mask=final_mask, transform=transform)
    
    polygons = []
    velocities = []
    coherences = []
    
    for geom, value in shapes:
        poly = shape(geom)
        polygons.append(poly)
        
        # Calculate statistics for each polygon (simplified bounding box approach or masked array)
        # For prototype: we just store dummy/approximate mean values or extract them via rasterio mask
        # We will do a simple extraction of the max/mean velocity using rasterio's geometry mask
        try:
            from rasterio.mask import mask
            out_vel, _ = mask(vel_src, [geom], crop=True)
            out_coh, _ = mask(coh_src, [geom], crop=True)
            
            valid_vel = out_vel[out_vel != vel_src.nodata]
            valid_coh = out_coh[out_coh != coh_src.nodata]
            
            mean_v = np.nanmean(valid_vel) if len(valid_vel) > 0 else 0.0
            max_v = np.nanmax(np.abs(valid_vel)) if len(valid_vel) > 0 else 0.0
            mean_c = np.nanmean(valid_coh) if len(valid_coh) > 0 else 0.0
        except Exception:
            mean_v, max_v, mean_c = 0.0, 0.0, 0.0
            
        velocities.append(mean_v)
        coherences.append(mean_c)

    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame({
        'geometry': polygons,
        'mean_velocity': velocities,
        'coherence': coherences,
        'confidence_score': coherences, # Coherence acts as a proxy for confidence here
        'event_type': 'deformation_candidate'
    }, crs=crs)

    gdf.to_file(output_geojson, driver='GeoJSON')
    print(f"Detected {len(gdf)} anomalies. Saved to {output_geojson}")
    return output_geojson
