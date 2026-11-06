"""Recompute Astra's post-hoc window-placement table from its raw records.

Usage, from the repo root: .venv/bin/python results/equity-overlays-review-20261106/window_placement_check.py PATH_TO_window_records.csv
Post-hoc and descriptive. Offsets overlap and must not be pooled.
"""
import math, sys
import numpy as np, pandas as pd

pd.set_option("display.width", 200, "display.max_columns", 20, "display.max_rows", 80)
records = pd.read_csv(sys.argv[1])


def es(values, tail=.25):
    ordered = np.sort(values)
    return -ordered[:math.ceil(tail * len(ordered))].mean()


rows = []
for (offset, split), frame in records.groupby(["offset_sessions", "split"]):
    pivot = frame.pivot_table(index="start", columns="label", values="pnl_pct")
    base, reduced = es(pivot["unhedged"].to_numpy()), es(pivot["reduced_75"].to_numpy())
    row = dict(offset=offset, split=split, windows=len(pivot), worst_unhedged=round(pivot["unhedged"].min(), 2))
    for label in pivot.columns:
        if label != "unhedged":
            row[label] = round(base - es(pivot[label].to_numpy()), 3)
    row["puts_vs_reduced"] = round(reduced - es(pivot["long_put_k90_b2"].to_numpy()), 3)
    row["collar_vs_reduced"] = round(reduced - es(pivot["collar_95_110_b2"].to_numpy()), 3)
    rows.append(row)
print(pd.DataFrame(rows).sort_values(["split", "offset"]).T.to_string())
