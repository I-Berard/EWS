"""
Unit tests for the synthetic InSAR demo engine.

Validates the geometry of the synthetic fields, the anomaly-detection
ranking/thresholding logic, PNG encoding correctness, and time-series
determinism - all pure stdlib, no heavy geo dependencies required.
"""

import struct
import zlib

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
