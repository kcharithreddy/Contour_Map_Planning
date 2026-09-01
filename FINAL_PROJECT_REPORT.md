# Final Project Submission Report: Contour-Based Pond Catchment Analysis API

---

## 1. Project Repository & Working Deployment Links

| Resource | Details / URL |
|---|---|
| **GitHub Repository** | [https://github.com/kcharithreddy/Contour_Map_Planning](https://github.com/kcharithreddy/Contour_Map_Planning) |
| **Working API Endpoint** | `http://10.1.75.51:3245/analyzeContour` |
| **Alternative Port Endpoint** | `http://10.1.75.51:3000/analyzeContour` |
| **Health Check URL** | `http://10.1.75.51:3245/health` |
| **Interactive Swagger Docs** | `http://10.1.75.51:3245/docs` |
| **OpenAPI Schema (JSON)** | `http://10.1.75.51:3245/openapi.json` |

---

## 2. Brief Explanation of Catchment Estimation Approach

The system implements a memory-efficient, pure-Python hydrological processing engine designed to transform 3D vector contour lines (KML/KMZ) into precise watershed metrics without relying on heavy desktop GIS dependencies.

### Technical Workflow:
1. **Streaming XML Parsing (`app/parser.py`)**: Uses `lxml` stream parsing to extract 3D coordinates from `LineString` and `Polygon` tags within `.kml` or `.kmz` archives. Computes contour intervals and elevation range `[min, max]`.
2. **Coordinate Transformation & DEM Construction (`app/dem.py`)**: Converts geographical WGS84 coordinates (`EPSG:4326`) to Universal Transverse Mercator metric projection (`UTM Zone 44N / EPSG:32644`). Interpolates sparse contour elevations onto a regular 2D grid using `scipy.interpolate.griddata`.
3. **Depression Filling & Hydrological Flow Routing (`app/terrain.py`)**:
   * Applies priority-flood algorithm to fill artificial sinks and depressions.
   * Computes D8 direction vectors (steepest descent vector among 8 neighboring cells).
   * Calculates cumulative flow accumulation matrix across the grid.
4. **Pond Site Selection & Catchment Boundary Delineation (`app/pond.py`)**:
   * Identifies optimal low-elevation outlet cells that meet or exceed `min_catchment_area_m2`.
   * Performs recursive reverse flow-tracing to delineate all upstream cells draining into the pond site.
   * Converts raster watershed boundary pixels back into a closed WGS84 GeoJSON Polygon.

---

## 3. Demonstration & Results (Sample File: `contours_1m (1).kml`)

Submitting `contours_1m (1).kml` to `POST http://10.1.75.51:3245/analyzeContour` yields the following verified analytical metrics:

### Executed Request:
* **File:** `contours_1m (1).kml` (6.7 MB)
* **`resolution_m`:** `10.0`
* **`min_catchment_area_m2`:** `500.0`

### Demonstration Summary Table:
| Property | Output Value | Description / Insight |
|---|---|---|
| **Optimal Pond Location** | `21.244413° N, 81.291006° E` | Natural low outlet suitable for water storage |
| **Outlet Elevation** | `275.0 m` | Low point relative to catchment high point (281m) |
| **Total Catchment Area** | `16,600 m²` (**1.66 ha**) | Total surface area harvesting rainfall run-off |
| **Catchment Cell Count** | `166 cells` | 166 (10m × 10m) grid cells drain to pond outlet |
| **Elevation Relief** | `6.0 m` | Elevational range within the catchment |
| **Mean / Max Slope** | `3.58%` / `10.93%` | Ideal gentle slope minimizing soil erosion |

---

## 4. API Documentation & Specifications

### Route: `POST /analyzeContour`

#### Request Parameters (`multipart/form-data`):
* `file`: `UploadFile` (Required) — `.kml` or `.kmz` map file containing contour vectors.
* `resolution_m`: `float` (Optional, default `10.0`) — Desired grid cell size in meters.
* `min_catchment_area_m2`: `float` (Optional, default `500.0`) — Minimum upstream catchment area threshold.

#### Response Parameters (`200 OK`):
* `contour_interval_m` *(float)*: Detected interval between contour lines (meters).
* `elevation_range_m` *(list[float])*: `[min, max]` elevation present on the map.
* `total_contour_lines` *(int)*: Number of parsed contour polylines.
* `grid_resolution_m` *(float)*: Resolution used for terrain DEM generation.
* `grid_shape` *(list[int])*: `[rows, cols]` dimensions of DEM raster.
* `resolution_auto_adjusted` *(bool)*: Flag indicating if resolution was coarsened to enforce RAM limits.
* `pond_site` *(object)*: Contains `lat`, `lon`, `elevation_m`, and `flow_accumulation_cells`.
* `catchment` *(object)*: Contains `area_m2`, `area_hectares`, `mean_slope_pct`, `max_slope_pct`, `min_elevation_m`, `max_elevation_m`, `relief_m`, `watershed_cell_count`, and `boundary_geojson`.
* `processing_time_ms` *(int)*: Total execution time in milliseconds.

---

## 5. Evaluation Matrix

| Criteria | Implementation Details |
|---|---|
| **Working API Endpoint** | Deployed and verified on ports 3000 and 3245 (`http://10.1.75.51:3245/analyzeContour`). Managed by an endless supervisor daemon. |
| **Catchment Identification & Estimation** | Accurate D8 flow accumulation and Priority-Flood depression filling algorithm. Computes area (1.66 ha), cell counts, relief, slope statistics, and valid GeoJSON boundary polygons. |
| **Code Extensibility for Future Phases** | Modular micro-architecture (`parser.py`, `dem.py`, `terrain.py`, `pond.py`, `schemas.py`). Readily extensible for Phase 2 runoff modeling, volumetric storage estimations, and multi-pond ranking. |
| **Documentation & Quality** | OpenAPI 3.0 interactive Swagger UI (`/docs`), automated pytest test suite (`test_golden.py`), Postman Collection (`postman_collection.json`), and comprehensive submission report. |

---

## 6. Artificial Intelligence (AI) Citation

*I used claude in some places*
