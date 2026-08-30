from dataclasses import dataclass
from collections import deque
from typing import Dict, Any
import numpy as np
from shapely.geometry import box, MultiPolygon
from shapely.ops import unary_union

from app.dem import DEMGrid
from app.terrain import TerrainAnalysis, D8_DR, D8_DC, D8_CODE_TO_INDEX


@dataclass
class PondSite:
    lat: float
    lon: float
    elevation_m: float
    grid_r: int
    grid_c: int
    flow_accumulation_cells: int


@dataclass
class Catchment:
    area_m2: float
    area_hectares: float
    mean_slope_pct: float
    max_slope_pct: float
    min_elevation_m: float
    max_elevation_m: float
    relief_m: float
    watershed_cell_count: int
    boundary_geojson: Dict[str, Any]


@dataclass
class PondAnalysisResult:
    pond_site: PondSite
    catchment: Catchment


def select_pond_and_delineate_catchment(
    dem_grid: DEMGrid,
    terrain: TerrainAnalysis,
    min_catchment_area_m2: float = 500.0
) -> PondAnalysisResult:
    """
    Select an optimal pond location (outlet cell) based on flow accumulation, slope,
    and interior placement, then trace upstream cells to delineate the catchment area.
    """
    nrows, ncols = dem_grid.grid.shape
    res = dem_grid.resolution_m
    cell_area_m2 = res * res

    # Edge margin (cells) to avoid selecting outlet on grid edge
    margin = max(2, min(nrows // 10, ncols // 10))

    mask = np.zeros((nrows, ncols), dtype=bool)
    mask[margin:nrows-margin, margin:ncols-margin] = True

    # Filter cells meeting min_catchment_area_m2
    valid_mask = mask & (terrain.flow_accumulation * cell_area_m2 >= min_catchment_area_m2)

    if not np.any(valid_mask):
        # Fallback to any interior cell with max flow accumulation
        valid_mask = mask
        if not np.any(valid_mask):
            raise ValueError("DEM extent too small to select interior pond site")

    # Score candidate cells: high flow accumulation, low slope, lower elevation
    min_elev, max_elev = float(dem_grid.grid.min()), float(dem_grid.grid.max())
    elev_range = max(1.0, max_elev - min_elev)

    scores = np.zeros((nrows, ncols), dtype=np.float64)

    # Heuristic score calculation over valid candidates
    valid_r, valid_c = np.where(valid_mask)
    for r, c in zip(valid_r, valid_c):
        acc = terrain.flow_accumulation[r, c]
        elev = terrain.filled_dem[r, c]
        slope = terrain.slopes[r, c]

        # Favor high flow accumulation, lower relative elevation, and flat terrain
        norm_elev = (max_elev - elev) / elev_range
        score = np.log1p(acc) * (1.0 + norm_elev) / (1.0 + slope / 10.0)
        scores[r, c] = score

    best_r, best_c = np.unravel_index(np.argmax(scores), dem_grid.grid.shape)

    outlet_x = dem_grid.x_coords[best_c]
    outlet_y = dem_grid.y_coords[best_r]
    outlet_lon, outlet_lat = dem_grid.transformer_to_wgs84.transform(outlet_x, outlet_y)
    outlet_elev = float(terrain.filled_dem[best_r, best_c])

    pond_site = PondSite(
        lat=round(float(outlet_lat), 6),
        lon=round(float(outlet_lon), 6),
        elevation_m=round(outlet_elev, 2),
        grid_r=int(best_r),
        grid_c=int(best_c),
        flow_accumulation_cells=int(terrain.flow_accumulation[best_r, best_c])
    )

    # Trace upstream catchment area starting from chosen outlet cell
    watershed_cells = set()
    queue = deque([(best_r, best_c)])
    watershed_cells.add((best_r, best_c))

    while queue:
        r, c = queue.popleft()
        for i in range(8):
            nr, nc = r + D8_DR[i], c + D8_DC[i]
            if 0 <= nr < nrows and 0 <= nc < ncols and (nr, nc) not in watershed_cells:
                code = terrain.flow_dir[nr, nc]
                if code in D8_CODE_TO_INDEX:
                    idx = D8_CODE_TO_INDEX[code]
                    # Check if (nr, nc) flows directly into (r, c)
                    if nr + D8_DR[idx] == r and nc + D8_DC[idx] == c:
                        watershed_cells.add((nr, nc))
                        queue.append((nr, nc))

    # Construct boundary polygon using Shapely
    half = res / 2.0
    cell_boxes = [
        box(
            dem_grid.x_coords[c] - half,
            dem_grid.y_coords[r] - half,
            dem_grid.x_coords[c] + half,
            dem_grid.y_coords[r] + half
        )
        for r, c in watershed_cells
    ]

    poly = unary_union(cell_boxes)

    # Dissolve small pixel corner gaps
    if poly.geom_type == 'MultiPolygon':
        poly = poly.buffer(0.01)

    if isinstance(poly, MultiPolygon):
        poly = max(poly.geoms, key=lambda g: g.area)

    simplified_poly = poly.simplify(res * 0.1)

    # Convert polygon exterior boundary coordinates to WGS84 (lon, lat)
    ext_coords = list(simplified_poly.exterior.coords)
    wgs84_coords = []
    for x, y in ext_coords:
        lon, lat = dem_grid.transformer_to_wgs84.transform(x, y)
        wgs84_coords.append([round(float(lon), 6), round(float(lat), 6)])

    geojson_polygon = {
        "type": "Polygon",
        "coordinates": [wgs84_coords]
    }

    area_m2 = float(len(watershed_cells) * cell_area_m2)
    area_ha = float(area_m2 / 10000.0)

    ws_slopes = [terrain.slopes[r, c] for r, c in watershed_cells]
    ws_elevs  = [terrain.filled_dem[r, c] for r, c in watershed_cells]

    mean_slope   = float(np.mean(ws_slopes))
    max_slope    = float(np.max(ws_slopes))
    min_elev_ws  = float(np.min(ws_elevs))
    max_elev_ws  = float(np.max(ws_elevs))
    relief       = round(max_elev_ws - min_elev_ws, 2)

    catchment = Catchment(
        area_m2=round(area_m2, 2),
        area_hectares=round(area_ha, 4),
        mean_slope_pct=round(mean_slope, 2),
        max_slope_pct=round(max_slope, 2),
        min_elevation_m=round(min_elev_ws, 2),
        max_elevation_m=round(max_elev_ws, 2),
        relief_m=relief,
        watershed_cell_count=len(watershed_cells),
        boundary_geojson=geojson_polygon
    )

    return PondAnalysisResult(
        pond_site=pond_site,
        catchment=catchment
    )
