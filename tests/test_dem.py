import os
import pytest
from app.parser import parse_contour_file, ContourDataset, Polyline
from app.dem import build_dem, DEMGrid


SAMPLE_KML_PATH = "contours_1m (1).kml"


def test_build_dem_from_sample():
    if not os.path.exists(SAMPLE_KML_PATH):
        pytest.skip("Sample KML missing")

    dataset = parse_contour_file(SAMPLE_KML_PATH)
    dem = build_dem(dataset, target_resolution_m=10.0)

    assert isinstance(dem, DEMGrid)
    assert dem.grid.ndim == 2
    assert dem.epsg_code == 32644  # UTM Zone 44N
    assert dem.grid.min() >= 267.0
    assert dem.grid.max() <= 298.0
    assert not dem.resolution_auto_adjusted


def test_build_dem_auto_coarsening():
    if not os.path.exists(SAMPLE_KML_PATH):
        pytest.skip("Sample KML missing")

    dataset = parse_contour_file(SAMPLE_KML_PATH)
    # Force max_cells to a very low limit to trigger auto coarsening
    dem = build_dem(dataset, target_resolution_m=2.0, max_cells=1000)

    assert dem.resolution_auto_adjusted
    assert dem.resolution_m > 2.0
    assert dem.grid.size <= 2500  # reasonably close to limited max_cells


def test_build_dem_empty_dataset():
    empty_ds = ContourDataset(polylines=[])
    with pytest.raises(ValueError, match="no polylines"):
        build_dem(empty_ds)
