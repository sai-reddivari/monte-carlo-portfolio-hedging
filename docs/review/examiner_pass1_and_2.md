# Independent examiner report: Research Release 2 (snapshot 71c0be1)

## 1. Claims audit

The document does not number its claims. Rows 1 to 16 follow its boundary table in order, and rows 17 to 21 are its later sections. "Folder" means the frozen evidence folder.

| # | Claim | Verdict | What I checked |
|---|---|---|---|
| 1 | Release status | Supported | `release-2/manifest.json`: publication_ready true, research_gate_2_passed false. Its 297 checks are hashes, presence and links. None tests a number in the prose. |
| 2 | Option prices are model prices | Supported | `astra_overlay_independent_portable.py` prices from a normal CDF with no quote input. |
| 3 | Budget is an allowance | Supported | Worst multiples 1.304, 2.599, 1.269, 4.125, 1.303 and 6.517 recomputed from `window_records.csv`. |
| 4 | Exposure drift | Supported | Test gross 126.644 to 140.634 recomputed from `window_records.csv`. |
| 5 | Collar exposure and upside | Supported, understated | `metadata.json`: +50.401 and -5.385. The folder's `terminal_pnl_reconstruction.csv` also holds the frozen half-size book, which nobody compares. See item 2. |
| 6 | Beta field omits options | Supported | `selected_test_summary.csv`: beta 67.14 for unhedged and every option policy. |
| 7 | XLF "cost" is underperformance | Supported | -0.086 less 1.644 is -1.73 in `selected_test_summary.csv`. |
| 8 | Tail is worst six of 23 | Supported | `metadata.json`, statistic field. |
| 9 | Episodes are clusters | Not in folder | Only `results/equity-overlays-20261106T023430248130Z/tail_episodes.csv` shows the four test clusters. |
| 10 | Drawdown definition | Supported | `hedging_harness/overlays.py:433`, and the owner check of 18.011 with +4.936. Marks stay uncertified. |
| 11 | Short calls purchased, tail worse | Supported | `paired_es_diagnostics.csv`: +0.237, interval 0.150 to 0.286. |
| 12 | Sleeve capture 0.946109, 0.946695 | Partly | The second figure exists only in `owner_checks_output.txt`, the owner's own check. |
| 13 | Forecast metrics | Not in folder | No forecast diagnostic is archived. Numbers reproduce from `results/feature-research-20261106T024244836968Z/scores.csv`: MSE skill -0.293. |
| 14 | Ten names, six banks | Not in folder | Reproduces from `cohort_coverage.csv`: 276 and 69 origins. |
| 15 | Funding interpretation | Supported, too weak | The adverse result is a level shift. See item 3. |
| 16 | Inconclusive is not null | Supported | `metadata.json`: multiplicity_adjusted false. |
| 17 | Realized premium spend | Supported | All ten aggregate ratios recomputed, including 0.072 and 1.166. |
| 18 | Independent review scope | Supported | 2,013 rows, residual 1.19e-7, 276 legs, 216 test cases, no failures. |
| 19 | Comparisons with the 75% book | Supported | All five rows match the block-4 rows of `paired_es_diagnostics.csv`. |
| 20 | Window placement | Numbers supported, pre-commitment partly | `comparisons.csv` matches. `pre_run_commitment.json` is written by line 33 of the same script, 61 seconds before completion. |
| 21 | Conclusions to avoid | Partly | Highest risk ratio in the 16 tail windows is 1.239. The "not attributed to exposure" wording is weaker than the folder's data allows. |

## 2. Hidden signal and alternative explanations

Tail loss means each policy's mean loss in its own worst quarter of windows. All figures are percent of capital per window. Every check is post-hoc on exposed data.

1. **Obvious. Under model prices, purchased protection matched or trailed a smaller book except in three deep selloffs.**
   - Evidence: `windows.csv` and `development_windows.csv`. I compared each candidate with a scaled book of the same starting delta, which avoids matching on realized upside. In test, 22 of 30 frozen option and ETF candidates had a higher tail loss and a lower mean. Selected puts had tail 5.700 against 5.513 and mean 1.451 against 1.577. In validation 26 of 30 beat it, and selected puts had 2.029 against 10.273. Puts beat the 75% book in 4 of 25 loss windows: 2011 Q3, 2016 Q1, 2018 Q4, 2020 Q1.
   - Cheapest test: repeat on the four offsets in `window_records.csv`. One minute, from `scratch/d3_grid_vs_scaling_and_breakeven.py`.
   - Confidence: high. Conclusion becomes: for these contracts, value over exposure reduction sits in three of 61 quarters and is absent elsewhere, not merely unestablished.

2. **Obvious. The collar is matched by the frozen half-size book, and its tail is a rally tail.**
   - Evidence: test tail 2.906 against 2.637, mean -0.033 against 1.325, upside 13% against 57%. Paired tail difference is +0.27, interval -0.90 to +1.80. Four of the collar's six worst test windows are not baseline tail windows. Its worst, -5.10, is the window where the unhedged book made +13.18. At a 0% rate the tails are 4.378 against 3.386.
   - Cheapest test: done in `scratch/b2_collar_tail_and_reduced50.py`. Two seconds.
   - Confidence: high. Conclusion becomes: the collar bought nothing that halving the book lacked, and it turns a net-long book net short in rallies.

3. **Orthogonal. The deposit result is calibration drift, not evidence about funding information.**
   - Evidence: `predictions.csv` and `selected_models.json`. The twenty-session coefficient is -0.262. Deposit share rose at all six banks after 2020, so the layer lowered every twenty-session test forecast, by 0.226 log points on average. Multiplying the reference forecast by that constant reproduces +0.0639 of the +0.0699 damage. With each bank's average shift removed the difference is +0.001, interval -0.004 to +0.007. The favourable liabilities/assets result is the same effect, since a constant reproduces -0.0062 of -0.0066. Within-bank correlation with later variance flips from -0.33 in training to +0.17 in test.
   - Cheapest test: refit one cohort with the ratio as a deviation from each bank's trailing mean. About two minutes.
   - Confidence: high on mechanism. Conclusion becomes: "made forecasts worse" turns into "untested in either direction."

4. **Obvious. The validation put advantage is a price effect: the coverage 2% bought at 20% volatility.**
   - Evidence: gross put payoff per unit of coverage is one function of long-sleeve loss beyond 10% across all 61 windows, R-squared 0.97. Two windows of equal depth split on coverage. In 2018 Q4, depth -16.0% and coverage 0.93, puts lost 2.65 against 5.10 for the 75% book. In 2022 Q2, depth -16.2% and coverage 0.39, puts lost 6.30 against 5.70. In `sensitivity.csv`, validation put tail at 1.5 times volatility is 8.979 against 9.034 for the 75% book.
   - Cheapest test: twelve real quotes, three-month 90% puts on the six long names on 2018-10-01 and 2020-01-02. One hour once sourced.
   - Confidence: medium. Conclusion becomes: the one positive result survives only if those puts cost near trailing volatility.

5. **Obvious. The test period could not have shown a put benefit.**
   - Evidence: the deepest test long-sleeve return is -16.2%, against -45.8% in validation. Only four test windows had an average long-sleeve loss beyond the 10% strike gap. Rescaling test coverage to validation's 0.70 gives tail 5.30, still above the 75% book's 4.46. The unhedged tail itself moves from 5.13 to 7.82 across offsets, while the largest put effect is 1.21.
   - Cheapest test: minimum detectable effect by resampling the payoff curve. Five minutes.
   - Confidence: high. Conclusion becomes: "inconclusive in test" is a design limit, not weak evidence either way.

6. **Orthogonal. Expiry payoff is fragile to window phase, and protection during the drawdown is not.**
   - Evidence: `window_records.csv`. Validation puts cut the tail by 84%, 65%, 63% and 25% of baseline across offsets. They cut the worst-quartile interim drawdown by 41%, 43%, 41% and 33%. The 75% book cuts 26% at every offset. In test puts cut the drawdown by 10% to 19%, below the 75% book.
   - Cheapest test: re-mark the saved legs at the trough with stressed volatility. Needs a replay of 44 windows, minutes.
   - Confidence: medium, because marks use entry volatility and are uncertified. Conclusion becomes: the sign change at offset 42 applies to expiry payoff only.

7. **Obvious. Variance forecasts time volatility, not hedge payoff.**
   - Evidence: I took the locked twenty-session ridge forecast over pricing volatility at each decision date. Its rank correlation with realized over pricing volatility is 0.50 across 61 windows and 0.73 in test. With put net payoff it is 0.14, p 0.28, with -0.43 in validation and +0.39 in test. The frozen risk ratio stays within plus or minus 0.17 at all four offsets. A calm-before-tail pattern I found at offset 0, p 0.04, vanished at the other three.
   - Cheapest test: done in `scratch/c2_forecast_to_hedge_and_phase.py`.
   - Confidence: medium. Conclusion becomes: the necessary condition for forecast-to-hedge value fails at 63 sessions.

8. **Probably wrong but interesting. Deposit share ranks who loses in a funding shock.**
   - Evidence: six banks, 2023-03-08 to 2023-05-04. Rank correlation of deposit share with return is -0.83, p 0.04. It is +0.26 in COVID and +0.20 in April 2025. Bank size is a confound.
   - Cheapest test: the same event study on the 42-name panel with SEC deposit tags, plus failed banks. About an hour of fetching.
   - Confidence: low. Conclusion becomes: funding structure matters for cross-sectional tail exposure, the target it was not tested on.

9. **Obvious. The 4% rate with no dividends flatters the collar and the reduced book.**
   - Evidence: `sensitivity.csv` at 0%. Collar coverage falls from 1.00 to 0.49, its delta moves from -5.4 to +23.0, and its tail cut falls from 3.37 to 2.39. The 75% book's upside falls from 78.7% to exactly 75.0%.
   - Cheapest test: rerun with pricing carry at zero and cash at 4%. One config change. The saved scenario moves both.
   - Confidence: medium. Conclusion becomes: base-case collar figures are an upper bound.

10. **Obvious. Both selections sit on a grid edge.**
    - Evidence: `validation_selection.csv`. Every twenty-session ridge layer picked 0.1, the smallest penalty, on 84 training dates. Per `protocol.json`, the overlay rule picked the largest eligible budget in three of four budgeted families.
    - Cheapest test: widen the penalty grid. Seconds.
    - Confidence: high, small effect. Conclusion becomes: validation mostly chose "spend the maximum."

## 3. Non-traditional framings

| Framing | What it would have measured | Usable proxy in the repo |
|---|---|---|
| Break-even depth | The loss depth where puts overtake scaling, and how often quarters exceed it | Yes. Puts overtook the 75% book beyond about 16% long-sleeve loss at coverage 0.9, or 26% at coverage 0.4. Three of 61 quarters qualify clearly. |
| State-contingent protection | Loss in bad states fixed in advance, plus new bad states the overlay creates | Yes. Mean result in baseline test tail windows: collar -0.65, half-size book -2.64, ETF hedge -2.83, 75% book -4.46, puts -5.70. |
| Price taking | Coverage per premium dollar as the decision variable | Partial. The coverage and full-coverage premium columns in `windows.csv`. |
| Carry comparison | Premium bleed against the return forgone by a delta-matched cut | Yes. Test mean gap for selected puts is -0.126 per window, about -0.5% a year. |
| Phase as noise floor | Offset spread of each statistic as its measurement error | Yes. Baseline test tail spread is 2.7 points. Proportional cut spread is 1.7 points for the 75% book and 12 for puts. |

## 4. Kill list

- **Laddered expiries, Opus item 1.** Deprioritise. Phase fragility is confined to the expiry payoff of one event, and one crash cannot evaluate a ladder.
- **Crisis simulator, Opus item 5.** Drop. Payoff is already a known function of depth and coverage, so a simulator returns the crash frequency and option price fed into it.
- **Adaptive against static puts, Sol item 3.** Deprioritise. The signals carry no payoff information at four offsets, and 61 windows cannot resolve a timing rule.
- **Usable liquidity, Sol item 2.** Defer. Ledger borrowing peaked at zero for every policy because short proceeds count as cash, so the engine cannot yet express a liquidity need.
- **Loss decomposition, Sol item 1 and Opus item 4.** Shrink to an hour. Long and short sleeve correlation is -0.92 to -0.95 in every split, and the tail is the long sleeve.
- **Cash-in rule, Opus item 2.** Keep the measurement and drop the sell-and-reset rule until marks reflect implied volatility.
- **Real-quote check, Opus item 3.** Keep, but narrow it to the twelve quotes in item 4.

## 5. Three questions for the original designer

1. Is a loss in a rally a bad state for this mandate? The answer decides whether the collar's own-tail figure or its baseline-tail figure is the right one.
2. Were the 2% budget, the 10% strike gap and the 25% cut meant to be cost-matched, and what quarterly loss must the book survive? Why was the frozen 50% book left out of every report?
3. Was deposit share meant to track one bank through time or to rank banks against each other? With issuer intercepts the model used only the first.

## 6. What I could not check

- **Option quotes and implied volatility.** None in the repo, so the size of the pricing bias is unknown.
- **Dividends and a dated rate series.** Absent, and the 0% scenario changes pricing and cash interest together.
- **Daily NAV paths.** Only one drawdown number per window is saved, so value at the trough against expiry is unmeasured.
- **Sensitivity runs for the half-size book and non-selected candidates.** Not saved. My 0% figure for the half book scales the unhedged row linearly.
- **Failed and acquired banks.** Absent. Item 8 rests on six survivors.
- **Review inputs.** The removed Astra briefing, the three reviewers' raw outputs and Opus's paused seven-lens review left no artifacts. The forecast reconstruction described in `docs/feature_research.md` has no archived output.
- **Tests and experiments.** I ran neither. Bundle hashes match for 47 of 48 entries, and the listed `.DS_Store` is missing.
- **Scratch folder.** My thirteen scripts are the `a`, `b`, `c` and `d` prefixed files in `scratch/`. Four `examiner_*.py` files appeared there during this session from another process. I did not write, run or change them.

## 7. Second pass: design rationale, Phase 0 and three computations

Inputs: `Astra Design Rationale.md` (found at `/Users/saireddivari/MonteCarloEvaluations/scratch/`, not in this worktree), `docs/PHASE0_REPORT.md` and `results/manifest_pre_refactor.json` in the main repo, read only. The authors' lineage answer closes rows 9, 13 and 14. Bundle check re-run: 47 of 48 verify, `.DS_Store` missing. Both new rounding errors confirmed against `comparisons.csv` (4.095485 printed 4.096; −0.230527 printed −0.230); Phase 0 records a third (3327.95 for 3327.9446). Computations, commands, runtimes and outputs are in `scratch/examiner_diagnostics.md`. Everything below is post-hoc on exposed data.

### Q1. Assumptions the data contradicted, and whether the authors noticed

| Rationale assumption | What the data did | Noticed? |
|---|---|---|
| Funding ratios separate banks facing the same sector move; "no universal sign" is assumed | Implemented as one pooled coefficient with issuer intercepts, so only each bank's level over time could matter, and that level's relation to variance inverted (within-bank correlation −0.51 train, +0.25 test). As a deviation from each bank's trailing mean the layer is a tight null: −0.003 [−0.007, +0.001] at 5 sessions, −0.001 [−0.010, +0.008] at 20. | The adverse number, yes. That the model form contradicted the rationale, no. The layer was already worse in validation at both horizons. |
| Validation selects among predefined candidates | Its tail is three windows, one of them COVID. Selection took the maximal variant in the ETF and collar families, and the adaptive arm equals the static 1% put in every tail window of both splits (ES 6.788 and 5.990 for both). | "Validation holds the largest loss", yes. The adaptive arm's collapse into its static twin, no. |
| Adaptive coverage from past-only risk estimates tests timing | The signal was read once per 63 sessions. It crossed 1.25 mid-window in four of six test tail windows and four sessions into COVID. | Treated as "signal late"; the sampling frequency was not questioned. |
| Puts protect against "substantial declines" | Power of the 23-window test against its own curve-implied effect is 0.21. One −30% quarter raises it to 0.45; three −20% quarters are needed for 0.80. | Called "inconclusive"; no power statement anywhere. |
| A budget "specified before test" | Realized 1.3× to 4.1× | Yes, errata. |
| One reduced-exposure benchmark is "essential" | Two scales were frozen; `primary_scale: 0.75` kept the half-size book out of every table | Not until review. |

### Q2. What I would have designed, and what the intent does to section 2

- Funding: test the cross-sectional claim the rationale makes, rank of loss within sector drawdowns or within-bank change, not a pooled level. The deviation refit turns item 3 from "untested" into a null for the time-series form and leaves item 8 as the only funding hypothesis still open.
- Selection: pool train and validation, 38 windows, and report the pick under each sample. The design's own success standard names predetermined equity reduction as a required comparator, so items 1 and 2 are the design's reading applied, more likely to stand. Item 10 is confirmed trivial: the wider grid moves no test interval; the 20-session layers migrate to the new edge at 0.001.
- Evaluation: pre-register the payoff kink and a power statement, and promote the drawdown the rationale lists as an accompanying metric to a secondary estimand. Item 6 becomes more likely to matter; item 5 becomes a design fact.
- Adaptive arm: daily-sampled trigger with mid-window entry at the 20-session horizon. Item 7 is what the rationale itself warned, "forecast accuracy alone will not establish economic hedge value", so no surprise.
- Pricing and carry, items 4 and 9: the rationale is silent on volatility source and rates; unchanged.

### Q3. Does the rationale or Phase 0 explain the three results?

- Deposit share: partly. The rationale refuses a universal sign and frames vulnerability cross-sectionally; the ridge imposes one sign on a within-bank level. The same-penalty refit, balance layer at the market layer's alpha of 1, gives +0.074 [+0.047, +0.103], five times the frozen +0.015, so heavy shrinkage hid most of the level damage at five sessions rather than causing it. Phase 0 shows the full feature run replays in 5.5 s; the refit takes 0.1 s per cohort. This was always a cheap check.
- Window sensitivity: explained by neither. The frozen objective, validation ES over the worst quarter of 11 windows, makes selection hostage to one window's phase, and the rationale's accompanying drawdown metric was never used to test it. Phase 0 replays the four-offset diagnostic in 73.6 s, so all 63 phases cost about 20 minutes.
- Half-size book: explained by `primary_scale: 0.75` plus the rationale's singular "reduced-exposure arm". It was computed, hashed (Phase 0: 0 differing cells), reconstructed by Astra within the 2,013 rows, and never tabulated. A reporting flag, not a computation gap.
