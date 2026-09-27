"""
Golden-value regression tests for the /analyzeContour endpoint
using the actual sample file: contours_1m (1).kml

These tests lock in the exact output the pipeline produces for the
known sample file. If any algorithm or parameter changes cause a
drift in the results, these tests will catch it immediately.
"""
import os
import pytest
from starlette.testclient import TestClient
from app.main import app

client = TestClient(app)

SAMPLE_KML_PATH = "contours_1m (1).kml"

# ---------------------------------------------------------------------------
# Shared fixture: run the API once and share the response across all tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def golden_response():
    """Send the real KML file to /analyzeContour and return the parsed JSON."""
    if not os.path.exists(SAMPLE_KML_PATH):
        pytest.skip("Sample KML file not found")

    with open(SAMPLE_KML_PATH, "rb") as f:
        files = {
            "contour_map": (os.path.basename(SAMPLE_KML_PATH), f,
                     "application/vnd.google-earth.kml+xml")
        }
        data = {"resolution_m": "10.0", "min_catchment_area_m2": "500.0"}
        response = client.post("/analyzeContour", files=files, data=data)

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )
    return response.json()


# ---------------------------------------------------------------------------
# TC-01: HTTP status & top-level response shape
# ---------------------------------------------------------------------------

def test_tc01_status_and_schema(golden_response):
    """TC-01: Response is HTTP 200 and contains all required top-level keys."""
    required_keys = [
        "contour_interval_m", "elevation_range_m", "total_contour_lines",
        "grid_resolution_m", "grid_shape", "resolution_auto_adjusted",
        "pond_site", "catchment", "processing_time_ms"
    ]
    for key in required_keys:
        assert key in golden_response, f"Missing top-level key: {key}"


# ---------------------------------------------------------------------------
# TC-02: Contour metadata (elevation range, interval, line count)
# ---------------------------------------------------------------------------

def test_tc02_contour_metadata(golden_response):
    """TC-02: Parser extracts correct elevation range, interval and line count."""
    assert golden_response["contour_interval_m"] == 1.0, \
        "Contour interval should be 1.0 m"
    assert golden_response["elevation_range_m"] == [267.0, 298.0], \
        "Elevation range must be [267.0, 298.0] for the sample file"
    assert golden_response["total_contour_lines"] == 2710, \
        "Expected exactly 2710 contour polylines"


# ---------------------------------------------------------------------------
# TC-03: DEM grid parameters
# ---------------------------------------------------------------------------

def test_tc03_dem_grid_parameters(golden_response):
    """TC-03: DEM is built at the requested resolution with no auto-adjustment."""
    assert golden_response["grid_resolution_m"] == 10.0, \
        "Grid resolution must equal requested 10.0 m"
    assert golden_response["grid_shape"] == [264, 326], \
        "DEM grid dimensions should be 264 rows × 326 cols at 10 m resolution"
    assert golden_response["resolution_auto_adjusted"] is False, \
        "Resolution should NOT be auto-adjusted for this file at 10 m"


# ---------------------------------------------------------------------------
# TC-04: Pond site location and elevation
# ---------------------------------------------------------------------------

def test_tc04_pond_site_location(golden_response):
    """TC-04: Pond outlet is within the known map extent and at correct elevation."""
    pond = golden_response["pond_site"]

    # Map extent from IMPLEMENTATION_PLAN: ~21.24°N – 21.26°N, ~81.28°E – 81.31°E
    assert 21.23 <= pond["lat"] <= 21.27, \
        f"Pond lat {pond['lat']} outside expected map bounds"
    assert 81.27 <= pond["lon"] <= 81.32, \
        f"Pond lon {pond['lon']} outside expected map bounds"

    # Elevation must be within the known range of the map
    assert 267.0 <= pond["elevation_m"] <= 298.0, \
        f"Pond elevation {pond['elevation_m']} outside map elevation range"

    # Golden exact values
    assert pond["lat"] == 21.244413
    assert pond["lon"] == 81.291006
    assert pond["elevation_m"] == 275.0


# ---------------------------------------------------------------------------
# TC-05: Pond site flow accumulation
# ---------------------------------------------------------------------------

def test_tc05_pond_flow_accumulation(golden_response):
    """TC-05: Flow accumulation at outlet matches catchment cell count."""
    pond = golden_response["pond_site"]
    catchment = golden_response["catchment"]

    assert pond["flow_accumulation_cells"] > 0, \
        "Flow accumulation must be positive"
    assert pond["flow_accumulation_cells"] == catchment["watershed_cell_count"], \
        "flow_accumulation_cells at outlet must equal watershed_cell_count"
    # Golden exact value
    assert pond["flow_accumulation_cells"] == 166


# ---------------------------------------------------------------------------
# TC-06: Catchment area values
# ---------------------------------------------------------------------------

def test_tc06_catchment_area(golden_response):
    """TC-06: Catchment area is self-consistent and matches golden values."""
    c = golden_response["catchment"]

    # Area consistency: hectares == area_m2 / 10000
    assert abs(c["area_m2"] / 10000.0 - c["area_hectares"]) < 0.01, \
        "area_hectares must equal area_m2 / 10000"

    # watershed_cell_count × cell_area (10m × 10m = 100 m²) == area_m2
    assert c["watershed_cell_count"] * 100.0 == c["area_m2"], \
        "area_m2 must equal watershed_cell_count × 100 m²"

    # Golden exact values
    assert c["area_m2"] == 16600.0
    assert c["area_hectares"] == 1.66
    assert c["watershed_cell_count"] == 166


# ---------------------------------------------------------------------------
# TC-07: Catchment slope and elevation statistics
# ---------------------------------------------------------------------------

def test_tc07_catchment_terrain_stats(golden_response):
    """TC-07: Slope and elevation stats are internally consistent and match golden."""
    c = golden_response["catchment"]

    # Slope sanity
    assert c["mean_slope_pct"] >= 0, "Mean slope cannot be negative"
    assert c["max_slope_pct"] >= c["mean_slope_pct"], \
        "Max slope must be >= mean slope"

    # Elevation sanity
    assert c["min_elevation_m"] <= c["max_elevation_m"], \
        "Min elevation must be <= max elevation"
    assert abs(c["relief_m"] - (c["max_elevation_m"] - c["min_elevation_m"])) < 0.01, \
        "relief_m must equal max_elevation_m - min_elevation_m"

    # Golden exact values
    assert c["mean_slope_pct"] == 3.58
    assert c["max_slope_pct"] == 10.93
    assert c["min_elevation_m"] == 275.0
    assert c["max_elevation_m"] == 281.0
    assert c["relief_m"] == 6.0


# ---------------------------------------------------------------------------
# TC-08: GeoJSON boundary polygon validity
# ---------------------------------------------------------------------------

def test_tc08_geojson_polygon(golden_response):
    """TC-08: Catchment boundary is a valid, closed GeoJSON Polygon."""
    geojson = golden_response["catchment"]["boundary_geojson"]

    assert geojson["type"] == "Polygon", "boundary_geojson type must be 'Polygon'"
    assert "coordinates" in geojson, "boundary_geojson must have coordinates"
    ring = geojson["coordinates"][0]
    assert len(ring) >= 4, "Polygon ring must have at least 4 points"

    # Polygon must be closed (first == last point)
    assert ring[0] == ring[-1], "GeoJSON polygon ring must be closed"

    # All coordinate pairs must be within the map's WGS84 extent
    for lon, lat in ring:
        assert 81.27 <= lon <= 81.32, f"Boundary lon {lon} out of map extent"
        assert 21.23 <= lat <= 21.27, f"Boundary lat {lat} out of map extent"

    # Golden: 39 coordinate pairs in the ring
    assert len(ring) == 39


# ---------------------------------------------------------------------------
# TC-09: Alternative resolution — coarser grid (20 m)
# ---------------------------------------------------------------------------

def test_tc09_coarser_resolution():
    """TC-09: At 20 m resolution the grid is smaller and results are still valid."""
    if not os.path.exists(SAMPLE_KML_PATH):
        pytest.skip("Sample KML file not found")

    with open(SAMPLE_KML_PATH, "rb") as f:
        files = {
            "contour_map": (os.path.basename(SAMPLE_KML_PATH), f,
                     "application/vnd.google-earth.kml+xml")
        }
        data = {"resolution_m": "20.0", "min_catchment_area_m2": "500.0"}
        response = client.post("/analyzeContour", files=files, data=data)

    assert response.status_code == 200
    body = response.json()

    assert body["grid_resolution_m"] == 20.0
    # At 20 m the grid should be roughly half the 10 m size in each dimension
    rows, cols = body["grid_shape"]
    assert rows < 264 and cols < 326, \
        "20 m grid must be smaller than 10 m grid"

    # Elevation metadata must still be correct
    assert body["elevation_range_m"] == [267.0, 298.0]
    assert body["catchment"]["area_m2"] >= 500.0


# ---------------------------------------------------------------------------
# TC-10: Larger min_catchment_area_m2 filter
# ---------------------------------------------------------------------------

def test_tc10_larger_min_area():
    """TC-10: Raising min_catchment_area_m2 still returns a valid pond >= that area."""
    if not os.path.exists(SAMPLE_KML_PATH):
        pytest.skip("Sample KML file not found")

    min_area = 5000.0

    with open(SAMPLE_KML_PATH, "rb") as f:
        files = {
            "contour_map": (os.path.basename(SAMPLE_KML_PATH), f,
                     "application/vnd.google-earth.kml+xml")
        }
        data = {"resolution_m": "10.0", "min_catchment_area_m2": str(min_area)}
        response = client.post("/analyzeContour", files=files, data=data)

    assert response.status_code == 200
    body = response.json()
    assert body["catchment"]["area_m2"] >= min_area, \
        f"Returned catchment area must be >= requested min {min_area} m²"


# ---------------------------------------------------------------------------
# TC-11: Invalid file extension returns 400
# ---------------------------------------------------------------------------

def test_tc11_invalid_extension():
    """TC-11: Uploading a .txt file returns HTTP 400 with correct error message."""
    files = {"contour_map": ("test.txt", b"dummy content", "text/plain")}
    response = client.post("/analyzeContour", files=files)

    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["detail"]


# ---------------------------------------------------------------------------
# TC-12: Corrupt / non-XML KML returns 400
# ---------------------------------------------------------------------------

def test_tc12_corrupt_kml():
    """TC-12: Uploading a .kml file with non-XML content returns HTTP 400."""
    files = {
        "contour_map": ("corrupt.kml", b"This is not XML at all",
                 "application/vnd.google-earth.kml+xml")
    }
    response = client.post("/analyzeContour", files=files)

    assert response.status_code == 400
    assert "Invalid or unparseable contour file" in response.json()["detail"]
