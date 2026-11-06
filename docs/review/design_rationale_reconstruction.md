This is a reconstruction of the original design rationale, rather than a verbatim quotation. It uses the planning brief and frozen specifications, without incorporating subsequent findings.
Motivation and central hypothesis
The project will extend the existing Monte Carlo and option-valuation work into a portfolio-risk decision problem: given an equity long/short mandate, can we identify changing risk and choose derivative protection that improves the portfolio’s downside outcome at an acceptable cost?
The central question is:
Do macro conditions and company funding characteristics improve five- and twenty-session risk forecasts—and do those improvements produce better hedging decisions after costs?
There are two separate hypotheses. First, information beyond a company’s recent returns may improve forecasts of its future variance and the portfolio’s covariance. Second, better risk information may help allocate a limited protection budget. Forecast accuracy alone will not establish economic hedge value.
The aim is to demonstrate the complete research and accounting process: estimate risk, specify protection, book the instruments, reconcile cash and NAV, and evaluate the trade-off between downside protection, cost and retained upside. Stock-selection alpha is outside the initial study.
Why financials and funding signals
Financial companies provide an economically connected universe with different business models, balance-sheet structures and funding exposures. Rates and financial conditions can affect their asset values, funding costs and earnings; leverage and funding composition may influence how strongly those shocks reach equity holders.
The motivation for adding company information is that trailing equity volatility describes recent market behaviour but may not fully capture differences in underlying vulnerability. Two companies experiencing the same sector move could face different subsequent risks because their liabilities, deposit funding or liquidity positions differ.
The initial empirical approach will therefore build information in layers:
Own-price volatility and return features.
Broad-market and financial-sector information.
Comparable, historically available balance-sheet ratios.
Interactions between company characteristics and recent sector conditions.
Candidate proxies include liabilities/assets, deposits/liabilities and available bank-liquidity measures. Deposit-based comparisons will be restricted to economically comparable banks. These are hypotheses about incremental predictive information; the design does not assume that a higher deposit share has a universally positive or negative effect on risk.
The broader macro ambition depends on obtaining historically available observations. Features must enter according to when they became available, rather than their financial reporting period alone.
The portfolio and eight comparison arms
The overlay experiment will use a predetermined financial-sector long/short book. Issuer selection, sides and weights will be fixed before evaluating outcomes, so changing stock selection cannot explain differences between protection policies.
The eight arms include two benchmarks and six hedge families, rather than eight derivative strategies:
Arm
Original purpose
Unhedged equity
Establish the mandate’s risk and return without protection.
Reduced equity exposure
Test whether simply holding less risk provides a better trade-off than buying insurance.
Sector ETF stock hedge
Provide a straightforward linear hedge against estimated financial-sector exposure.
Purchased puts on long positions
Protect individual long holdings against substantial declines while preserving upside beyond the premium cost.
Purchased calls on short positions
Limit losses from substantial rises in the shares sold short.
Sector puts
Test portfolio-level downside protection through a common sector instrument, allowing for imperfect correspondence with the book.
Put spread or collar
Examine whether accepting limited protection or surrendering upside can reduce the cost of insurance.
Modest risk-informed protection
Test whether changing coverage using past-only risk estimates improves on static protection.
The reduced-exposure benchmark is essential: lower losses alone do not demonstrate that derivatives add value, because reducing the equity position can also lower losses. The comparison must consider protection alongside cost and participation in favourable outcomes.
All arms will use the same initial capital, dates and underlying paths. Protective overlays will retain the same core equity holdings; the reduced-exposure arm will explicitly change those holdings and retain the remaining cash. Protective options will not automatically be delta-neutralized.
The first adaptive overlay will use price-history risk estimates. Connecting a validated funding or macro forecast to hedge decisions is a separate step. [Original Stage 6 handoff](/Users/saireddivari/MonteCarloEvaluations/docs/opus_stage6_handoff.md)
Chronological design
The agreed split is:
Period
Role
2010–2017
Training and estimation of forecasting relationships.
2018–2020
Validation and selection from predefined model or policy candidates.
2021–November 4, 2026
Held-out evaluation after selection is locked.
Chronological separation is intended to reproduce the information constraint faced by a decision-maker: future observations cannot influence earlier forecasts or policy choices.
Forecast targets will cover the next five and twenty trading sessions. Protection budgets, candidate strikes, maturities, execution assumptions and selection rules will be specified before test evaluation. Overlapping outcomes and companies exposed to the same episode will not be treated as independent observations.
For the overlay study, the frozen selection objective is validation expected shortfall over the worst quarter of window outcomes, subject to the prescribed budget eligibility rules. Cost, drawdown, upside retained and financing requirements will accompany that objective. [Overlay specification](/Users/saireddivari/MonteCarloEvaluations/config/equity_overlay_study.json)
What would count as success
There are three distinct standards:
Forecasting success: additional market or funding information improves held-out variance or portfolio-risk forecasts relative to simple price-history baselines, with uncertainty evaluated on matched observations.
Economic success: a locked protection policy offers a defensible improvement in the downside–cost–upside trade-off relative to unhedged equity, static protection and predetermined equity reduction.
Research success: the study produces a reproducible, reconciled and honestly bounded answer, whether or not either economic hypothesis is supported.
The original design does not specify a universal minimum percentage improvement or require every hedge to win. The ambition is evidence of useful incremental protection under stated constraints—not merely a favourable backtest, a more complicated forecast, or lower risk obtained by silently changing the portfolio.
