# Examiner diagnostics, second pass (2026-11-06)

**Status: every number here is post-hoc on exposed data.** Nothing was reselected, no frozen file was changed, nothing was committed. Scripts and raw outputs are untracked files under `scratch/`.

Item numbers refer to section 2 of `scratch/examiner_report.md`: item 3 (deposit layer as calibration drift), item 5 (test could not show a put benefit), item 10 (selections sit on a grid edge).

Reproduction check: before any variant, the refit code reproduced the frozen `bank_six_deposits` and `sec_ten_generic` selections (alphas 1/100, 0.1/0.1; 1000/1000, 0.1/0.1) and test intervals to six decimals (+0.015012 [0.000559, 0.032661]; +0.069935 [0.028081, 0.124801]; −0.006598 [−0.010952, −0.002792]; +0.006480 [0.001666, 0.011008]). The refits import the frozen runner's own cohort builder, so matched samples are identical (5,706 and 9,510 rows).

## Commands and runtimes

| Script | Command | Wall time |
|---|---|---|
| `scratch/x1_deposit_refit_and_grid.py` (items 3 and 10) | `.venv/bin/python scratch/x1_deposit_refit_and_grid.py > scratch/x1_output.txt` | 4.6 s (2.2 s cohort build; each refit 0.1 to 0.3 s) |
| `scratch/x2_put_mde.py` (item 5, unconditioned curve) | `.venv/bin/python scratch/x2_put_mde.py > scratch/x2_output.txt` | 3.1 s |
| `scratch/x2b_put_mde_coverage.py` (item 5, coverage-conditioned curve, primary) | `.venv/bin/python scratch/x2b_put_mde_coverage.py > scratch/x2b_output.txt` | 3.2 s |

Environment: the worktree's `.venv` (Python 3.14.8, numpy 2.5.4, pandas 3.1.1), same as the Phase 0 freeze.

## Item 3. Deposit share as a deviation from each bank's trailing mean

Method: for each bank, the ratio at an origin minus the mean of that bank's prior K distinct filings (original vintage per period, strictly earlier period ends, past-only). Primary K = 8 filings with at least 4; secondary K = 4 with at least 2. Layers `ridge_price` and `ridge_market_sector` unchanged; `ridge_balance_dev` replaces the level with the deviation; `ridge_interactions_dev` adds deviation × XLF five-session return. Same alpha grid, same validation selection, same block bootstrap seeds. Rows unchanged (5,706 and 9,510).

Output (`x1_output.txt`, bank_six_deposits), test QLIKE difference versus `ridge_market_sector`, pointwise 95% interval:

| Feature form | 5 sessions | 20 sessions |
|---|---|---|
| Level (frozen) | +0.015012 [+0.000559, +0.032661] | +0.069935 [+0.028081, +0.124801] |
| Deviation, K = 8 | −0.002796 [−0.007223, +0.001470] | −0.001042 [−0.010498, +0.007588] |
| Deviation × XLF return, K = 8 | −0.000048 [−0.003782, +0.003354] | +0.008164 [−0.008723, +0.022828] |
| Deviation, K = 4 | +0.005592 [+0.001951, +0.009486] | +0.001419 [−0.000438, +0.003513] |

Validation QLIKE for the K = 8 deviation layer is slightly better than the market layer at both horizons (−5.29752 vs −5.29598; −3.57425 vs −3.56951). The deviation feature's split means are +0.0153 (train), +0.0046 (validation), −0.0020 (test) against standard deviations near 0.02 to 0.03, so the train/test gap that drove the level result is gone.

sec_ten_generic, liabilities/assets:

| Feature form | 5 sessions | 20 sessions |
|---|---|---|
| Level (frozen) | −0.006598 [−0.010952, −0.002792] | +0.006480 [+0.001666, +0.011008] |
| Deviation, K = 8 | −0.002947 [−0.006356, −0.000063] | +0.002468 [−0.002388, +0.006944] |
| Deviation, K = 4 | −0.001616 [−0.003660, +0.000201] | +0.000570 [−0.002976, +0.003731] |

Reading: in deviation form the deposit layer is a tight null at both horizons, with intervals of about ±0.007 and ±0.01 around zero. The frozen adverse result was the level's train-to-test drift, not information. The one-year trailing window (K = 4) leaves part of the trend in and shows a small residual harm at five sessions. The favourable liabilities/assets result shrinks by more than half and its 20-session harm disappears, so most of it was the same level artifact; a small five-session effect survives at the edge of significance. "Made forecasts worse" should read: the within-bank change in deposit share carries no 5- or 20-session variance information in this cohort; the cross-sectional hypothesis in the design rationale was never tested by this model form.

## Item 10. Wider ridge penalty grid

Method: 17-point grid from 0.001 to 100,000 replacing 0.1 to 1,000; every layer reselected on validation QLIKE; same seeds. Plus a same-penalty variant: the balance-sheet layer refitted at the market layer's selected alpha, to separate the feature from the regularisation.

Selected alphas (frozen grid in brackets):

| Cohort, horizon | ridge_price | ridge_market_sector | ridge_balance_sheet |
|---|---|---|---|
| bank_six, 5 | 0.001, edge [0.1] | 3 [1] | 300 [100] |
| bank_six, 20 | 0.001, edge [0.1] | 0.001, edge [0.1] | 0.001, edge [0.1] |
| sec_ten, 5 | 0.001, edge [0.1] | 1000 [1000] | 1000 [1000] |
| sec_ten, 20 | 0.001, edge [0.1] | 0.001, edge [0.1] | 0.001, edge [0.1] |
| core_ten, 5 | 300 [100] | 30 [10] | n/a |
| core_ten, 20 | 0.001, edge [0.1] | 0.001, edge [0.1] | n/a |

Test intervals under the wider grid: bank_six balance vs market +0.019771 [+0.000911, +0.042001] at 5 sessions and +0.072087 [+0.029633, +0.128475] at 20; sec_ten −0.006598 (unchanged) and +0.006770 [+0.001941, +0.011298]; core_ten ridge_price vs EWMA −0.057300 [−0.094349, −0.026399] and −0.070676 [−0.136659, −0.028473] (frozen −0.057330 and −0.070668).

Same-penalty variant, bank_six balance-sheet layer at the market layer's alpha: 5 sessions, alpha 1 instead of 100, +0.074244 [+0.047256, +0.103132]; 20 sessions unchanged (both already 0.1).

Reading: widening the grid moves no test conclusion. Every 20-session layer migrates from the old edge (0.1) to the new edge (0.001), so validation prefers an essentially unpenalised fit at 20 sessions and the "grid edge" finding is a property of the data, not of the grid. The same-penalty check reverses my earlier suspicion: heavy shrinkage at five sessions hid most of the deposit level's damage (+0.074 at the market layer's alpha versus +0.015 frozen); regularisation attenuated the artifact rather than causing it.

## Item 5. Minimum detectable put effect in the test period

Method: the selected long-put policy's increment over the unhedged book, per window, is fitted as a hinge in the unhedged window P&L U on the 244 overlapping offset windows from the Astra diagnostic. Primary form conditions on the coverage each window bought: inc = a + b × coverage × min(U − k, 0). Test-like samples are circular block resamples (block 4) of the 23 frozen test windows, drawing (U, coverage) pairs jointly; put P&L = U + curve + Gaussian residual (separate residual SD below and above the kink); estimand is the paired own-tail ES difference (worst 6 of 23). Power is the share of 400 outer samples whose inner 1,000-draw paired block-bootstrap interval excludes zero. MDE at 80% power is 2.80 × the outer SE. The overlapping offset windows are not independent, so the curve is descriptive.

Curve fit (`x2b_output.txt`): kink −3.75, premium drag a = −0.426, b = −1.309 per unit coverage, R² 0.950, residual SD 1.43 below and 0.24 above the kink. Implied slope at test mean coverage 0.351 is −0.46; at validation mean 0.70 it is −0.92. The unconditioned hinge (`x2_output.txt`) has kink −6.5 and slope −1.31, a slope above one that reflects COVID-era coverage near 1.0, which is why the coverage-conditioned form is primary. On that unconditioned curve the put increment overtakes the 75% book's linear increment at U ≈ −8.6.

| Sample | Implied ES reduction | SE | MDE (80%) | Power | Windows for 80% |
|---|---:|---:|---:|---:|---:|
| Test, offset 0 (23) | 0.92 | 0.76 | 2.14 | 0.21 | 125 |
| Test, offset 5 (23) | 1.61 | 1.02 | 2.85 | 0.36 | 72 |
| Train (27) | 0.05 | 0.50 | 1.41 | 0.01 | n/a |
| Validation (11) | 9.95 | 6.82 | 19.1 | 0.31 | 41 |
| Test U, coverage forced to 0.70 | 1.87 | 1.03 | 2.87 | 0.49 | 55 |
| Test U, coverage forced to 1.00 | 2.62 | 1.25 | 3.49 | 0.56 | 41 |
| Test with one window at −15% | 2.02 | 1.11 | 3.10 | 0.45 | 54 |
| Test with one window at −30% | 3.55 | 2.35 | 6.58 | 0.45 | 79 |
| Test with two windows at −20% | 4.25 | 2.60 | 7.30 | 0.58 | 68 |
| Test with three windows at −20% | 6.03 | 2.63 | 7.36 | 0.81 | 34 |

From the frozen interval directly: observed 0.580 with [−1.35, +0.25] implies SE about 0.41, so 90 test-like windows (about 22 years of quarters) would be needed for 80% power at the observed effect. The curve-implied test effect would need a 2.3× budget to reach its own MDE.

Reading: the test design had roughly one chance in five of detecting the effect its own payoff curve implies, and one chance in a hundred in a training-like sample. Adding a single crash of any depth from −15% to −30% leaves power at 0.45, because one window dominates a six-window tail and the block bootstrap drops it in most draws; three −20% quarters among 23 are needed to reach 0.80. The validation result's barely-significant interval is the same arithmetic with one crash. "Inconclusive in test" is therefore a design property, not weak evidence either way, and no single future crisis will change it under this estimand and this sample size. Coverage matters more than depth: the same test windows with validation-era coverage double the implied effect.

## Caveats

- Offset windows overlap; the payoff curve is a description of 244 dependent outcomes, not an independent sample.
- The hinge treats premium drag as constant; it scales with budget, so the 2.3× budget statement is approximate.
- Deposit deviation uses the original-vintage filing per period; same-period revisions are ignored, which is conservative for availability.
- These runs use the frozen 180-day staleness rules, the frozen splits and the frozen seeds; nothing was tuned on test.
