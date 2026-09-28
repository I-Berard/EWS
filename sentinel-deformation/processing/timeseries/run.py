import os
from typing import List, Tuple
from ..insar.interferogram import generate_interferogram
from ..insar.unwrap import unwrap_phase
from ..insar.geocode import geocode_unwrapped_phase

def process_insar_pair(master_zip: str, slave_zip: str, output_dir: str, subswath: str = "IW2") -> str:
    """
    Orchestrates the processing of a single InSAR pair.
    Returns the path to the geocoded displacement GeoTIFF.
    """
    pair_name = f"{os.path.basename(master_zip)[:15]}_{os.path.basename(slave_zip)[:15]}"
    pair_dir = os.path.join(output_dir, pair_name)
    os.makedirs(pair_dir, exist_ok=True)
    
    interferogram_dimap = os.path.join(pair_dir, f"{pair_name}_ifg.dim")
    unwrapped_dimap = os.path.join(pair_dir, f"{pair_name}_unw.dim")
    geocoded_tif = os.path.join(pair_dir, f"{pair_name}_disp.tif")
    
    # 1. Coregister and generate flattened interferogram
    print(f"--- Processing Pair: {pair_name} ---")
    generate_interferogram(master_zip, slave_zip, interferogram_dimap, subswath)
    
    # 2. Phase unwrapping via SNAPHU
    unwrap_phase(interferogram_dimap, unwrapped_dimap)
    
    # 3. Geocode and convert to LOS Displacement
    geocode_unwrapped_phase(unwrapped_dimap, geocoded_tif)
    
    return geocoded_tif

def process_time_series_stack(acquisitions: List[str], output_dir: str) -> List[str]:
    """
    Creates a small-baseline network of interferograms from a list of acquisitions.
    In a real MVP, you would select pairs based on temporal/perpendicular baselines.
    For this prototype, we'll connect each consecutive acquisition (A-B, B-C, C-D).
    """
    if len(acquisitions) < 2:
        raise ValueError("Need at least 2 acquisitions to form a time series.")
        
    acquisitions = sorted(acquisitions) # Simplistic sorting by filename/date
    results = []
    
    for i in range(len(acquisitions) - 1):
        master = acquisitions[i]
        slave = acquisitions[i + 1]
        
        try:
            result_tif = process_insar_pair(master, slave, output_dir)
            results.append(result_tif)
        except Exception as e:
            print(f"Failed to process pair {master}-{slave}: {e}")
            
    print(f"Time series stack processing complete. Generated {len(results)} displacement maps.")
    
    # At this point, the stack of geocoded_tif files could be fed into MintPy 
    # for advanced time-series inversion and velocity estimation.
    return results
