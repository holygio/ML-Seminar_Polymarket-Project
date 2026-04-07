# Polymarket Signal Dashboard

## 1. What This Project Is

Polymarket is a prediction market. Instead of buying a stock or an option directly, traders buy and sell contracts that pay out based on whether an event happens. In this project, the event is a binary question such as "Will AAPL close up today?" Polymarket represents that question with a YES token and a NO token. If the event resolves true, the YES token pays out; if it resolves false, the NO token pays out. Because the two sides trade in a market, the price of the YES token can be read as the market's implied probability. A YES price of `0.62` means the market is roughly pricing a 62% chance that the stock closes up on the day.

This project monitors those Polymarket-implied probabilities overnight and asks a very specific research question: do changes in Polymarket's overnight probabilities contain information about next-day stock direction before the traditional equity market fully reacts? The system watches Polymarket's up/down contracts before the New York market opens, records how the probability moves between midnight and the cash equity open, and compares that signal with what the stock does after the opening bell.

The intended users are portfolio managers, discretionary macro or equity traders, and researchers who care about information flow. A practitioner might use the dashboard as a morning signal board: which names saw unusually bullish or bearish overnight prediction-market activity, and did those signals historically align with same-day stock direction? A researcher might use the same system as a structured data collection and visualization environment for testing lead-lag relationships, calibrating signal quality thresholds, or expanding the sample.

The dashboard currently focuses on two working pages. Page 2 is the asset detail view. It shows one stock at a time with a probability chart, a stock chart, a true-sentiment chart, and a metrics block summarizing the pre-open signal. Page 3 is the signal alignment heatmap. It summarizes day-level agreement or disagreement between Polymarket direction and realized stock direction across the tracked universe. Page 1, a broader market-context page, is intentionally deferred and not yet implemented.

This is interesting because Polymarket runs continuously while traditional equities do not. The platform can absorb overnight earnings commentary, macro headlines, geopolitics, and sentiment shifts when the cash equity market is closed or thin. If that overnight information shows up first in Polymarket prices, then the probability path before 9:30 AM New York time may contain a genuine information advantage rather than just noise.

## 2. The Research Question

The core hypothesis is simple: Polymarket-implied probabilities may contain information that has not yet been fully reflected in traditional asset prices. Put differently, if Polymarket traders move the implied probability that a stock will finish up before the stock market opens, that movement may help predict the stock's next move after the open.

Why might that be true? Polymarket is open around the clock and updates continuously when new information arrives. Traditional stocks, by contrast, have deep liquidity only during regular market hours, and even pre-market trading is much thinner than the main session. That mismatch creates a window in which news can be discussed, interpreted, and priced in a prediction market before it is fully expressed in the underlying stock.

In this project, "information advantage" does not mean certainty and it does not mean guaranteed profit. It means that the probability series on Polymarket may carry incremental predictive content beyond what is already visible in standard pre-open stock controls such as gap returns or prior-day momentum. If that content exists, then Polymarket is not merely mirroring the stock market; it is contributing an additional pricing signal.

The 9:30 AM firewall is the key discipline that makes the analysis credible. The project deliberately stops using signal information at the New York Stock Exchange cash open. That prevents look-ahead bias. If the model were allowed to use data from after the stock market had already reacted, then the apparent predictive power would be contaminated by future information leaking into the feature set. The firewall therefore acts as a hard boundary between "signal formation" and "outcome realization."

The primary daily signal is the overnight probability change: the change in Polymarket-implied probability from New York midnight to the pre-open firewall. In the current production code the firewall is `09:30 AM` New York time, so the operational signal is the move from `00:00` to `09:30` New York time. Historical research notes in the archive sometimes refer to `09:00`; those notes reflect an earlier experimental snapshot, but the live dashboard and pipeline use the stricter `09:30` boundary.

## 3. Academic Grounding

**Efficient Market Hypothesis (Fama 1970).** EMH says that asset prices should reflect all available information. This project is a direct practical test of that idea. If Polymarket can move first and those moves help forecast the next stock move, then either information is not being incorporated into the stock instantly or the stock cannot fully express that information because of timing, liquidity, or market-structure frictions. The project therefore does not reject EMH in a broad philosophical sense, but it does examine whether a specific 24/7 market can temporarily lead a more constrained one.

**Asset Pricing Theory.** Classical asset-pricing frameworks such as CAPM and later Fama-French models treat expected returns as functions of systematic risk exposures or observable state variables. This project treats Polymarket prices as an alternative state variable: a market-generated expectation about next-day direction. In that sense, the project extends the spirit of asset-pricing theory by asking whether a prediction-market probability can serve as an additional explanatory input alongside traditional price- and volatility-based variables.

**Alternative Data Literature.** A large literature studies whether unconventional data sources help explain or forecast asset moves. Tetlock (2007) connects media tone to returns. Da, Engelberg, and Gao (2011) use Google search volume as an attention measure. Loughran and McDonald (2011) show that domain-specific language matters for interpreting financial text. Polymarket fits naturally into this tradition, but with an important twist: it is not only a text or attention proxy. It is a live market price formed by traders taking positions and committing capital, which makes it a particularly compact summary of dispersed beliefs.

**Prediction Markets Literature.** Wolfers and Zitzewitz (2004) show why prediction-market prices are useful aggregators of distributed expectations. Manski (2006) reminds us that market prices are not identical to true probabilities because budget constraints, risk aversion, and market conditions distort them. Berg, Nelson, and Rietz (2008) document that prediction markets can be remarkably accurate in practice. This project borrows from that literature by treating Polymarket prices as informative but imperfect belief aggregates: valuable because they synthesize expectations, but not sacred or assumption-free.

**Why Polymarket May Lead TradFi.** Miller (1977) emphasizes disagreement and short-sale constraints, Shleifer and Vishny (1997) emphasize limits to arbitrage, and Black (1986) distinguishes information from noise in prices. Together those ideas make Polymarket's potential edge plausible. If some beliefs are hard to express quickly or cheaply in stocks, and if arbitrage capital is limited or slow, then a separate market that allows fast directional expression can incorporate overnight information before the stock fully catches up.

## 4. The Signal: True Sentiment

The raw Polymarket probability is the market-implied chance that the stock closes up on the day. If a YES token for "AAPL up today" trades at `0.58`, then the market is effectively saying there is about a 58% chance that AAPL closes above its open.

That raw probability is not enough by itself. A probability of 60% is not necessarily bullish in an economically meaningful way. It might simply be fair value given where the stock already is, how volatile it has been, how much time remains until expiry, and the risk-neutral distribution implied by standard finance assumptions. The project therefore does not treat every high Polymarket probability as a directional edge. It treats the probability as a signal only when it departs from a model-based benchmark.

That benchmark is the Black-Scholes `N(d2)` term. In option pricing, `N(d2)` can be interpreted as the risk-neutral probability that a European call option expires in the money. The project uses that quantity as a model-based "fair" probability for the same economic question the Polymarket contract is asking: will the stock finish the day above its opening level?

The core formula is:

```text
true_sentiment = avg_price_up - bs_neutral_prob
```

Here, `avg_price_up` is the average Polymarket up probability during a window, and `bs_neutral_prob` is the Black-Scholes risk-neutral probability of finishing above the strike. The result is the amount by which Polymarket is more bullish or more bearish than the model benchmark.

Positive true sentiment means Polymarket is more bullish than Black-Scholes would suggest after accounting for the stock's current price, the day's opening level, estimated volatility, and remaining time to expiry. Negative true sentiment means Polymarket is more bearish than the benchmark. A value near zero means Polymarket is close to model fair value and therefore not obviously offering a strong directional opinion.

This is a better signal than raw probability because it controls for information that is already embedded in the stock and its volatility. Without that adjustment, a high raw probability can simply be the natural mechanical consequence of the stock already trading above the day's open with little time remaining. True sentiment attempts to isolate the portion of Polymarket pricing that looks like extra belief or conviction rather than a straightforward option-like fair value.

The Black-Scholes inputs used in this project are intentionally simple and explicit:

- `S` = current stock close from the matched 5-minute Yahoo Finance bar
- `K` = the day's stock open, treated as the strike because the binary contract resolves YES if the close is above the open
- `sigma` = rolling annualized volatility estimated from 5-minute log returns
- `T` = time to expiry in years, implemented as remaining hours until the `4:00 PM` cash close converted into a trading-year fraction
- `r` = annual risk-free rate from configuration, currently `0.04`

Operationally, the implementation treats the binary up/down contract as a cash-or-nothing call option on the daily close relative to the day's open. That is not a perfect structural identity, but it is a useful and transparent approximation. It creates a principled benchmark against which to measure whether Polymarket is pricing extra bullishness or bearishness.

## 5. The Pipeline Architecture

The project is built as a staged pipeline that starts with external market data and ends with a dashboard:

```text
Polymarket Gamma API        -> market metadata, condition IDs, token IDs
Polymarket Goldsky GraphQL  -> raw orderbook fills for YES/NO tokens
Yahoo Finance               -> stock daily and 5-minute OHLCV data

        v

Orderbook class             -> fetches and assembles raw Polymarket trade history
fetch_raw_orderbook()       -> PM-only data, no stock dependency
attach_stock_data()         -> merges Yahoo Finance daily and 5-minute bars

        v

build_preopen_panel()       -> signals_today.csv (pre-open snapshot, PM data only)
collapse_to_windows()       -> panel_15m.csv feature panel with Black-Scholes benchmark
check_lead_lag()            -> next_stock_move, abs_sentiment, diagnostics

        v

signals_today.csv           -> one row per asset with pre-open metrics
panel_15m.csv               -> full intraday feature panel
last_run.json               -> pipeline health and run metadata
orderbook_latest.csv        -> latest raw orderbook export for pre-open chart reconstruction

        v

FastAPI server              -> JSON endpoints for health, signals, asset detail, pre-open chart, and heatmap
Next.js frontend            -> Page 2 asset detail and Page 3 heatmap
```

The important architectural decision is that pre-open metrics and intraday analytics are deliberately separated. The pre-open signal file is built directly from raw Polymarket data and does not depend on any stock merge. The intraday panel is built only after stock bars have been attached. That split prevents pre-open rows from being discarded just because no cash-equity close exists before 9:30 AM.

## 6. Design Decisions And Assumptions

**1. Pre-open vs intraday split.** The project writes `signals_today.csv` before it fetches or merges stock data because the overnight signal should survive even if the stock-data step fails. The alternative would have been to derive the signal from the intraday feature panel. That approach turned out to be fragile because pre-open rows are naturally missing stock fields, which caused the panel-building step to drop them. Building the pre-open snapshot from raw Polymarket trades preserves data integrity and keeps the pipeline useful even when later stages fail.

**2. Five-minute window size.** The production configuration uses 5-minute windows. A 1-minute window would provide more granularity but would be noisier, sparser, and more sensitive to mismatched timestamps and illiquid bursts. A 15-minute window would be smoother but would blur timing and reduce the usefulness of the lead-lag analysis. Five minutes is the compromise: fine enough to show intraday progression and estimate rolling volatility, but coarse enough to avoid turning the entire panel into microstructure noise. The filename `panel_15m.csv` is a historical naming leftover; the current contents are generated at 5-minute resolution.

**3. The 9:30 AM firewall.** The firewall is non-negotiable because without it the analysis risks using information from after the cash market already opened. The production code enforces this in `build_preopen_panel()` by filtering raw orderbook timestamps from New York midnight up to, but not including, `09:30 AM` New York time. Earlier archived notes mention `09:00`, but the live implementation intentionally uses the more conservative boundary.

**4. Liquidity threshold of $500.** The project marks signals as high-liquidity when pre-open Polymarket volume exceeds `$500`. That threshold is not a universal law; it is an empirical rule of thumb chosen because low-volume contracts behaved too erratically to trust. In the archived research sample, applying the high-liquidity filter dropped roughly `78%` of observations but raised accuracy materially, from `67.0%` in the unrestricted boosting model to `75.7%` when focusing on higher-quality observations. Low-liquidity signals are not thrown away operationally, but they are labeled as weaker and shown with lower quality.

**5. True Sentiment vs raw probability.** Raw Polymarket probabilities are easy to read but can be misleading as signals because they mix fair-value mechanics with directional opinion. The Black-Scholes adjustment is the attempt to separate those two effects. The risk of using raw probability alone is that the dashboard would confuse "already implied by the stock and volatility" with "new information." True sentiment is not perfect, but it is a better attempt at isolating incremental belief.

**6. Daily pipeline rather than real-time infrastructure.** The system runs once per day because the goal is a reliable morning research and presentation pipeline, not a full streaming production stack. A real-time architecture would require persistent ingestion, storage, incremental recomputation, and more operational complexity. The daily run sacrifices freshness in exchange for transparency, reproducibility, and low maintenance, which is appropriate for a seminar project and an early-stage research prototype.

**7. A narrow asset universe.** The current production configuration tracks eight major U.S. stocks: `AAPL`, `MSFT`, `NVDA`, `GOOGL`, `META`, `AMZN`, `NFLX`, and `TSLA`. Earlier research notes mention ten markets and include broad indices such as `SPX`, `NDX`, and `DJIA`. The current dashboard narrowed the universe to major single-name equities because they are easier to explain, map cleanly to Yahoo Finance tickers, and are more practical for a demo. That also means the results should not be generalized to all assets or to non-equity Polymarket markets.

**8. Binary market structure as an option analogue.** The project assumes that an up/down contract can be treated approximately like a European cash-or-nothing option on whether the stock closes above the open. That approximation is strongest when the market is liquid enough that the contract price behaves like a smooth probability and when the stock itself is not undergoing discontinuous jumps that break the diffusion assumption. It breaks down when liquidity is thin, when traders are constrained in non-standard ways, or when the binary contract embeds frictions not represented in Black-Scholes.

**9. Goldsky as the trade-data source.** Goldsky's GraphQL endpoint is used because it exposes order-filled events in a structured way that is much better suited to historical fill reconstruction than the simpler market-metadata interfaces. The tradeoff is that it requires chunked querying, careful rate management, and stitching results together, which makes the pipeline slower. The alternative would have been to rely only on Polymarket's native metadata APIs, but those are not sufficient for reconstructing a robust raw order-flow panel.

**10. Mock data for development.** Frontend development used synthetic CSV fixtures so the API and UI could be built before the live pipeline was ready and without waiting 20 to 40 minutes for a full historical fetch on each iteration. That made development much faster and safer. The downside is that the mock files simplify reality. For example, the mock `orderbook_latest.csv` only contains the columns required by the pre-open endpoint, whereas the real pipeline writes the full raw orderbook export.

## 7. Key Findings From The Research

The headline empirical result from the intraday experiment is that Polymarket appears to lead the stock rather than simply react to it. In the archived notebook output, the overall correlation between `true_sentiment` at time `t` and `next_stock_move` at time `t+1` is `0.1688`, while the reverse-direction lag correlation is only `0.0362`. That is not a claim of strong causality, but it is directionally consistent with the idea that the Polymarket signal often moves first.

The archived model progression for the daily pre-open experiment is:

| Model | Description | AUC | Accuracy | Brier Score |
| --- | --- | ---: | ---: | ---: |
| A | TradFi Baseline (Gap + Momentum) | 0.716 | 54.5% | 0.252 |
| B | Polymarket Only | 0.594 | 57.3% | 0.239 |
| C | Combined (Logit) | 0.599 | 58.8% | 0.239 |
| D | Combined (Gradient Boosting) | 0.694 | 67.0% | 0.223 |
| E | Boosting + High Liquidity (`>$500` volume) | 0.688 | 75.7% | 0.200 |

The liquidity result is one of the clearest takeaways. Filtering to high-liquidity observations improved accuracy from `67.0%` in the unrestricted boosting model to `75.7%` in the liquidity-filtered version. The price of that improvement was sample loss: roughly `78%` of observations were discarded because most Polymarket contracts did not trade enough to be trustworthy.

Another important finding is that velocity matters more than level. The most useful daily feature was not the raw pre-open implied probability itself, but the overnight change in that probability. That suggests that what matters is not simply "where the market is," but "how the market moved overnight" as news arrived and beliefs were revised.

These findings are promising but not definitive. The sample in the research notes is only about 60 days long, and while directional accuracy improved, that does not prove investable alpha. Trading costs, slippage, spread crossing, contract fees, and operational frictions were not fully modeled in the dashboard itself.

## 8. Limitations And Caveats

The first limitation is sample size. Sixty days is useful for prototyping, feature design, and demonstrating that the idea is worth exploring, but it is not enough to claim a durable structural relationship. Regimes change, overnight news intensity varies, and a short window can flatter or punish a model by chance.

The second limitation is that no proven alpha has been established. A classifier that reaches `75.7%` directional accuracy under a filtered sample does not automatically become a profitable strategy. Real trading would have to pay spreads, tolerate slippage, respect fees, and deal with uncertain execution quality in both the stock and the Polymarket contract.

The third limitation is liquidity sparsity. Most Polymarket markets are not liquid enough to support high-confidence inference. That is why the high-liquidity filter improves quality so much. The practical implication is that the signal may only be usable in a small subset of names and days.

The fourth limitation is causal interpretation. A lead-lag relationship does not prove that Polymarket causes stock moves. Both markets may simply be responding to the same external information with different speeds or frictions. The dashboard is designed to show timing and association, not to prove structural causality.

The fifth limitation is model overfitting risk. The archived work used walk-forward validation, which is much better than random shuffling for time series, but the sample is still small enough that any complex model can overfit. The dashboard should therefore be read as an evidence display and research tool, not a final production signal engine.

The sixth limitation is the Black-Scholes analogy itself. Interpreting `N(d2)` as a fair benchmark assumes continuous trading, log-normal returns, and frictionless pricing in a way that real binary prediction markets do not satisfy exactly. That assumption is useful and transparent, but it is still an approximation.

## 9. How To Run The Project

### Backend setup

```bash
cd backend
pip install -r requirements.txt
python test_imports.py
python run_daily.py --dry-run
python run_daily.py
uvicorn api.server:app --reload --port 8000
```

What each step does:

- `pip install -r requirements.txt` installs the Python dependencies for the pipeline and API.
- `python test_imports.py` confirms the module split is healthy before any runtime work begins.
- `python run_daily.py --dry-run` runs the pipeline logic without writing files, which is useful for smoke testing.
- `python run_daily.py` performs the real daily pipeline run and writes the CSV and JSON outputs.
- `uvicorn api.server:app --reload --port 8000` starts the FastAPI server consumed by the frontend.

The full live pipeline currently takes roughly `20-40 minutes` because historical Goldsky requests are chunked and deliberately slowed with a short sleep to avoid rate-limit problems.

### Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Then open:

```text
http://localhost:3000
```

The root route redirects automatically to the default asset page.

### Scheduling the pipeline

On macOS or Linux, the daily run can be scheduled with `cron`:

```bash
# Add to crontab - runs at 8:30 AM every weekday
30 8 * * 1-5 cd /path/to/backend && python run_daily.py >> logs/cron.log 2>&1
```

That schedule is designed to finish before the New York equity open so the pre-open signal file and dashboard data are ready for the day.

## 10. Project Structure Overview

The tree below focuses on authored source files, research artifacts, runtime data files, and committed placeholders. Regenerable caches such as `node_modules`, `.next`, `__pycache__`, and `.DS_Store` are documented in `TECHNICAL.md` rather than listed here inline.

```text
polymarket dashboard/
|- 01. Code/
|  |- FML Experiment 2 Class Based (2).ipynb    - original Colab notebook containing the monolithic prototype and archived experiment outputs
|  |- FML Experiment 2 Class Based (2).py       - Python export of the original Colab notebook, used as the source for the refactor
|  `- Visual Architecture.md                    - early architecture sketch connecting browser, API, and data storage concepts
|- 02. Ispiration/
|  |- 01. Visual/
|  |  |- Untitled 5.png                         - visual reference image for dashboard direction
|  |  |- Untitled 6.png                         - visual reference image for dashboard direction
|  |  |- Untitled 7.png                         - visual reference image for dashboard direction
|  |  |- Untitled 10.png                        - visual reference image for dashboard direction
|  |  `- Untitled 11.png                        - visual reference image for dashboard direction
|  |- 02. Github Resources/
|  |  |- Polymarket Dashboard README.md         - external reference dashboard readme collected during inspiration research
|  |  `- Polyrec README.md                      - external reference readme for a different Polymarket analytics project
|  `- 03. Context Document/
|     |- Master Brief Product Logic.pdf         - product logic brief used to shape the dashboard concept
|     |- Polymarket Dashboard README.md         - master research and product-context document with findings, model table, and design notes
|     `- roadmap.json                           - detailed build plan used to stage the refactor, API, and frontend implementation
|- backend/
|  |- __init__.py                               - package marker for backend imports
|  |- config.py                                 - central configuration for assets, APIs, thresholds, paths, and runtime constants
|  |- requirements.txt                          - pinned Python dependencies for the backend
|  |- run_daily.py                              - daily pipeline entry point that writes signals, panel, raw orderbook, and metadata
|  |- test_imports.py                           - import-chain smoke test for the refactored backend
|  |- api/
|  |  |- __init__.py                            - package marker for the API module
|  |  `- server.py                              - FastAPI application serving health, signals, asset detail, pre-open series, and heatmap
|  |- pipeline/
|  |  |- __init__.py                            - re-export layer for pipeline functions and the Orderbook class
|  |  |- features.py                            - feature engineering, pre-open panel construction, and lead-lag analysis
|  |  `- orderbook.py                           - raw Polymarket ingestion, Goldsky querying, and Yahoo Finance stock merge logic
|  |- models/
|  |  |- __init__.py                            - re-export layer for backtest functions
|  |  `- backtest.py                            - retained research backtest functions from the original monolith
|  |- data/
|  |  |- .gitkeep                               - placeholder to keep the data directory in version control before real outputs exist
|  |  |- signals_today.csv                      - pre-open snapshot, one row per asset
|  |  |- panel_15m.csv                          - intraday feature panel used by charts and the heatmap
|  |  |- orderbook_latest.csv                   - latest raw orderbook export used to reconstruct the overnight probability segment
|  |  `- last_run.json                          - metadata consumed by the API health endpoint and stale-data banner
|  `- logs/
|     |- .gitkeep                               - placeholder to keep the log directory in version control
|     `- pipeline_2026-04-03.log                - example pipeline log from a previous run
|- frontend/
|  |- .env.local                                - frontend runtime environment variable pointing the app to the local FastAPI backend
|  |- .gitignore                                - ignore rules for Next.js build and dependency artifacts
|  |- AGENTS.md                                 - local instruction file noting that this Next.js version may differ from older conventions
|  |- CLAUDE.md                                 - alias document that points to AGENTS.md
|  |- README.md                                 - default create-next-app readme retained from scaffold generation
|  |- next-env.d.ts                             - Next.js-generated TypeScript ambient types
|  |- next.config.ts                            - Next.js configuration entry point, currently minimal
|  |- package.json                              - frontend package manifest with scripts and dependencies
|  |- package-lock.json                         - exact npm dependency lockfile
|  |- postcss.config.mjs                        - PostCSS configuration enabling Tailwind CSS v4 integration
|  |- tsconfig.json                             - TypeScript compiler configuration including the `@/*` path alias
|  |- app/
|  |  |- favicon.ico                            - application favicon
|  |  |- globals.css                            - global dark-theme tokens and baseline styling
|  |  |- layout.tsx                             - root layout that mounts the stale-data banner, navbar, and content frame
|  |  |- page.tsx                               - root redirect to the default asset page
|  |  |- asset/[ticker]/page.tsx                - asset detail page that fetches server-side data for Page 2
|  |  `- heatmap/page.tsx                       - heatmap page client entry point for Page 3
|  |- components/
|  |  |- layout/
|  |  |  |- NavBar.tsx                          - top navigation with asset selector and heatmap link
|  |  |  `- StaleBanner.tsx                     - client banner that warns when the backend data is stale or missing
|  |  |- asset/
|  |  |  |- AssetDaySelector.tsx                - client time-range selector for `1D`, `7D`, and `30D`
|  |  |  |- AssetHeader.tsx                     - summary header with ticker, overnight change, pre-open probability, and trade badge
|  |  |  |- ProbabilityChart.tsx                - Polymarket probability chart with pre-open prepend and volume context
|  |  |  |- StockChart.tsx                      - stock line chart for the selected time range
|  |  |  |- TrueSentimentChart.tsx              - bar chart of `true_sentiment` against zero
|  |  |  `- SignalMetricsBlock.tsx              - signal-quality and pre-open metrics cards
|  |  `- heatmap/
|  |     |- AlignmentGrid.tsx                   - clickable daily alignment table colored by quadrant
|  |     |- AlignmentSummaryStats.tsx           - client-side rollup cards summarizing alignment quality
|  |     |- QuadrantLegend.tsx                  - legend for the four heatmap colors
|  |     `- TimeFilterBar.tsx                   - day-range selector for the heatmap
|  |- lib/
|  |  |- api.ts                                 - fetch wrapper and typed API helpers
|  |  `- types.ts                               - shared TypeScript contracts for API responses and UI props
|  `- public/
|     |- file.svg                               - default scaffold asset icon
|     |- globe.svg                              - default scaffold globe icon
|     |- next.svg                               - default Next.js logo asset
|     |- vercel.svg                             - default Vercel logo asset
|     `- window.svg                             - default scaffold window icon
|- README.md                                    - this high-level project and research guide
`- TECHNICAL.md                                 - exhaustive technical implementation reference
```

The fastest way to understand the project end to end is:

1. Read Sections 1 through 4 of this README for the idea and the signal logic.
2. Run the backend and frontend using Section 9.
3. Read `TECHNICAL.md` for the exact file inventory, API contracts, and implementation details.
