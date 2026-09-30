"""
Synthetic InSAR data engine for the Sentinel Deformation Monitor demo mode.

Generates deterministic, seeded velocity / coherence fields over an AOI,
extracts deformation anomalies (connected components above threshold),
encodes SAR backscatter and velocity rasters as PNG images, and produces
displacement time series - all using only the Python standard library so the
API can run (and be tested) without the heavy geo-processing stack
(numpy / rasterio / SNAP). The real pipeline in `processing/` replaces this
when actual Sentinel-1 products are available.
"""

import math
import random
import struct
import zlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

GRID_W = 300  # raster width in pixels
GRID_H = 300  # raster height in pixels

# Thresholds aligned with processing/detection/anomaly.py
VELOCITY_THRESHOLD_MM_YR = 10.0
COHERENCE_THRESHOLD = 0.45
MIN_ANOMALY_PIXELS = 12
MAX_ANOMALIES = 12

M_PER_DEG_LAT = 111_320.0

# Sentinel-1 12-day revisit: the synthetic mission is a stack of co-registered
# visits spanning PRODUCT_START -> PRODUCT_END.
ACQUISITION_CYCLE_DAYS = 12
N_ACQUISITIONS = 36
DAYS_PER_YEAR = 365.25
PRODUCT_END = datetime(2026, 9, 28, tzinfo=timezone.utc)
PRODUCT_START = PRODUCT_END - timedelta(days=(N_ACQUISITIONS - 1) * ACQUISITION_CYCLE_DAYS)

# Period-movement analysis (stack overlay)
MIN_MOVEMENT_MM = 1.0  # floor for the |movement| detection threshold in a period
MIN_MOVEMENT_AREA_PIXELS = 12
MAX_MOVEMENT_AREAS = 10
SEASONAL_AMPLITUDE_MM = 3.0  # per-pixel seasonal oscillation amplitude
VISIT_NOISE_SIGMA_MM = 1.2  # spatial pattern scale of visit-to-visit decorrelation noise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_from(text: str) -> int:
    return zlib.crc32(text.encode("utf-8")) & 0xFFFFFFFF


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pixel_size_deg(bbox: List[float]) -> Tuple[float, float]:
    """Returns (deg_per_px_lon, deg_per_px_lat)."""
    west, south, east, north = bbox
    return (east - west) / GRID_W, (north - south) / GRID_H


def _pixel_area_m2(bbox: List[float]) -> float:
    west, south, east, north = bbox
    lat_center = (north + south) / 2.0
    px_lon, px_lat = _pixel_size_deg(bbox)
    return px_lon * M_PER_DEG_LAT * math.cos(math.radians(lat_center)) * px_lat * M_PER_DEG_LAT


def _pixel_to_lonlat(bbox: List[float], x: float, y: float) -> Tuple[float, float]:
    """Convert pixel coordinates (grid edges) to lon/lat."""
    west, south, east, north = bbox
    px_lon, px_lat = _pixel_size_deg(bbox)
    return west + x * px_lon, north - y * px_lat


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


# ---------------------------------------------------------------------------
# Synthetic fields
# ---------------------------------------------------------------------------

def generate_fields(bbox: List[float], aoi_id: str) -> Tuple[List[List[float]], List[List[float]]]:
    """
    Generate deterministic velocity (mm/yr, LOS, negative = subsidence) and
    coherence (0..1) grids seeded by the AOI id.
    """
    rng = random.Random(_seed_from(f"fields:{aoi_id}"))

    # Deformation hotspots: one severe, one moderate, one mild subsidence
    # bowl, plus the chance of an uplift patch for variety.
    hotspots = []
    peak = -rng.uniform(18.0, 26.0)
    hotspots.append((rng.uniform(0.2, 0.45), rng.uniform(0.35, 0.6), rng.uniform(9, 14), peak))
    hotspots.append((rng.uniform(0.45, 0.7), rng.uniform(0.55, 0.8), rng.uniform(7, 11), -rng.uniform(11.0, 17.0)))
    hotspots.append((rng.uniform(0.15, 0.8), rng.uniform(0.15, 0.4), rng.uniform(5, 9), -rng.uniform(10.0, 14.0)))
    if rng.random() < 0.6:
        hotspots.append((rng.uniform(0.6, 0.85), rng.uniform(0.2, 0.45), rng.uniform(6, 10), rng.uniform(6.0, 12.0)))

    # Simulated water / layover patch for the SAR image (independent of velocity)
    dark_blobs = [(rng.uniform(0.1, 0.9), rng.uniform(0.1, 0.9), rng.uniform(18, 34), rng.uniform(0.25, 0.4))
                  for _ in range(2)]

    velocity: List[List[float]] = [[0.0] * GRID_W for _ in range(GRID_H)]
    coherence: List[List[float]] = [[0.0] * GRID_W for _ in range(GRID_H)]

    trend_slope = rng.uniform(-1.5, 1.5)  # gentle regional gradient (mm/yr across grid)
    for y in range(GRID_H):
        fy = y / (GRID_H - 1)
        lat_factor = math.cos(math.radians(bbox[1] + fy * (bbox[3] - bbox[1])))
        for x in range(GRID_W):
            fx = x / (GRID_W - 1)
            v = trend_slope * (fx - 0.5) * 2.0
            c = rng.uniform(0.78, 0.95)
            for cx, cy, sigma, peak_v in hotspots:
                d2 = ((fx - cx) * GRID_W) ** 2 + ((fy - cy) * GRID_H) ** 2
                g = peak_v * math.exp(-d2 / (2.0 * sigma * sigma))
                v += g
                # Coherence stays usable above deformation areas (else they
                # would be filtered out), but drops slightly.
                c -= 0.25 * abs(g) / 25.0
            for cx, cy, sigma, depth in dark_blobs:
                d2 = ((fx - cx) * GRID_W) ** 2 + ((fy - cy) * GRID_H) ** 2
                v += 0.0  # dark blobs do not fake deformation
                c -= depth * 0.9 * math.exp(-d2 / (2.0 * sigma * sigma))
            velocity[y][x] = round(v * lat_factor, 3)
            coherence[y][x] = round(_clamp(c, 0.05, 0.99), 3)

    return velocity, coherence


# ---------------------------------------------------------------------------
# Anomaly detection (pure-python mirror of processing/detection/anomaly.py)
# ---------------------------------------------------------------------------

def _label_components(mask: List[List[bool]]) -> List[List[int]]:
    """Iterative flood-fill connected-component labelling (4-neighbourhood)."""
    labels = [[0] * GRID_W for _ in range(GRID_H)]
    current = 0
    for sy in range(GRID_H):
        for sx in range(GRID_W):
            if not mask[sy][sx] or labels[sy][sx] != 0:
                continue
            current += 1
            stack = [(sx, sy)]
            labels[sy][sx] = current
            while stack:
                x, y = stack.pop()
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < GRID_W and 0 <= ny < GRID_H and mask[ny][nx] and labels[ny][nx] == 0:
                        labels[ny][nx] = current
                        stack.append((nx, ny))
    return labels


def detect_anomalies(
    velocity: List[List[float]],
    coherence: List[List[float]],
    bbox: List[float],
    aoi_id: str,
) -> List[Dict[str, Any]]:
    """
    Threshold the velocity field, clean up, extract connected regions and
    return GeoJSON-style polygon features with statistics. Features are ranked
    by peak |velocity| (rank 1 = fastest deformation).
    """
    mask = [
        [abs(velocity[y][x]) >= VELOCITY_THRESHOLD_MM_YR and coherence[y][x] >= COHERENCE_THRESHOLD
         for x in range(GRID_W)]
        for y in range(GRID_H)
    ]
    labels = _label_components(mask)

    n_labels = max((max(row) for row in labels), default=0)
    if n_labels == 0:
        return []

    px_area = _pixel_area_m2(bbox)
    seed = _seed_from(f"anomalies:{aoi_id}")
    features: List[Dict[str, Any]] = []

    for label in range(1, n_labels + 1):
        xs: List[int] = []
        ys: List[int] = []
        v_sum = 0.0
        v_peak = 0.0
        v_peak_signed = 0.0
        c_sum = 0.0
        count = 0
        for y in range(GRID_H):
            row = labels[y]
            for x in range(GRID_W):
                if row[x] != label:
                    continue
                xs.append(x)
                ys.append(y)
                v = velocity[y][x]
                c = coherence[y][x]
                v_sum += v
                c_sum += c
                count += 1
                if abs(v) > abs(v_peak):
                    v_peak = v
                    v_peak_signed = v
        if count < MIN_ANOMALY_PIXELS:
            continue

        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        # Bounding-box polygon (grid edges -> lon/lat), closed ring.
        corners = [(x0, y0), (x1 + 1, y0), (x1 + 1, y1 + 1), (x0, y1 + 1), (x0, y0)]
        ring = [list(_pixel_to_lonlat(bbox, cx, cy)) for cx, cy in corners]

        mean_v = v_sum / count
        mean_c = c_sum / count
        area_m2 = count * px_area
        # Coherence drives confidence, small areas get a size penalty.
        confidence = _clamp(mean_c * 0.85 + (0.1 if count > 80 else 0.03), 0.05, 0.99)
        event_type = "uplift" if mean_v > 0 else "subsidence"

        features.append({
            "type": "Feature",
            "properties": {
                "id": f"anomaly-{seed:08x}-{len(features) + 1:02d}",
                "aoi_id": aoi_id,
                "event_type": event_type,
                "area_m2": round(area_m2),
                "mean_velocity": round(mean_v, 2),
                "max_velocity": round(v_peak_signed, 2),
                "coherence": round(mean_c, 2),
                "confidence": round(confidence, 2),
                "pixel_count": count,
                "detected_at": _now_iso(),
            },
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        })

    features.sort(key=lambda f: abs(f["properties"]["max_velocity"]), reverse=True)
    features = features[:MAX_ANOMALIES]
    for rank, feature in enumerate(features, start=1):
        feature["properties"]["rank"] = rank
    return features


def get_anomaly_collection(bbox: List[float], aoi_id: str) -> Dict[str, Any]:
    velocity, coherence = generate_fields(bbox, aoi_id)
    features = detect_anomalies(velocity, coherence, bbox, aoi_id)
    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# PNG encoding (RGBA, no external dependencies)
# ---------------------------------------------------------------------------

def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def encode_png(width: int, height: int, rows: List[bytes]) -> bytes:
    """Encode 8-bit RGBA scanlines (each row: width*4 bytes) into a PNG."""
    if len(rows) != height:
        raise ValueError(f"expected {height} rows, got {len(rows)}")
    raw = b"".join(b"\x00" + row for row in rows)  # filter type 0 per row
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(raw, 6))
        + _png_chunk(b"IEND", b"")
    )


def _lerp_color(a: Tuple[int, int, int], b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


# Velocity colour ramp shared with the frontend legend (magnitude mm/yr -> RGBA)
VELOCITY_RAMP: List[Tuple[float, Tuple[int, int, int], int]] = [
    (3.0, (255, 220, 0), 130),
    (8.0, (255, 150, 0), 165),
    (14.0, (255, 60, 0), 200),
    (20.0, (200, 0, 0), 220),
    (30.0, (130, 0, 0), 235),
]

UPLIFT_RAMP: List[Tuple[float, Tuple[int, int, int], int]] = [
    (3.0, (0, 220, 255), 130),
    (8.0, (0, 160, 255), 165),
    (14.0, (0, 100, 255), 200),
    (20.0, (0, 60, 220), 220),
    (30.0, (0, 30, 180), 235),
]


def velocity_to_rgba(v: float) -> Tuple[int, int, int, int]:
    """Map a signed LOS velocity (mm/yr) to an RGBA colour (transparent when flat)."""
    mag = abs(v)
    ramp = UPLIFT_RAMP if v > 0 else VELOCITY_RAMP
    if mag < ramp[0][0]:
        return (0, 0, 0, 0)
    for i in range(len(ramp) - 1):
        m0, c0, a0 = ramp[i]
        m1, c1, a1 = ramp[i + 1]
        if mag <= m1:
            t = (mag - m0) / (m1 - m0)
            r, g, b = _lerp_color(c0, c1, t)
            alpha = int(a0 + (a1 - a0) * t)
            return (r, g, b, alpha)
    _, c, a = ramp[-1]
    return (c[0], c[1], c[2], a)


def render_velocity_png(velocity: List[List[float]]) -> bytes:
    """Render the velocity field as a transparent-overlay RGBA PNG."""
    rows: List[bytes] = []
    for y in range(GRID_H):
        row = bytearray(GRID_W * 4)
        for x in range(GRID_W):
            r, g, b, a = velocity_to_rgba(velocity[y][x])
            if a:
                i = x * 4
                row[i] = r
                row[i + 1] = g
                row[i + 2] = b
                row[i + 3] = a
        rows.append(bytes(row))
    return encode_png(GRID_W, GRID_H, rows)


def render_visit_png(aoi_id: str, visit_index: int) -> bytes:
    """
    Render the grayscale SAR backscatter image of a single Sentinel-1 visit.
    Each visit gets its own speckle realisation (and a small brightness bias),
    exactly like separate acquisitions of the same frame.
    """
    rng = random.Random(_seed_from(f"sar:{aoi_id}:{visit_index}"))
    brightness_bias = 0.01 * ((visit_index % 5) - 2)

    dark_blobs = [(rng.uniform(0.1, 0.9), rng.uniform(0.15, 0.85), rng.uniform(20, 40)) for _ in range(2)]
    bright_blob = (rng.uniform(0.2, 0.8), rng.uniform(0.2, 0.8), rng.uniform(14, 26))

    rows: List[bytes] = []
    for y in range(GRID_H):
        fy = y / (GRID_H - 1)
        row = bytearray(GRID_W * 4)
        for x in range(GRID_W):
            fx = x / (GRID_W - 1)
            # Terrain-ish structure + speckle
            brightness = (
                0.50
                + brightness_bias
                + 0.15 * math.sin((fx + fy) * 21.0)
                + 0.07 * math.sin(fx * 44.0) * math.sin(fy * 39.0)
                + rng.gauss(0.0, 0.11)
            )
            for cx, cy, sigma in dark_blobs:
                d2 = ((fx - cx) * GRID_W) ** 2 + ((fy - cy) * GRID_H) ** 2
                brightness -= 0.38 * math.exp(-d2 / (2.0 * sigma * sigma))
            cx, cy, sigma = bright_blob
            d2 = ((fx - cx) * GRID_W) ** 2 + ((fy - cy) * GRID_H) ** 2
            brightness += 0.30 * math.exp(-d2 / (2.0 * sigma * sigma))
            gray = int(_clamp(brightness, 0.04, 0.96) * 255)
            i = x * 4
            row[i] = gray
            row[i + 1] = gray
            row[i + 2] = gray
            row[i + 3] = 255
        rows.append(bytes(row))
    return encode_png(GRID_W, GRID_H, rows)


def render_sar_png(aoi_id: str) -> bytes:
    """Render a synthetic grayscale SAR backscatter image (amplitude)."""
    return render_visit_png(aoi_id, 0)


# ---------------------------------------------------------------------------
# Products / time series
# ---------------------------------------------------------------------------

def get_product_meta(aoi: Dict[str, Any]) -> Dict[str, Any]:
    aoi_id = aoi["id"]
    # Derive the bbox from the polygon ring (coordinates are NW, NE, SE, SW...)
    lons = [c[0] for c in aoi["geometry"]["coordinates"][0]]
    lats = [c[1] for c in aoi["geometry"]["coordinates"][0]]
    west, east, south, north = min(lons), max(lons), min(lats), max(lats)
    end = PRODUCT_END
    start = PRODUCT_START
    return {
        "id": f"demo-{aoi_id}",
        "aoi_id": aoi_id,
        "satellite": "SENTINEL-1 (SYNTHETIC DEMO)",
        "product_type": "SLC",
        "bands": ["sar", "velocity"],
        "width": GRID_W,
        "height": GRID_H,
        "bbox": [round(west, 4), round(south, 4), round(east, 4), round(north, 4)],
        "acquisition": {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d")},
        "generated_at": _now_iso(),
    }


def get_time_series(aoi_id: str, lat: float, lng: float) -> Dict[str, Any]:
    """
    Deterministic cumulative LOS displacement series for a point
    (linear trend + annual seasonal signal + noise), in millimetres.
    """
    rng = random.Random(_seed_from(f"ts:{aoi_id}:{lat:.4f}:{lng:.4f}"))
    trend = rng.uniform(-28.0, 6.0)  # mm/yr, mostly subsidence for the demo
    seasonal_amp = rng.uniform(1.0, 3.0)
    noise_sigma = 0.7

    points: List[Dict[str, Any]] = []
    displacement = 0.0
    end = datetime(2026, 9, 1, tzinfo=timezone.utc)
    for i in range(12):
        month = end - timedelta(days=30 * (11 - i))
        displacement += trend / 12.0
        displacement += seasonal_amp * (math.cos(2 * math.pi * i / 12.0) - math.cos(2 * math.pi * (i - 1) / 12.0))
        displacement += rng.gauss(0.0, noise_sigma)
        points.append({
            "date": month.strftime("%Y-%m"),
            "displacement_mm": round(displacement, 2),
        })

    return {
        "aoi_id": aoi_id,
        "location": {"lat": round(lat, 5), "lng": round(lng, 5)},
        "unit": "mm (LOS)",
        "velocity_mm_per_yr": round(trend, 2),
        "points": points,
    }


def get_summary(bbox: List[float], aoi_id: str) -> Dict[str, Any]:
    """Aggregate statistics used by the frontend header / legend."""
    collection = get_anomaly_collection(bbox, aoi_id)
    features = collection["features"]
    if not features:
        return {
            "aoi_id": aoi_id,
            "n_anomalies": 0,
            "max_subsidence_mm_yr": None,
            "max_uplift_mm_yr": None,
            "total_area_m2": 0,
            "top_features": [],
        }
    velocities = [f["properties"]["mean_velocity"] for f in features]
    return {
        "aoi_id": aoi_id,
        "n_anomalies": len(features),
        "max_subsidence_mm_yr": min(velocities + [0.0]),
        "max_uplift_mm_yr": max(velocities + [0.0]),
        "total_area_m2": sum(f["properties"]["area_m2"] for f in features),
        "top_features": [f["properties"] for f in features[:5]],
    }


# ---------------------------------------------------------------------------
# Multi-visit stack overlay: movement in an arbitrary period
# ---------------------------------------------------------------------------
def get_acquisitions(aoi_id: str) -> List[Dict[str, Any]]:
    """
    Every synthetic Sentinel-1 visit (12-day revisit) for an AOI: id, stack
    index and acquisition date, ordered chronologically.
    """
    return [
        {
            "id": f"{aoi_id}-S1-{i + 1:03d}",
            "index": i,
            "date": (PRODUCT_START + timedelta(days=i * ACQUISITION_CYCLE_DAYS)).strftime("%Y-%m-%d"),
        }
        for i in range(N_ACQUISITIONS)
    ]


def select_acquisitions(
    aoi_id: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], str, str]:
    """
    Select the visits falling inside [start, end] (ISO dates, inclusive).

    Raises ValueError when the dates are malformed, inverted, or the period
    holds fewer than two visits - nothing to overlay then.
    """
    acquisitions = get_acquisitions(aoi_id)
    start = start or acquisitions[0]["date"]
    end = end or acquisitions[-1]["date"]
    try:
        start_date = datetime.strptime(start, "%Y-%m-%d").date()
        end_date = datetime.strptime(end, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Dates must be formatted as YYYY-MM-DD") from exc
    if start_date > end_date:
        raise ValueError(f"Period start {start} is after period end {end}")

    selected = [a for a in acquisitions if start <= a["date"] <= end]
    if len(selected) < 2:
        raise ValueError(
            f"Period {start} -> {end} contains {len(selected)} Sentinel-1 visit(s); "
            "at least 2 are required to measure movement"
        )
    return selected, start, end


# Movement magnitude colour ramp (cumulative mm over the period -> RGBA).
# Deliberately a single magenta/violet family so period movement reads
# differently from the red (subsidence) / blue (uplift) velocity overlay.
MOVEMENT_RAMP: List[Tuple[float, Tuple[int, int, int], int]] = [
    (1.0, (150, 110, 255), 115),
    (4.0, (205, 60, 235), 160),
    (10.0, (255, 45, 165), 200),
    (18.0, (255, 140, 60), 225),
    (28.0, (255, 235, 140), 240),
]


def movement_to_rgba(m: float) -> Tuple[int, int, int, int]:
    """Map a cumulative movement magnitude (mm) to RGBA (transparent when flat)."""
    mag = abs(m)
    if mag < MOVEMENT_RAMP[0][0]:
        return (0, 0, 0, 0)
    for i in range(len(MOVEMENT_RAMP) - 1):
        m0, c0, a0 = MOVEMENT_RAMP[i]
        m1, c1, a1 = MOVEMENT_RAMP[i + 1]
        if mag <= m1:
            t = (mag - m0) / (m1 - m0)
            r, g, b = _lerp_color(c0, c1, t)
            alpha = int(a0 + (a1 - a0) * t)
            return (r, g, b, alpha)
    _, c, a = MOVEMENT_RAMP[-1]
    return (c[0], c[1], c[2], a)


def render_movement_png(movement: List[List[float]], coherence: List[List[float]]) -> bytes:
    """
    Render the stacked period-movement field as a transparent RGBA overlay;
    alpha is damped by coherence so decorrelated patches read as uncertain.
    """
    rows: List[bytes] = []
    for y in range(GRID_H):
        row = bytearray(GRID_W * 4)
        for x in range(GRID_W):
            r, g, b, a = movement_to_rgba(movement[y][x])
            if a:
                i = x * 4
                row[i] = r
                row[i + 1] = g
                row[i + 2] = b
                row[i + 3] = max(0, int(a * (0.55 + 0.45 * coherence[y][x])))
        rows.append(bytes(row))
    return encode_png(GRID_W, GRID_H, rows)


def compute_period_movement(
    bbox: List[float],
    aoi_id: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Tuple[List[List[float]], List[List[float]], Dict[str, Any]]:
    """
    Overlay the co-registered stack of Sentinel-1 visits inside the period and
    estimate the cumulative LOS movement of every pixel over that period.

    The synthetic displacement of a pixel at visit k is

        d_k = v * t_k + amp * cos(w * t_k + phase) + pattern * n_k

    (linear trend + seasonal cycle + visit-to-visit decorrelation noise). The
    movement rate is recovered with a per-pixel ordinary-least-squares fit of
    d_k against t_k - a lightweight stack inversion in the spirit of MintPy.
    Because the model is linear in its per-pixel coefficients, every visit only
    contributes scalars (time/seasonal/noise sums), so the whole N-visit stack
    collapses into a single pass over the grid - the rasters never have to be
    held in memory at once.

    Returns (movement_mm, coherence, meta).
    """
    visits, start, end = select_acquisitions(aoi_id, start, end)
    velocity, coherence = generate_fields(bbox, aoi_id)

    omega = 2.0 * math.pi / DAYS_PER_YEAR
    noise_rng = random.Random(_seed_from(f"visit:{aoi_id}"))
    times: List[float] = []
    cos_t: List[float] = []
    sin_t: List[float] = []
    noise: List[float] = []
    for visit in visits:
        days = (datetime.strptime(visit["date"], "%Y-%m-%d").date() - PRODUCT_START.date()).days
        times.append(days / DAYS_PER_YEAR)
        cos_t.append(math.cos(omega * days))
        sin_t.append(math.sin(omega * days))
        noise.append(noise_rng.gauss(0.0, 1.0))

    n = len(times)
    t_mean = sum(times) / n
    s_tt = sum((t - t_mean) ** 2 for t in times)
    # How the seasonal cycle and the visit noise leak into the fitted rate for
    # *this* selection of visits - three stack-wide scalars.
    alpha_cos = sum((t - t_mean) * c for t, c in zip(times, cos_t)) / s_tt
    alpha_sin = sum((t - t_mean) * s for t, s in zip(times, sin_t)) / s_tt
    alpha_noise = sum((t - t_mean) * e for t, e in zip(times, noise)) / s_tt
    dt_years = max(times) - min(times)

    # Spatial pattern of the decorrelation noise: smooth (spatially correlated)
    # plus a little white texture, deterministic per AOI.
    pattern_rng = random.Random(_seed_from(f"visit-noise:{aoi_id}"))
    f1 = pattern_rng.uniform(40.0, 90.0)
    f2 = pattern_rng.uniform(40.0, 90.0)
    p1 = pattern_rng.uniform(0.0, 2.0 * math.pi)
    p2 = pattern_rng.uniform(0.0, 2.0 * math.pi)

    # Same physical threshold as the anomaly detector (10 mm/yr equivalent),
    # floored so very short periods do not flag pure noise.
    threshold_mm = max(MIN_MOVEMENT_MM, VELOCITY_THRESHOLD_MM_YR * dt_years)

    movement: List[List[float]] = [[0.0] * GRID_W for _ in range(GRID_H)]
    for y in range(GRID_H):
        fy = y / (GRID_H - 1)
        v_row = velocity[y]
        m_row = movement[y]
        for x in range(GRID_W):
            fx = x / (GRID_W - 1)
            amp = SEASONAL_AMPLITUDE_MM * (0.55 + 0.45 * math.sin(3.1 * fx + 2.3 * fy + 0.7))
            phase = 2.0 * math.pi * (0.6 * fx + 0.4 * fy)
            u = amp * math.cos(phase)        # coefficient of cos(w t)
            w_v = -amp * math.sin(phase)     # coefficient of sin(w t)
            pattern = VISIT_NOISE_SIGMA_MM * (
                0.7 * math.sin(f1 * fx + p1) * math.sin(f2 * fy + p2)
                + 0.3 * pattern_rng.gauss(0.0, 1.0)
            )
            rate = v_row[x] + u * alpha_cos + w_v * alpha_sin + pattern * alpha_noise
            m_row[x] = round(rate * dt_years, 3)

    period_days = (
        datetime.strptime(end, "%Y-%m-%d").date() - datetime.strptime(start, "%Y-%m-%d").date()
    ).days
    meta = {
        "aoi_id": aoi_id,
        "period": {"start": start, "end": end, "days": period_days},
        "acquisitions": visits,
        "n_acquisitions": n,
        "dt_years": dt_years,
        "threshold_mm": round(threshold_mm, 2),
    }
    return movement, coherence, meta


def detect_movement_areas(
    movement: List[List[float]],
    coherence: List[List[float]],
    bbox: List[float],
    aoi_id: str,
    meta: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Threshold the stacked movement field, extract connected regions and return
    GeoJSON polygons for the areas that moved the most during the period.
    Ranked by peak |movement| (rank 1 = highest movement).
    """
    threshold = meta["threshold_mm"]
    mask = [
        [abs(movement[y][x]) >= threshold and coherence[y][x] >= COHERENCE_THRESHOLD
         for x in range(GRID_W)]
        for y in range(GRID_H)
    ]
    labels = _label_components(mask)

    n_labels = max((max(row) for row in labels), default=0)
    if n_labels == 0:
        return []

    px_area = _pixel_area_m2(bbox)
    seed = _seed_from(f"movement:{aoi_id}")
    dt_years = meta["dt_years"]
    period = meta["period"]
    n_acquisitions = meta["n_acquisitions"]
    features: List[Dict[str, Any]] = []

    for label in range(1, n_labels + 1):
        xs: List[int] = []
        ys: List[int] = []
        m_sum = 0.0
        m_peak = 0.0
        m_peak_signed = 0.0
        c_sum = 0.0
        count = 0
        for y in range(GRID_H):
            row = labels[y]
            for x in range(GRID_W):
                if row[x] != label:
                    continue
                xs.append(x)
                ys.append(y)
                m = movement[y][x]
                c_sum += coherence[y][x]
                m_sum += m
                count += 1
                if abs(m) > abs(m_peak):
                    m_peak = m
                    m_peak_signed = m
        if count < MIN_MOVEMENT_AREA_PIXELS:
            continue

        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        corners = [(x0, y0), (x1 + 1, y0), (x1 + 1, y1 + 1), (x0, y1 + 1), (x0, y0)]
        ring = [list(_pixel_to_lonlat(bbox, cx, cy)) for cx, cy in corners]

        mean_m = m_sum / count
        mean_c = c_sum / count
        confidence = _clamp(mean_c * 0.85 + (0.1 if count > 80 else 0.03), 0.05, 0.99)

        features.append({
            "type": "Feature",
            "properties": {
                "id": f"movement-{seed:08x}-{len(features) + 1:02d}",
                "aoi_id": aoi_id,
                "event_type": "uplift" if mean_m > 0 else "subsidence",
                "period_start": period["start"],
                "period_end": period["end"],
                "n_acquisitions": n_acquisitions,
                "area_m2": round(count * px_area),
                "mean_movement_mm": round(mean_m, 2),
                "peak_movement_mm": round(m_peak_signed, 2),
                "mean_velocity_mm_yr": round(mean_m / dt_years, 2),
                "coherence": round(mean_c, 2),
                "confidence": round(confidence, 2),
                "pixel_count": count,
                "detected_at": _now_iso(),
            },
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        })

    features.sort(key=lambda f: abs(f["properties"]["peak_movement_mm"]), reverse=True)
    features = features[:MAX_MOVEMENT_AREAS]
    for rank, feature in enumerate(features, start=1):
        feature["properties"]["rank"] = rank
    return features


def get_movement_analysis(
    bbox: List[float],
    aoi_id: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Overlay every Sentinel-1 visit in the period, estimate per-pixel movement
    and return the ranked areas that moved the most, plus period statistics.
    """
    movement, coherence, meta = compute_period_movement(bbox, aoi_id, start, end)
    features = detect_movement_areas(movement, coherence, bbox, aoi_id, meta)

    peak_x = peak_y = 0
    peak_v = 0.0
    for y in range(GRID_H):
        row = movement[y]
        for x in range(GRID_W):
            if abs(row[x]) > abs(peak_v):
                peak_v = row[x]
                peak_x, peak_y = x, y
    lon, lat = _pixel_to_lonlat(bbox, peak_x + 0.5, peak_y + 0.5)

    return {
        "aoi_id": aoi_id,
        "unit": "mm (LOS)",
        "period": meta["period"],
        "n_acquisitions": meta["n_acquisitions"],
        "acquisitions": meta["acquisitions"],
        "threshold_mm": meta["threshold_mm"],
        "stats": {
            "max_movement_mm": round(peak_v, 2),
            "max_movement_magnitude_mm": round(abs(peak_v), 2),
            "peak_velocity_mm_yr": round(peak_v / meta["dt_years"], 2),
            "peak_location": {"lat": round(lat, 5), "lng": round(lon, 5)},
            "n_areas": len(features),
            "total_area_m2": sum(f["properties"]["area_m2"] for f in features),
        },
        "areas": {"type": "FeatureCollection", "features": features},
    }


def get_movement_image(
    bbox: List[float],
    aoi_id: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> bytes:
    """Render the stacked period-movement heatmap as an RGBA PNG overlay."""
    movement, coherence, _ = compute_period_movement(bbox, aoi_id, start, end)
    return render_movement_png(movement, coherence)
