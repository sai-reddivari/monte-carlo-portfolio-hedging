# Conditional breadth and composition research

All50 requested current issuer IDs remain in the coverage audit. The master universe contains 42 complete histories; the 8 partial names are explicitly excluded without filling: KKR, BAM, APO, HOOD, PYPL, ARES, RKT, COIN. This retrospective full-history condition uses availability through2026 and is not an eligibility rule known in2020.

## Frozen experiment

Past-only calibration through 2020-12-31 uses 252 log returns and fixed20% diagonal covariance shrinkage. 5,000 Q paths are generated once for each full42-name master scenario, and every nested3/10/25/40 book takes its named columns from that cube. Total underlying notional stays $300,000. The canonical chain preserves the core three and core ten; two predeclared seeded chains vary composition. A common-shock correlation mixture is a synthetic stress, not an observed stress distribution. Historical realized volatilities are model-pricing proxies, not market implied volatilities.

The locked gate-1 rule is **maturity_band_050**. It is compared with daily and five-session rebalancing at 5 bp without reselection. Budget feasibility under the original $500 expected financed-cost cap is reported rather than assumed to generalize.

## Canonical policy outcomes

| scenario | breadth | policy | mean_pnl | pnl_std | loss_es95 | mean_financed_cost | cost_budget_upper_bound_passes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| calibrated_dependence | 3 | maturity_band_050 | -434.4049 | 2,843.4879 | 6,669.0869 | 488.0074 | True |
| calibrated_dependence | 3 | daily | -495.4137 | 2,750.3446 | 6,673.6766 | 545.5870 | False |
| calibrated_dependence | 3 | weekly | -278.9289 | 5,914.1613 | 14,178.9946 | 337.7407 | True |
| calibrated_dependence | 10 | maturity_band_050 | -450.5944 | 2,470.9075 | 5,914.6392 | 488.3296 | True |
| calibrated_dependence | 10 | daily | -505.9257 | 2,421.1595 | 5,947.5065 | 545.9319 | False |
| calibrated_dependence | 10 | weekly | -270.7831 | 5,256.0328 | 12,512.5241 | 337.8023 | True |
| calibrated_dependence | 25 | maturity_band_050 | -457.2340 | 1,821.4839 | 4,521.1266 | 487.5768 | True |
| calibrated_dependence | 25 | daily | -515.8194 | 1,792.1257 | 4,582.0542 | 545.2076 | False |
| calibrated_dependence | 25 | weekly | -300.5704 | 3,944.3502 | 9,539.4335 | 337.1190 | True |
| calibrated_dependence | 40 | maturity_band_050 | -452.3557 | 1,892.0692 | 4,640.8407 | 487.9497 | True |
| calibrated_dependence | 40 | daily | -513.6605 | 1,865.2031 | 4,713.8325 | 545.5937 | False |
| calibrated_dependence | 40 | weekly | -288.1529 | 4,102.5122 | 9,913.9770 | 337.5639 | True |
| synthetic_common_shock_stress | 3 | maturity_band_050 | -419.6845 | 3,092.0354 | 7,303.0655 | 487.7544 | True |
| synthetic_common_shock_stress | 3 | daily | -473.8461 | 3,000.0382 | 7,274.4316 | 545.3368 | False |
| synthetic_common_shock_stress | 3 | weekly | -235.8763 | 6,481.6143 | 15,521.7769 | 337.5447 | True |
| synthetic_common_shock_stress | 10 | maturity_band_050 | -441.7228 | 2,874.3209 | 6,862.2509 | 487.8636 | True |
| synthetic_common_shock_stress | 10 | daily | -498.7213 | 2,819.9290 | 6,926.2615 | 545.5363 | False |
| synthetic_common_shock_stress | 10 | weekly | -256.0762 | 6,131.2322 | 14,664.3812 | 337.5908 | True |
| synthetic_common_shock_stress | 25 | maturity_band_050 | -443.7042 | 2,309.4890 | 5,610.1046 | 487.3204 | True |
| synthetic_common_shock_stress | 25 | daily | -504.0515 | 2,271.2940 | 5,705.2401 | 544.9887 | False |
| synthetic_common_shock_stress | 25 | weekly | -277.0431 | 4,994.0225 | 12,042.9980 | 336.9135 | True |
| synthetic_common_shock_stress | 40 | maturity_band_050 | -437.5432 | 2,419.3639 | 5,825.3384 | 487.6301 | True |
| synthetic_common_shock_stress | 40 | daily | -501.0005 | 2,381.3507 | 5,923.5823 | 545.3340 | False |
| synthetic_common_shock_stress | 40 | weekly | -267.5222 | 5,242.4176 | 12,657.8237 | 337.3332 | True |

The full policy table also includes both seeded composition chains. `paired_ES_differences.csv` contains same-outcome bootstrap intervals for ES(locked) minus ES(reference), not ES of the P&L difference. A negative estimate favors the locked policy under this loss statistic. Pointwise intervals do not establish simultaneous dominance across all books or model validity.

## Actual static-equity diagnostic

| composition | breadth | periods | tail_observations | mean_20_session_pnl | mean_block_lower | mean_block_upper | pnl_std | loss_es95 | es95_block_lower | es95_block_upper | industry_weight_hhi | largest_current_industry_tail_contributor |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| canonical | 3 | 73 | 4 | 4,387.5006 | 366.6929 | 8,289.3258 | 20,122.0295 | 38,366.3984 | 25,892.0529 | 46,003.6904 | 0.3333 | Banks - Regional |
| canonical | 10 | 73 | 4 | 4,189.9567 | -47.2709 | 8,213.7007 | 21,201.7017 | 43,544.6044 | 26,856.9147 | 56,050.8436 | 0.3000 | Banks - Diversified |
| canonical | 25 | 73 | 4 | 3,894.9766 | 813.4750 | 6,855.5817 | 16,565.6259 | 32,446.3430 | 22,823.4001 | 34,905.6359 | 0.1200 | Banks - Diversified |
| canonical | 40 | 73 | 4 | 3,846.8809 | 883.0219 | 6,691.9373 | 16,312.2827 | 32,525.4480 | 22,010.7849 | 37,365.3375 | 0.1013 | Asset Management |
| seed_730711 | 3 | 73 | 4 | 3,118.1222 | -332.7878 | 6,198.3658 | 17,723.4643 | 36,138.8314 | 24,071.5195 | 49,813.6108 | 0.5556 | Financial - Data & Stock Exchanges |
| seed_730711 | 10 | 73 | 4 | 3,122.2443 | 114.2409 | 6,058.3380 | 17,145.9333 | 34,356.5153 | 23,882.8393 | 42,422.9375 | 0.2400 | Financial - Data & Stock Exchanges |
| seed_730711 | 25 | 73 | 4 | 3,603.2985 | 825.0292 | 6,431.4053 | 15,961.7136 | 32,433.7251 | 20,972.7285 | 38,282.4750 | 0.1296 | Financial - Data & Stock Exchanges |
| seed_730711 | 40 | 73 | 4 | 3,757.6468 | 759.3755 | 6,724.2061 | 16,874.0919 | 33,474.0534 | 22,951.7600 | 39,149.1540 | 0.1100 | Banks - Regional |
| seed_730712 | 3 | 73 | 4 | 2,915.0100 | -560.8497 | 6,342.0116 | 19,457.5566 | 38,938.6653 | 27,582.5395 | 44,772.4702 | 0.3333 | Banks - Regional |
| seed_730712 | 10 | 73 | 4 | 3,712.8975 | 1,157.9754 | 6,486.1797 | 15,572.5012 | 30,340.2039 | 19,991.3894 | 37,500.7889 | 0.2000 | Asset Management |
| seed_730712 | 25 | 73 | 4 | 3,663.8871 | 928.7784 | 6,466.0048 | 15,259.2749 | 31,811.1028 | 19,551.4573 | 38,383.7559 | 0.1200 | Financial - Data & Stock Exchanges |
| seed_730712 | 40 | 73 | 4 | 3,689.1863 | 764.7217 | 6,618.4045 | 16,221.7536 | 32,271.5227 | 21,980.2564 | 37,596.3765 | 0.1088 | Asset Management |

Each20-session interval holds equal initial dollar equity amounts and re-establishes the same notional at the next nonoverlapping interval. These are price-only diagnostics without derivatives, costs, funding or dividends. They condition on a2026 survivor/availability-selected cohort; they are not untouched-universe historical OOS. Current-industry tail contributions use the same worst portfolio intervals and sum to portfolio ES. Circular four-period block intervals address some serial dependence; the small number of tail periods does not become more independent evidence merely because more companies were observed.

## Stage-7 boundary

Computational breadth, label alignment, fixed-notional comparisons and explicit exclusion accounting pass. **The full stage-7 gate remains false.** Point-in-time membership, historically valid classifications, plausible derivative execution and untouched overlay-policy generalization are not supplied by this diagnostic. FMP's documented absence of options data also prevents a historical market-option backtest claim.
