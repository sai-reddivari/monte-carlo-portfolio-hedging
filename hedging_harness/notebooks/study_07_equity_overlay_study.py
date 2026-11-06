"""07_equity_overlay_study: original study operations moved from notebook cells."""
from IPython.display import display
from hedging_harness.configuration import defaults, notebook_controls
from hedging_harness.notebook_views import verify_frozen_overlay, historical_root, historical_path


def run():
    _controls = notebook_controls('07_equity_overlay_study')
    from pathlib import Path
    import json, sys
    import pandas as pd
    from IPython.display import Image, Markdown, display

    ROOT = Path.cwd()
    if not (ROOT / "hedging_harness").is_dir():
        ROOT = ROOT.parent
    assert (ROOT / "hedging_harness").is_dir(), f"Wrong project root: {ROOT}"
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from hedging_harness import overlays as ov
    from scripts import run_overlay_research as runner

    RUN = ROOT / "results/equity-overlays-20261106T023430248130Z"
    protocol, digest, changed = verify_frozen_overlay(RUN)
    log = json.loads((RUN / "test_evaluation_log.json").read_text())
    pd.set_option("display.width", 200, "display.max_columns", 40, "display.max_rows", 80)
    print("Label:", protocol["label"])
    print("Protocol SHA-256:", digest)
    print("Selection saw prices through:", protocol["last_price_visible_to_selection"])
    print("Test evaluation attempts:", len(log), "| test-informed:", [row["test_informed"] for row in log])
    print("changed_since_freeze:", changed)
    assert len(log) == 1 and not log[0]["test_informed"]

    config = protocol["config"]
    book = pd.Series(ov.signed_weights(config), name="weight").rename_axis("issuer").reset_index()
    display(book.assign(side=book["weight"].map(lambda w: "long" if w > 0 else "short")))
    print(f"Capital ${config['capital']:,.0f} | gross {config['book']['gross_exposure']:.0%} | net {config['book']['net_exposure']:.0%}")
    display(pd.read_csv(RUN / "window_counts.csv"))

    selection = pd.DataFrame([dict(family=family, selected=item["label"], validation_es_loss_pct=item["validation_es_loss_pct"],
                                   candidates=len(item["candidates_considered"])) for family, item in protocol["selection"].items()])
    display(selection.round(3))
    labels = [row["label"] for row in runner.selected_candidates(protocol)]
    summary = pd.read_csv(RUN / "summary.csv")
    pick = lambda split, columns: summary.loc[summary["split"].eq(split)].set_index("label").reindex(labels)[columns].round(3)
    risk = ["n_windows", "mean_pnl_pct", "worst_pnl_pct", "es_loss_pct", "worst_max_drawdown_pct", "downside_capture", "upside_retained"]
    display(Markdown("**Validation, % of capital per window**"))
    display(pick("validation", risk))

    display(Markdown("**Test, % of capital per window**"))
    display(pick("test", risk))
    display(Markdown("**Test costs and financing, % of capital per year (spending rates, not compounded returns)**"))
    display(pick("test", ["annual_premium_paid_pct", "annual_premium_received_pct", "annual_settlement_net_pct", "annual_stock_cost_pct",
                          "annual_interest_pct", "peak_borrowing_pct", "peak_funding_ex_short_proceeds_pct"]))
    display(Markdown("**Test exposure at inception, % of capital**"))
    display(pick("test", ["mean_gross_exposure_pct", "mean_net_exposure_pct", "mean_etf_exposure_pct", "mean_delta_adjusted_net_pct", "mean_beta_net_pct", "mean_target_coverage"]))

    display(Image(RUN / "frontier_validation.png"))
    display(Image(RUN / "frontier_test.png"))
    display(Image(RUN / "window_scatter_test.png"))
    display(pd.read_csv(RUN / "attribution_test.csv").round(3))
    display(Image(RUN / "attribution_test.png"))

    uncertainty = pd.read_csv(RUN / "uncertainty.csv")
    display(uncertainty.drop(columns=["block_windows"]).round(3))
    display(pd.read_csv(RUN / "tail_episodes.csv").query("split == 'test'").round(2))
    display(Markdown("**Protection on the protected side, in windows where that side lost money**"))
    display(pd.read_csv(RUN / "side_protection.csv").round(3))

    sensitivity = pd.read_csv(RUN / "sensitivity.csv")
    display(Markdown("**ES loss reduction against unhedged, points. Budgets stay fixed, so dearer options buy less coverage.**"))
    display(sensitivity.loc[sensitivity["label"].isin(labels) & sensitivity["label"].ne("unhedged")]
            .pivot_table(index=["split", "label"], columns="scenario", values="es_reduction_pct").round(3))
    display(Image(RUN / "pricing_sensitivity.png"))
    basis = pd.read_csv(RUN / "sector_basis.csv")
    display(Markdown("**Sector basis: the six worst test windows, % of capital**"))
    display(basis.loc[basis["split"].eq("test")].nsmallest(6, "book_pnl_pct").round(2))

    prices = ov.load_panel(config, ROOT)
    weights, settings = ov.signed_weights(config), ov.Settings.from_config(config)
    windows = {item.key: item for item in runner._windows_for(config, prices.index)["test"]}
    by_label = {row["label"]: row for row in protocol["candidates"]}
    stored = pd.read_csv(RUN / "windows.csv").set_index(["key", "label"])
    rows, hand = [], []
    for case, key, family in (("long downside", "test-005", "long_puts"), ("short upside", "test-017", "short_calls")):
        candidate = by_label[protocol["selection"][family]["label"]]
        table, legs = runner.hand_reconciliation(prices, windows[key], candidate, weights, settings, case, list(windows.values()))
        hand.append(table)
        state = ov.estimate_state(prices, windows[key].decision_date, weights, settings)
        instruction = ov.build_instruction(candidate, state, windows[key], weights, settings)
        live = ov.run_window(prices, windows[key], instruction, settings)
        rows.append(dict(case=case, window=key, policy=candidate["label"], live_terminal_nav=live.terminal_nav,
                         stored_terminal_nav=stored.loc[(key, candidate["label"]), "terminal_nav"]))
    reproduced = pd.DataFrame(rows).assign(difference=lambda frame: frame.live_terminal_nav - frame.stored_terminal_nav)
    display(reproduced.round(2))
    hand = pd.concat(hand, ignore_index=True)
    display(hand[["case", "stage", "item", "hand", "ledger", "residual"]].round(2))
    assert reproduced["difference"].abs().max() < 1e-6
    assert hand["residual"].abs().max() < 1e-5
    print("Largest hand residual: $", f"{hand['residual'].abs().max():.2e}")
    legs = pd.read_csv(RUN / "hand_legs.csv")
    display(legs.loc[legs["case"].str.startswith("test")].sort_values("settlement", ascending=False).groupby("case").head(1)
            [["case", "window", "underlying", "kind", "book_shares", "contracts", "covered_fraction", "strike", "decision_close",
              "execution_close", "expiry_close", "premium", "settlement", "stock_pnl_on_book_shares"]].round(3).T)

    display(pd.DataFrame(json.loads((RUN / "gate_status.json").read_text())["gates"]))
    for item in runner.LIMITATIONS:
        print("-", item)
    print()
    for item in protocol["pre_freeze_disclosures"]:
        print("Disclosure:", item)
    return locals()
