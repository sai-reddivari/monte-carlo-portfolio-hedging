# Financial sector hedging research evidence checkpoint

**Conditional Research Release 2: ready for separate human review.** No public upload has occurred.

[Publication summary](../docs/Final%20Findings%20and%20Takeaways/research_release_2_publication.md) · [Claims and errata](../docs/Final%20Findings%20and%20Takeaways/research_release_2_claims_and_errata.md) · [Opus owner addendum](../docs/equity_overlay_review_addendum.md)

**Research Gate 1 is complete for the controlled synthetic study and independently reproduced. Full empirical Research Gate 2 remains open.** Publication readiness does not certify market execution or survivorship-safe generalization.

The locked maturity-sensitive hedge has held-out ES95 $3,327.95 and mean financed stock cost $487.97, with a $490.18 upper endpoint under its $500 expected-cost screen. ES95 improves relative to weekly; the daily comparison is inconclusive at lower cost.

| Workstream | Canonical evidence | Scope |
|---|---|---|
| Shared inputs | `config/illustrative_study.json`, `data/study_inputs/` | One validated source; Book retained |
| Market panel | [Data gate](../data/market/data_gate_status.json) | Ten names plus SPY/XLF; 4,236 sessions; current-survivor universe |
| Breadth coverage | [Data coverage](../docs/data_coverage.md) | Fifty current names: 42 complete, eight partial histories retained |
| model replay | [Report](../results/model-contract-replay-20261106T014523263280Z/report.md) | Historical stocks; hypothetical European options; accounting and lifecycle checks |
| price risk | [Report](../results/risk-research-20261106T014747676804Z/report.md) | Past-only five-/twenty-session risk forecasts; chronological evaluation |
| incremental features original | [Report](../results/feature-research-20261106T024225834886Z/report.md) | Original three-name/two-bank cohorts; retained for comparison |
| incremental features | [Report](../results/feature-research-20261106T024244836968Z/report.md) | Final ten-name liabilities/assets and six-bank deposit extension; mixed and adverse results retained |
| conditional breadth | [Report](../results/breadth-20261106T020730752645Z/report.md) | 3/10/25/40-name common-path computations; current availability conditioned; not full stage7 certification |
| equity overlays | [Report](../results/equity-overlays-20261106T023430248130Z/report.md) | 23 separate quarterly test accounts; model prices; worst six-window mean loss; independent terminal reconstruction |

Astra independently reconstructed all 2,013 base-case stage6 terminal outcomes with maximum P&L discrepancy $1.1921e-7, all 276 test collar legs and original bootstrap intervals. This does not certify all intrawindow marks/drawdowns, sensitivity runs or vendor/execution assumptions.

Reviewer evidence is preserved outside `/tmp` in the [Astra archive](../results/research-release-2/astra-review-20261106/archive_manifest.json); the [Opus archive](../results/research-release-2/opus-review-20261106/archive_manifest.json) preserves his addendum/checks. Original frozen reports are unchanged. Post-hoc comparator and window-placement diagnostics are labelled in the claims supplement.

The combined suite passed **194 tests plus 22 subtests**, with 28 pandas timezone deprecation warnings and no failures. [Recorded test cases](release_2_tests.xml) · [Integrity/link verification](release_2_verification.json).

The final feature extension covers ten names/six banks, not only the earlier three names/two banks. Liabilities/assets gives a small five-day QLIKE gain and worse twenty-day QLIKE; deposit-share features worsen incremental QLIKE. Forecast-to-hedge value remains unestablished.

No historical option quotes or observed implied volatility were acquired. Remaining empirical requirements include market quotes/contract terms, historical membership and failed names, realistic execution/financing and a separately frozen forecast-to-hedge study. A negative or inconclusive result does not block this conditional publication.

[Next-protocol requirements](../docs/next_economic_protocol_requirements.md) are recorded separately; the exact new economic protocol has not been frozen or run. Retrospective remeasurement does not restore untouched-test status.

Machine-readable state: [research_status.json](research_status.json). Canonical releases are pinned in `config/research_release_2_package.json`; status no longer selects a result by filesystem modification time.
