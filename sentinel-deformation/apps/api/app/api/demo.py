"""
Demo-mode API endpoints backed by the synthetic InSAR engine.

Routes (all prefixed with /api/demo)
------------------------------------
GET  /aois/{id}              AOI definition
GET  /aois/{id}/product      product metadata + bbox
GET  /aois/{id}/anomalies    anomaly FeatureCollection ranked by peak |velocity|
GET  /aois/{id}/summary      aggregate stats + top-5 features
GET  /aois/{id}/timeseries   displacement time series (?lat=&lng=)
GET  /aois/{id}/acquisitions Sentinel-1 visit schedule (12-day revisit)
GET  /aois/{id}/movement     stacked movement analysis for ?start=&end=
GET  /aois/{id}/images/sar        SAR backscatter PNG overlay
GET  /aois/{id}/images/velocity   velocity RGBA PNG overlay
GET  /aois/{id}/images/movement   period-movement heatmap PNG (?start=&end=)
GET  /aois/{id}/images/visit/{i}  backscatter PNG of a single Sentinel-1 visit
"""

from typing import Any, Optional
import requests

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from .. import demo_engine

router = APIRouter()

DEMO_AOIS = [
    {
        "id": "demo-rwanda-1",
        "name": "Kigali Deformation Demo",
        "description": "Synthetic Sentinel-1 scene over Kigali, Rwanda",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[29.9, -2.0], [30.2, -2.0], [30.2, -1.8], [29.9, -1.8], [29.9, -2.0]]],
        },
    },
    {
        "id": "demo-rwanda-2",
        "name": "Lake Muhazi Corridor Demo",
        "description": "Synthetic Sentinel-1 scene east of Kigali",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[30.28, -1.85], [30.48, -1.85], [30.48, -1.68], [30.28, -1.68], [30.28, -1.85]]],
        },
    },
]


def _get_aoi(aoi_id: str) -> dict:
    for aoi in DEMO_AOIS:
        if aoi["id"] == aoi_id:
            return aoi
    raise HTTPException(status_code=404, detail="AOI not found")


@router.get("/aois")
def list_aois():
    return DEMO_AOIS


@router.get("/aois/{aoi_id}")
def get_aoi(aoi_id: str):
    return _get_aoi(aoi_id)


@router.get("/aois/{aoi_id}/product")
def get_product(aoi_id: str):
    aoi = _get_aoi(aoi_id)
    return demo_engine.get_product_meta(aoi)


@router.get("/aois/{aoi_id}/anomalies")
def get_anomalies(aoi_id: str):
    aoi = _get_aoi(aoi_id)
    bbox = demo_engine.get_product_meta(aoi)["bbox"]
    return demo_engine.get_anomaly_collection(bbox, aoi_id)


@router.get("/aois/{aoi_id}/summary")
def get_summary(aoi_id: str):
    aoi = _get_aoi(aoi_id)
    bbox = demo_engine.get_product_meta(aoi)["bbox"]
    return demo_engine.get_summary(bbox, aoi_id)


@router.get("/aois/{aoi_id}/timeseries")
def get_timeseries(aoi_id: str, lat: float, lng: float):
    _get_aoi(aoi_id)
    return demo_engine.get_time_series(aoi_id, lat, lng)


@router.get("/aois/{aoi_id}/acquisitions")
def get_acquisitions(aoi_id: str):
    """Schedule of Sentinel-1 visits that make up the demo stack."""
    _get_aoi(aoi_id)
    return {
        "aoi_id": aoi_id,
        "cycle_days": demo_engine.ACQUISITION_CYCLE_DAYS,
        "acquisitions": demo_engine.get_acquisitions(aoi_id),
    }


def _run_movement(engine_fn: Any, aoi_id: str, start: Optional[str], end: Optional[str]) -> Any:
    """Resolve AOI/bbox and translate engine ValueErrors into HTTP 422."""
    aoi = _get_aoi(aoi_id)
    bbox = demo_engine.get_product_meta(aoi)["bbox"]
    try:
        return engine_fn(bbox, aoi_id, start, end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/aois/{aoi_id}/movement")
def get_movement(aoi_id: str, start: Optional[str] = None, end: Optional[str] = None):
    """
    Overlay every Sentinel-1 visit inside [start, end] (defaults: full
    mission) and return the areas that moved the most in that period.
    """
    return _run_movement(demo_engine.get_movement_analysis, aoi_id, start, end)


@router.get("/aois/{aoi_id}/images/movement")
def get_movement_image(aoi_id: str, start: Optional[str] = None, end: Optional[str] = None):
    png = _run_movement(demo_engine.get_movement_image, aoi_id, start, end)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/aois/{aoi_id}/images/visit/{visit_index}")
def get_visit_image(aoi_id: str, visit_index: int):
    """Backscatter image of a single Sentinel-1 visit (stack member)."""
    _get_aoi(aoi_id)
    if not 0 <= visit_index < demo_engine.N_ACQUISITIONS:
        raise HTTPException(
            status_code=404,
            detail=f"Visit index {visit_index} outside 0..{demo_engine.N_ACQUISITIONS - 1}",
        )
    return Response(
        content=demo_engine.render_visit_png(aoi_id, visit_index),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


def _png_response(aoi_id: str, kind: str) -> Response:
    aoi = _get_aoi(aoi_id)
    bbox = demo_engine.get_product_meta(aoi)["bbox"]
    if kind == "velocity":
        velocity, _ = demo_engine.generate_fields(bbox, aoi_id)
        png = demo_engine.render_velocity_png(velocity)
    elif kind == "sar":
        png = demo_engine.render_sar_png(aoi_id)
    else:
        raise HTTPException(status_code=404, detail="Unknown image kind")
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/aois/{aoi_id}/images/sar")
def get_sar_image(aoi_id: str):
    return _png_response(aoi_id, "sar")


@router.get("/aois/{aoi_id}/images/velocity")
def get_velocity_image(aoi_id: str):
    return _png_response(aoi_id, "velocity")

@router.get("/aois/{aoi_id}/real-timeline")
def get_real_timeline(aoi_id: str, min_lng: Optional[float] = None, min_lat: Optional[float] = None, max_lng: Optional[float] = None, max_lat: Optional[float] = None):
    """Fetches real Sentinel-1 GRD quicklooks from Copernicus Data Space Ecosystem."""
    aoi = _get_aoi(aoi_id)
    bbox = demo_engine.get_product_meta(aoi)["bbox"]
    if min_lng is not None and min_lat is not None and max_lng is not None and max_lat is not None:
        bbox = [min_lng, min_lat, max_lng, max_lat]
    
    url = "https://catalogue.dataspace.copernicus.eu/stac/search"
    payload = {
        "collections": ["sentinel-1-grd"],
        "bbox": bbox,
        "datetime": "2023-01-01T00:00:00Z/2023-06-30T23:59:59Z",
        "limit": 30
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        features = response.json().get("features", [])
        
        timeline = []
        for f in features:
            if "thumbnail" in f.get("assets", {}):
                timeline.append({
                    "id": f["id"],
                    "date": f["properties"].get("datetime"),
                    "thumbnail_url": f["assets"]["thumbnail"]["href"],
                    "image_bbox": f.get("bbox")
                })
        timeline.sort(key=lambda x: x["date"])
        return timeline
    except Exception as e:
        print(f"STAC search failed: {e}")
        return []
