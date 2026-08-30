from dataclasses import dataclass
import heapq
from collections import deque
import numpy as np
from app.dem import DEMGrid


# D8 direction offsets and codes:
# Index: 0=E, 1=SE, 2=S, 3=SW, 4=W, 5=NW, 6=N, 7=NE
D8_DR = [0, 1, 1, 1, 0, -1, -1, -1]
D8_DC = [1, 1, 0, -1, -1, -1, 0, 1]
D8_CODES = [1, 2, 4, 8, 16, 32, 64, 128]
D8_CODE_TO_INDEX = {code: idx for idx, code in enumerate(D8_CODES)}


@dataclass
class TerrainAnalysis:
    filled_dem: np.ndarray
    flow_dir: np.ndarray
    flow_accumulation: np.ndarray
    slopes: np.ndarray


def fill_depressions(dem: np.ndarray) -> np.ndarray:
    """
    Priority-flood depression fill algorithm (Barnes et al., 2014).
    Ensures all cells flow continuously towards grid boundaries.
    """
    nrows, ncols = dem.shape
    filled = np.copy(dem).astype(np.float64)
    visited = np.zeros((nrows, ncols), dtype=bool)
    heap = []

    # Insert all boundary cells into min-heap
    for r in range(nrows):
        for c in range(ncols):
            if r == 0 or r == nrows - 1 or c == 0 or c == ncols - 1:
                visited[r, c] = True
                heapq.heappush(heap, (filled[r, c], r, c))

    while heap:
        elev, r, c = heapq.heappop(heap)
        for i in range(8):
            nr, nc = r + D8_DR[i], c + D8_DC[i]
            if 0 <= nr < nrows and 0 <= nc < ncols and not visited[nr, nc]:
                visited[nr, nc] = True
                filled[nr, nc] = max(dem[nr, nc], elev)
                heapq.heappush(heap, (filled[nr, nc], nr, nc))

    return filled


def calculate_d8_flow_dir(filled_dem: np.ndarray, resolution_m: float) -> np.ndarray:
    """
    Calculate D8 flow direction matrix from filled DEM grid.
    Returns uint8 array with direction codes (1, 2, 4, 8, 16, 32, 64, 128, 0 for outlet/flat).
    """
    nrows, ncols = filled_dem.shape
    flow_dir = np.zeros((nrows, ncols), dtype=np.uint8)

    diag_dist = resolution_m * np.sqrt(2.0)
    distances = np.array([
        resolution_m, diag_dist, resolution_m, diag_dist,
        resolution_m, diag_dist, resolution_m, diag_dist
    ])

    for r in range(nrows):
        for c in range(ncols):
            curr_elev = filled_dem[r, c]
            max_drop_rate = 0.0
            best_code = 0

            for i in range(8):
                nr, nc = r + D8_DR[i], c + D8_DC[i]
                if 0 <= nr < nrows and 0 <= nc < ncols:
                    drop = curr_elev - filled_dem[nr, nc]
                    drop_rate = drop / distances[i]
                    if drop_rate > max_drop_rate:
                        max_drop_rate = drop_rate
                        best_code = D8_CODES[i]

            flow_dir[r, c] = best_code

    return flow_dir


def calculate_flow_accumulation(flow_dir: np.ndarray) -> np.ndarray:
    """
    Calculate flow accumulation matrix (total upstream cells contributing flow to each cell).
    Uses topological sort queue.
    """
    nrows, ncols = flow_dir.shape
    in_degree = np.zeros((nrows, ncols), dtype=np.int32)
    accumulation = np.ones((nrows, ncols), dtype=np.float64)

    # Compute in-degree for each cell
    for r in range(nrows):
        for c in range(ncols):
            code = flow_dir[r, c]
            if code in D8_CODE_TO_INDEX:
                idx = D8_CODE_TO_INDEX[code]
                dr, dc = D8_DR[idx], D8_DC[idx]
                nr, nc = r + dr, c + dc
                if 0 <= nr < nrows and 0 <= nc < ncols:
                    in_degree[nr, nc] += 1

    # Queue headwater cells (in-degree == 0)
    queue = deque()
    for r in range(nrows):
        for c in range(ncols):
            if in_degree[r, c] == 0:
                queue.append((r, c))

    while queue:
        r, c = queue.popleft()
        code = flow_dir[r, c]
        if code in D8_CODE_TO_INDEX:
            idx = D8_CODE_TO_INDEX[code]
            dr, dc = D8_DR[idx], D8_DC[idx]
            nr, nc = r + dr, c + dc
            if 0 <= nr < nrows and 0 <= nc < ncols:
                accumulation[nr, nc] += accumulation[r, c]
                in_degree[nr, nc] -= 1
                if in_degree[nr, nc] == 0:
                    queue.append((nr, nc))

    return accumulation


def calculate_slopes(filled_dem: np.ndarray, resolution_m: float) -> np.ndarray:
    """
    Calculate terrain slope percentage for each DEM cell.
    """
    dy, dx = np.gradient(filled_dem, resolution_m, resolution_m)
    slope_rad = np.arctan(np.sqrt(dx * dx + dy * dy))
    slope_pct = np.tan(slope_rad) * 100.0
    return slope_pct


def analyze_terrain(dem_grid: DEMGrid) -> TerrainAnalysis:
    """
    Perform complete terrain analysis on a DEMGrid object.
    """
    filled_dem = fill_depressions(dem_grid.grid)
    flow_dir = calculate_d8_flow_dir(filled_dem, dem_grid.resolution_m)
    flow_acc = calculate_flow_accumulation(flow_dir)
    slopes = calculate_slopes(filled_dem, dem_grid.resolution_m)

    return TerrainAnalysis(
        filled_dem=filled_dem,
        flow_dir=flow_dir,
        flow_accumulation=flow_acc,
        slopes=slopes
    )
