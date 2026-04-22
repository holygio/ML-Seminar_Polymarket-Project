# Technical Reference: Polymarket Signal Dashboard

## 1. Architecture Summary

The dashboard is built from three system layers that share one workspace but solve different problems. The first is the historical research pipeline, which is file-backed and designed to produce stable daily artifacts for signal analysis. That path is run manually through `run_daily.py`, typically once per trading day, and writes the CSV/JSON files that power the asset detail page, the heatmap page, and the `/health` freshness endpoint.

The second layer is the live market dashboard bundle, which is in-memory rather than file-backed. It continuously assembles the `Markets` page payload by merging Yahoo Finance or Stooq spot/futures snapshots with live Polymarket probabilities. This bundle is maintained inside `backend/live_data.py`, stored in `_shared_state`, protected by `_data_lock`, and refreshed by a background thread. In the live application, `backend/server.py` starts that thread with a 30-second interval the first time `/api/live` is requested.

The third layer is the live geopolitical discovery path. Instead of persisting intermediate files, it performs search-first Polymarket discovery on demand and caches the final result in-process. The search and parsing logic lives in `backend/pipeline.py`, while the HTTP and cache wrapper lives in `backend/server.py`. Its refresh cadence is request-triggered with a 5-minute cache window, so the first request after cache expiry rebuilds the geopolitical payload.

## 2. `backend/config.py`

Purpose: central configuration file for both the historical pipeline and the live dashboard.

Major exported constants:

- `BASE_DIR`, `DATA_DIR`, `LOG_DIR`
  - path resolution anchored to `Path(__file__).parent`
  - `DATA_DIR` and `LOG_DIR` are used directly by the API server and pipeline runner
- `ASSETS`
  - list of `(slug, exchange)` tuples for the 10 tracked historical equities
  - current values use lowercase slugs such as `("nflx", "new york")`
  - this list is used by the historical pipeline for Goldsky / Polymarket ingestion
- `TICKER_MAP`
  - dict mapping lowercase slugs to uppercase display tickers
  - example: `"nflx" -> "NFLX"`
- `ASSET_UNIVERSE`
  - list of dictionaries with `ticker`, `label`, `category`, and `yf_symbol`
  - includes all 22 displayed assets: 10 U.S. equities, 6 indices, 3 crypto assets, and 3 commodities
- `EQUITY_TICKERS`
  - derived from `ASSET_UNIVERSE`
  - contains the 10 U.S. equity tickers only
- `CATEGORY_ORDER`
  - `["US Equities", "Indices", "Crypto", "Commodities"]`
- `POLYMARKET_RIGHT_PANEL`
  - per-category mapping of right-panel labels to Polymarket symbols
  - used by the live non-equity tile builder
- `POLYMARKET_YF_SYMBOL_MAP`
  - maps `(category, poly_symbol.upper())` to the market-data symbol actually fetched from Yahoo or Stooq
- `DAYS_BACK`, `INTRADAY_WINDOW_MINUTES`, `MAX_WORKERS`, `START_DAY_FROM_NOW`
  - historical pipeline controls
  - `INTRADAY_WINDOW_MINUTES` is currently `5`
- `LIQUIDITY_THRESHOLD`
  - `500` USDC
  - used in signal quality / low-liquidity classification
- `FIREWALL_HOUR_NY`, `FIREWALL_MINUTE_NY`
  - `9` and `30`
  - define the pre-open signal cutoff in New York time
- `RISK_FREE_ANN`
  - annualized risk-free rate used in the Black-Scholes neutral benchmark
  - currently `0.04`
- `HEATMAP_MIN_MOVE`
  - currently `0.005`
  - below this absolute price move, the heatmap treats the day as too small to be a directional signal
- `GAMMA_API`, `GOLDSKY_URL`
  - external endpoint roots for Polymarket event discovery and Goldsky GraphQL history

Important distinction:

- `ASSETS` and `TICKER_MAP` use lowercase slugs intended for historical ingestion and normalization.
- `ASSET_UNIVERSE` uses uppercase tickers and display labels intended for frontend output and live dashboard assembly.
- These should not be treated as interchangeable structures.

## 3. `backend/pipeline.py`

Purpose: merged historical-pipeline and live-Polymarket module. This is the largest backend file and the core of the research logic.

### Section A — Orderbook / ingestion logic

Primary class:

- `Orderbook`

Key methods:

- `fetch_raw_orderbook(self, keys)`
  - top-level entry for raw historical Polymarket data retrieval
  - resets internal state before each run so assets do not contaminate one another
  - inputs: a list of `(slug, exchange)` tuples
  - output: normalized raw orderbook dataframe
- `attach_stock_data(self, orderbook=None)`
  - enriches the raw orderbook dataframe with stock-market information
  - output: dataframe with stock columns added
- `get_data(self, keys)`
  - convenience method that fetches raw data and then attaches stock data
- `_get_market_tokens(self, key_tuple)`
  - discovers Polymarket token IDs for a single asset/day combination
- `_get_multiple_tokens(self, keys)`
  - batches token discovery across keys
- `_get_single_orderfills(self, asset_id, start_dt, end_dt, up_down_key)`
  - performs the Goldsky GraphQL request for one asset/time bucket/outcome side
- `_process_all_orderfills(self)`
  - normalizes and assembles raw trade events into the working orderbook dataframe
- `_pull_stock_close(self)`
  - daily Yahoo close data for the tracked equity
- `_pull_stock_minutes(self, minutes=5, window_size=5)`
  - intraday Yahoo bars plus rolling volatility estimates

Inputs:

- Polymarket/Gamma token discovery
- Goldsky GraphQL order-fill history
- Yahoo Finance daily and minute bars

Outputs:

- raw or stock-enriched Polymarket orderbook dataframe

Non-obvious details:

- the class is stateful, but each top-level fetch path resets state before reuse
- the method signatures currently use `keys` rather than a single `ticker, days_back` pair
- the current consolidated file does not contain an explicit `time.sleep(0.1)` rate-limit delay, but runs are still long because they perform many sequential external calls

### Section B — Feature engineering and signal construction

Key functions:

- `collapse_to_windows(df, minutes=5, risk_free_ann=RISK_FREE_ANN) -> pd.DataFrame`
  - resamples raw orderbook rows into 5-minute windows
  - computes:
    - `open_bet`
    - `close_bet`
    - `avg_price_up`
    - `high_bet`
    - `low_bet`
    - `total_volume`
    - `trade_count`
    - `bull_volume`
    - `bear_volume`
    - `poly_vol_imbalance`
    - `stock_close`
    - `stock_vol`
  - then computes:
    - `bs_neutral_prob = N(d2)`
    - `true_sentiment = avg_price_up - bs_neutral_prob`
- `check_lead_lag(df) -> pd.DataFrame`
  - adds forward and backward move columns and prints correlation diagnostics
- `analyse_sentiment_dynamics(df)`
  - prints OLS and logit regression summaries for research analysis
- `build_preopen_panel(orderbook: pd.DataFrame, target_date=None) -> pd.DataFrame`
  - filters the raw orderbook to the midnight-to-09:30 New York window
  - computes:
    - `pre_open_implied_prob`
    - `overnight_prob_change`
    - `pre_open_pm_volume`
    - `pre_open_buy_ratio`
    - `is_high_liquidity`
    - `signal_direction`
    - `signal_quality_score`
  - intentionally does not require stock enrichment, so the pre-open file can still be produced even if Yahoo stock merging fails later in the run

Key formula:

- `true_sentiment = avg_price_up - N(d2)`

Where:

- `d2 = (ln(S/K) + (r - 0.5σ²)T) / (σ√T)`
- `S` is the stock price
- `K` is the open reference level
- `σ` is annualized rolling volatility
- `T` is time to close

Interpretation:

- positive `true_sentiment` means the crowd is pricing more upside than the neutral Black-Scholes-style benchmark
- negative `true_sentiment` means the crowd is pricing less upside, or more downside, than that benchmark

### Section C — Live runtime and geopolitical discovery

Important constants:

- `GAMMA_MARKETS_URL`
- `GAMMA_EVENTS_URL`
- `CLOB_BOOK_URL`
- `CLOB_PRICES_HISTORY_URL`
- `GAMMA_SEARCH_URL`
- `GEOPOLITICAL_TAG_ID`
- `TICKER_ALIASES`
- `PRIORITY_MACRO_TOPICS`

Key functions:

- `get_effective_nyse_market_date(now=None) -> date`
  - returns the correct NYSE trading date for current lookup timing
- `get_effective_crypto_market_date(now=None) -> date`
  - uses a different roll convention for crypto
- `build_up_down_slug(symbol: str, target_date: date) -> str`
  - generates Polymarket-style daily slugs such as `nvidia-up-or-down-on-april-14-2026`
- `get_market_probabilities_by_slug(...) -> dict`
  - direct slug lookup against Gamma
- `get_probabilities_for_tickers(tickers) -> pd.DataFrame`
  - batch probability lookup for equity tickers
- `_extract_probability_robust(market) -> tuple[float | None, str | None, str]`
  - handles binary and categorical markets
  - categorical markets return both the leading probability and the leading outcome label
  - important implementation detail: `outcomePrices` and related fields arrive as JSON-stringified strings and must be `json.loads()`-ed first
- `fetch_probability_change_24h(yes_token_id) -> float | None`
  - uses `CLOB /prices-history`
  - currently requests `fidelity=60` and returns `current_prob - prob_24h_ago`
- `search_events(query, limit) -> list[dict]`
  - uses Gamma `public-search`
  - current implementation uses `params={"q": query, "limit": limit}`
- `find_best_market_for_topic(search_query, category, equity_tickers, display_label) -> dict | None`
  - searches, scores candidates, parses probability, and injects category/exposure metadata
- `fetch_macro_geopolitical_markets(max_curated, max_dynamic) -> list[dict]`
  - two-tier discovery:
    - curated `PRIORITY_MACRO_TOPICS` first
    - then filtered dynamic tag discovery
  - noise filtering removes highly specific battlefield or niche corporate markets
  - results are sorted curated-first, then by category and volume

Dependencies:

- Polymarket Gamma API
- Polymarket CLOB API
- pandas
- requests
- optional `pandas_market_calendars`

## 4. `backend/live_data.py`

Purpose: power the `/api/live` payload and the live bundle shown on the `Markets` page.

### Section A — Base utilities

Key values and helpers:

- `ASSETS`
  - derived directly from `ASSET_UNIVERSE`
  - stored as `(category, label, yf_symbol)` tuples
- `human_num(x)`
  - humanizes large quantities such as `1.2T` or `850B`
- `human_price(x)`
  - formats prices with more precision below `1` and two decimals above it
- `get_market_cap(ticker) -> float`
  - uses `yfinance` `fast_info` when possible, then falls back to `info`

### Section B — Live bundle assembly

Threading state:

- `_data_lock`
  - `threading.Lock`
- `_shared_state`
  - dictionary containing `df`, `history`, and `last_fetched`

Key functions:

- `_yf_live_snapshot(symbol) -> dict`
  - multi-fallback live market-data collector
  - tries several Yahoo-derived paths before giving up
  - returns a structure including `date`, `prev_close`, `last_close`, `chg_abs`, and `ret_pct`
- `_stooq_live_snapshot(symbol) -> dict`
  - used for gold and silver spot-style snapshots
  - these align better with Polymarket `XAUUSD` and `XAGUSD` naming than the corresponding Yahoo futures symbols
- `_fetch_right_panel_market(category, label, symbol, target_date) -> dict`
  - attempts a direct slug-based Polymarket lookup first
  - falls back to text search if the slug lookup returns no useful probability
- `_poly_market_rows() -> pd.DataFrame`
  - builds the live right-panel rows for indices, crypto, and commodities
- `_stock_live_rows(stock_assets, poly_lookup) -> list[dict]`
  - builds the equity rows, including `vol_ratio` versus recent average volume
- `load_market_bundle() -> tuple[pd.DataFrame, dict, str]`
  - assembles the complete live market dataframe and supporting history structures
- `start_background_refresh(interval_seconds: int = 10)`
  - starts the daemon refresh loop
  - in practice, `backend/server.py` calls it as `start_background_refresh(interval_seconds=30)` for the `/api/live` API

Important implementation details:

- right-panel rows emit `ret_pct` and `last_close` for all categories, not just crypto
- Stooq is used only where it improves semantic alignment with the Polymarket contract naming
- a backend-local `polymarket_runtime.py` shim exists for compatibility, but `live_data.py` ultimately resolves Polymarket helpers from the consolidated backend module set

Dependencies:

- `yfinance`
- `requests`
- `pandas`
- Polymarket Gamma/CLOB helpers via `pipeline.py`

## 5. `backend/server.py`

Purpose: FastAPI application and HTTP boundary for all dashboard data.

Startup behavior:

- creates the FastAPI app
- configures CORS using `CORS_ORIGINS`, defaulting to `http://localhost:3000`

Helper functions:

- `nan_safe(val)`
  - converts NaN, inf, and numpy scalar values into JSON-safe Python types
- `serialize_signal_row(row)`
  - converts a `signals_today.csv` row into the API response shape
  - notably coerces `is_high_liquidity` using `str(val).lower() == "true"` semantics for string values
  - lowercases `signal_direction` to match the TypeScript union expected by the frontend
- `_derive_equity_exposure(title)`
  - keyword-based mapping from event text to affected tickers
- `_build_macro_heat(markets)`
  - aggregates per-market exposure into a ticker-by-category heat grid
- `_plain_english_interpretation(...)`
  - produces readable geopolitical probability summaries for the frontend cards

Endpoints:

- `GET /health`
  - source: `data/last_run.json`
  - returns pipeline freshness and run summary information
- `GET /api/signals/today`
  - source: `data/signals_today.csv`
  - returns the current pre-open signal table
- `GET /api/asset/{ticker}/preopen`
  - source: `data/orderbook_latest.csv`
  - filters to the current New York calendar date and pre-09:30 observations
- `GET /api/asset/{ticker}`
  - source: `data/panel_15m.csv` plus `data/signals_today.csv`
  - returns price, probability, sentiment series, and the latest signal snapshot
- `GET /api/heatmap`
  - source: `data/panel_15m.csv`
  - computes day-level alignment quadrants on the fly
- `GET /api/live`
  - source: `live_data.py` `_shared_state`
  - starts the background refresh thread on first request if it is not already running
- `GET /api/geopolitical`
  - source: `pipeline.py` live discovery functions
  - wraps the output in a 5-minute in-process cache using `_GEO_CACHE`
  - filters out markets with `probability is None` or `0.0`
  - fetches 24h change only for the first 15 eligible markets to limit CLOB pressure
  - categorical markets include `leading_outcome` in the response

Known response-shape details:

- `latest_signal` is returned as `null` when no signal row exists for the asset
- `signal_direction` leaves the CSV as uppercase in practice, but the API intentionally normalizes it to lowercase
- `is_high_liquidity` may arrive from CSV as a string-like value and is explicitly coerced

## 6. `backend/run_daily.py`

Purpose: orchestrate the end-to-end historical pipeline and persist the daily artifacts.

Execution order:

1. `setup_logging()`
   - creates the dated log file under `logs/`
2. `step1_fetch_raw()`
   - runs `Orderbook.fetch_raw_orderbook()` per configured asset
3. `step2_build_and_save_signals()`
   - runs `build_preopen_panel()` and writes `signals_today.csv`
   - important design choice: this happens before stock enrichment, so the morning signal file survives even if the Yahoo merge fails
4. `save_raw_orderbook()`
   - writes `orderbook_latest.csv`
5. `step3_attach_stock()`
   - runs `Orderbook.attach_stock_data()`
6. `step4_build_and_save_panel()`
   - runs `collapse_to_windows()` and `check_lead_lag()`, then writes `panel_15m.csv`
7. `step5_save_metadata()`
   - writes `last_run.json`

CLI behavior:

- supports `--dry-run`
- `--dry-run` still performs live external requests; it only suppresses file writes

Operational note:

- full runs can still take a long time because they depend on repeated external requests to Goldsky, Polymarket, and market-data providers

## 7. `frontend/lib/index.ts`

Purpose: single merged frontend support module for types, API calls, and formatting helpers.

Exported types and constants:

- `HealthStatus`
  - `status`, `timestamp`, `date`, `hours_ago`, `assets_ok`, `assets_failed`, `panel_rows`, `signals_rows`
- `SignalToday`
  - pre-open signal row shape, including `true_sentiment` and optional `stock_vol_ann` / `bs_neutral_prob`
- `ProbabilityPoint`
  - `timestamp`, `price_up`, `volume`, `open_bet`, `high_bet`, `low_bet`
- `StockPoint`
  - `timestamp`, `close`
- `SentimentPoint`
  - `timestamp`, `true_sentiment`, `abs_sentiment`, `bs_neutral_prob`
- `AssetDetail`
  - `ticker`, `days`, `row_count`, `latest_signal`, and the three series arrays
- `HeatmapEntry`
  - `ticker`, `date`, `prob_direction`, `price_direction`, `prob_change`, `price_move`, `volume`, `quadrant`
- `HeatmapResponse`
  - `days`, `count`, `data`
- `LiveRecord`
  - live bundle row including `ticker`, `category`, `label`, `last_close`, `prev_close`, `ret_pct`, `chg_abs`, `market_cap`, `volume`, `vol_ratio`, `poly_up_probability`, `poly_target_date`, `date`, `last_fetched`
- `GeoMarket`
  - geopolitical market record including `display_label`, `leading_outcome`, `market_type`, `interpretation`, `prob_24h_change`, and `equity_exposure`
- `GeoResponse`
  - `markets`, `macro_heat`, `summary`, `fetched_at`
- `Ticker`
  - string-literal union of the 10 tracked equities
- `ALL_TICKERS`
  - constant array of those 10 tickers

Fetch helpers:

- `fetchHealth`
- `fetchSignalsToday`
- `fetchAsset`
- `fetchAssetPreopen`
- `fetchHeatmap`
- `fetchLive`
  - tolerates non-OK responses by returning `[]`, which is how the frontend handles the warm-up state for `/api/live`
- `fetchGeopolitical`

All fetch helpers use:

- `NEXT_PUBLIC_API_URL`
- `cache: 'no-store'`

Formatter functions:

- `retColor(ret)`
  - multi-bucket red-to-teal color scale
- `polyColor(prob)`
  - green above `55%`, red below `45%`, gray otherwise
- `diagColors(ret, prob)`
  - returns `{ ul, lr }` for diagonal tile coloring
- `fmtRet(ret)`
  - formats returns as strings like `+2.44%`
- `fmtPrice(p)`
  - formats prices with commas above `1000`
- `fmtProb(prob)`
  - formats probabilities as whole percentages such as `64%`

## 8. Frontend Pages

### `app/layout.tsx`

- rendering model: server component
- responsibility: root shell for all routes
- key components:
  - `NavBar`
  - `StaleBanner`
- non-obvious detail:
  - `layout.tsx` exports metadata, so the hook-using client components remain under `components/layout/` instead of being inlined

### `app/live/page.tsx`

- rendering model: client component with `'use client'`
- data fetching:
  - polls `/api/live`
- refresh behavior:
  - fetch every 10 seconds
  - local countdown UI updates every second
- key components used:
  - `Banner`
  - `EquityTile`
  - `RightPanel`
  - `RightTile`
  - all of these are now inlined in the page file
- non-obvious details:
  - Recharts `Treemap` uses `foreignObject` to render arbitrary HTML tiles inside SVG space
  - tile colors are encoded with layered rgba diagonal overlays on top of a dark base tile

### `app/geopolitical/page.tsx`

- rendering model: client component with `'use client'`
- data fetching:
  - polls `/api/geopolitical`
- refresh behavior:
  - fetch every 60 seconds in the current implementation
- key components used:
  - `EventCard`
  - `MacroHeatGrid`
  - `MacroMovers`
  - `SummaryCards`
  - all of these are inlined in the page file
- non-obvious details:
  - category filtering is fully client-side via `useState`
  - markets are regrouped on the client by section before rendering

### `app/heatmap/page.tsx`

- rendering model: client component with `'use client'`
- data fetching:
  - loads `/api/heatmap?days=N`
- refresh behavior:
  - re-fetches when the day-range filter changes
- key components used:
  - `AlignmentGrid`
  - `AlignmentSummaryStats`
  - `QuadrantLegend`
  - `TimeFilterBar`
  - all are inlined in the page file

### `app/asset/[ticker]/page.tsx`

- rendering model: async server component
- data fetching:
  - performs `fetchAsset`, `fetchAssetPreopen`, and `fetchHeatmap` in parallel
- validation:
  - rejects unknown tickers using `ALL_TICKERS` and `notFound()`
- query params:
  - supports `?days=`
  - clamps values to `1..60`
  - current route default is `60`
- non-obvious detail:
  - the page remains server-rendered while charting and navigation widgets stay under `components/asset/` because they are client-only

## 9. Data Contracts (CSV schemas)

### `signals_today.csv`

Current columns:

- `ticker`
- `date`
- `pre_open_implied_prob`
- `overnight_prob_change`
- `pre_open_pm_volume`
- `pre_open_buy_ratio`
- `is_high_liquidity`
- `signal_direction`
- `signal_quality_score`
- `true_sentiment`

Observed storage details:

- `is_high_liquidity` is written as `True` / `False`
- `signal_direction` is written as uppercase values such as `UP`
- `true_sentiment` is blank in the CSV today, which reads back as null/NaN

### `panel_15m.csv`

Current columns:

- `KEY`
- `TIMESTAMP`
- `time_to_exp`
- `open_bet`
- `close_bet`
- `avg_price_up`
- `high_bet`
- `low_bet`
- `total_volume`
- `trade_count`
- `stock_open_day`
- `stock_close`
- `stock_avg_period`
- `stock_vol`
- `poly_vol_imbalance`
- `bs_neutral_prob`
- `true_sentiment`
- `next_stock_move`
- `curr_stock_move`
- `next_true_sent`
- `abs_sentiment`

Important note:

- the file retains the old `panel_15m.csv` name even though the actual interval is now 5 minutes
- the identifier column is `KEY`, not `ticker`

### `orderbook_latest.csv`

Minimum columns needed by the pre-open endpoint:

- `KEY`
- `TIMESTAMP`
- `PRICE_UP`
- `USDC`

Current file also includes additional raw-orderbook columns such as:

- `REL_HOUR`
- `TIME_TO_EXP`
- `UP_DOWN`
- `MAKER`
- `TAKER`
- `SHARES`
- `PRICE`
- `BUY_SELL`
- `log_odds`
- `country`

### `last_run.json`

Current fields:

- `timestamp`
- `date`
- `assets_ok`
- `assets_failed`
- `panel_rows`
- `signals_rows`

## 10. Known Issues

1. `panel_15m.csv` is a legacy filename even though the current resampling interval is 5 minutes. Renaming it would require coordinated changes in the API server and any local tooling that loads it.
2. `dashboard/frontend/` is tracked directly in the main repository now. Older notes about a nested frontend checkout are obsolete.
3. `/api/asset/{ticker}/preopen` filters against the current New York date, not the historical pipeline run date. If the pipeline data is stale, the pre-open overlay may disappear even while older historical panels still render.
4. The geopolitical curation layer uses Gamma `public-search` with `q=`, and some phrases can still resolve to a related rather than exact contract. These probabilities should be treated as approximate indicators.
5. CORS defaults to `http://localhost:3000`. Any deployment needs an explicit `CORS_ORIGINS` environment variable.
6. `run_daily.py --dry-run` still performs live network calls. It only suppresses writes to disk.
7. The frontend production build is type-sensitive and currently passing. Earlier type issues around inlined heatmap component props were resolved during consolidation.
8. Market-data fallbacks remain necessary because Yahoo throttling and response inconsistency are still common. Gold and silver therefore use Stooq spot-style snapshots in the live bundle.
9. For local development, `next dev --webpack` is currently the safer frontend entrypoint. Turbopack has shown module-resolution failures with the current `recharts` / `d3` dependency tree on chart-heavy routes.

## 11. Running in Production

### Backend

Suggested target: Railway or Render

- Python runtime using `requirements.txt`
- persistent storage for `data/` and `logs/`
- `CORS_ORIGINS` set to the production frontend URL
- scheduled job to run `python run_daily.py` before `09:30 ET` on trading days
- process restart on deploy so the API server is reloaded cleanly

Run command:

```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

### Frontend

Suggested target: Vercel

- required environment variable:
  - `NEXT_PUBLIC_API_URL=https://<backend-url>`
- build command:
  - `npm run build`
- output:
  - standard Next.js `.next/` build output

Local dev note:

- prefer `npm run dev -- --webpack` until the Turbopack compatibility issue with the chart stack is resolved
