# Phase 3: VIVA & Demo Submission Guide
**CS559: Computer Systems Design — Assignment 1**
**Project:** AI-Based Village Pond Planning & Catchment Analysis System
**Author:** Kakarla Soma Charith Reddy | Student ID: 12341040 | Email: kakarlac@iitbhilai.ac.in | IIT Bhilai

---

## 1. Submission URLs & Quick Reference

| Deliverable | URL / Information |
|---|---|
| **GitHub Repository** | `https://github.com/kcharithreddy/Contour_Map_Planning` |
| **YouTube Video Demo Link** | `https://www.youtube.com/playlist?list=PLAHMqE-Hy_PY` |
| **Working Front-End URL (Remote)** | `http://10.1.75.51:3245/` |
| **Alternative Front-End Port** | `http://10.1.75.51:3000/` |
| **Local Working Front-End URL** | `http://localhost:3245/` |
| **API Documentation (Swagger UI)** | `http://10.1.75.51:3245/docs` |
| **OpenAPI Schema (JSON)** | `http://10.1.75.51:3245/openapi.json` |

---

## 2. Fulfillment of Expected System Requirements

| System Requirement | Implementation Details | Verification / Evidence |
|---|---|---|
| **1. Fully working front-end** | Built a responsive web dashboard served at `GET /` using Leaflet.js, Carto & Esri World Imagery basemaps, custom CSS glassmorphism, and live KPI telemetry cards. | Verified at `http://localhost:3245/` and `http://10.1.75.51:3245/`. |
| **2. Option to select land area on a map** | Implemented interactive drag-to-select bounding box tool on the map (`btn-draw-area`), a full village extent preset (`btn-full-area`), and custom KML/KMZ upload modal. | Real-time crosshair cursor, drag bounding box rectangle on canvas, immediate coordinates bounding capture. |
| **3. Generation of results based on selected land area** | Backend endpoint `POST /analyzeArea` dynamically clips vector contours to `[min_lon, min_lat, max_lon, max_lat]`, constructs DEM raster, and routes hydrological flow within ~1–2 seconds. | Tested with automated test `test_analyze_area_endpoint` and manual bounding box selection. |
| **4. Results Include Pond Location, Catchment Area, & Expected Water Volume** | • **Pond Site:** Lat, Lon, Elevation (m), Draining flow cells.<br>• **Catchment:** Area ($m^2$ & ha), mean/max slope (%), relief (m).<br>• **Expected Water Volume:** Runoff volume ($m^3$ & Liters) via $V = P \times A \times C$.<br>• **Engineered Pond Sizing:** Rec. depth (3m), top surface area ($m^2$), target storage capacity ($m^3$). | Verified through schemas and live UI display. |
| **5. Map Overlay and Visualization** | • Selected bounding box highlighted in dashed cyan.<br>• Catchment area overlaid as filled semi-transparent GeoJSON polygon with interactive tooltip.<br>• Suggested pond location marked with animated ripple/pulsing water icon and popup statistics. | Visualized directly on Leaflet map canvas with auto-panning and zoom fitting. |
| **6. Speed, Stress, Scaling & Multi-System Considerations** | • Memory-safe execution within 512MB RAM budget (no GDAL/rasterio heavy C-bindings).<br>• Automatic DEM grid coarsening if cell count exceeds 250k budget.<br>• Spatial bounding box clipping reduces grid dimensions for sub-second responses.<br>• Background supervisor daemon running multi-port redundant instances (3245 & 3000) ready for reverse-proxy load balancing across the four systems. | Automated test suite passed 31/31 unit and golden benchmark tests in 26s. |

---

## 3. Hydrological Methodology & Formulas

### A. Runoff Volume Estimation (Rational Equation)
$$V = P \times A \times C$$
- **$V$ (Expected Runoff Volume in $m^3$):** Total harvestable surface runoff draining into the pond location.
- **$P$ (Annual Precipitation in meters):** Fetched dynamically from Open-Meteo Historical Archive API (fallback regional baseline for Central India: $1220\text{ mm} = 1.22\text{ m}$).
- **$A$ (Catchment Area in $m^2$):** Delineated surface area contributing flow to the pond site.
- **$C$ (Runoff Coefficient):** Dimensionless factor ($0.35 - 0.50$ for rural agricultural terrain; configurable via the dashboard slider).

### B. Farm Pond Dimensioning
- **Target Storage Capacity ($m^3$):** Designed to capture $30\%$ of annual catchment runoff (minimum $150\text{ m}^3$).
- **Excavation Depth ($d$):** Standard agricultural farm pond depth: $3.0\text{ m}$.
- **Top Surface Area:** $\approx 1.25 \times \frac{V_{\text{target}}}{d}$ accounting for a stable $1.5:1$ ($H:V$) side slope trapezoidal cross-section.

---

## 4. 5-Minute YouTube Video Demo Script

Follow this suggested script to record your 5-minute video:

### [0:00 – 0:45] Introduction & Problem Statement
- **Speaker:** "Hello everyone. My name is Charith Reddy. This is the demonstration of our AI-Based Village Pond Planning & Catchment Analysis System for CS559 System Design."
- **Visual:** Show title slide and open `http://localhost:3245/` (or remote server URL).
- **Key Point:** Highlight the objective: helping rural communities and engineers identify optimal rainwater harvesting pond sites and calculate harvestable water volume without expensive on-site surveys.

### [0:45 – 2:00] End-to-End System Architecture & Algorithms
- **Visual:** Briefly show the architecture diagram from `FINAL_PROJECT_REPORT.md` or the Swagger UI docs.
- **Explanation:**
  1. **Streaming KML Parser (`app/parser.py`):** Parses 3D contour lines and elevation metadata without loading the entire DOM into memory.
  2. **UTM Projection & DEM Grid (`app/dem.py`):** Converts WGS84 coordinates to local metric UTM (EPSG:32644) and interpolates a regular elevation grid.
  3. **Hydrological Flow Routing (`app/terrain.py`):** Fills depressions using priority-flood, computes D8 steepest-descent flow vectors, and calculates flow accumulation.
  4. **Pond Site & Catchment Delineation (`app/pond.py`):** Selects optimal low-elevation outlet cells and traces upstream cells to delineate the watershed boundary.
  5. **Water Volume Modeling (`app/hydrology.py`):** Implements $V = P \times A \times C$ and calculates physical pond dimensions.

### [2:00 – 3:45] Live Interactive Website Demo
- **Visual:** Full-screen browser on the web interface.
  1. **Show preloaded map:** Toggle between Satellite imagery and Street basemaps.
  2. **Demonstrate Land Area Selection:** Click **"Select Land Area"**, drag a bounding box across a sub-region of the village terrain.
  3. **Observe Results:**
     - Point out the execution time badge (e.g. ~1200 ms).
     - Show the **Selected Area Bounding Box** (dashed cyan outline).
     - Show the **Catchment Area Boundary** overlaid as a semi-transparent polygon.
     - Show the **Animated Pond Marker**; click it to open the popup showing Elevation, Coordinates, Catchment Area, and Expected Water Volume.
  4. **Demonstrate Configurable Sliders:** Adjust the Runoff Coefficient ($C$) from $0.40$ to $0.50$ and see the Expected Water Volume update in real-time.
  5. **Demonstrate GeoJSON Export:** Click **"Download Catchment GeoJSON"** and show the downloaded file.
  6. **Demonstrate Custom KML Upload:** Click **"Upload KML"** and show the drag-and-drop modal.

### [3:45 – 4:45] Stress, Scaling & Multi-System Considerations
- **Key Points:**
  - **Memory Constraint (512MB RAM):** The system operates entirely in pure Python, numpy, and scipy without bloated desktop GIS packages (GDAL, QGIS). Total memory footprint is under 180MB.
  - **Auto-Coarsening Guardrail:** If an uploaded contour map exceeds 250,000 grid cells, resolution automatically coarsens to prevent Out-Of-Memory (OOM) crashes.
  - **Sub-Area Cropping:** Clipping contours to the user-selected bounding box drops calculation time from ~10s down to <2s.
  - **Four-System Scaling:** Background supervisor daemon (`start_daemon.sh`) runs redundant workers across ports 3245 and 3000, easily load-balanced across the 4 student systems.

### [4:45 – 5:00] Conclusion & Wrap-up
- Reiterate that all test suites pass (31/31 automated tests).
- Thank the viewer and conclude.

---

## 5. Report Template Mapping (Overleaf)

When preparing your report using the template at `https://www.overleaf.com/read/pzfvwbrjswhz#d2b10f`:

1. **Section 1: Introduction & Problem Definition [MUST BE INCLUDED]**
   - Context: Rainwater runoff harvesting in rural Indian topography.
   - Objectives: Automated terrain analysis, pond placement, catchment delineation, and water volume estimation.
2. **Section 2: System Architecture & Design Choices [MUST BE INCLUDED]**
   - Layered architecture: Presentation layer (Leaflet.js UI), Application layer (FastAPI), Processing engine (scipy/numpy hydrological pipeline), Data layer (Open-Meteo & spatial GeoJSON).
   - Justification for avoiding heavy desktop GIS libraries (GDAL) to strictly abide by the 512MB RAM budget.
3. **Section 3: Mathematical Formulation & Algorithms [MUST BE INCLUDED]**
   - UTM metric projection math.
   - Priority-Flood sink depression filling algorithm.
   - D8 steepest-descent flow routing and recursive reverse flow upstream tracing.
   - Rational Runoff Formula ($V = P \times A \times C$) and trapezoidal pond geometry.
4. **Section 4: Front-end Interface & Interactive Area Selection [MUST BE INCLUDED]**
   - Screenshots of the working web application (`/static/index.html`).
   - Description of the interactive drag bounding box selector, satellite overlays, pond popup, and real-time parameter tuning.
5. **Section 5: Performance, Stress & Multi-System Scaling [MUST BE INCLUDED]**
   - Benchmarking table comparing full area vs. sub-area selection latency.
   - Memory profile graph/table showing RAM utilization staying under 200MB.
   - Multi-port daemon configuration across student systems.
6. **Section 6: Testing & Validation [MUST BE INCLUDED]**
   - Summary of test coverage: 31 passed tests (API tests, DEM grid tests, terrain tests, golden benchmarks).
