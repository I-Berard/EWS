import os
import requests
import json
from typing import Dict, Any, List
from dotenv import load_dotenv
from .base import DataSource

load_dotenv()

class CopernicusSource(DataSource):
    """
    Copernicus Data Space Ecosystem (CDSE) data source implementation.
    """
    def __init__(self):
        self.username = os.getenv("COPERNICUS_USERNAME")
        self.password = os.getenv("COPERNICUS_PASSWORD")
        self.auth_url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
        self.search_url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
        self.download_url_template = "https://zipper.dataspace.copernicus.eu/odata/v1/Products({product_id})/$value"
        self.access_token = None

    def _authenticate(self):
        """Fetches an OAuth token from Copernicus Keycloak."""
        if not self.username or not self.password:
            raise ValueError("Copernicus credentials not found. Please set COPERNICUS_USERNAME and COPERNICUS_PASSWORD in your .env file.")
            
        data = {
            "client_id": "cdse-public",
            "username": self.username,
            "password": self.password,
            "grant_type": "password"
        }
        
        response = requests.post(self.auth_url, data=data)
        response.raise_for_status()
        
        self.access_token = response.json().get("access_token")
        if not self.access_token:
            raise Exception("Failed to extract access token from authentication response.")

    def search(self, bbox: list, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Searches the Copernicus Data Space Ecosystem for Sentinel-1 SLC acquisitions.
        """
        min_lon, min_lat, max_lon, max_lat = bbox
        polygon = f"POLYGON(({min_lon} {min_lat}, {max_lon} {min_lat}, {max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat}))"
        
        # Filter for S1, SLC
        query = (
            f"?$filter=Collection/Name eq 'SENTINEL-1' "
            f"and Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' and att/OData.CSC.StringAttribute/Value eq 'SLC') "
            f"and OData.CSC.Intersects(area=geography'SRID=4326;{polygon}') "
            f"and ContentDate/Start ge {start_date}T00:00:00.000Z "
            f"and ContentDate/Start le {end_date}T23:59:59.999Z"
        )
        
        response = requests.get(self.search_url + query, timeout=30)
        response.raise_for_status()
        
        results = response.json()
        return results.get("value", [])

    def download(self, product_id: str, output_dir: str, name: str = None) -> str:
        """
        Downloads a specific product from CDSE.
        """
        if not self.access_token:
            self._authenticate()
            
        os.makedirs(output_dir, exist_ok=True)
        filename = f"{name}.zip" if name else f"{product_id}.zip"
        filepath = os.path.join(output_dir, filename)
        
        download_url = self.download_url_template.format(product_id=product_id)
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        # We use a streaming request to handle large files
        response = requests.get(download_url, headers=headers, stream=True)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    
        return filepath
