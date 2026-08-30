import os
import pytest
from starlette.testclient import TestClient
from app.main import app


client = TestClient(app)
SAMPLE_KML_PATH = "contours_1m (1).kml"


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_contour_sample():
    if not os.path.exists(SAMPLE_KML_PATH):
        pytest.skip("Sample KML missing")

    with open(SAMPLE_KML_PATH, "rb") as f:
        files = {"file": (os.path.basename(SAMPLE_KML_PATH), f, "application/vnd.google-earth.kml+xml")}
        data = {"resolution_m": "10.0", "min_catchment_area_m2": "500.0"}
        response = client.post("/analyzeContour", files=files, data=data)

    assert response.status_code == 200
    json_resp = response.json()

    assert json_resp["contour_interval_m"] == 1.0
    assert json_resp["elevation_range_m"] == [267.0, 298.0]
    assert json_resp["total_contour_lines"] > 2000
    assert json_resp["grid_resolution_m"] == 10.0
    assert len(json_resp["grid_shape"]) == 2
    assert all(d > 0 for d in json_resp["grid_shape"])
    assert json_resp["resolution_auto_adjusted"] is False

    pond = json_resp["pond_site"]
    assert "lat" in pond and "lon" in pond and "elevation_m" in pond
    assert pond["flow_accumulation_cells"] > 0

    catchment = json_resp["catchment"]
    assert catchment["area_m2"] >= 500.0
    assert catchment["area_hectares"] > 0
    assert catchment["max_slope_pct"] >= catchment["mean_slope_pct"]
    assert catchment["min_elevation_m"] <= catchment["max_elevation_m"]
    assert catchment["relief_m"] >= 0
    assert catchment["watershed_cell_count"] > 0
    assert catchment["boundary_geojson"]["type"] == "Polygon"

    assert "processing_time_ms" in json_resp


def test_analyze_contour_invalid_extension():
    files = {"file": ("test.txt", b"dummy content", "text/plain")}
    response = client.post("/analyzeContour", files=files)
    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["detail"]


def test_analyze_contour_corrupt_file():
    files = {"file": ("corrupt.kml", b"Not XML at all", "application/vnd.google-earth.kml+xml")}
    response = client.post("/analyzeContour", files=files)
    assert response.status_code == 400
    assert "Invalid or unparseable contour file" in response.json()["detail"]
