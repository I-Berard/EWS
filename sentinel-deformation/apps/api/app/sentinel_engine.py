"""
Real Sentinel-1 data engine backed by Copernicus Data Space Ecosystem (CDSE).

Fetches real VV/VH GRD backscatter for two date windows (baseline vs monitoring),
computes per-pixel dB change, runs Z-score anomaly detection, labels connected
components, and returns ranked GeoJSON features + base64-encoded PNG overlays.
"""

from __future__ import annotations

import base64
import io
import math
import struct
import zlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# API constants
# ---------------------------------------------------------------------------

TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/"
    "auth/realms/CDSE/protocol/openid-connect/token"
)
PROCESS_URL = "https://sh.dataspace.copernicus.eu/process/v1"

GRID_W = 512
GRID_H = 512
M_PER_DEG_LAT = 111_320.0
MIN_ANOMALY_PIXELS = 8
MAX_ANOMALIES = 15

# ---------------------------------------------------------------------------
# OAuth2
# ---------------------------------------------------------------------------

def _make_oauth_session(client_id: str, client_secret: str):
    from oauthlib.oauth2 import BackendApplicationClient
    from requests_oauthlib import OAuth2Session
    client = BackendApplicationClient(client_id=client_id)
    oauth = OAuth2Session(client=client)
    oauth.fetch_token(
        token_url=TOKEN_URL,
        client_secret=client_secret,
        include_client_id=True,
    )
    return oauth

# ---------------------------------------------------------------------------
# Evalscripts
# ---------------------------------------------------------------------------

_S1_EVALSCRIPT = """
//VERSION=3
function setup() {
    return {
        input: [{ bands: ["VV", "VH"], units: "LINEAR_POWER" }],
        output: { bands: 2, sampleType: "FLOAT32" }
    };
}
function evaluatePixel(sample) {
    return [sample.VV, sample.VH];
}
"""

_S2_EVALSCRIPT = """
//VERSION=3
function setup() {
    return {
        input: [{ bands: ["B02", "B03", "B04"] }],
        output: { bands: 3, sampleType: "AUTO" }
    };
}
function evaluatePixel(sample) {
    return [2.5 * sample.B04, 2.5 * sample.B03, 2.5 * sample.B02];
}
"""

# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def _fetch_s1(oauth, bbox, start_date, end_date, width=GRID_W, height=GRID_H):
    import tifffile
    body = {
        "input": {
            "bounds": {
                "bbox": bbox,
                "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"},
            },
            "data": [{
                "type": "sentinel-1-grd",
                "dataFilter": {
                    "timeRange": {
                        "from": f"{start_date}T00:00:00Z",
                        "to":   f"{end_date}T23:59:59Z",
                    },
                    "acquisitionMode": "IW",
                    "mosaickingOrder": "mostRecent",
                },
                "processing": {"orthorectify": True},
            }],
        },
        "output": {
            "width": width,
            "height": height,
            "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}],
        },
        "evalscript": _S1_EVALSCRIPT,
    }
    try:
        resp = oauth.post(PROCESS_URL, json=body, timeout=120)
        resp.raise_for_status()
        data = tifffile.imread(io.BytesIO(resp.content))
        arr = np.asarray(data, dtype=np.float32)
        if arr.ndim == 2:
            arr = arr[:, :, np.newaxis]
        if arr.shape[-1] == 1:
            arr = np.concatenate([arr, arr], axis=-1)
        return arr
    except Exception as exc:
        print(f"[sentinel_engine] S1 fetch failed ({start_date}-{end_date}): {exc}")
        return np.zeros((height, width, 2), dtype=np.float32)


def _fetch_s2_rgb(oauth, bbox, start_date, end_date, width=512, height=512):
    body = {
        "input": {
            "bounds": {
                "bbox": bbox,
                "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"},
            },
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {
                    "timeRange": {
                        "from": f"{start_date}T00:00:00Z",
                        "to":   f"{end_date}T23:59:59Z",
                    },
                    "mosaickingOrder": "leastCC",
                },
            }],
        },
        "output": {
            "width": width,
            "height": height,
            "responses": [{"identifier": "default", "format": {"type": "image/png"}}],
        },
        "evalscript": _S2_EVALSCRIPT,
    }
    try:
        resp = oauth.post(PROCESS_URL, json=body, timeout=120)
        resp.raise_for_status()
        return resp.content
    except Exception as exc:
        print(f"[sentinel_engine] S2 fetch failed ({start_date}-{end_date}): {exc}")
        return b""

# ---------------------------------------------------------------------------
# dB conversion
# ---------------------------------------------------------------------------

def _linear_to_db(arr):
    return 10.0 * np.log10(np.maximum(arr, 1e-10))

# ---------------------------------------------------------------------------
# Z-score change detection
# ---------------------------------------------------------------------------

def _zscore_change_mask(baseline_db, monitoring_db, threshold_sigma=2.5):
    diff = monitoring_db - baseline_db
    valid = diff[np.isfinite(diff)]
    if valid.size < 16:
        return np.zeros(diff.shape, dtype=bool)
    mu = float(np.mean(valid))
    sigma = float(np.std(valid))
    if sigma < 0.5:
        sigma = 0.5
    return np.isfinite(diff) & (np.abs(diff - mu) > threshold_sigma * sigma)

# ---------------------------------------------------------------------------
# Connected-component labelling
# ---------------------------------------------------------------------------

def _label_components_2d(mask):
    from scipy import ndimage
    labeled, n = ndimage.label(mask)
    return labeled, n

# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

def _pixel_area_m2(bbox, w, h):
    west, south, east, north = bbox
    lat_center = (north + south) / 2.0
    px_lon = (east - west) / w
    px_lat = (north - south) / h
    return px_lon * M_PER_DEG_LAT * math.cos(math.radians(lat_center)) * px_lat * M_PER_DEG_LAT

def _pixel_to_lonlat(bbox, w, h, x, y):
    west, south, east, north = bbox
    px_lon = (east - west) / w
    px_lat = (north - south) / h
    return west + x * px_lon, north - y * px_lat

def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ---------------------------------------------------------------------------
# PNG encoding (no PIL required)
# ---------------------------------------------------------------------------

def _png_chunk(tag, data):
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

def _encode_png_rgba(rows, width, height):
    raw = b"".join(b"\x00" + row for row in rows)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(raw, 6))
        + _png_chunk(b"IEND", b"")
    )

_CHANGE_RAMP = [
    (2.0,  (255, 220, 0),   130),
    (4.0,  (255, 150, 0),   165),
    (7.0,  (255,  60, 0),   200),
    (10.0, (200,   0, 0),   220),
    (15.0, (130,   0, 0),   235),
]

def _change_to_rgba(delta_db):
    mag = abs(delta_db)
    for i in range(len(_CHANGE_RAMP) - 1):
        m0, c0, a0 = _CHANGE_RAMP[i]
        m1, c1, a1 = _CHANGE_RAMP[i + 1]
        if mag <= m1:
            if mag < m0:
                return (0, 0, 0, 0)
            t = (mag - m0) / (m1 - m0)
            r = int(c0[0] + (c1[0] - c0[0]) * t)
            g = int(c0[1] + (c1[1] - c0[1]) * t)
            b = int(c0[2] + (c1[2] - c0[2]) * t)
            a = int(a0 + (a1 - a0) * t)
            return (r, g, b, a)
    _, c, a = _CHANGE_RAMP[-1]
    return (c[0], c[1], c[2], a)


def render_change_png(diff_db):
    H, W = diff_db.shape
    rows = []
    for y in range(H):
        row = bytearray(W * 4)
        for x in range(W):
            v = diff_db[y, x]
            if not math.isfinite(float(v)):
                pass
            else:
                r, g, b, a = _change_to_rgba(float(v))
                i = x * 4
                row[i]     = r
                row[i + 1] = g
                row[i + 2] = b
                row[i + 3] = a
        rows.append(bytes(row))
    return _encode_png_rgba(rows, W, H)


def render_sar_from_array(vv_db):
    H, W = vv_db.shape
    rows = []
    lo, hi = -25.0, 5.0
    for y in range(H):
        row = bytearray(W * 4)
        for x in range(W):
            v = float(vv_db[y, x])
            gray = int(_clamp((v - lo) / (hi - lo), 0.0, 1.0) * 255)
            i = x * 4
            row[i]     = gray
            row[i + 1] = gray
            row[i + 2] = gray
            row[i + 3] = 255
        rows.append(bytes(row))
    return _encode_png_rgba(rows, W, H)

# ---------------------------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------------------------

def analyse_area(
    client_id: str,
    client_secret: str,
    bbox: List[float],
    baseline_start: str,
    baseline_end: str,
    monitoring_start: str,
    monitoring_end: str,
    aoi_id: str = "real-aoi",
    zscore_threshold: float = 2.5,
    min_pixels: int = MIN_ANOMALY_PIXELS,
) -> Dict[str, Any]:
    """
    Fetch Sentinel-1 GRD for two date windows, detect anomalous backscatter
    changes, and return ranked GeoJSON features + base64 PNG overlays.
    """
    oauth = _make_oauth_session(client_id, client_secret)

    print(f"[sentinel_engine] Fetching baseline  S1 {baseline_start} - {baseline_end}")
    base_raw = _fetch_s1(oauth, bbox, baseline_start, baseline_end)
    print(f"[sentinel_engine] Fetching monitoring S1 {monitoring_start} - {monitoring_end}")
    mon_raw  = _fetch_s1(oauth, bbox, monitoring_start, monitoring_end)

    # Also fetch S2 true-color for the monitoring window (non-blocking on failure)
    print(f"[sentinel_engine] Fetching S2 RGB {monitoring_start} - {monitoring_end}")
    s2_png_bytes = _fetch_s2_rgb(oauth, bbox, monitoring_start, monitoring_end)

    base_vv_db = _linear_to_db(base_raw[..., 0])
    mon_vv_db  = _linear_to_db(mon_raw[..., 0])

    diff_db = mon_vv_db - base_vv_db
    change_mask = _zscore_change_mask(base_vv_db, mon_vv_db, zscore_threshold)

    H, W = base_vv_db.shape
    px_area = _pixel_area_m2(bbox, W, H)

    labels, n_labels = _label_components_2d(change_mask)
    features: List[Dict[str, Any]] = []

    for label_id in range(1, n_labels + 1):
        ys_arr, xs_arr = np.where(labels == label_id)
        count = len(xs_arr)
        if count < min_pixels:
            continue

        delta_vals = diff_db[ys_arr, xs_arr]
        base_vals  = base_vv_db[ys_arr, xs_arr]
        mon_vals   = mon_vv_db[ys_arr, xs_arr]

        mean_delta = float(np.nanmean(delta_vals))
        peak_delta = float(delta_vals[int(np.argmax(np.abs(delta_vals)))])
        mean_base  = float(np.nanmean(base_vals))
        mean_mon   = float(np.nanmean(mon_vals))

        x0, x1 = int(xs_arr.min()), int(xs_arr.max())
        y0, y1 = int(ys_arr.min()), int(ys_arr.max())
        corners = [(x0, y0), (x1 + 1, y0), (x1 + 1, y1 + 1), (x0, y1 + 1), (x0, y0)]
        ring = [list(_pixel_to_lonlat(bbox, W, H, cx, cy)) for cx, cy in corners]

        area_m2 = count * px_area
        signal_strength = _clamp(abs(mean_delta) / 10.0, 0.0, 1.0)
        size_bonus = _clamp(count / 200.0, 0.0, 0.3)
        confidence = _clamp(0.4 * signal_strength + 0.6 * size_bonus + 0.2, 0.0, 0.99)
        event_type = "backscatter_decrease" if mean_delta < 0 else "backscatter_increase"

        features.append({
            "type": "Feature",
            "properties": {
                "id": f"real-{aoi_id}-{len(features) + 1:03d}",
                "aoi_id": aoi_id,
                "event_type": event_type,
                "area_m2": round(area_m2),
                "mean_change_db": round(mean_delta, 2),
                "peak_change_db": round(peak_delta, 2),
                "baseline_vv_db": round(mean_base, 2),
                "monitoring_vv_db": round(mean_mon, 2),
                "confidence": round(confidence, 2),
                "pixel_count": count,
                "rank": 0,
                "detected_at": _now_iso(),
            },
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        })

    features.sort(key=lambda f: abs(f["properties"]["peak_change_db"]), reverse=True)
    features = features[:MAX_ANOMALIES]
    for rank, feat in enumerate(features, 1):
        feat["properties"]["rank"] = rank

    valid_diff = diff_db[np.isfinite(diff_db)]
    total_change_pixels = int(np.sum(change_mask))

    stats: Dict[str, Any] = {
        "mean_change_db":        round(float(np.mean(valid_diff)), 3) if valid_diff.size else 0.0,
        "std_change_db":         round(float(np.std(valid_diff)), 3)  if valid_diff.size else 0.0,
        "peak_change_db":        round(float(np.max(np.abs(valid_diff))), 3) if valid_diff.size else 0.0,
        "total_change_pixels":   total_change_pixels,
        "total_change_area_m2":  round(total_change_pixels * px_area),
        "n_anomalies":           len(features),
        "zscore_threshold":      zscore_threshold,
    }

    sar_base_png = render_sar_from_array(base_vv_db)
    sar_mon_png  = render_sar_from_array(mon_vv_db)
    change_png   = render_change_png(diff_db)

    return {
        "aoi_id":     aoi_id,
        "satellite":  "SENTINEL-1 GRD (REAL)",
        "bbox":       bbox,
        "baseline":   {"start": baseline_start,  "end": baseline_end},
        "monitoring": {"start": monitoring_start, "end": monitoring_end},
        "stats":      stats,
        "anomalies":  {"type": "FeatureCollection", "features": features},
        "images": {
            "sar_baseline":   base64.b64encode(sar_base_png).decode(),
            "sar_monitoring": base64.b64encode(sar_mon_png).decode(),
            "change_overlay": base64.b64encode(change_png).decode(),
            "sentinel2_rgb":  base64.b64encode(s2_png_bytes).decode() if s2_png_bytes else "",
        },
        "generated_at": _now_iso(),
    }
