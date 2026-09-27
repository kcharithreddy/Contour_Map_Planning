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


def test_serve_frontend():
    response = client.get("/")
    assert response.status_code == 200
    assert "AI Pond Planner" in response.text
    assert "Select Land Area" in response.text


def test_dataset_bounds():
    response = client.get("/api/dataset-bounds")
    assert response.status_code == 200
    data = response.json()
    assert "min_lat" in data and "max_lat" in data
    assert "min_lon" in data and "max_lon" in data
    assert data["min_lat"] < data["max_lat"]
    assert data["min_lon"] < data["max_lon"]
    assert data["total_contours"] > 1000


def test_analyze_contour_sample():
    if not os.path.exists(SAMPLE_KML_PATH):
        pytest.skip("Sample KML missing")

    with open(SAMPLE_KML_PATH, "rb") as f:
        files = {"contour_map": (os.path.basename(SAMPLE_KML_PATH), f, "application/vnd.google-earth.kml+xml")}
        data = {"resolution_m": "10.0", "min_catchment_area_m2": "500.0", "runoff_coefficient": "0.40"}
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

    # Hydrology & Water Volume assertions
    assert "water_volume" in json_resp
    water = json_resp["water_volume"]
    assert water["expected_water_volume_m3"] > 0
    assert water["expected_water_volume_liters"] == water["expected_water_volume_m3"] * 1000.0
    assert water["runoff_coefficient"] == 0.40
    assert water["annual_rainfall_mm"] > 0

    sizing = water["pond_sizing"]
    assert sizing["recommended_depth_m"] > 0
    assert sizing["surface_area_m2"] > 0
    assert sizing["storage_capacity_m3"] > 0

    assert "processing_time_ms" in json_resp


def test_analyze_area_endpoint():
    # Test bounding box land area selection on the preloaded dataset
    payload = {
        "min_lat": 21.240,
        "min_lon": 81.285,
        "max_lat": 21.250,
        "max_lon": 81.298,
        "resolution_m": 10.0,
        "min_catchment_area_m2": 500.0,
        "runoff_coefficient": 0.40
    }
    response = client.post("/analyzeArea", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "selected_bounds" in data
    assert data["selected_bounds"]["min_lat"] == 21.240
    assert "pond_site" in data
    assert "catchment" in data
    assert "water_volume" in data
    assert data["catchment"]["area_m2"] >= 500.0
    assert data["water_volume"]["expected_water_volume_m3"] > 0
    assert data["processing_time_ms"] > 0


def test_analyze_contour_missing_file():
    """Verify 422 is returned when no file field is supplied."""
    response = client.post("/analyzeContour")
    assert response.status_code == 422


def test_analyze_contour_invalid_extension():
    files = {"contour_map": ("test.txt", b"dummy content", "text/plain")}
    response = client.post("/analyzeContour", files=files)
    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["detail"]


def test_analyze_contour_corrupt_file():
    files = {"contour_map": ("corrupt.kml", b"Not XML at all", "application/vnd.google-earth.kml+xml")}
    response = client.post("/analyzeContour", files=files)
    assert response.status_code == 400
    assert "Invalid or unparseable contour file" in response.json()["detail"]
