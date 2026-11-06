# Technical qualifications and display corrections

This reference supplies definitions used in the [research study](research_study.pdf). It does not report a separate experiment or replace the original saved outcomes.

| Quantity | Interpretation |
|---|---|
| Controlled ES95 | Average loss in the worst 5% of 10,000 held-out simulated paths. Policies share paths. |
| Historical tail loss | Average loss in the worst six of 23 separate 63-session test accounts; a 25% tail fraction with ceiling rounding. |
| Upside retained | Aggregate policy gain divided by aggregate unhedged gain in windows where the unhedged book gains. It is not an annual return. |
| Historical drawdown | Maximum running-peak NAV minus current NAV, divided by initial capital. It is neither running-peak-normalized drawdown nor full-period chained-NAV drawdown. |
| Gross and net exposure | 130% gross and 50% net are decision-close targets. Lagged execution produces test initial gross exposure of 126.644%–140.634%. |
| Option-inclusive exposure | Local Black–Scholes dollar delta is not market beta. The saved beta field covers equity/ETF sleeves and omits options. |
| Premium allowance | Decision-time sizing allowance, not an execution-enforced cap. Worst-window spending can exceed it even when aggregate spending does not. |
| XLF underperformance | A P&L difference from the unhedged book includes exposure and financing; it is not transaction cost or option premium. |
| Short-sleeve calls | Purchased calls protect short equities. They can reduce sleeve losses while worsening whole-book tail loss. |
| Financing-adjusted short capture | 0.946695 including marginal premium financing, versus 0.946109 in the original sleeve measure. This is a side-specific result. |

## Inference and validation

Reported bootstrap intervals are pointwise. An interval crossing zero does not prove that protection has no value, and an interval excluding zero is not a multiplicity-adjusted discovery guarantee. Shifted windows overlap and do not add independent historical crises. All additional comparisons on already observed outcomes are post-hoc.

Independent terminal reconstruction checks 2,013 candidate/window outcomes, with maximum absolute terminal-P&L discrepancy of $1.1921e-7. The collar reconstruction checks 276 test legs. These checks do not certify every intrawindow mark, every sensitivity, vendor observations or executable fills. Validation code and reference tables are under [tests/](../tests/README.md).

## Corrections to earlier displays

The current paper uses direct rounding of the saved full-precision results. No conclusion changes.

| Quantity | Earlier display | Correct display | Full precision |
|---|---:|---:|---:|
| Selected controlled-policy ES95, dollars | 3,327.95 | 3,327.94 | 3327.944637142751 |
| Validation put benefit versus 75% equity, offset 21 | 4.096 | 4.095 | 4.095485201507027 |
| Same comparison, offset 42 | −0.230 | −0.231 | −0.23052718796931604 |

Sources: [controlled evaluation](../results/research-release-1/release-1/evaluation_metrics.csv) and [window-placement comparisons](../tests/artifacts/independent_validation/window_placement/comparisons.csv).
