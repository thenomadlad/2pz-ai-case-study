import numpy as np

from scripts.build_cells import block_sum


def test_block_sum_pads_ragged_edges():
    a = np.ones((5, 3))
    out = block_sum(a, 2)
    assert out.shape == (3, 2)
    assert out.sum() == a.sum()
    assert out[0, 0] == 4 and out[2, 1] == 1   # corner block holds a single pixel
