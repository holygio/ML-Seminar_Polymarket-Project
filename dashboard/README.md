# Polymarket Signal Dashboard

## 1. What This Is

This is a prediction-market analytics dashboard built to test whether Polymarket's overnight pricing for daily equity up/down contracts leads, lags, or simply contextualizes what traditional assets do after the cash market opens. The product has three user-facing surfaces: `Markets`, `Geopolitical`, and `Asset`. Under the hood it runs on two distinct backend data flows: a file-backed historical research pipeline for signal and heatmap analysis, and a live in-memory market bundle for the real-time dashboard views.

## 2. The Research Signal

The historical signal is defined around a hard New York pre-open cutoff: `09:30 AM America/New_York`. Everything before that time contributes to the daily pre-open snapshot, and everything after it is excluded from the pre-open signal file. `pre_open_implied_prob` is the last implied Polymarket up-probability observed before the firewall, `overnight_prob_change` is the change from the overnight baseline to that final pre-open reading, `signal_direction` is the directional interpretation of that move, and `signal_quality_score` is a composite confidence score driven primarily by volume and microstructure quality. The valuation anchor is a Black-Scholes-style neutral benchmark, and the core diagnostic is `true_sentiment = avg_price_up - bs_neutral_prob`. Positive `true_sentiment` means the crowd is more bullish than the Black-Scholes neutral benchmark would imply, while negative `true_sentiment` means the crowd is more bearish. In practice, the most reliable signals come from higher-liquidity markets, so the research flow explicitly tracks liquidity and treats low-volume moves with less confidence.

## 3. The Three Pages

### Markets

The `Markets` page is a live overview surface for equities plus non-equity reference assets. Its center panel is a live treemap of the 10 tracked U.S. equities sized by market cap, while the right panel shows equal-sized tiles for indices, crypto, and commodities. The key encoding is diagonal: the upper-left triangle reflects the live Yahoo/Stooq return direction, and the lower-right triangle reflects the Polymarket crowd probability direction. The page is powered by `/api/live`, and the backend refresh loop for that payload is started by the API server with a 30-second interval while the frontend polls more frequently.

### Geopolitical

The `Geopolitical` page surfaces curated macro and geopolitical prediction markets discovered from Polymarket. Markets are grouped into `Rates`, `Trade`, `Markets`, `Conflict`, and `Politics`, and each card shows a category pill, a plain-English interpretation, a probability bar, a leading outcome for categorical markets, a 24-hour probability change when available, and equity exposure pills. The data comes from `/api/geopolitical`, which uses search-first event discovery plus filtered dynamic fallback discovery. The endpoint is cached in-process for 5 minutes so repeated frontend refreshes do not hammer the Polymarket APIs.

### Asset

The `Asset` page is the single-ticker deep dive for any of the 10 tracked U.S. equities. It combines a split chart with a stock price panel and a Polymarket probability panel, a true-sentiment display, a pre-open probability timeline, a historical alignment grid, and a signal quality panel. Its data comes from three backend routes: `/api/asset/{ticker}`, `/api/asset/{ticker}/preopen`, and `/api/heatmap` filtered to the active ticker. The route itself is server-rendered, while the charting and navigation widgets stay in client components under `frontend/components/asset/`.

## 4. Architecture Overview

```text
Flow A — Historical pipeline (file-backed)
  Goldsky GraphQL + Polymarket token discovery
    -> backend/pipeline.py (Orderbook + feature engineering)
    -> backend/run_daily.py
    -> signals_today.csv / panel_15m.csv / orderbook_latest.csv / last_run.json
    -> /api/signals/today / /api/asset / /api/asset/{ticker}/preopen / /api/heatmap

Flow B — Live bundle (in-memory)
  Yahoo Finance / Stooq snapshots
  + Polymarket Gamma lookups
    -> backend/live_data.py background refresh worker
    -> _shared_state dict under _data_lock
    -> /api/live

Flow C — Geopolitical (cached)
  Polymarket Gamma public-search + events
  + CLOB price history
    -> backend/pipeline.py fetch_macro_geopolitical_markets()
    -> backend/server.py /api/geopolitical cache (5 minutes)
    -> /api/geopolitical
```

## 5. File Structure

```text
dashboard/
  README.md
    - project-level runtime and usage guide
  TECHNICAL.md
    - implementation-level reference for the dashboard codebase

  backend/
    __init__.py
      - package marker
    config.py
      - central config: asset universe, thresholds, API URLs, symbol maps
    server.py
      - FastAPI app: all 7 endpoints, CORS, serialization, live-cache logic
    pipeline.py
      - Orderbook class, feature engineering, Black-Scholes signal logic,
        Polymarket runtime helpers, geopolitical search/discovery
    live_data.py
      - live market bundle assembly: Yahoo/Stooq + Polymarket snapshot merge,
        background refresh worker, _shared_state
    backtest.py
      - offline research utilities: pro_backtest and beta_backtest
    polymarket_runtime.py
      - compatibility shim that re-exports Polymarket helpers from pipeline.py
    run_daily.py
      - daily pipeline orchestrator that writes all CSV/JSON artifacts
    test_imports.py
      - import smoke test for the consolidated backend
    requirements.txt
      - Python dependencies
    data/
      .gitkeep
        - placeholder for empty-directory tracking
      signals_today.csv
        - pre-open signal snapshot, one row per tracked equity
      panel_15m.csv
        - intraday feature panel in 5-minute windows, legacy filename retained
      orderbook_latest.csv
        - latest raw orderbook export for pre-open chart reconstruction
      last_run.json
        - pipeline freshness metadata used by /health
    logs/
      .gitkeep
        - placeholder for empty-directory tracking
      pipeline_2026-04-03.log
      pipeline_2026-04-12.log
      pipeline_2026-04-13.log
        - dated pipeline execution logs

  frontend/
    app/
      layout.tsx
        - root shell: NavBar + StaleBanner for all routes
      page.tsx
        - redirect: / -> /asset/AAPL
      globals.css
        - global styles and CSS tokens
      favicon.ico
        - favicon
      live/page.tsx
        - Markets page with the live-only UI components inlined locally
      geopolitical/page.tsx
        - Geopolitical page with the geo UI components inlined locally
      heatmap/page.tsx
        - Historical heatmap page with heatmap UI components inlined locally
      asset/[ticker]/page.tsx
        - Asset detail page, implemented as an async server component
    components/
      layout/
        NavBar.tsx
          - top navigation kept separate because it uses client-only hooks
        StaleBanner.tsx
          - data freshness warning banner, polls /health
      asset/
        AlignmentGrid.tsx
          - 30-day historical alignment square grid for a single ticker
        AssetDaySelector.tsx
          - day-range selector using Next navigation hooks
        AssetPageHeader.tsx
          - ticker header, price, return, Polymarket probability, day selector
        CombinedChart.tsx
          - split stock price + Polymarket probability chart
        ModelSnapshot.tsx
          - Black-Scholes values and interpretation card
        PreOpenTimeline.tsx
          - midnight-to-09:30 probability timeline
        SignalQualityPanel.tsx
          - signal score circle, liquidity, and summary metrics
        TrueSentimentPanel.tsx
          - true-sentiment bar and sparkline summary
    lib/
      index.ts
        - merged TypeScript types, API fetch helpers, and color/format utilities
    public/
      file.svg
      globe.svg
      next.svg
      vercel.svg
      window.svg
        - static SVG assets from the Next scaffold
    .env.local
      - local frontend environment configuration
    .gitignore
      - frontend-local ignore rules
    .next
      - generated Next.js build output
    AGENTS.md
      - local agent instructions
    CLAUDE.md
      - alias note for AGENTS.md
    next-env.d.ts
      - Next ambient typings
    next.config.ts
      - minimal Next.js configuration
    node_modules
      - installed frontend dependencies
    package.json
      - frontend dependency and script manifest
    package-lock.json
      - locked npm dependency tree
    postcss.config.mjs
      - Tailwind/PostCSS integration
    README.md
      - scaffold frontend README retained from project initialization
    screenshot.js
      - local screenshot helper
    tsconfig.json
      - TypeScript compiler configuration
```

## 6. How To Run

Prerequisites: Python 3.11+, Node.js 18+

### Step 1 — Install backend dependencies (once)

```bash
cd dashboard/backend
pip install -r requirements.txt
```

### Step 2 — Run the daily data pipeline (once per trading day, before 09:30 ET)

```bash
cd dashboard/backend
python run_daily.py
```

Note: this can take 20–40 minutes on slower runs because the pipeline makes many live Goldsky and market-data requests. The live `Markets` and `Geopolitical` pages work without this step. Only the `Asset` detail page and historical `Heatmap` require fresh pipeline data.

### Step 3 — Start the API server (Terminal 1)

```bash
cd dashboard/backend
python -m uvicorn server:app --reload --port 8000
```

### Step 4 — Install and start the frontend (Terminal 2)

```bash
cd dashboard/frontend
npm install
npm run dev -- --webpack
```

Why `--webpack`:

- the current `recharts` / `d3` dependency combination is reliable under the Webpack dev server
- Turbopack can currently fail during route compilation for chart-heavy pages such as `/asset/[ticker]`

### Step 5 — Open the app

- `http://localhost:3000/live` — Markets page
- `http://localhost:3000/geopolitical` — Geopolitical page
- `http://localhost:3000/asset/NVDA` — Asset detail
- `http://localhost:3000/heatmap` — Historical heatmap

Environment variable note:

`dashboard/frontend/.env.local` must contain:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 7. The Asset Universe

The historical research pipeline tracks these 10 U.S. equity tickers:

- `AAPL` — Apple
- `AMZN` — Amazon
- `COIN` — Coinbase
- `GOOGL` — Alphabet
- `META` — Meta
- `MSFT` — Microsoft
- `NFLX` — Netflix
- `NVDA` — Nvidia
- `PLTR` — Palantir
- `TSLA` — Tesla

`COIN` and `PLTR` were added after the original 8-equity research universe.

The right-panel assets shown live on the `Markets` page are not part of the historical research pipeline:

- Indices: `DAX`, `Dow Jones`, `Nasdaq 100`, `QQQ`, `Russell 2000`, `S&P 500`
- Crypto: `Bitcoin (BTC-USD)`, `Ethereum (ETH-USD)`, `Solana (SOL-USD)`
- Commodities: `Gold (Stooq XAUUSD)`, `Silver (Stooq XAGUSD)`, `WTI (CL=F)`

Commodity source distinction:

- Gold and Silver use Stooq spot-style snapshots so the underlying naming aligns more closely with Polymarket `XAUUSD` and `XAGUSD` markets.
- WTI uses Yahoo `CL=F` because that aligns better with Polymarket's active-month futures wording.

## 8. API Surface

### `GET /health`

- Source: `backend/data/last_run.json`
- Returns: `status`, `timestamp`, `date`, `hours_ago`, `assets_ok`, `assets_failed`, `panel_rows`, `signals_rows`

### `GET /api/signals/today`

- Source: `backend/data/signals_today.csv`
- Returns: one row per ticker with `pre_open_implied_prob`, `overnight_prob_change`, `signal_direction`, `signal_quality_score`, liquidity flags, and related signal fields

### `GET /api/asset/{ticker}?days=N`

- Source: `backend/data/panel_15m.csv` plus `backend/data/signals_today.csv`
- Returns: `probability_series`, `stock_series`, `true_sentiment_series`, `latest_signal`, and route metadata such as `ticker`, `days`, and `row_count`

### `GET /api/asset/{ticker}/preopen`

- Source: `backend/data/orderbook_latest.csv`
- Returns: `preopen_series` with `timestamp`, `price_up`, and `volume`
- Filters to the current New York date and keeps only observations before `09:30`

### `GET /api/heatmap?days=N`

- Source: `backend/data/panel_15m.csv`
- Returns: per-ticker, per-day alignment data with `prob_direction`, `price_direction`, `prob_change`, `price_move`, `volume`, and `quadrant`
- Quadrants are `green`, `red`, `yellow`, or `gray`

### `GET /api/live`

- Source: `backend/live_data.py` `_shared_state` in-memory bundle, refreshed every 30 seconds by the API server
- Returns: a list of `LiveRecord` rows for equities, indices, crypto, and commodities with fields such as `ret_pct`, `poly_up_probability`, `market_cap`, `volume`, and `vol_ratio`

### `GET /api/geopolitical`

- Source: `backend/pipeline.py` `fetch_macro_geopolitical_markets()` plus a 5-minute cache in `backend/server.py`
- Returns: `markets`, `macro_heat`, and `summary`
- Each market record includes `category`, `display_label`, `probability`, `interpretation`, `leading_outcome`, `prob_24h_change`, and `equity_exposure`

## 9. Known Limitations

- Pipeline freshness is file-backed: the asset page and heatmap reflect the last successful `run_daily.py` snapshot, not real-time prices.
- Geopolitical curation is search-driven, so some queries can still land on a related market rather than the exact intended contract.
- `panel_15m.csv` is a legacy filename even though the current resampling window is 5 minutes.
- `true_sentiment` is intentionally blank in `signals_today.csv` because the pre-open signal file is designed to survive even if stock enrichment fails later.
- The Black-Scholes benchmark is a fair-value proxy for directional context, not a literal structural replication of the contract.
- `dashboard/frontend/` is now tracked directly in the main repository rather than as a separate nested checkout.
- Local frontend development currently works more reliably with `npm run dev -- --webpack` than with Turbopack because of chart-library module resolution issues.
- CORS defaults to `http://localhost:3000`; any deployment needs an explicit `CORS_ORIGINS` override.
