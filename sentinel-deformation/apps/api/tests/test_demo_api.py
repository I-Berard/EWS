"""
Integration tests for the demo API endpoints.

Uses FastAPI's TestClient (httpx) against the real app, covering AOI listing,
anomaly collection shape, image serving (PNG magic bytes + caching), summary,
and time series - including error paths.
"""

import struct

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

AOI = "demo-rwanda-1"
MISSING = "does-not-exist"


class TestRootAndHealth:
    def test_health(self):
        res = client.get("/health")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "ok"

    def test_root_lists_endpoints(self):
        res = client.get("/")
        assert res.status_code == 200
        assert "/api/demo/aois" in res.json()["endpoints"]


class TestAois:
    def test_list_aois(self):
        res = client.get("/api/demo/aois")
        assert res.status_code == 200
        aois = res.json()
        assert len(aois) >= 1
        ids = [a["id"] for a in aois]
        assert AOI in ids
        for aoi in aois:
            assert aoi["geometry"]["type"] == "Polygon"

    def test_get_single_aoi(self):
        res = client.get(f"/api/demo/aois/{AOI}")
        assert res.status_code == 200
        assert res.json()["id"] == AOI

    def test_get_missing_aoi_404(self):
        res = client.get(f"/api/demo/aois/{MISSING}")
        assert res.status_code == 404


class TestProductMeta:
    def test_product_meta(self):
        res = client.get(f"/api/demo/aois/{AOI}/product")
        assert res.status_code == 200
        meta = res.json()
        assert meta["aoi_id"] == AOI
        assert len(meta["bbox"]) == 4
        west, south, east, north = meta["bbox"]
        assert west < east and south < north


class TestAnomalies:
    def test_anomaly_collection(self):
        res = client.get(f"/api/demo/aois/{AOI}/anomalies")
        assert res.status_code == 200
        collection = res.json()
        assert collection["type"] == "FeatureCollection"
        features = collection["features"]
        assert len(features) > 0

        peaks = [abs(f["properties"]["max_velocity"]) for f in features]
        assert peaks == sorted(peaks, reverse=True)
        assert [f["properties"]["rank"] for f in features] == list(range(1, len(features) + 1))

    def test_anomalies_for_missing_aoi(self):
        res = client.get(f"/api/demo/aois/{MISSING}/anomalies")
        assert res.status_code == 404


class TestSummary:
    def test_summary_matches_anomalies(self):
        anomalies = client.get(f"/api/demo/aois/{AOI}/anomalies").json()
        summary = client.get(f"/api/demo/aois/{AOI}/summary").json()

        assert summary["aoi_id"] == AOI
        assert summary["n_anomalies"] == len(anomalies["features"])
        assert summary["total_area_m2"] == sum(
            f["properties"]["area_m2"] for f in anomalies["features"]
        )
        assert summary["max_subsidence_mm_yr"] <= 0

    def test_summary_missing_aoi(self):
        res = client.get(f"/api/demo/aois/{MISSING}/summary")
        assert res.status_code == 404


class TestTimeSeries:
    def test_timeseries_valid_point(self):
        res = client.get(f"/api/demo/aois/{AOI}/timeseries", params={"lat": -1.95, "lng": 30.06})
        assert res.status_code == 200
        body = res.json()
        assert body["aoi_id"] == AOI
        assert len(body["points"]) == 12
        assert all("date" in p and "displacement_mm" in p for p in body["points"])

    def test_timeseries_missing_aoi(self):
        res = client.get(f"/api/demo/aois/{MISSING}/timeseries", params={"lat": -1.95, "lng": 30.06})
        assert res.status_code == 404

    def test_timeseries_requires_params(self):
        res = client.get(f"/api/demo/aois/{AOI}/timeseries")
        assert res.status_code == 422


class TestImageServing:
    @pytest.mark.parametrize("kind", ["sar", "velocity"])
    def test_image_is_png(self, kind):
        res = client.get(f"/api/demo/aois/{AOI}/images/{kind}")
        assert res.status_code == 200
        assert res.headers["content-type"] == "image/png"
        assert "max-age" in res.headers.get("cache-control", "")
        # PNG magic number
        assert res.content[:8] == b"\x89PNG\r\n\x1a\n"
        # IHDR: width/height must match the engine grid
        width, height = struct.unpack(">II", res.content[16:24])
        from app import demo_engine
        assert (width, height) == (demo_engine.GRID_W, demo_engine.GRID_H)

    def test_unknown_image_kind_404(self):
        res = client.get(f"/api/demo/aois/{AOI}/images/bogus")
        assert res.status_code == 404

    def test_image_missing_aoi(self):
        res = client.get(f"/api/demo/aois/{MISSING}/images/sar")
        assert res.status_code == 404


class TestAcquisitions:
    def test_visit_schedule(self):
        res = client.get(f"/api/demo/aois/{AOI}/acquisitions")
        assert res.status_code == 200
        body = res.json()
        assert body["aoi_id"] == AOI
        assert body["cycle_days"] == 12
        acq = body["acquisitions"]
        assert len(acq) >= 10
        dates = [a["date"] for a in acq]
        assert dates == sorted(dates)
        assert [a["index"] for a in acq] == list(range(len(acq)))

    def test_acquisitions_missing_aoi(self):
        res = client.get(f"/api/demo/aois/{MISSING}/acquisitions")
        assert res.status_code == 404


class TestMovement:
    def test_full_mission_default_period(self):
        res = client.get(f"/api/demo/aois/{AOI}/movement")
        assert res.status_code == 200
        body = res.json()
        assert body["aoi_id"] == AOI
        assert body["n_acquisitions"] >= 2
        assert body["n_acquisitions"] == len(body["acquisitions"])
        assert body["period"]["start"] <= body["period"]["end"]
        assert body["unit"] == "mm (LOS)"
        assert body["threshold_mm"] > 0
        assert "max_movement_magnitude_mm" in body["stats"]

    def test_explicit_period(self):
        full = client.get(f"/api/demo/aois/{AOI}/movement").json()
        res = client.get(
            f"/api/demo/aois/{AOI}/movement",
            params={"start": "2026-03-01", "end": "2026-09-01"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["period"]["start"] == "2026-03-01"
        assert body["period"]["end"] == "2026-09-01"
        assert body["n_acquisitions"] < full["n_acquisitions"]
        for acq in body["acquisitions"]:
            assert "2026-03-01" <= acq["date"] <= "2026-09-01"

    def test_areas_are_ranked_feature_collection(self):
        body = client.get(f"/api/demo/aois/{AOI}/movement").json()
        areas = body["areas"]
        assert areas["type"] == "FeatureCollection"
        features = areas["features"]
        peaks = [abs(f["properties"]["peak_movement_mm"]) for f in features]
        assert peaks == sorted(peaks, reverse=True)
        assert [f["properties"]["rank"] for f in features] == list(range(1, len(features) + 1))
        assert body["stats"]["n_areas"] == len(features)

    def test_movement_missing_aoi(self):
        res = client.get(f"/api/demo/aois/{MISSING}/movement")
        assert res.status_code == 404

    def test_period_without_enough_visits_422(self):
        res = client.get(
            f"/api/demo/aois/{AOI}/movement",
            params={"start": "2026-09-01", "end": "2026-09-02"},
        )
        assert res.status_code == 422
        assert "visit" in res.json()["detail"]

    def test_inverted_period_422(self):
        res = client.get(
            f"/api/demo/aois/{AOI}/movement",
            params={"start": "2026-09-01", "end": "2026-01-01"},
        )
        assert res.status_code == 422

    def test_malformed_date_422(self):
        res = client.get(
            f"/api/demo/aois/{AOI}/movement",
            params={"start": "not-a-date", "end": "2026-01-01"},
        )
        assert res.status_code == 422


class TestMovementImage:
    def test_movement_image_is_png(self):
        res = client.get(
            f"/api/demo/aois/{AOI}/images/movement",
            params={"start": "2026-01-01", "end": "2026-09-01"},
        )
        assert res.status_code == 200
        assert res.headers["content-type"] == "image/png"
        assert "max-age" in res.headers.get("cache-control", "")
        assert res.content[:8] == b"\x89PNG\r\n\x1a\n"
        width, height = struct.unpack(">II", res.content[16:24])
        from app import demo_engine
        assert (width, height) == (demo_engine.GRID_W, demo_engine.GRID_H)

    def test_movement_image_bad_period_422(self):
        res = client.get(
            f"/api/demo/aois/{AOI}/images/movement",
            params={"start": "2026-09-01", "end": "2026-09-02"},
        )
        assert res.status_code == 422

    def test_movement_image_missing_aoi(self):
        res = client.get(f"/api/demo/aois/{MISSING}/images/movement")
        assert res.status_code == 404


class TestVisitImage:
    @pytest.mark.parametrize("index", [0, 17, 35])
    def test_visit_image_is_png(self, index):
        res = client.get(f"/api/demo/aois/{AOI}/images/visit/{index}")
        assert res.status_code == 200
        assert res.headers["content-type"] == "image/png"
        assert res.content[:8] == b"\x89PNG\r\n\x1a\n"
        width, height = struct.unpack(">II", res.content[16:24])
        from app import demo_engine
        assert (width, height) == (demo_engine.GRID_W, demo_engine.GRID_H)

    def test_visits_differ_from_each_other(self):
        first = client.get(f"/api/demo/aois/{AOI}/images/visit/0").content
        later = client.get(f"/api/demo/aois/{AOI}/images/visit/1").content
        assert first != later  # separate speckle realisations per visit

    def test_visit_index_out_of_range_404(self):
        assert client.get(f"/api/demo/aois/{AOI}/images/visit/999").status_code == 404
        assert client.get(f"/api/demo/aois/{AOI}/images/visit/-1").status_code == 404

    def test_visit_image_missing_aoi(self):
        res = client.get(f"/api/demo/aois/{MISSING}/images/visit/0")
        assert res.status_code == 404
