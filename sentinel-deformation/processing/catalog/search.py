import os
import requests
from typing import List, Dict, Any

# Copernicus Data Space Ecosystem API URLs
OAUTH2_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
STAC_API_URL = "https://catalogue.dataspace.copernicus.eu/stac/search"

def get_token() -> str:
    client_id = os.getenv("CDSE_CLIENT_ID")
    client_secret = os.getenv("CDSE_CLIENT_SECRET")
    
    if not client_id or not client_secret or client_id == "your_cdse_client_id_here":
        # For MVP/Demo purposes, return None or mock if no creds
        return None

    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    
    response = requests.post(OAUTH2_URL, data=data)
    response.raise_for_status()
    return response.json()["access_token"]

def search_sentinel1(
    aoi_geometry: Dict[str, Any],
    start_date: str,
    end_date: str,
    product_type: str = "SLC",
    mode: str = "IW",
    polarization: str = "VV",
    orbit_direction: str = None
) -> List[Dict[str, Any]]:
    
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    payload = {
        "collections": ["sentinel-1-grd", "sentinel-1-slc"], # OData vs STAC mapping might differ, CDSE provides STAC
        "intersects": aoi_geometry,
        "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
        "limit": 100,
        "query": {
            "s1:product_type": {"eq": product_type},
            "s1:instrument_mode": {"eq": mode}
        }
    }
    
    if orbit_direction:
        payload["query"]["sat:orbit_state"] = {"eq": orbit_direction.lower()}
        
    try:
        # Warning: Using the STAC API may require adjusting exact property names depending on the CDSE STAC schema.
        response = requests.post(STAC_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        return response.json().get("features", [])
    except Exception as e:
        print(f"STAC search failed: {e}")
        # Return mock for demo purposes if it fails
        return []
