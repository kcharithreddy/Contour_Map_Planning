import os
import pytest
from app.parser import parse_contour_file, ContourDataset, Polyline


SAMPLE_KML_PATH = "contours_1m (1).kml"


def test_parse_sample_kml():
    if not os.path.exists(SAMPLE_KML_PATH):
        pytest.skip(f"Sample KML file {SAMPLE_KML_PATH} not found")

    dataset = parse_contour_file(SAMPLE_KML_PATH)
    assert isinstance(dataset, ContourDataset)
    assert len(dataset.polylines) > 2000
    assert dataset.min_elevation == 267.0
    assert dataset.max_elevation == 298.0
    assert dataset.contour_interval == 1.0


def test_parse_invalid_path():
    with pytest.raises(ValueError, match="File not found"):
        parse_contour_file("non_existent_file.kml")


def test_parse_corrupt_kml(tmp_path):
    bad_file = tmp_path / "bad.kml"
    bad_file.write_text("This is not valid XML")
    with pytest.raises(ValueError):
        parse_contour_file(str(bad_file))
