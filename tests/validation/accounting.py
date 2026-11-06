"""Independently reconstruct a frozen Stage-6 base-case window study.

Run from the repository root:
    python tests/validation/accounting.py --output-dir NEW_DIRECTORY

No production valuation, risk, overlay or replay functions are imported. Recorded
legs/holdings are not used. The protocol and raw closes determine every position.
This verifies numerical implementation, not executable prices or economic claims.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import platform

import numpy as np
import pandas as pd
import scipy
from scipy.special import ndtr


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    parser.add_argument('--run', type=Path,
                        default=Path('results/equity-overlays-20261106T023430248130Z'))
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    root = args.repo.resolve()
    run = (root / args.run).resolve()
    destination = args.output_dir.resolve()
    require(not destination.exists(), 'Use a new output directory; existing evidence is never replaced.')
    protocol = json.loads((run / 'protocol.json').read_text())
    config = protocol['config']
    manifest = json.loads((run / 'manifest.json').read_text())

    def verify_frozen_inputs():
        source = {name: sha(root / name) == digest for name, digest in protocol['source_sha256'].items()}
        inputs = {name: sha(root / name) == digest for name, digest in protocol['input_sha256'].items()}
        artifacts = {name: sha(run / name) == digest for name, digest in manifest['artifacts_sha256'].items()}
        config_ok = sha(root / protocol['config_path']) == protocol['config_sha256']
        protocol_ok = sha(run / 'protocol.json') == (run / 'protocol.sha256').read_text().strip()
        require(all(source.values()) and all(inputs.values()) and all(artifacts.values())
                and config_ok and protocol_ok, 'Frozen source/input/config/artifact identity mismatch.')
        return source, inputs, artifacts, config_ok

    source_checks, input_checks, artifact_checks, config_matches = verify_frozen_inputs()
    require(config['schema_version'] == 1 and config['study'] == 'stage6_equity_overlays',
            'Only the frozen Stage-6 schema version 1 is supported.')
    require(config['execution']['liquidate_at_window_end'] is True,
            'This closed-form audit requires liquidation at each window end.')
    require(config['execution']['option_execution'] ==
            'model value, no option bid/ask charge (replay limitation)',
            'This audit assumes zero option execution charge.')
    require(config['estimation']['pricing_volatility'].startswith('Sample standard deviation'),
            'This audit is the base-case trailing-sample-volatility reconstruction only.')
    require(config['book']['rebalance_rule'].endswith('No trading inside a window.'),
            'This audit requires fixed shares inside separate-capital windows.')
    require(config['windows']['decision_lag_sessions'] >= 1, 'Decision must precede execution.')

    core = pd.read_csv(root / config['data']['core_prices'], index_col=0, parse_dates=True)
    benchmark = pd.read_csv(root / config['data']['benchmark_prices'], index_col=0, parse_dates=True)
    etf = config['data']['sector_etf']
    require(core.index.equals(benchmark.index), 'Core and benchmark sessions must align exactly.')
    require(core.index.is_unique and core.index.is_monotonic_increasing, 'Invalid price calendar.')
    require(etf not in core.columns, 'ETF must be separate from the core equity names.')
    price = core.join(benchmark[[etf]])
    require(np.isfinite(price.to_numpy()).all() and (price.to_numpy() > 0).all(), 'Invalid raw prices.')
    windows = pd.read_csv(run / 'windows.csv')
    candidates = {item['label']: item for item in protocol['candidates']}
    require(len(candidates) == len(protocol['candidates']), 'Duplicate candidate labels.')
    weights = {**config['book']['longs'], **{key: -value for key, value in config['book']['shorts'].items()}}
    require(not set(config['book']['longs']) & set(config['book']['shorts']), 'Overlapping long/short names.')
    execution, estimation = config['execution'], config['estimation']
    capital, rate = float(config['capital']), float(execution['rate'])
    bps, multiplier = execution['stock_cost_bps'] / 10000, float(execution['contract_multiplier'])
    year, lookback = int(execution['sessions_per_year']), int(estimation['lookback'])
    sessions, lag = int(config['windows']['sessions']), int(config['windows']['decision_lag_sessions'])
    require(capital > 0 and multiplier > 0 and year > 0 and lookback >= 2 and sessions > 0, 'Invalid units.')
    names = list(weights) + [etf]
    returns = np.log(price[names] / price[names].shift()).dropna()

    # Reconstruct eligible windows from dates/rules, rather than trusting saved row dates.
    expected_windows = {}
    calendar = price.index
    for split, (first_date, last_date) in config['splits'].items():
        eligible = np.flatnonzero((calendar >= first_date) & (calendar <= last_date))
        if not len(eligible):
            continue
        start_index, number = max(int(eligible[0]), lookback + lag), 0
        while start_index + sessions <= int(eligible[-1]):
            expected_windows[f'{split}-{number:03d}'] = (
                split, calendar[start_index - lag], calendar[start_index], calendar[start_index + sessions])
            start_index += sessions
            number += 1
    require(set(windows.key) == set(expected_windows), 'Missing or extra saved windows.')
    require(not windows.duplicated(['key', 'label']).any(), 'Duplicate saved window/candidate observations.')

    def option_price(spot, strike, maturity, sigma, kind):
        d1 = (math.log(spot / strike) + (rate + sigma * sigma / 2) * maturity) / (sigma * math.sqrt(maturity))
        d2 = d1 - sigma * math.sqrt(maturity)
        if kind == 'call':
            return spot * ndtr(d1) - strike * math.exp(-rate * maturity) * ndtr(d2)
        require(kind == 'put', 'Unknown option type.')
        return strike * math.exp(-rate * maturity) * ndtr(-d2) - spot * ndtr(-d1)

    errors, components = [], []
    for key, group in windows.groupby('key'):
        split, decision, start, end = expected_windows[key]
        require(set(group.label) == set(candidates), f'Incomplete candidate grid for {key}.')
        require((group.split == split).all() and (group.sessions == sessions).all(), 'Window schema mismatch.')
        require((group.initial_capital == capital).all(), 'Initial capital differs between policies.')
        for field, value in [('decision_date', decision), ('start', start), ('end', end)]:
            require((pd.to_datetime(group[field]) == value).all(), f'{key}: unexpected {field}.')
        maturity = sessions / year
        history = returns.loc[:decision]
        past = history.iloc[-lookback:]
        require(len(past) == lookback, 'Insufficient past return observations.')
        prior, opening, closing = price.loc[decision], price.loc[start], price.loc[end]
        sigma = past.std(ddof=1) * math.sqrt(year)
        covariance = np.cov(past.to_numpy(), rowvar=False)
        require(covariance[-1, -1] > 0, 'ETF variance must be positive.')
        betas = dict(zip(names[:-1], covariance[:-1, -1] / covariance[-1, -1]))
        book_return = history[list(weights)].to_numpy() @ np.array(list(weights.values()))
        ratio = math.sqrt(pd.Series(book_return ** 2).ewm(alpha=1 - estimation['ewma_lambda'], adjust=False)
                          .mean().iloc[-1] / np.mean(book_return[-lookback:] ** 2))
        for row in group.itertuples(index=False):
            candidate = candidates[row.label]
            family = candidate['family']
            scale = candidate['scale'] if family == 'reduced_equity' else 1
            shares = {name: math.trunc(scale * weight * capital / prior[name]) for name, weight in weights.items()}
            beta_dollars = sum(shares[name] * prior[name] * betas[name] for name in shares)
            if family == 'etf_hedge':
                shares[etf] = -math.trunc(candidate['hedge_ratio'] * beta_dollars / prior[etf])
            budget = candidate.get('annual_budget', 0) * capital * maturity
            legs, exposures = [], {}
            if family in ('long_puts', 'risk_informed'):
                exposures = {name: units for name, units in shares.items() if units > 0}
                legs = [('put', candidate['moneyness'], 1)]
                if family == 'risk_informed' and ratio < candidate['threshold']:
                    budget *= candidate['low_state_budget_fraction']
            elif family == 'short_calls':
                exposures = {name: -units for name, units in shares.items() if units < 0}
                legs = [('call', candidate['moneyness'], 1)]
            elif family == 'sector_puts':
                exposures = {etf: max(beta_dollars, 0) / prior[etf]}
                legs = [('put', candidate['moneyness'], 1)]
            elif family == 'structures':
                exposures = {name: units for name, units in shares.items() if units > 0}
                legs = [('put', candidate['long_put'], 1)]
                if candidate['structure'] == 'put_spread':
                    legs.append(('put', candidate['short_put'], -1))
                else:
                    require(candidate['structure'] == 'collar', 'Unsupported option structure.')
                    legs.append(('call', candidate['short_call'], -1))
            else:
                require(family in ('unhedged', 'reduced_equity', 'etf_hedge'), 'Unsupported policy family.')
            full_premium = sum(sign * units * option_price(prior[name], m * prior[name], maturity, sigma[name], kind)
                               for name, units in exposures.items() for kind, m, sign in legs)
            coverage = 1 if full_premium <= budget else budget / full_premium
            premium, settlement = 0.0, 0.0
            for name, units in exposures.items():
                # Same declared whole-lot convention; tiny tolerance only avoids floating-point integer drift.
                contracts = math.floor(coverage * units / multiplier + 1e-9)
                for kind, moneyness, sign in legs:
                    strike, signed_units = moneyness * prior[name], sign * contracts * multiplier
                    premium += signed_units * option_price(opening[name], strike, maturity, sigma[name], kind)
                    settlement += signed_units * max((closing[name] - strike) * (1 if kind == 'call' else -1), 0)
            stock_in = sum(units * opening[name] for name, units in shares.items())
            stock_out = sum(units * closing[name] for name, units in shares.items())
            entry_cost = bps * sum(abs(units) * opening[name] for name, units in shares.items())
            exit_cost = bps * sum(abs(units) * closing[name] for name, units in shares.items())
            opening_cash = capital - stock_in - premium - entry_cost
            pnl = opening_cash * math.exp(rate * maturity) + stock_out + settlement - exit_cost - capital
            errors.append(dict(key=key, label=row.label, pnl=pnl, saved=row.pnl, residual=pnl - row.pnl))
            components.append(dict(key=key, label=row.label, net_premium=premium, option_payoff=settlement,
                                   capital=capital, interest=opening_cash * math.expm1(rate * maturity),
                                   stock_cost=entry_cost + exit_cost))

    rebuilt = pd.DataFrame(errors)
    maximum = float(rebuilt.residual.abs().max())
    require(maximum < 1e-6, f'Terminal-PnL reconstruction mismatch: {maximum} dollars.')
    require(len(rebuilt) == len(expected_windows) * len(candidates), 'Incomplete reconstruction.')
    verify_frozen_inputs()  # Detect concurrent mutations during this read-only audit.
    destination.mkdir(parents=True, exist_ok=False)
    rebuilt.to_csv(destination / 'terminal_pnl_reconstruction.csv', index=False)
    pd.DataFrame(components).to_csv(destination / 'terminal_cash_components.csv', index=False)
    summary = dict(
        reviewed_utc=datetime.now(timezone.utc).isoformat(), frozen_run=str(args.run),
        protocol_sha256=sha(run / 'protocol.json'), status='passed', rows=len(rebuilt),
        windows_by_split=windows.groupby('split').key.nunique().to_dict(),
        scope='All frozen base-case grid terminal P&Ls independently reconstructed from raw prices and protocol; no production functions or saved legs used; no reselection or new research scenarios.',
        max_absolute_pnl_residual_dollars=maximum,
        mean_absolute_pnl_residual_dollars=float(rebuilt.residual.abs().mean()),
        max_attribution_residual_dollars=float(abs(windows.pnl - (windows.long_equity_pnl + windows.short_equity_pnl
            + windows.etf_pnl + windows.option_pnl + windows.interest - windows.stock_cost)).max()),
        source_checks=source_checks, input_checks=input_checks, config_matches=config_matches,
        artifact_count=len(artifact_checks), artifact_hash_mismatches=[name for name, ok in artifact_checks.items() if not ok],
        environment=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__, scipy=scipy.__version__),
        script=dict(name=Path(__file__).name, sha256=sha(__file__)),
        artifacts_sha256={name: sha(destination / name) for name in ['terminal_pnl_reconstruction.csv', 'terminal_cash_components.csv']},
        not_validated=['All intrawindow option marks/drawdowns', 'All predeclared sensitivity runs',
                       'Underlying data vendor accuracy/corporate actions', 'Observed option market costs or availability',
                       'Economic generalization or independent crisis counts'])
    (destination / 'audit_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(dict(status='passed', rows=len(rebuilt), max_absolute_pnl_residual_dollars=maximum,
                          summary=str(destination / 'audit_summary.json'))))


if __name__ == '__main__':
    main()
