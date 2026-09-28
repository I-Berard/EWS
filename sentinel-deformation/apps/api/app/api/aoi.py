from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

router = APIRouter()

# Mock data for phase 1 demo
DEMO_AOIS = [
    {
        "id": "demo-rwanda-1",
        "name": "Kigali Deformation Demo",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[29.9, -2.0], [30.2, -2.0], [30.2, -1.8], [29.9, -1.8], [29.9, -2.0]]]
        },
        "created_at": "2026-09-28T00:00:00Z"
    }
]

@router.get("/")
def list_aois() -> List[Dict[str, Any]]:
    return DEMO_AOIS

@router.get("/{id}")
def get_aoi(id: str) -> Dict[str, Any]:
    for aoi in DEMO_AOIS:
        if aoi["id"] == id:
            return aoi
    raise HTTPException(status_code=404, detail="AOI not found")

@router.post("/")
def create_aoi(aoi: Dict[str, Any]) -> Dict[str, Any]:
    # Placeholder for database insertion
    aoi["id"] = f"aoi-{len(DEMO_AOIS) + 1}"
    DEMO_AOIS.append(aoi)
    return aoi

@router.delete("/{id}")
def delete_aoi(id: str):
    global DEMO_AOIS
    DEMO_AOIS = [a for a in DEMO_AOIS if a["id"] != id]
    return {"status": "success"}
