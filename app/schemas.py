from typing import List, Dict, Any, Optional
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


class PondSizingResponse(BaseModel):
    recommended_depth_m: float = Field(..., description="Recommended pond excavation depth in meters")
    surface_area_m2: float = Field(..., description="Recommended top surface area of the pond in square meters")
    storage_capacity_m3: float = Field(..., description="Target pond water storage capacity in cubic meters")
    storage_capacity_liters: float = Field(..., description="Target pond water storage capacity in Liters")
    pond_shape: str = Field("Trapezoidal Farm Pond", description="Recommended geometry type")
    side_slope_ratio: str = Field("1.5:1 (Horizontal:Vertical)", description="Bank stability slope ratio")


class WaterVolumeResponse(BaseModel):
    annual_rainfall_mm: float = Field(..., description="Annual precipitation used for runoff estimation in millimeters")
    rainfall_source: str = Field(..., description="Source of precipitation data")
    runoff_coefficient: float = Field(..., description="Hydrological runoff coefficient (C factor)")
    expected_water_volume_m3: float = Field(..., description="Expected harvestable runoff volume in cubic meters")
    expected_water_volume_liters: float = Field(..., description="Expected harvestable runoff volume in Liters")
    pond_sizing: PondSizingResponse = Field(..., description="Engineered pond physical dimensions and capacity")


class AnalyzeContourResponse(BaseModel):
    contour_interval_m: float = Field(..., description="Estimated contour interval in meters")
    elevation_range_m: List[float] = Field(..., description="[min_elevation, max_elevation] range in meters")
    total_contour_lines: int = Field(..., description="Total number of contour polylines parsed from the file")
    grid_resolution_m: float = Field(..., description="Grid cell resolution used for analysis in meters")
    grid_shape: List[int] = Field(..., description="[rows, cols] dimensions of the DEM raster grid")
    resolution_auto_adjusted: bool = Field(..., description="Whether grid resolution was coarsened for memory safety")
    pond_site: PondSiteResponse
    catchment: CatchmentResponse
    water_volume: WaterVolumeResponse
    processing_time_ms: int = Field(..., description="Total pipeline execution time in milliseconds")


class AnalyzeAreaRequest(BaseModel):
    min_lat: float = Field(..., description="South bounding latitude")
    min_lon: float = Field(..., description="West bounding longitude")
    max_lat: float = Field(..., description="North bounding latitude")
    max_lon: float = Field(..., description="East bounding longitude")
    resolution_m: float = Field(10.0, description="Target grid resolution in meters")
    min_catchment_area_m2: float = Field(500.0, description="Minimum acceptable catchment area")
    runoff_coefficient: float = Field(0.40, description="Runoff coefficient C (0.1 to 1.0)")
    rainfall_mm: Optional[float] = Field(None, description="Optional custom annual rainfall in mm")


class AnalyzeAreaResponse(AnalyzeContourResponse):
    selected_bounds: Dict[str, float] = Field(..., description="User selected bounding box coordinates")


class DatasetBoundsResponse(BaseModel):
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float
    center_lat: float
    center_lon: float
    total_contours: int
    elevation_range_m: List[float]


class HealthResponse(BaseModel):
    status: str = "ok"
