"""
Real-data API endpoints backed by the Copernicus Data Space Ecosystem (CDSE).

Routes (all prefixed with /api/real)
--------------------------------------
POST /analyse   Run real Sentinel-1 change detection over a user-drawn bbox.
GET  /images/{kind}  Serve cached PNG overlays as binary (sar_baseline,
                     sar_monitoring, change_overlay, sentinel2_rgb).
"""

from __future__ import annotations

import asyncio
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..config import settings
from .. import sentinel_engine

router = APIRouter()

# In-memory cache (keyed by cache_key → result dict).
# A production system would use Redis/S3, but for a prototype this is fine.
_cache: dict = {}


class AnalyseRequest(BaseModel):
    bbox: List[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="[west, south, east, north] in WGS-84",
    )
    baseline_start: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    baseline_end: str   = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    monitoring_start: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    monitoring_end: str   = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    zscore_threshold: float = Field(2.5, ge=1.0, le=5.0)
    aoi_id: str = Field("real-aoi", max_length=64)


def _cache_key(req: AnalyseRequest) -> str:
    return (
        f"{req.aoi_id}|{req.bbox}|"
        f"{req.baseline_start}:{req.baseline_end}|"
        f"{req.monitoring_start}:{req.monitoring_end}|"
        f"{req.zscore_threshold}"
    )


@router.post("/analyse")
def analyse(req: AnalyseRequest):
    """
    Fetch real Sentinel-1 GRD data for the given bbox + date windows,
    run Z-score change detection, and return ranked anomaly polygons.

    Results are cached in memory for the lifetime of the server process
    (identical requests are served instantly from cache).
    """
    key = _cache_key(req)
    if key in _cache:
        result = _cache[key].copy()
        result["cached"] = True
        return result

    west, south, east, north = req.bbox
    span_lon = east - west
    span_lat = north - south
    if span_lon <= 0 or span_lat <= 0:
        raise HTTPException(status_code=422, detail="bbox must have positive extent")
    if span_lon > 5 or span_lat > 5:
        raise HTTPException(
            status_code=422,
            detail="bbox too large (max 5° × 5°). Please select a smaller area.",
        )

    try:
        result = sentinel_engine.analyse_area(
            client_id=settings.CDSE_CLIENT_ID,
            client_secret=settings.CDSE_CLIENT_SECRET,
            bbox=req.bbox,
            baseline_start=req.baseline_start,
            baseline_end=req.baseline_end,
            monitoring_start=req.monitoring_start,
            monitoring_end=req.monitoring_end,
            aoi_id=req.aoi_id,
            zscore_threshold=req.zscore_threshold,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Sentinel data fetch failed: {exc}") from exc

    _cache[key] = result
    result = result.copy()
    result["cached"] = False
    return result


@router.post("/analyse/image/{kind}")
def analyse_image(req: AnalyseRequest, kind: str):
    """
    Return one of the PNG overlays from the analysis as a binary PNG response.
    kind: sar_baseline | sar_monitoring | change_overlay | sentinel2_rgb
    """
    import base64

    valid_kinds = {"sar_baseline", "sar_monitoring", "change_overlay", "sentinel2_rgb"}
    if kind not in valid_kinds:
        raise HTTPException(status_code=404, detail=f"Unknown image kind '{kind}'")

    key = _cache_key(req)
    if key not in _cache:
        raise HTTPException(
            status_code=404,
            detail="Analysis result not found. Run POST /api/real/analyse first.",
        )

    b64 = _cache[key].get("images", {}).get(kind, "")
    if not b64:
        raise HTTPException(status_code=404, detail="Image not available")

    png_bytes = base64.b64decode(b64)
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/cache/clear")
def clear_cache():
    _cache.clear()
    return {"cleared": True}
