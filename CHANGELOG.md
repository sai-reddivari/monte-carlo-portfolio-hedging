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

| Old path | New implementation path | Compatibility / evidence |
|---|---|---|
| `scripts/run_research_release_1.py` | `hedging_harness/experiments/run_research_release_1.py` | CLI and imported names preserved |
| `scripts/run_model_contract_replay.py` | `hedging_harness/experiments/run_model_contract_replay.py` | CLI and imported names preserved |
| `scripts/run_risk_research.py` | `hedging_harness/experiments/run_risk_research.py` | CLI and imported names preserved |
| `scripts/run_feature_research.py` | `hedging_harness/experiments/run_feature_research.py` | CLI and imported names preserved |
| `scripts/run_breadth_research.py` | `hedging_harness/experiments/run_breadth_research.py` | CLI and imported names preserved |
| `scripts/run_overlay_research.py` | `hedging_harness/experiments/run_overlay_research.py` | CLI and imported names preserved |
| RiskProtocol, breadth/replay defaults and ridge grid in code | `config/published_defaults.json` | Original defaults, split placement, seeds, floating values and ordering retained |

Configuration extraction: 94/94 saved CSVs remain byte-identical; selected ES95 before/after `3327.944637142751`, delta `0`. These are existing experiments, with no strategy or parameter tuning.
