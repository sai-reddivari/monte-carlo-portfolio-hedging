"""Evaluation interfaces; arithmetic preserved from the frozen core."""
import numpy as np
import pandas as pd


def summarize(result):
    """Dollar metrics. ES95 = negative mean of worst ceil(5%*N) P&Ls.

    It is allowed to be negative if even that tail is profitable. mean_se is
    Monte Carlo uncertainty in the mean, not economic risk or a tail interval.
    Costs are already included in net P&L and must not be subtracted again.
    """
    rows = []
    for j, name in enumerate((*result.names, "Portfolio")):
        total = j == len(result.names)
        take = lambda x: x.sum(axis=1) if total else x[:, j]
        pnl = take(result.terminal_pnl)
        m = len(pnl)
        std = pnl.std(ddof=1) if m > 1 else np.nan
        rows.append(dict(name=name, paths=m, mean_pnl=pnl.mean(), mean_se=std/np.sqrt(m),
            pnl_std=std, rmse=np.sqrt(np.mean(pnl**2)), pnl_p05=np.quantile(pnl,.05),
            loss_es95=-np.sort(pnl)[:max(1,int(np.ceil(.05*m)))].mean(),
            mean_cost=take(result.nominal_costs).mean(),
            mean_financed_cost=take(result.financed_costs).mean(),
            mean_turnover=take(result.turnover).mean(), mean_trades=take(result.trade_counts).mean()))
        borrowing = (result.peak_portfolio_borrowing if total
                     else (None if result.peak_borrowing is None else result.peak_borrowing[:, j]))
        rows[-1].update(
            mean_peak_borrowing=np.nan if borrowing is None else np.mean(borrowing),
            peak_borrowing_p95=np.nan if borrowing is None else np.quantile(borrowing, .95),
            max_peak_borrowing=np.nan if borrowing is None else np.max(borrowing))
    return pd.DataFrame(rows).set_index("name")



def paired_difference(left, right):
    """Compare results sharing actual stock paths and asset order.

    Legacy manually constructed results without fingerprints retain shape/name
    checks; results produced by hedge carry computed fingerprints automatically.
    """
    if left.names != right.names or left.terminal_pnl.shape != right.terminal_pnl.shape:
        raise ValueError("Paired results must have matching names and shape.")
    if (left.scenario_id is not None or right.scenario_id is not None) and left.scenario_id != right.scenario_id:
        raise ValueError("Paired results must have matching scenario IDs (actual paths and asset order).")
    d = (left.terminal_pnl - right.terminal_pnl).sum(axis=1)
    se = d.std(ddof=1) / np.sqrt(len(d)) if len(d)>1 else np.nan
    return {"mean_difference":float(d.mean()), "paired_se":float(se),
            "mc_95_low":float(d.mean()-1.96*se), "mc_95_high":float(d.mean()+1.96*se)}

