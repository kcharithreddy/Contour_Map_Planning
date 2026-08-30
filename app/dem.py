from dataclasses import dataclass
import math
from typing import Tuple
import numpy as np
from scipy.interpolate import griddata
from pyproj import Transformer
from app.parser import ContourDataset


@dataclass
class DEMGrid:
    grid: np.ndarray
    x_coords: np.ndarray
    y_coords: np.ndarray
    resolution_m: float
    epsg_code: int
    bounds_utm: Tuple[float, float, float, float]  # min_x, min_y, max_x, max_y
    resolution_auto_adjusted: bool
    transformer_to_wgs84: Transformer
    transformer_from_wgs84: Transformer


def build_dem(
    dataset: ContourDataset,
    target_resolution_m: float = 10.0,
    max_cells: int = 250000
) -> DEMGrid:
    """
    Build a raster Digital Elevation Model (DEM) from a ContourDataset.
    Reprojects WGS84 (lon, lat) points to auto-detected local UTM CRS (EPSG:326xx/327xx).
    Enforces memory safety by auto-coarsening resolution if total grid cells exceeds max_cells.
    """
    if not dataset.polylines:
        raise ValueError("ContourDataset contains no polylines")

    all_lons = []
    all_lats = []
    all_zs = []

    for poly in dataset.polylines:
        for lon, lat in poly.points:
            all_lons.append(lon)
            all_lats.append(lat)
            all_zs.append(poly.elevation)

    if not all_lons:
        raise ValueError("No coordinate points found in ContourDataset")

    mean_lon = float(np.mean(all_lons))
    mean_lat = float(np.mean(all_lats))

    # Determine UTM EPSG code
    utm_zone = int((mean_lon + 180) / 6) + 1
    epsg_code = (32600 + utm_zone) if mean_lat >= 0 else (32700 + utm_zone)

    transformer_from_wgs84 = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg_code}", always_xy=True)
    transformer_to_wgs84 = Transformer.from_crs(f"EPSG:{epsg_code}", "EPSG:4326", always_xy=True)

    xs, ys = transformer_from_wgs84.transform(all_lons, all_lats)

    min_x, max_x = float(np.min(xs)), float(np.max(xs))
    min_y, max_y = float(np.min(ys)), float(np.max(ys))

    width_m = max_x - min_x
    height_m = max_y - min_y

    if width_m <= 0 or height_m <= 0:
        raise ValueError("Invalid spatial extent for DEM grid construction")

    resolution_m = max(1.0, float(target_resolution_m))
    resolution_auto_adjusted = False

    # Check cell count limit for memory safety on 512MB RAM
    estimated_cols = math.ceil(width_m / resolution_m) + 1
    estimated_rows = math.ceil(height_m / resolution_m) + 1
    total_cells = estimated_cols * estimated_rows

    if total_cells > max_cells:
        # Scale resolution up to stay within max_cells budget
        scale_factor = math.sqrt(total_cells / max_cells)
        resolution_m = round(resolution_m * scale_factor, 2)
        resolution_auto_adjusted = True

    x_coords = np.arange(min_x, max_x + resolution_m, resolution_m)
    y_coords = np.arange(max_y, min_y - resolution_m, -resolution_m)

    grid_x, grid_y = np.meshgrid(x_coords, y_coords)
    points = np.column_stack((xs, ys))
    values = np.array(all_zs, dtype=np.float64)

    # Interpolate DEM grid
    grid = griddata(points, values, (grid_x, grid_y), method='linear')

    # Fill NaN values along borders / outer convex hull with nearest-neighbor interpolation
    nan_mask = np.isnan(grid)
    if np.any(nan_mask):
        grid_nearest = griddata(points, values, (grid_x, grid_y), method='nearest')
        grid[nan_mask] = grid_nearest[nan_mask]

    return DEMGrid(
        grid=grid,
        x_coords=x_coords,
        y_coords=y_coords,
        resolution_m=resolution_m,
        epsg_code=epsg_code,
        bounds_utm=(min_x, min_y, max_x, max_y),
        resolution_auto_adjusted=resolution_auto_adjusted,
        transformer_to_wgs84=transformer_to_wgs84,
        transformer_from_wgs84=transformer_from_wgs84
    )
