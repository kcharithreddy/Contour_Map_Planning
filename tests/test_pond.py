import os
import pytest
from app.parser import parse_contour_file
from app.dem import build_dem
from app.terrain import analyze_terrain
from app.pond import select_pond_and_delineate_catchment, PondAnalysisResult


SAMPLE_KML_PATH = "contours_1m (1).kml"


def test_select_pond_and_delineate_catchment_sample():
    if not os.path.exists(SAMPLE_KML_PATH):
        pytest.skip("Sample KML missing")

    dataset = parse_contour_file(SAMPLE_KML_PATH)
    dem = build_dem(dataset, target_resolution_m=10.0)
    terrain = analyze_terrain(dem)

    result = select_pond_and_delineate_catchment(dem, terrain, min_catchment_area_m2=500.0)

    assert isinstance(result, PondAnalysisResult)
    assert result.pond_site.lat > 0
    assert result.pond_site.lon > 0
    assert result.pond_site.elevation_m >= dataset.min_elevation
    assert result.catchment.area_m2 >= 500.0
    assert result.catchment.area_hectares > 0
    assert result.catchment.boundary_geojson["type"] == "Polygon"
    assert len(result.catchment.boundary_geojson["coordinates"][0]) > 3
