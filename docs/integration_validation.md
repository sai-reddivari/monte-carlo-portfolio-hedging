# Independent shared-input and notebook integration review

This review covers `hedging_harness/study.py`, the canonical controlled-study source, its generated relational views, notebook input integration, and the cached Research Release 1 notebook. It is separate from the implementation owner and from the independent numerical re-execution of all 28 production policy cases documented in `docs/independent_validation.md`.

**Result: the shared-input and cached-release integration checks pass after one cache/source-identity correction by the notebook owner.** No existing implementation module or notebook was edited by this reviewer. Five compact cross-boundary regression tests were added in `tests/test_integration.py`.

## Canonical input identity

The authoritative controlled-study source remains `config/illustrative_study.json`, with SHA256:

`17a3148a1fa6f6826edac8a835b77ae9b940735c7eb76e7b01bb6ca30808694d`

`load_named_inputs` first uses the validated `Book` loader, then creates named notebook views of its fields. The `Book` class remains the numerical input container, as requested. The named portfolio, path-volatility map and named correlation pairs preserve the source asset ordering and field associations. They are derived views rather than independently maintained model defaults.

Notebooks 00–03 now obtain the book/scenario inputs and baseline seed/path count from the shared source. Experiment-specific controls, such as which option to inspect, hedge frequencies, cost grids and sensitivity settings, remain explicit in the notebooks and are recorded with their actual values. This review does not claim that changing every possible experiment control in one file automatically propagates to all unrelated experiments.

Notebook 00 correctly restores the `Book` constructor after the abandoned DataFrame exploration, initializes the project import path before importing the shared loader, and retains the user's consistent `option_delta_shares` and `equity_hedge_shares` names. Delta remains a share-equivalent sensitivity; dollar delta adds spot multiplication. Stock hedge shares offset option delta at reset times without removing gamma or discretization risk.

## Derived input tables and accounting semantics

The actual committed files in `data/study_inputs` were compared with freshly generated shared-source views, and every source/file checksum in their manifest was verified.

| Table | Verified meaning |
|---|---|
| `underlyings.csv` | Unique stable study identifiers, USD, an explicitly synthetic 252-session calendar and illustrative classifications |
| `instruments.csv` | Unique model call identifiers linked to valid underlyings; European cash settlement; relative session expiry rather than an invented calendar expiry |
| `positions.csv` | Valid instrument foreign keys; negative signed call quantities; explicit multiplier of 1 |
| `model_observations.csv` | Aligned spot/pricing-vol/path-vol/rate observations carrying the shared source hash and `market_observed=False` |

For the canonical three names, each signed quantity is −1,000 share-equivalent call units. Multiplying its magnitude by multiplier 1 and spot 100 reconstructs the $100,000 underlying notional. The multiplier fields in positions and instruments agree; they should not both be multiplied into quantity a second time.

These are inspectable derived tables, not an independent database or a claim that normalized model spots are timestamped market quotes. The source manifest explicitly records `derived_views_only=True`.

## Cross-boundary regression evidence

The tests deliberately use nonuniform spots, strikes, notionals and distinct pricing/path volatilities, with the security order changed to GS/JPM/PNC. This avoids a false pass caused by every spot being 100 and every quantity being 1,000.

1. Reconstructing the numerical book and correlation matrix from the named views reproduces the direct canonical-loader stock paths exactly, then reproduces the same costly hedge P&Ls.
2. Shuffling the generated position, instrument, underlying and observation rows still permits valid one-to-one foreign-key joins. Signed quantities and multipliers reconstruct each name's intended notional by identifier rather than accidental row position.
3. Exported views and their source/file checksum manifest match exact persisted bytes.
4. Executing notebook 04's actual cached-artifact cell with a valid existing release never calls `run_release` and never replaces the locked policy with a rule that looks better in the evaluation table.
5. Changing either the current protocol file or current shared study file is rejected by the cached-artifact cell, while preserving the existing cached selection and avoiding an implicit rerun.

Run:

```sh
.venv/bin/python -m unittest discover -s tests -p test_integration.py -v
```

All five tests pass. The mismatch method separately tests both protocol and shared-study changes.

## Integration issue found and corrected

The initial notebook 04 artifact cell verified checksums inside the cached release but did not compare the cached commitment to the current protocol/source used in its introduction. A later edit to canonical inputs could therefore have shown current assumptions beside older cached results.

The notebook owner added guards comparing `protocol_commitment.json`'s `protocol_sha256` with the current `PROTOCOL` bytes and its `study_sha256` with the current shared `study_path` bytes. A mismatch raises an explicit error directing the user to a new separate run. The new regression test failed on the original cell and passed after that correction.

The current Research Release 1 protocol SHA256 is:

`6bf5148edb3f7b822bc59fc21b60e047205d6daa66fbc2a7676c350bec64b6cb`

The cached release currently matches that protocol and the canonical study hash above. Every artifact checksum in its manifest was independently verified. Notebook 04 defaults to reading that audited release; new selection/evaluation runs require the explicit new-run control or absence of existing artifacts. It does not reselect using held-out results.

## Scope and gate boundaries

The controlled release's status is complete for Research Gate 1, with human review separately pending. Its own gate marker explicitly leaves `market_or_stage7_gate_passed=False`. Completion of a controlled synthetic study does not establish empirical forecast improvement, listed-option execution, point-in-time membership, macro/funding interactions or stage-7 overlay generalization.

The replay and breadth components separately preserve these boundaries. The final conditional breadth artifact `results/breadth-20261106T020730752645Z` verifies its exact persisted protocol SHA256 as `8523480cb63fc4fcbee114d0aa69a8db751762c9f732282b9034371f7222efe6`, equal to the corresponding artifact checksum. Source/data/artifact hashes match current files, and its full stage-7 gate remains false. No heavy breadth rerun was performed for this integration review.
