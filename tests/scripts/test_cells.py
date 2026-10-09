import numpy as np

from scripts.build_cells import block_sum, market_women, residential_share


def test_block_sum_pads_ragged_edges():
    a = np.ones((5, 3))
    out = block_sum(a, 2)
    assert out.shape == (3, 2)
    assert out.sum() == a.sum()
    assert out[0, 0] == 4 and out[2, 1] == 1   # corner block holds a single pixel


def test_residential_share_rebalances_to_emirate_total():
    # 1,000 adults, 300 of them women; 200 adults in worker housing at 5% female.
    s = residential_share(women=300, adults=1000, worker_adults=200, worker_share=0.05)
    assert round(s, 4) == round((300 - 10) / 800, 4)
    assert round(0.05 * 200 + s * 800) == 300   # the emirate total is preserved


def test_residential_share_clipped_to_valid_range():
    assert residential_share(women=10, adults=100, worker_adults=90, worker_share=0.5) == 0.0
    assert residential_share(women=100, adults=100, worker_adults=0, worker_share=0.05) == 1.0


def test_market_women_splits_worker_and_residential():
    assert market_women(adults=1000, worker_adults=400, worker_share=0.05,
                        resid_share=0.45) == 0.05 * 400 + 0.45 * 600


def test_women_15plus_keeps_each_emirate_total():
    import pandas as pd
    from scripts.build_cells import women_15plus
    cells = pd.DataFrame({"emirate": ["Dubai", "Dubai"], "adults": [1000, 1000],
                          "adults_worker": [800, 0], "women_worldpop": [336, 336]})
    emirates = pd.DataFrame({"adults": [2000], "women_worldpop": [672], "worker_adults": [800]},
                            index=["Dubai"])
    w = women_15plus(cells, emirates, worker_share=0.05)
    assert round(w.sum()) == 672           # same women, moved between cells
    assert w[0] < 336 < w[1]               # out of worker housing, into the residential cell
