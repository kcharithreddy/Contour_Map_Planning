import os
import time
import tempfile
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status

from app.schemas import AnalyzeContourResponse, PondSiteResponse, CatchmentResponse, HealthResponse
from app.parser import parse_contour_file
from app.dem import build_dem
from app.terrain import analyze_terrain
from app.pond import select_pond_and_delineate_catchment

app = FastAPI(
    title="Contour-Based Pond Catchment Analysis API",
    description="API that accepts a contour map (KML/KMZ), analyzes terrain, selects an optimal pond site, and delineates catchment area.",
    version="1.0.0"
)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Simple healthcheck endpoint."""
    return HealthResponse(status="ok")


@app.post(
    "/analyzeContour",
    response_model=AnalyzeContourResponse,
    status_code=status.HTTP_200_OK,
    tags=["Analysis"]
)
async def analyze_contour(
    file: UploadFile = File(...),
    resolution_m: float = Form(default=10.0),
    min_catchment_area_m2: float = Form(default=500.0)
):
    """
    Accepts a .kml or .kmz contour map file upload and analyzes terrain to identify
    an optimal pond location and delineate its upstream catchment area.
    """
    filename = file.filename or "uploaded_file.kml"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".kml", ".kmz"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file extension. Only .kml and .kmz files are allowed."
        )

    start_time = time.time()
    tmp_path = None

    try:
        # Stream file to disk to avoid buffering large files entirely in memory
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
            tmp_path = tmp_file.name
            while chunk := await file.read(1024 * 1024):  # 1MB chunk
                tmp_file.write(chunk)

        # 1. Parse contour file
        try:
            dataset = parse_contour_file(tmp_path)
        except ValueError as ve:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or unparseable contour file: {str(ve)}"
            ) from ve

        # 2. Build DEM grid
        try:
            dem = build_dem(dataset, target_resolution_m=resolution_m)
        except ValueError as ve:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to generate DEM grid: {str(ve)}"
            ) from ve

        # 3. Analyze terrain
        terrain = analyze_terrain(dem)

        # 4. Select pond site and delineate catchment
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

        elapsed_ms = int((time.time() - start_time) * 1000)

        response_data = AnalyzeContourResponse(
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
            processing_time_ms=elapsed_ms
        )

        return response_data

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
