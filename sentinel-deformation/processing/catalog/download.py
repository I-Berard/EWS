import os
import requests
import shutil
from pathlib import Path
from typing import Optional
from .search import get_token

DOWNLOAD_URL_TEMPLATE = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products({product_id})/$value"

def download_product(product_id: str, output_dir: str, file_name: Optional[str] = None) -> str:
    """
    Downloads a Sentinel-1 product from the Copernicus Data Space Ecosystem.
    """
    token = get_token()
    if not token:
        raise ValueError("CDSE authentication token not available. Please check credentials.")

    headers = {"Authorization": f"Bearer {token}"}
    url = DOWNLOAD_URL_TEMPLATE.format(product_id=product_id)
    
    os.makedirs(output_dir, exist_ok=True)
    
    if not file_name:
        file_name = f"{product_id}.zip"
        
    output_path = Path(output_dir) / file_name
    
    print(f"Starting download for {product_id} to {output_path}")
    
    with requests.get(url, headers=headers, stream=True) as response:
        response.raise_for_status()
        
        # Check if the file name was provided in the headers
        content_disposition = response.headers.get("Content-Disposition")
        if content_disposition and "filename=" in content_disposition:
            suggested_name = content_disposition.split("filename=")[1].strip('"')
            output_path = Path(output_dir) / suggested_name

        with open(output_path, 'wb') as f:
            shutil.copyfileobj(response.raw, f)
            
    print(f"Successfully downloaded: {output_path}")
    return str(output_path)
