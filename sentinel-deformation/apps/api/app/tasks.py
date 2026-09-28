import os
from celery import Celery
from ...processing.catalog.search import search_sentinel1
from ...processing.catalog.download import download_product
from ...processing.insar.prepare import preprocess_sentinel1_intensity
from ...processing.timeseries.run import process_time_series_stack
from typing import List
from .config import settings

# Initialize Celery
celery_app = Celery(
    "sentinel_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

@celery_app.task(bind=True)
def run_preprocessing_pipeline(self, product_id: str, output_dir: str):
    """
    Background task to download and preprocess a single Sentinel-1 product.
    This implements: Download -> Orbit Correction -> Noise Removal -> Calibration -> Terrain Correction.
    """
    self.update_state(state='DOWNLOADING', meta={'product_id': product_id})
    
    try:
        # Step 1: Download
        zip_path = download_product(product_id, output_dir)
        
        # Step 2: Preprocess
        self.update_state(state='PREPROCESSING', meta={'product_id': product_id})
        output_tif = os.path.join(output_dir, f"{product_id}_preprocessed.tif")
        
        # NOTE: This requires SNAP 'gpt' in the system PATH to succeed.
        preprocess_sentinel1_intensity(zip_path, output_tif)
        
        return {"status": "success", "product_id": product_id, "output": output_tif}
        
    except Exception as e:
        self.update_state(state='FAILED', meta={'error': str(e)})
        raise e

@celery_app.task(bind=True)
def run_timeseries_pipeline(self, acquisitions: List[str], output_dir: str):
    """
    Background task to process a time series of Sentinel-1 SLCs into unwrapped, geocoded displacements.
    """
    self.update_state(state='TIMESERIES', meta={'acquisitions': len(acquisitions)})
    try:
        results = process_time_series_stack(acquisitions, output_dir)
        return {"status": "success", "processed_pairs": len(results), "outputs": results}
    except Exception as e:
        self.update_state(state='FAILED', meta={'error': str(e)})
        raise e

