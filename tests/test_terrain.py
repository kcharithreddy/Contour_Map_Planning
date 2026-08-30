import numpy as np
import pytest
from app.terrain import (
    fill_depressions,
    calculate_d8_flow_dir,
    calculate_flow_accumulation,
    calculate_slopes
)


def test_fill_depressions_synthetic_pit():
    dem = np.array([
        [10.0, 10.0, 10.0, 10.0, 10.0],
        [10.0,  5.0,  5.0,  5.0, 10.0],
        [10.0,  5.0,  2.0,  5.0, 10.0],
        [10.0,  5.0,  4.0,  5.0, 10.0],
        [10.0, 10.0,  3.0, 10.0, 10.0]
    ])

    filled = fill_depressions(dem)
    # The center pit at (2,2) should be filled to 4.0
    assert filled[2, 2] == 4.0
    # Boundary outlet at (4,2) should remain 3.0
    assert filled[4, 2] == 3.0


def test_d8_flow_dir_synthetic_v_valley():
    # V-valley sloping down to the center column (col 1), then down towards bottom (row 2)
    dem = np.array([
        [5.0, 3.0, 5.0],
        [4.0, 2.0, 4.0],
        [3.0, 1.0, 3.0]
    ])

    flow_dir = calculate_d8_flow_dir(dem, resolution_m=10.0)
    # (0,0) should flow to (1,1) -> SE (code 2)
    assert flow_dir[0, 0] == 2
    # (0,2) should flow to (1,1) -> SW (code 8)
    assert flow_dir[0, 2] == 8
    # (0,1) should flow to (1,1) -> S (code 4)
    assert flow_dir[0, 1] == 4
    # (1,1) should flow to (2,1) -> S (code 4)
    assert flow_dir[1, 1] == 4


def test_flow_accumulation():
    # Flow direction matrix where top row and sides flow to center outlet (2,1)
    flow_dir = np.array([
        [2, 4, 8],
        [2, 4, 8],
        [0, 0, 0]
    ], dtype=np.uint8)

    acc = calculate_flow_accumulation(flow_dir)
    # Accumulation at outlet (2,1) should gather flow from upstream cells
    assert acc[2, 1] >= 6.0
    # Headwater cell (0,0) should have accumulation == 1.0
    assert acc[0, 0] == 1.0


def test_calculate_slopes():
    dem = np.array([
        [0.0, 10.0],
        [0.0, 10.0]
    ])
    slopes = calculate_slopes(dem, resolution_m=10.0)
    assert np.all(slopes >= 0.0)
