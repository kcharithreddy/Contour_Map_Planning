"""
hydrology.py — Water Volume Estimation and Pond Sizing Calculations.

Implements the Rational Runoff formula:
    Runoff Volume (m³) = Precipitation (m) × Catchment Area (m²) × Runoff Coefficient (C)

Provides:
- Regional historical rainfall estimation / API lookup
- Expected runoff water volume in m³ and Liters
- Farm pond physical dimensioning and storage capacity recommendations
"""
import urllib.request
import json
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

logger = logging.getLogger("app.hydrology")

# Default annual precipitation for Chhattisgarh / Central India in mm (~1200 mm)
DEFAULT_ANNUAL_RAINFALL_MM = 1220.0
# Default runoff coefficient for rural / agricultural terrain with moderate clay/loam soil
DEFAULT_RUNOFF_COEFFICIENT = 0.40


@dataclass
class PondDimensions:
    recommended_depth_m: float
    surface_area_m2: float
    storage_capacity_m3: float
    storage_capacity_liters: float
    pond_shape: str
    side_slope_ratio: str  # e.g., "1.5:1 (H:V)"


@dataclass
class HydrologyResult:
    catchment_area_m2: float
    annual_rainfall_mm: float
    rainfall_source: str
    runoff_coefficient: float
    expected_water_volume_m3: float
    expected_water_volume_liters: float
    pond_sizing: PondDimensions


def fetch_rainfall_data(lat: float, lon: float, timeout_sec: float = 3.0) -> Dict[str, Any]:
    """
    Attempt to fetch historical rainfall from Open-Meteo archive API.
    Gracefully falls back to regional default if network is unavailable or times out.
    """
    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat:.4f}&longitude={lon:.4f}&"
        f"start_date=2023-01-01&end_date=2023-12-31&"
        f"daily=precipitation_sum&timezone=auto"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AIPondPlanner/1.0"})
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode())
            precip_list = data.get("daily", {}).get("precipitation_sum", [])
            total_precip = sum(p for p in precip_list if p is not None)
            if total_precip > 100.0:  # Valid annual rainfall
                return {
                    "annual_rainfall_mm": round(total_precip, 1),
                    "source": "Open-Meteo Historical Archive (2023)"
                }
    except Exception as e:
        logger.debug(f"Open-Meteo rainfall fetch skipped/failed ({e}), using regional baseline.")

    return {
        "annual_rainfall_mm": DEFAULT_ANNUAL_RAINFALL_MM,
        "source": "Regional Baseline (Central India Agrometeorology)"
    }


def calculate_water_volume_and_sizing(
    catchment_area_m2: float,
    lat: float,
    lon: float,
    rainfall_mm: Optional[float] = None,
    runoff_coefficient: float = DEFAULT_RUNOFF_COEFFICIENT,
    target_harvest_pct: float = 0.30
) -> HydrologyResult:
    """
    Calculates expected runoff collection and recommends pond dimensions.
    
    Parameters:
    - catchment_area_m2: Delineated catchment area in m²
    - lat, lon: Pond site coordinates
    - rainfall_mm: Optional custom annual rainfall in mm (if None, fetched or regional)
    - runoff_coefficient: Dimensionless runoff coefficient (typically 0.30 - 0.50)
    - target_harvest_pct: Fraction of total annual runoff to design storage for (default 30% for seasonal storage)
    """
    if rainfall_mm is not None and rainfall_mm > 0:
        annual_rainfall = float(rainfall_mm)
        source = "User Configured / Override"
    else:
        rain_info = fetch_rainfall_data(lat, lon)
        annual_rainfall = rain_info["annual_rainfall_mm"]
        source = rain_info["source"]

    # Runoff volume: V = P(m) × A(m²) × C
    rainfall_m = annual_rainfall / 1000.0
    c_factor = max(0.1, min(1.0, runoff_coefficient))
    expected_runoff_m3 = round(catchment_area_m2 * rainfall_m * c_factor, 2)
    expected_runoff_liters = round(expected_runoff_m3 * 1000.0, 2)

    # Pond sizing:
    # Target storage is a fraction of total runoff (or minimum 150 m³)
    target_capacity_m3 = max(150.0, expected_runoff_m3 * target_harvest_pct)

    # Standard rural farm pond recommended depth: 2.5m - 3.5m (default 3.0m)
    recommended_depth = 3.0
    # Assuming trapezoidal inverted pyramid with 1.5:1 side slope
    # Mean area = Volume / Depth
    mean_area_m2 = target_capacity_m3 / recommended_depth
    # Top surface area is roughly 1.25x mean area due to sloped banks
    top_surface_area_m2 = round(mean_area_m2 * 1.25, 1)

    dimensions = PondDimensions(
        recommended_depth_m=recommended_depth,
        surface_area_m2=top_surface_area_m2,
        storage_capacity_m3=round(target_capacity_m3, 2),
        storage_capacity_liters=round(target_capacity_m3 * 1000.0, 2),
        pond_shape="Trapezoidal Farm Pond",
        side_slope_ratio="1.5:1 (Horizontal:Vertical)"
    )

    return HydrologyResult(
        catchment_area_m2=round(catchment_area_m2, 2),
        annual_rainfall_mm=annual_rainfall,
        rainfall_source=source,
        runoff_coefficient=round(c_factor, 2),
        expected_water_volume_m3=expected_runoff_m3,
        expected_water_volume_liters=expected_runoff_liters,
        pond_sizing=dimensions
    )
