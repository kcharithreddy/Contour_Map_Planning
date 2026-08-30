from typing import List, Dict, Any
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field


class PondSiteResponse(BaseModel):
    lat: float = Field(..., description="Latitude of selected pond outlet site in WGS84 degrees")
    lon: float = Field(..., description="Longitude of selected pond outlet site in WGS84 degrees")
    elevation_m: float = Field(..., description="Elevation of selected pond outlet site in meters")
    flow_accumulation_cells: int = Field(..., description="Number of upstream cells draining into the pond outlet")


class CatchmentResponse(BaseModel):
    area_m2: float = Field(..., description="Catchment surface area in square meters")
    area_hectares: float = Field(..., description="Catchment surface area in hectares")
    mean_slope_pct: float = Field(..., description="Average terrain slope percentage across catchment area")
    max_slope_pct: float = Field(..., description="Maximum terrain slope percentage within the catchment area")
    min_elevation_m: float = Field(..., description="Minimum elevation within the catchment in meters")
    max_elevation_m: float = Field(..., description="Maximum elevation within the catchment in meters")
    relief_m: float = Field(..., description="Elevation relief (max - min) within the catchment in meters")
    watershed_cell_count: int = Field(..., description="Number of DEM grid cells in the delineated watershed")
    boundary_geojson: Dict[str, Any] = Field(..., description="GeoJSON Polygon object representing catchment boundary")


class AnalyzeContourResponse(BaseModel):
    contour_interval_m: float = Field(..., description="Estimated contour interval in meters")
    elevation_range_m: List[float] = Field(..., description="[min_elevation, max_elevation] range in meters")
    total_contour_lines: int = Field(..., description="Total number of contour polylines parsed from the file")
    grid_resolution_m: float = Field(..., description="Grid cell resolution used for analysis in meters")
    grid_shape: List[int] = Field(..., description="[rows, cols] dimensions of the DEM raster grid")
    resolution_auto_adjusted: bool = Field(..., description="Whether grid resolution was coarsened for memory safety")
    pond_site: PondSiteResponse
    catchment: CatchmentResponse
    processing_time_ms: int = Field(..., description="Total pipeline execution time in milliseconds")


class HealthResponse(BaseModel):
    status: str = "ok"
