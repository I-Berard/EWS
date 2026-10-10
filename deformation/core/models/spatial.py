import numpy as np
from scipy.ndimage import label
from typing import Tuple

def spatial_clustering(anomaly_scores: np.ndarray, threshold: float, min_size: int) -> Tuple[np.ndarray, list]:
    """
    Identifies connected components (clusters) of candidate anomaly pixels.
    anomaly_scores: 2D array of scores
    threshold: Score threshold for candidacy
    min_size: Minimum number of pixels in a cluster
    Returns:
        labeled_mask: 2D array with cluster IDs
        cluster_props: List of properties for each cluster
    """
    binary_mask = anomaly_scores >= threshold
    
    # Find connected components (8-connectivity)
    structure = np.ones((3, 3), dtype=int)
    labeled_mask, num_features = label(binary_mask, structure=structure)
    
    cluster_props = []
    
    # Filter by size
    for i in range(1, num_features + 1):
        pixel_count = np.sum(labeled_mask == i)
        if pixel_count >= min_size:
            cluster_props.append({
                'id': i,
                'size': pixel_count,
                # we can add centroid etc later using regionprops
            })
        else:
            labeled_mask[labeled_mask == i] = 0
            
    # Relabel sequentially
    final_mask = np.zeros_like(labeled_mask)
    final_props = []
    current_id = 1
    for prop in cluster_props:
        final_mask[labeled_mask == prop['id']] = current_id
        prop['id'] = current_id
        final_props.append(prop)
        current_id += 1
        
    return final_mask, final_props
