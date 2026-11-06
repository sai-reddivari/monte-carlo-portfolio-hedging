# Publication refactor changelog

Frozen tag: `pre-refactor` = `a96d99210ea16ac2dd33f46623aaf96cbc563196`. Original artifacts and pre-refactor notebook copies remain unchanged. Compatibility modules/links preserve historical entry paths. No commit is amended or squashed.

| Old path | New implementation path | Compatibility / evidence |
|---|---|---|
| `hedging_harness/core.py`: Book, HedgeResult and validation | `hedging_harness/domain.py` | Original imports remain available through core.py |
| `hedging_harness/core.py`: load_study | `hedging_harness/data_loading.py` | Same JSON and insertion order |
| `hedging_harness/core.py`: correlated paths | `hedging_harness/simulation.py` | Function/class ASTs unchanged; 94 CSV comparisons byte-identical |
| `hedging_harness/core.py`: hedge | `hedging_harness/hedging.py` | Cash, costs and reduction order unchanged |
| `hedging_harness/core.py`: summarize, paired_difference | `hedging_harness/evaluation.py` | Full-precision results preserved |
| `hedging_harness/core.py`: provenance | `hedging_harness/reporting.py` | New module identities are metadata, not economic results |
| `BlackScholes_Functions/BlackScholes_D1D2_Price_Payoff_Greeks.py` | `hedging_harness/pricing.py` | Original module is a compatibility import; formula bodies unchanged |

Structure validation: 194 tests and 22 subtests passed. All eight research variants matched 94 saved CSVs (1,870,832 numeric cells), including selected ES95 before/after `3327.944637142751`, delta `0`.
