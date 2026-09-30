"""
Unit tests for the synthetic InSAR demo engine.

Validates the geometry of the synthetic fields, the anomaly-detection
ranking/thresholding logic, PNG encoding correctness, and time-series
determinism - all pure stdlib, no heavy geo dependencies required.
"""

import struct
import zlib
from datetime import datetime, timedelta

import pytest

from app import demo_engine as engine

BBOX = [29.9, -2.0, 30.2, -1.8]
AOI_ID = "demo-rwanda-1"


@pytest.fixture(scope="module")
def fields():
    return engine.generate_fields(BBOX, AOI_ID)


# ---------------------------------------------------------------------------
# Synthetic fields
# ---------------------------------------------------------------------------

class TestGenerateFields:
    def test_grid_dimensions(self, fields):
        velocity, coherence = fields
        assert len(velocity) == engine.GRID_H
        assert len(velocity[0]) == engine.GRID_W
        assert len(coherence) == engine.GRID_H

    def test_velocity_ranges(self, fields):
        velocity, _ = fields
        flat = [v for row in velocity for v in row]
        assert min(flat) >= -40.0
        assert max(flat) <= 40.0
        # The demo is seeded to contain real subsidence bowls
        assert min(flat) <= -engine.VELOCITY_THRESHOLD_MM_YR

    def test_coherence_in_unit_range(self, fields):
        _, coherence = fields
        flat = [c for row in coherence for c in row]
        assert min(flat) >= 0.0
        assert max(flat) <= 1.0

    def test_deterministic_for_same_aoi(self):
        v1, c1 = engine.generate_fields(BBOX, AOI_ID)
        v2, c2 = engine.generate_fields(BBOX, AOI_ID)
        assert v1 == v2
        assert c1 == c2

    def test_differs_between_aois(self):
        v1, _ = engine.generate_fields(BBOX, AOI_ID)
        v2, _ = engine.generate_fields(BBOX, "demo-rwanda-2")
        assert v1 != v2


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

class TestDetectAnomalies:
    def test_finds_ranked_anomalies(self, fields):
        velocity, coherence = fields
        features = engine.detect_anomalies(velocity, coherence, BBOX, AOI_ID)
        assert len(features) > 0

        props = [f["properties"] for f in features]
        # Ranked by peak |velocity| descending
        peaks = [abs(p["max_velocity"]) for p in props]
        assert peaks == sorted(peaks, reverse=True)
        # Rank property matches position
        assert [p["rank"] for p in props] == list(range(1, len(props) + 1))
        # All exceed the velocity threshold
        assert all(abs(p["max_velocity"]) >= engine.VELOCITY_THRESHOLD_MM_YR for p in props)

    def test_feature_schema(self, fields):
        velocity, coherence = fields
        features = engine.detect_anomalies(velocity, coherence, BBOX, AOI_ID)
        for f in features:
            assert f["type"] == "Feature"
            assert f["geometry"]["type"] == "Polygon"
            ring = f["geometry"]["coordinates"][0]
            assert len(ring) >= 4
            assert ring[0] == ring[-1]  # closed ring
            for lon, lat in ring:
                assert BBOX[0] - 0.01 <= lon <= BBOX[2] + 0.01
                assert BBOX[1] - 0.01 <= lat <= BBOX[3] + 0.01
            p = f["properties"]
            for key in ("id", "aoi_id", "event_type", "area_m2", "mean_velocity",
                        "max_velocity", "coherence", "confidence", "rank", "detected_at"):
                assert key in p
            assert p["event_type"] in ("subsidence", "uplift")
            assert 0.0 <= p["confidence"] <= 1.0
            assert 0.0 <= p["coherence"] <= 1.0

    def test_feature_collection(self, fields):
        velocity, coherence = fields
        collection = engine.get_anomaly_collection(BBOX, AOI_ID)
        assert collection["type"] == "FeatureCollection"

    def test_bbox_isolation(self):
        """A hotspot in a separate AOI seed must not leak into another."""
        v1, c1 = engine.generate_fields(BBOX, "alpha")
        v2, c2 = engine.generate_fields(BBOX, "beta")
        f1 = engine.detect_anomalies(v1, c1, BBOX, "alpha")
        f2 = engine.detect_anomalies(v2, c2, BBOX, "beta")
        ids1 = {f["properties"]["id"] for f in f1}
        ids2 = {f["properties"]["id"] for f in f2}
        assert ids1.isdisjoint(ids2)


# ---------------------------------------------------------------------------
# PNG encoding
# ---------------------------------------------------------------------------

def _parse_png_chunks(data: bytes):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    chunks = []
    offset = 8
    while offset < len(data):
        (length,) = struct.unpack(">I", data[offset:offset + 4])
        tag = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + length]
        (crc,) = struct.unpack(">I", data[offset + 8 + length:offset + 12 + length])
        assert crc == zlib.crc32(tag + payload) & 0xFFFFFFFF, f"bad CRC for {tag}"
        chunks.append((tag, payload))
        offset += 12 + length
    return chunks


class TestPngEncoding:
    def test_valid_png_structure(self, fields):
        velocity, _ = fields
        png = engine.render_velocity_png(velocity)
        chunks = _parse_png_chunks(png)
        tags = [tag for tag, _ in chunks]
        assert tags[0] == b"IHDR"
        assert tags[-1] == b"IEND"
        assert b"IDAT" in tags

        width, height, bit_depth, color_type = struct.unpack(">IIBB", chunks[0][1][:10])
        assert (width, height) == (engine.GRID_W, engine.GRID_H)
        assert bit_depth == 8
        assert color_type == 6  # RGBA

    def test_sar_png_is_opaque_grayscale(self):
        png = engine.render_sar_png(AOI_ID)
        chunks = _parse_png_chunks(png)
        width, height, _, color_type = struct.unpack(">IIBB", chunks[0][1][:10])
        assert (width, height) == (engine.GRID_W, engine.GRID_H)
        assert color_type == 6

    def test_velocity_colormap_extremes(self):
        # Transparent when flat, opaque-ish at the extreme
        r, g, b, a = engine.velocity_to_rgba(0.0)
        assert a == 0
        r, g, b, a = engine.velocity_to_rgba(-25.0)
        assert a > 100
        r, g, b, a = engine.velocity_to_rgba(+25.0)
        assert b > r  # uplift ramp is blue


# ---------------------------------------------------------------------------
# Time series
# ---------------------------------------------------------------------------

class TestTimeSeries:
    def test_deterministic_per_point(self):
        a = engine.get_time_series(AOI_ID, -1.95, 30.06)
        b = engine.get_time_series(AOI_ID, -1.95, 30.06)
        assert a == b

    def test_schema_and_length(self):
        ts = engine.get_time_series(AOI_ID, -1.95, 30.06)
        assert len(ts["points"]) == 12
        assert ts["unit"] == "mm (LOS)"
        assert ts["location"] == {"lat": -1.95, "lng": 30.06}
        dates = [p["date"] for p in ts["points"]]
        assert dates == sorted(dates)
        assert all(set(p) == {"date", "displacement_mm"} for p in ts["points"])

    def test_varying_locations_differ(self):
        a = engine.get_time_series(AOI_ID, -1.95, 30.06)
        b = engine.get_time_series(AOI_ID, -1.90, 30.10)
        assert a["points"] != b["points"]

    def test_velocity_field_consistency(self):
        ts = engine.get_time_series(AOI_ID, -1.95, 30.06)
        first, last = ts["points"][0], ts["points"][-1]
        approx_trend = (last["displacement_mm"] - first["displacement_mm"]) / 11 * 12
        assert abs(approx_trend - ts["velocity_mm_per_yr"]) < 15  # seasonal+noise slack


# ---------------------------------------------------------------------------
# Summary + product metadata
# ---------------------------------------------------------------------------

class TestSummaryAndProduct:
    def test_summary_shape(self, fields):
        summary = engine.get_summary(BBOX, AOI_ID)
        assert summary["aoi_id"] == AOI_ID
        assert summary["n_anomalies"] > 0
        assert summary["max_subsidence_mm_yr"] is not None and summary["max_subsidence_mm_yr"] < 0
        assert len(summary["top_features"]) <= 5
        assert summary["total_area_m2"] > 0

    def test_product_meta(self):
        aoi = {
            "id": "demo-rwanda-1",
            "geometry": {"type": "Polygon",
                         "coordinates": [[[29.9, -2.0], [30.2, -2.0], [30.2, -1.8], [29.9, -1.8], [29.9, -2.0]]]},
        }
        meta = engine.get_product_meta(aoi)
        assert meta["aoi_id"] == "demo-rwanda-1"
        assert meta["bbox"] == [29.9, -2.0, 30.2, -1.8]
        assert meta["width"] == engine.GRID_W
        assert meta["height"] == engine.GRID_H
        assert meta["acquisition"]["start"] < meta["acquisition"]["end"]


# ---------------------------------------------------------------------------
# Sentinel-1 acquisition schedule
# ---------------------------------------------------------------------------

class TestAcquisitions:
    def test_schedule_shape(self):
        acq = engine.get_acquisitions(AOI_ID)
        assert len(acq) == engine.N_ACQUISITIONS
        assert [a["index"] for a in acq] == list(range(engine.N_ACQUISITIONS))
        assert len({a["id"] for a in acq}) == len(acq)
        for a in acq:
            datetime.strptime(a["date"], "%Y-%m-%d")  # ISO format

    def test_dates_sorted_with_12_day_revisit(self):
        dates = [a["date"] for a in engine.get_acquisitions(AOI_ID)]
        assert dates == sorted(dates)
        parsed = [datetime.strptime(d, "%Y-%m-%d") for d in dates]
        deltas = [(b - a).days for a, b in zip(parsed, parsed[1:])]
        assert deltas == [engine.ACQUISITION_CYCLE_DAYS] * len(deltas)

    def test_deterministic(self):
        assert engine.get_acquisitions(AOI_ID) == engine.get_acquisitions(AOI_ID)

    def test_product_window_matches_schedule(self):
        aoi = {
            "id": AOI_ID,
            "geometry": {"type": "Polygon",
                         "coordinates": [[[29.9, -2.0], [30.2, -2.0], [30.2, -1.8], [29.9, -1.8], [29.9, -2.0]]]},
        }
        meta = engine.get_product_meta(aoi)
        acq = engine.get_acquisitions(AOI_ID)
        assert meta["acquisition"]["start"] == acq[0]["date"]
        assert meta["acquisition"]["end"] == acq[-1]["date"]


class TestSelectAcquisitions:
    def test_defaults_to_full_mission(self):
        selected, start, end = engine.select_acquisitions(AOI_ID)
        assert len(selected) == engine.N_ACQUISITIONS
        assert start == selected[0]["date"]
        assert end == selected[-1]["date"]

    def test_filters_by_period(self):
        selected, start, end = engine.select_acquisitions(AOI_ID, "2026-01-01", "2026-03-31")
        assert start == "2026-01-01" and end == "2026-03-31"
        assert len(selected) >= 2
        assert all("2026-01-01" <= a["date"] <= "2026-03-31" for a in selected)

    def test_requires_two_visits(self):
        with pytest.raises(ValueError, match="at least 2"):
            engine.select_acquisitions(AOI_ID, "2026-09-01", "2026-09-01")

    def test_rejects_inverted_period(self):
        with pytest.raises(ValueError, match="after period end"):
            engine.select_acquisitions(AOI_ID, "2026-09-01", "2026-01-01")

    def test_rejects_bad_date_format(self):
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            engine.select_acquisitions(AOI_ID, "01/01/2026", "2026-06-01")


# ---------------------------------------------------------------------------
# Period movement analysis (stack overlay)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def movement_analysis():
    return engine.get_movement_analysis(BBOX, AOI_ID)


def _strip_timestamps(result):
    """detected_at is wall-clock time, so it is excluded from equality checks."""
    for feature in result["areas"]["features"]:
        feature["properties"].pop("detected_at", None)
    return result


class TestMovementAnalysis:
    def test_schema(self, movement_analysis):
        result = movement_analysis
        assert result["aoi_id"] == AOI_ID
        assert result["unit"] == "mm (LOS)"
        for key in ("period", "n_acquisitions", "acquisitions", "threshold_mm", "stats", "areas"):
            assert key in result
        assert result["period"]["start"] <= result["period"]["end"]
        assert result["period"]["days"] >= 0
        assert result["n_acquisitions"] >= 2
        assert result["n_acquisitions"] == len(result["acquisitions"])
        stats = result["stats"]
        for key in ("max_movement_mm", "max_movement_magnitude_mm", "peak_velocity_mm_yr",
                    "peak_location", "n_areas", "total_area_m2"):
            assert key in stats
        assert stats["max_movement_magnitude_mm"] == abs(stats["max_movement_mm"])

    def test_uses_only_visits_inside_period(self, movement_analysis):
        for acq in movement_analysis["acquisitions"]:
            assert movement_analysis["period"]["start"] <= acq["date"] <= movement_analysis["period"]["end"]

    def test_peak_location_inside_bbox(self, movement_analysis):
        loc = movement_analysis["stats"]["peak_location"]
        west, south, east, north = BBOX
        assert west <= loc["lng"] <= east
        assert south <= loc["lat"] <= north

    def test_deterministic(self):
        a = engine.get_movement_analysis(BBOX, AOI_ID, "2026-01-01", "2026-06-01")
        b = engine.get_movement_analysis(BBOX, AOI_ID, "2026-01-01", "2026-06-01")
        assert _strip_timestamps(a) == _strip_timestamps(b)

    def test_areas_ranked_by_peak_movement(self, movement_analysis):
        features = movement_analysis["areas"]["features"]
        assert movement_analysis["stats"]["n_areas"] == len(features)
        peaks = [abs(f["properties"]["peak_movement_mm"]) for f in features]
        assert peaks == sorted(peaks, reverse=True)
        assert [f["properties"]["rank"] for f in features] == list(range(1, len(features) + 1))
        # Every detected area cleared the period threshold
        for f in features:
            assert abs(f["properties"]["peak_movement_mm"]) >= movement_analysis["threshold_mm"] - 0.02

    def test_area_feature_schema(self, movement_analysis):
        for f in movement_analysis["areas"]["features"]:
            assert f["type"] == "Feature"
            assert f["geometry"]["type"] == "Polygon"
            ring = f["geometry"]["coordinates"][0]
            assert len(ring) >= 4
            assert ring[0] == ring[-1]
            for lon, lat in ring:
                assert BBOX[0] - 0.01 <= lon <= BBOX[2] + 0.01
                assert BBOX[1] - 0.01 <= lat <= BBOX[3] + 0.01
            p = f["properties"]
            for key in ("id", "aoi_id", "event_type", "period_start", "period_end",
                        "n_acquisitions", "area_m2", "mean_movement_mm", "peak_movement_mm",
                        "mean_velocity_mm_yr", "coherence", "confidence", "pixel_count",
                        "rank", "detected_at"):
                assert key in p
            assert p["event_type"] in ("subsidence", "uplift")
            assert p["period_start"] <= p["period_end"]
            assert 0.0 <= p["confidence"] <= 1.0

    def test_shorter_period_uses_fewer_visits_and_lower_threshold(self, movement_analysis):
        short = engine.get_movement_analysis(BBOX, AOI_ID, "2026-04-01", "2026-09-01")
        assert short["n_acquisitions"] < movement_analysis["n_acquisitions"]
        assert short["period"]["days"] < movement_analysis["period"]["days"]
        assert short["threshold_mm"] < movement_analysis["threshold_mm"]
        # Cumulative movement grows with the length of the period
        assert (short["stats"]["max_movement_magnitude_mm"]
                <= movement_analysis["stats"]["max_movement_magnitude_mm"])

    def test_error_paths(self):
        with pytest.raises(ValueError):
            engine.get_movement_analysis(BBOX, AOI_ID, "2026-09-01", "2026-09-01")
        with pytest.raises(ValueError):
            engine.get_movement_analysis(BBOX, AOI_ID, "2026-06-01", "2026-01-01")

    def test_area_ids_do_not_leak_between_aois(self):
        f1 = engine.get_movement_analysis(BBOX, "alpha")["areas"]["features"]
        f2 = engine.get_movement_analysis(BBOX, "beta")["areas"]["features"]
        ids1 = {f["properties"]["id"] for f in f1}
        ids2 = {f["properties"]["id"] for f in f2}
        assert ids1.isdisjoint(ids2)


# ---------------------------------------------------------------------------
# Movement heatmap PNG
# ---------------------------------------------------------------------------

def _decode_rgba(data: bytes):
    """Decode an engine-produced RGBA PNG into (width, height, rows)."""
    chunks = dict(_parse_png_chunks(data))
    width, height = struct.unpack(">II", chunks[b"IHDR"][:8])
    raw = zlib.decompress(chunks[b"IDAT"])
    stride = width * 4 + 1
    rows = [raw[i * stride + 1:(i + 1) * stride] for i in range(height)]
    return width, height, rows


class TestMovementPng:
    def test_valid_rgba_png(self):
        png = engine.get_movement_image(BBOX, AOI_ID, "2026-01-01", "2026-06-01")
        width, height, rows = _decode_rgba(png)
        assert (width, height) == (engine.GRID_W, engine.GRID_H)
        assert len(rows) == engine.GRID_H
        chunks = _parse_png_chunks(png)
        assert chunks[0][0] == b"IHDR"
        assert chunks[-1][0] == b"IEND"

    def test_ramp_extremes(self):
        # Flat terrain stays transparent
        assert engine.movement_to_rgba(0.0)[3] == 0
        assert engine.movement_to_rgba(0.5)[3] == 0
        # Strong movement renders in the magenta family with high alpha
        r, g, b, a = engine.movement_to_rgba(25.0)
        assert a > 200
        assert r == 255 and g > 150

    def test_alpha_grows_with_magnitude(self):
        alphas = [engine.movement_to_rgba(m)[3] for m in (2.0, 6.0, 12.0, 25.0)]
        assert alphas == sorted(alphas)

    def test_coherence_damps_alpha(self):
        movement = [[20.0] * engine.GRID_W for _ in range(engine.GRID_H)]
        confident = engine.render_movement_png(movement, [[0.95] * engine.GRID_W for _ in range(engine.GRID_H)])
        decorrelated = engine.render_movement_png(movement, [[0.10] * engine.GRID_W for _ in range(engine.GRID_H)])
        _, _, rows_strong = _decode_rgba(confident)
        _, _, rows_weak = _decode_rgba(decorrelated)
        assert rows_strong[0][3] > rows_weak[0][3] > 0
