# Tests and numerical validation

Run `make test` from the repository root. The suite covers pricing identities, hedge and cash accounting, input validation, chronology, feature availability, portfolio breadth and policy selection. A three-experiment regression compares current outputs with saved full-precision results.

`validation/` contains independent terminal accounting, statistical reconstruction and window-placement checks. `make reproduce` runs these against an extracted, identity-verified historical input workspace. The window diagnostic uses the current overlay engine; independent accounting and statistics use their own formulas.

`artifacts/independent_validation/` contains reference CSVs for those checks. The historical XML files are saved test reports, not test implementations or claims about the current checkout. `make verify` checks the retained artifacts against `artifacts/manifest.json`.

New temporary test outputs and reproduction directories are not committed. Passing arithmetic checks does not establish executable prices or economic hedge value.
