"""
Demo-mode API endpoints backed by the synthetic InSAR engine.

Routes (all prefixed with /api/demo)
------------------------------------
GET  /aois/{id}              AOI definition
GET  /aois/{id}/product      product metadata + bbox
GET  /aois/{id}/anomalies    anomaly FeatureCollection ranked by peak |velocity|
GET  /aois/{id}/summary      aggregate stats + top-5 features
GET  /aois/{id}/timeseries   displacement time series (?lat=&lng=)
GET  /aois/{id}/images/sar        SAR backscatter PNG overlay
GET  /aois/{id}/images/velocity   velocity RGBA PNG overlay
"""

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
