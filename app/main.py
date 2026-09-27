import os
import time
import math
import tempfile
import logging
from typing import Optional
from contextlib import asynccontextmanager

# pyrefly: ignore [missing-import]
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    AnalyzeContourResponse,
    AnalyzeAreaRequest,
    AnalyzeAreaResponse,
    DatasetBoundsResponse,
    PondSiteResponse,
    CatchmentResponse,
    WaterVolumeResponse,
    PondSizingResponse,
    HealthResponse
)
from app.parser import parse_contour_file, filter_dataset_by_bounds, get_dataset_bounds, ContourDataset
from app.dem import build_dem
from app.terrain import analyze_terrain
from app.pond import select_pond_and_delineate_catchment
from app.hydrology import calculate_water_volume_and_sizing, fetch_rainfall_data

logger = logging.getLogger("app.main")

# Global in-memory cache for default village contour dataset
CACHED_DATASET: Optional[ContourDataset] = None
CACHED_BOUNDS: Optional[dict] = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def load_default_dataset():
    global CACHED_DATASET, CACHED_BOUNDS
    candidates = [
        os.path.join(BASE_DIR, "contours_1m (1).kml"),
        os.path.join(BASE_DIR, "contours_1m.kml"),
        "/home/charithreddy/Downloads/contours_1m (1).kml",
        "/home/charithreddy/Downloads/contours_1m.kml",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                t0 = time.time()
                CACHED_DATASET = parse_contour_file(path)
                min_lon, min_lat, max_lon, max_lat = get_dataset_bounds(CACHED_DATASET)
                CACHED_BOUNDS = {
                    "min_lat": min_lat,
                    "min_lon": min_lon,
                    "max_lat": max_lat,
                    "max_lon": max_lon,
                    "center_lat": round((min_lat + max_lat) / 2.0, 6),
                    "center_lon": round((min_lon + max_lon) / 2.0, 6),
                    "total_contours": len(CACHED_DATASET.polylines),
                    "elevation_range_m": [float(CACHED_DATASET.min_elevation), float(CACHED_DATASET.max_elevation)]
                }
                logger.info(f"Loaded default contour dataset from {path} in {(time.time()-t0):.2f}s ({len(CACHED_DATASET.polylines)} polylines)")
                return
            except Exception as e:
                logger.warning(f"Failed to preload {path}: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: preload default village dataset
    load_default_dataset()
    yield


app = FastAPI(
    title="AI-Based Village Pond Planning & Catchment Analysis API",
    description="Full-stack AI pond planning system with interactive map area selection, hydrological flow routing, watershed catchment delineation, and expected water volume estimation.",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for browser integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Simple healthcheck endpoint."""
    return HealthResponse(status="ok")


@app.get("/api/dataset-bounds", response_model=DatasetBoundsResponse, tags=["Dataset"])
async def get_preloaded_bounds():
    """Returns spatial bounds and center coordinates of the preloaded village contour map."""
    global CACHED_BOUNDS
    if CACHED_BOUNDS is None:
        load_default_dataset()
    if CACHED_BOUNDS is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No preloaded contour dataset found on server."
        )
    return DatasetBoundsResponse(**CACHED_BOUNDS)


@app.get("/api/rainfall", tags=["Hydrology"])
async def get_rainfall(lat: float = Query(...), lon: float = Query(...)):
    """Returns historical/annual precipitation data for given coordinates."""
    return fetch_rainfall_data(lat, lon)


@app.post(
    "/analyzeArea",
    response_model=AnalyzeAreaResponse,
    status_code=status.HTTP_200_OK,
    tags=["Analysis"]
)
async def analyze_selected_area(req: AnalyzeAreaRequest):
    """
    Accepts bounding box coordinates of a selected land area on the map,
    crops the contour dataset, executes hydrological routing and catchment delineation,
    and returns suggested pond location, catchment metrics, and expected harvestable water volume.
    """
    global CACHED_DATASET, CACHED_BOUNDS
    if CACHED_DATASET is None or CACHED_BOUNDS is None:
        load_default_dataset()
    if CACHED_DATASET is None or CACHED_BOUNDS is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default contour dataset is not available for area clipping."
        )

    # Validate basic bounding box format
    if req.min_lat >= req.max_lat or req.min_lon >= req.max_lon:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bounding box: min_lat/min_lon must be strictly less than max_lat/max_lon."
        )

    # 1. Enforce Contour Region Boundary: Check overlap with valid contour dataset
    b = CACHED_BOUNDS
    if (req.max_lat <= b["min_lat"] or req.min_lat >= b["max_lat"] or
        req.max_lon <= b["min_lon"] or req.min_lon >= b["max_lon"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Selected land area is completely outside the valid contour region (Lat: {b['min_lat']:.4f}°–{b['max_lat']:.4f}°, Lon: {b['min_lon']:.4f}°–{b['max_lon']:.4f}°). Please select an area within the village contour boundaries."
        )

    # Clamp selection box to the valid contour boundary
    clamped_min_lat = max(req.min_lat, b["min_lat"])
    clamped_max_lat = min(req.max_lat, b["max_lat"])
    clamped_min_lon = max(req.min_lon, b["min_lon"])
    clamped_max_lon = min(req.max_lon, b["max_lon"])

    # 2. Enforce Minimum and Maximum selection size limits
    lat_mid_rad = math.radians((clamped_min_lat + clamped_max_lat) / 2.0)
    width_m = (clamped_max_lon - clamped_min_lon) * 111320.0 * math.cos(lat_mid_rad)
    height_m = (clamped_max_lat - clamped_min_lat) * 110540.0
    approx_area_m2 = width_m * height_m

    MIN_DIM_M = 50.0          # Minimum 50 meters dimension
    MIN_AREA_M2 = 2500.0      # Minimum 2,500 m² (0.25 hectares)
    MAX_AREA_M2 = 12000000.0  # Maximum 12 km² (covers entire village extent)

    if width_m < MIN_DIM_M or height_m < MIN_DIM_M or approx_area_m2 < MIN_AREA_M2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Selected land area is too small ({width_m:.0f}m × {height_m:.0f}m, ~{approx_area_m2:.0f} m²). Minimum allowed selection is 50m × 50m (2,500 m²)."
        )

    if approx_area_m2 > MAX_AREA_M2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Selected land area is too large (~{approx_area_m2/1e6:.1f} km²). Maximum allowed selection is 12 km² (full village extent)."
        )

    start_time = time.time()

    try:
        # 1. Filter polylines to selected (clamped) area
        sub_dataset = filter_dataset_by_bounds(
            CACHED_DATASET,
            min_lon=clamped_min_lon,
            min_lat=clamped_min_lat,
            max_lon=clamped_max_lon,
            max_lat=clamped_max_lat
        )

        # 2. Build DEM grid
        dem = build_dem(sub_dataset, target_resolution_m=req.resolution_m)

        # 3. Terrain analysis
        terrain = analyze_terrain(dem)

        # 4. Select pond and delineate catchment
        result = select_pond_and_delineate_catchment(
            dem_grid=dem,
            terrain=terrain,
            min_catchment_area_m2=req.min_catchment_area_m2
        )

        # 5. Hydrology and water volume estimation
        hydro = calculate_water_volume_and_sizing(
            catchment_area_m2=result.catchment.area_m2,
            lat=result.pond_site.lat,
            lon=result.pond_site.lon,
            rainfall_mm=req.rainfall_mm,
            runoff_coefficient=req.runoff_coefficient
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        return AnalyzeAreaResponse(
            selected_bounds={
                "min_lat": req.min_lat,
                "min_lon": req.min_lon,
                "max_lat": req.max_lat,
                "max_lon": req.max_lon
            },
            contour_interval_m=float(sub_dataset.contour_interval),
            elevation_range_m=[float(sub_dataset.min_elevation), float(sub_dataset.max_elevation)],
            total_contour_lines=len(sub_dataset.polylines),
            grid_resolution_m=float(dem.resolution_m),
            grid_shape=list(dem.grid.shape),
            resolution_auto_adjusted=dem.resolution_auto_adjusted,
            pond_site=PondSiteResponse(
                lat=result.pond_site.lat,
                lon=result.pond_site.lon,
                elevation_m=result.pond_site.elevation_m,
                flow_accumulation_cells=result.pond_site.flow_accumulation_cells
            ),
            catchment=CatchmentResponse(
                area_m2=result.catchment.area_m2,
                area_hectares=result.catchment.area_hectares,
                mean_slope_pct=result.catchment.mean_slope_pct,
                max_slope_pct=result.catchment.max_slope_pct,
                min_elevation_m=result.catchment.min_elevation_m,
                max_elevation_m=result.catchment.max_elevation_m,
                relief_m=result.catchment.relief_m,
                watershed_cell_count=result.catchment.watershed_cell_count,
                boundary_geojson=result.catchment.boundary_geojson
            ),
            water_volume=WaterVolumeResponse(
                annual_rainfall_mm=hydro.annual_rainfall_mm,
                rainfall_source=hydro.rainfall_source,
                runoff_coefficient=hydro.runoff_coefficient,
                expected_water_volume_m3=hydro.expected_water_volume_m3,
                expected_water_volume_liters=hydro.expected_water_volume_liters,
                pond_sizing=PondSizingResponse(
                    recommended_depth_m=hydro.pond_sizing.recommended_depth_m,
                    surface_area_m2=hydro.pond_sizing.surface_area_m2,
                    storage_capacity_m3=hydro.pond_sizing.storage_capacity_m3,
                    storage_capacity_liters=hydro.pond_sizing.storage_capacity_liters,
                    pond_shape=hydro.pond_sizing.pond_shape,
                    side_slope_ratio=hydro.pond_sizing.side_slope_ratio
                )
            ),
            processing_time_ms=elapsed_ms
        )

    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve)
        ) from ve
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during area analysis: {str(e)}"
        ) from e


@app.post(
    "/analyzeContour",
    response_model=AnalyzeContourResponse,
    status_code=status.HTTP_200_OK,
    tags=["Analysis"]
)
async def analyze_contour(
    contour_map: UploadFile = File(default=None, description="The .kml or .kmz contour map file upload under variable name 'contour_map'."),
    file: UploadFile = File(default=None, description="Legacy alias for contour_map."),
    resolution_m: float = Form(default=10.0),
    min_catchment_area_m2: float = Form(default=500.0),
    runoff_coefficient: float = Form(default=0.40),
    rainfall_mm: Optional[float] = Form(default=None)
):
    """
    Accepts a .kml or .kmz contour map file upload and analyzes terrain to identify
    an optimal pond location, delineate upstream catchment area, and compute harvestable water volume.
    """
    upload_file = contour_map or file
    if upload_file is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing required file field 'contour_map'."
        )

    filename = upload_file.filename or "uploaded_file.kml"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".kml", ".kmz"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file extension. Only .kml and .kmz files are allowed."
        )

    start_time = time.time()
    tmp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
            tmp_path = tmp_file.name
            while chunk := await upload_file.read(1024 * 1024):
                tmp_file.write(chunk)

        try:
            dataset = parse_contour_file(tmp_path)
        except ValueError as ve:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or unparseable contour file: {str(ve)}"
            ) from ve

        try:
            dem = build_dem(dataset, target_resolution_m=resolution_m)
        except ValueError as ve:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to generate DEM grid: {str(ve)}"
            ) from ve

        terrain = analyze_terrain(dem)

        try:
            result = select_pond_and_delineate_catchment(
                dem_grid=dem,
                terrain=terrain,
                min_catchment_area_m2=min_catchment_area_m2
            )
        except ValueError as ve:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Could not delineate pond site / catchment area: {str(ve)}"
            ) from ve

        hydro = calculate_water_volume_and_sizing(
            catchment_area_m2=result.catchment.area_m2,
            lat=result.pond_site.lat,
            lon=result.pond_site.lon,
            rainfall_mm=rainfall_mm,
            runoff_coefficient=runoff_coefficient
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        return AnalyzeContourResponse(
            contour_interval_m=float(dataset.contour_interval),
            elevation_range_m=[float(dataset.min_elevation), float(dataset.max_elevation)],
            total_contour_lines=len(dataset.polylines),
            grid_resolution_m=float(dem.resolution_m),
            grid_shape=list(dem.grid.shape),
            resolution_auto_adjusted=dem.resolution_auto_adjusted,
            pond_site=PondSiteResponse(
                lat=result.pond_site.lat,
                lon=result.pond_site.lon,
                elevation_m=result.pond_site.elevation_m,
                flow_accumulation_cells=result.pond_site.flow_accumulation_cells
            ),
            catchment=CatchmentResponse(
                area_m2=result.catchment.area_m2,
                area_hectares=result.catchment.area_hectares,
                mean_slope_pct=result.catchment.mean_slope_pct,
                max_slope_pct=result.catchment.max_slope_pct,
                min_elevation_m=result.catchment.min_elevation_m,
                max_elevation_m=result.catchment.max_elevation_m,
                relief_m=result.catchment.relief_m,
                watershed_cell_count=result.catchment.watershed_cell_count,
                boundary_geojson=result.catchment.boundary_geojson
            ),
            water_volume=WaterVolumeResponse(
                annual_rainfall_mm=hydro.annual_rainfall_mm,
                rainfall_source=hydro.rainfall_source,
                runoff_coefficient=hydro.runoff_coefficient,
                expected_water_volume_m3=hydro.expected_water_volume_m3,
                expected_water_volume_liters=hydro.expected_water_volume_liters,
                pond_sizing=PondSizingResponse(
                    recommended_depth_m=hydro.pond_sizing.recommended_depth_m,
                    surface_area_m2=hydro.pond_sizing.surface_area_m2,
                    storage_capacity_m3=hydro.pond_sizing.storage_capacity_m3,
                    storage_capacity_liters=hydro.pond_sizing.storage_capacity_liters,
                    pond_shape=hydro.pond_sizing.pond_shape,
                    side_slope_ratio=hydro.pond_sizing.side_slope_ratio
                )
            ),
            processing_time_ms=elapsed_ms
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during processing: {str(e)}"
        ) from e
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


# Serve Static files and Frontend
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "AI Pond Planner API running. Frontend assets not yet deployed."}
