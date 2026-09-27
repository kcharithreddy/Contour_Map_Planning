from dataclasses import dataclass, field
import os
import zipfile
from typing import List, Tuple, Optional
from lxml import etree


@dataclass
class Polyline:
    elevation: float
    points: List[Tuple[float, float]]  # (longitude, latitude)


@dataclass
class ContourDataset:
    polylines: List[Polyline] = field(default_factory=list)
    min_elevation: float = 0.0
    max_elevation: float = 0.0
    contour_interval: float = 1.0


def _extract_elevation(placemark: etree._Element) -> Optional[float]:
    """
    Robustly extract elevation float value from a Placemark.
    Checks:
    1. Placemark <name> text (exact float check)
    2. ExtendedData / SimpleData fields (with known elevation names or pure float text)
    3. 3D coordinates z-component
    """
    # 1. Check <name>
    name_elem = placemark.find('.//{*}name')
    if name_elem is not None and name_elem.text:
        text = name_elem.text.strip()
        try:
            val = float(text)
            return val
        except ValueError:
            pass

    # 2. Check ExtendedData / SimpleData or Data
    elev_keys = {'elevation', 'elev', 'contour', 'height', 'z', 'level'}
    for sd in placemark.findall('.//{*}SimpleData'):
        name_attr = sd.attrib.get('name', '').lower()
        if name_attr in elev_keys:
            if sd.text:
                try:
                    return float(sd.text.strip())
                except ValueError:
                    pass

    for d in placemark.findall('.//{*}Data'):
        name_attr = d.attrib.get('name', '').lower()
        val_elem = d.find('{*}value')
        if name_attr in elev_keys and val_elem is not None and val_elem.text:
            try:
                return float(val_elem.text.strip())
            except ValueError:
                pass

    # 3. Check 3D coordinates z values
    coords_elem = placemark.find('.//{*}coordinates')
    if coords_elem is not None and coords_elem.text:
        raw_coords = coords_elem.text.strip().split()
        if raw_coords:
            first_pt = raw_coords[0].split(',')
            if len(first_pt) >= 3:
                try:
                    return float(first_pt[2])
                except ValueError:
                    pass

    return None


def _parse_coordinates(coords_text: str) -> List[Tuple[float, float]]:
    """
    Parse KML coordinates string into list of (lon, lat) tuples.
    """
    points = []
    tokens = coords_text.strip().split()
    for token in tokens:
        parts = token.split(',')
        if len(parts) >= 2:
            try:
                lon = float(parts[0])
                lat = float(parts[1])
                points.append((lon, lat))
            except ValueError:
                continue
    return points


def parse_contour_file(file_path: str) -> ContourDataset:
    """
    Parse KML or KMZ file and return a ContourDataset object.
    Raises ValueError for corrupt or unsupported files.
    """
    if not os.path.exists(file_path):
        raise ValueError(f"File not found: {file_path}")

    kml_bytes = None

    if file_path.lower().endswith('.kmz') or zipfile.is_zipfile(file_path):
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                kml_names = [n for n in zf.namelist() if n.lower().endswith('.kml')]
                if not kml_names:
                    raise ValueError("No .kml file found inside .kmz archive")
                doc_kml = next((n for n in kml_names if os.path.basename(n).lower() == 'doc.kml'), kml_names[0])
                kml_bytes = zf.read(doc_kml)
        except zipfile.BadZipFile as e:
            raise ValueError(f"Corrupt KMZ archive: {str(e)}") from e
    else:
        try:
            with open(file_path, 'rb') as f:
                kml_bytes = f.read()
        except Exception as e:
            raise ValueError(f"Error reading KML file: {str(e)}") from e

    if not kml_bytes:
        raise ValueError("Empty file provided")

    try:
        parser = etree.XMLParser(recover=True, huge_tree=True)
        root = etree.fromstring(kml_bytes, parser=parser)
    except Exception as e:
        raise ValueError(f"Failed to parse XML: {str(e)}") from e

    if root is None:
        raise ValueError("Invalid KML XML structure")

    placemarks = root.findall('.//{*}Placemark')
    if not placemarks:
        raise ValueError("No Placemarks found in KML file")

    polylines: List[Polyline] = []

    for placemark in placemarks:
        # Ignore outer boundary polygon features
        if placemark.find('.//{*}Polygon') is not None:
            continue

        elev = _extract_elevation(placemark)
        if elev is None:
            continue

        coords_elems = placemark.findall('.//{*}LineString/{*}coordinates')
        if not coords_elems:
            coords_elems = placemark.findall('.//{*}coordinates')

        for ce in coords_elems:
            if ce.text:
                pts = _parse_coordinates(ce.text)
                if len(pts) >= 1:
                    polylines.append(Polyline(elevation=elev, points=pts))

    if not polylines:
        raise ValueError("No valid contour polylines found with elevation data")

    elevations = sorted(list({p.elevation for p in polylines}))
    min_elev = min(elevations)
    max_elev = max(elevations)

    contour_interval = 1.0
    if len(elevations) > 1:
        diffs = [round(elevations[i+1] - elevations[i], 4) for i in range(len(elevations)-1)]
        positive_diffs = [d for d in diffs if d > 0]
        if positive_diffs:
            positive_diffs.sort()
            contour_interval = positive_diffs[len(positive_diffs) // 2]

    return ContourDataset(
        polylines=polylines,
        min_elevation=min_elev,
        max_elevation=max_elev,
        contour_interval=contour_interval
    )


def get_dataset_bounds(dataset: ContourDataset) -> Tuple[float, float, float, float]:
    """
    Returns (min_lon, min_lat, max_lon, max_lat) for the dataset.
    """
    if not dataset.polylines:
        raise ValueError("ContourDataset contains no polylines")

    min_lon = float('inf')
    max_lon = float('-inf')
    min_lat = float('inf')
    max_lat = float('-inf')

    for poly in dataset.polylines:
        for lon, lat in poly.points:
            if lon < min_lon: min_lon = lon
            if lon > max_lon: max_lon = lon
            if lat < min_lat: min_lat = lat
            if lat > max_lat: max_lat = lat

    return min_lon, min_lat, max_lon, max_lat


def filter_dataset_by_bounds(
    dataset: ContourDataset,
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    buffer_ratio: float = 0.08
) -> ContourDataset:
    """
    Clips and filters a ContourDataset to only include contour geometry within
    [min_lon, min_lat, max_lon, max_lat] with a margin buffer for DEM edge consistency.
    """
    d_lon = max_lon - min_lon
    d_lat = max_lat - min_lat
    buf_lon = max(0.0001, d_lon * buffer_ratio)
    buf_lat = max(0.0001, d_lat * buffer_ratio)

    b_min_lon = min_lon - buf_lon
    b_max_lon = max_lon + buf_lon
    b_min_lat = min_lat - buf_lat
    b_max_lat = max_lat + buf_lat

    filtered_polylines: List[Polyline] = []

    for poly in dataset.polylines:
        # Segment points that lie inside the buffered box
        current_segment = []
        for lon, lat in poly.points:
            if b_min_lon <= lon <= b_max_lon and b_min_lat <= lat <= b_max_lat:
                current_segment.append((lon, lat))
            else:
                if len(current_segment) >= 2:
                    filtered_polylines.append(Polyline(elevation=poly.elevation, points=current_segment))
                current_segment = []
        if len(current_segment) >= 2:
            filtered_polylines.append(Polyline(elevation=poly.elevation, points=current_segment))

    if not filtered_polylines:
        raise ValueError("No contour lines found inside the selected bounding box. Please select an area overlapping the contour map.")

    elevations = sorted(list({p.elevation for p in filtered_polylines}))
    min_elev = min(elevations)
    max_elev = max(elevations)

    interval = dataset.contour_interval
    if len(elevations) > 1:
        diffs = [round(elevations[i+1] - elevations[i], 4) for i in range(len(elevations)-1)]
        pos = [d for d in diffs if d > 0]
        if pos:
            pos.sort()
            interval = pos[len(pos) // 2]

    return ContourDataset(
        polylines=filtered_polylines,
        min_elevation=min_elev,
        max_elevation=max_elev,
        contour_interval=interval
    )

