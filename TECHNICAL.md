# Technical Reference: Polymarket Signal Dashboard

This document is the implementation-level reference for the current repository. It is written for a developer or researcher who wants to understand exactly how the project works, what each file does, what assumptions the code makes, and where the known rough edges are.

The document describes the codebase as it exists now, not only as originally planned. Where archived research notes or roadmap files differ from the live implementation, this document calls that out explicitly.

## 1. Complete File Inventory

This section inventories the repository files that currently matter for understanding, rebuilding, or extending the system. It covers authored source files, runtime data files, development fixtures, archived research artifacts, and the generated local files presently sitting in the workspace. It does not inventory directory contents of `frontend/node_modules`, `frontend/.next`, or `.git`, because those are dependency/build/version-control directories rather than authored files.

One important note up front: there is **no** `tailwind.config.ts` in this repository. The frontend uses Tailwind CSS v4 through `postcss.config.mjs` and CSS custom properties in `frontend/app/globals.css`.

### Root-level files

- `README.md`
  - Purpose: high-level project documentation for mixed technical and non-technical audiences.
  - Imports: none.
  - Exports or exposes: human-readable project overview, research framing, architecture, and run instructions.
  - Non-obvious detail: this file is intentionally written from simple explanation to technical depth so it can onboard both practitioners and developers.

- `TECHNICAL.md`
  - Purpose: exhaustive implementation reference for the current repository.
  - Imports: none.
  - Exports or exposes: human-readable technical documentation.
  - Non-obvious detail: it documents the live code, including inconsistencies between archived notes and current implementation.

- `.DS_Store`
  - Purpose: macOS Finder metadata.
  - Imports: none.
  - Exports or exposes: none.
  - Non-obvious detail: safe to delete; not part of the application.

### Legacy research and prototype files under `01. Code/`

- `01. Code/FML Experiment 2 Class Based (2).ipynb`
  - Purpose: original Colab notebook containing the monolithic prototype, exploratory analysis, and archived output cells.
  - Imports: notebook cells import `requests`, `json`, `time`, `pandas`, `pytz`, `yfinance`, `numpy`, `statsmodels`, plotting libraries, and more.
  - Exports or exposes: no formal module exports; it is an interactive research notebook.
  - Non-obvious detail: this is the source of the exact printed lead/lag correlation values cited in the README; it also contains the earlier duplicate `pro_backtest` definitions that were later cleaned up in the refactor.

- `01. Code/FML Experiment 2 Class Based (2).py`
  - Purpose: Python export of the original notebook, preserved as the monolithic source that the backend refactor split into modules.
  - Imports: `requests`, `json`, `time`, `pandas`, `pytz`, `yfinance`, `numpy`, `datetime`, `ThreadPoolExecutor`, and later `statsmodels`.
  - Exports or exposes: legacy `Orderbook`, feature engineering functions, analytics helpers, and backtest functions in one file.
  - Non-obvious detail: the refactor pulled the runtime-relevant pieces out of this file into `backend/pipeline/` and `backend/models/`, but the original file remains valuable because it preserves experimental outputs and comments that were not all migrated into production modules.

- `01. Code/Visual Architecture.md`
  - Purpose: early architecture memo showing how the browser, API, processing layer, and CSV storage were originally imagined.
  - Imports: none.
  - Exports or exposes: human-readable system diagram and design intent.
  - Non-obvious detail: it still references an older three-page layout and a different API surface than the live FastAPI implementation.

### Inspiration and context files under `02. Ispiration/`

- `02. Ispiration/.DS_Store`
  - Purpose: macOS Finder metadata for the inspiration folder.
  - Imports: none.
  - Exports or exposes: none.
  - Non-obvious detail: safe to delete.

- `02. Ispiration/01. Visual/Untitled 5.png`
  - Purpose: external visual inspiration image.
  - Imports: none.
  - Exports or exposes: bitmap reference.
  - Non-obvious detail: used only for design inspiration, not at runtime.

- `02. Ispiration/01. Visual/Untitled 6.png`
  - Purpose: external visual inspiration image.
  - Imports: none.
  - Exports or exposes: bitmap reference.
  - Non-obvious detail: not used by the app.

- `02. Ispiration/01. Visual/Untitled 7.png`
  - Purpose: external visual inspiration image.
  - Imports: none.
  - Exports or exposes: bitmap reference.
  - Non-obvious detail: not used by the app.

- `02. Ispiration/01. Visual/Untitled 10.png`
  - Purpose: external visual inspiration image.
  - Imports: none.
  - Exports or exposes: bitmap reference.
  - Non-obvious detail: not used by the app.

- `02. Ispiration/01. Visual/Untitled 11.png`
  - Purpose: external visual inspiration image.
  - Imports: none.
  - Exports or exposes: bitmap reference.
  - Non-obvious detail: not used by the app.

- `02. Ispiration/02. Github Resources/Polymarket Dashboard README.md`
  - Purpose: imported reference README from another Polymarket dashboard project.
  - Imports: none.
  - Exports or exposes: human-readable reference material.
  - Non-obvious detail: describes a different tech stack centered on Next.js API routes, SQLite, and Bitquery rather than the Python/FastAPI architecture in this repository.

- `02. Ispiration/02. Github Resources/Polyrec README.md`
  - Purpose: imported reference README for a different Polymarket research project focused on BTC prediction markets.
  - Imports: none.
  - Exports or exposes: human-readable reference material.
  - Non-obvious detail: useful for general prediction-market tooling ideas, but not directly connected to the current dashboard.

- `02. Ispiration/03. Context Document/Master Brief Product Logic.pdf`
  - Purpose: product-logic brief used to shape the dashboard concept.
  - Imports: none.
  - Exports or exposes: PDF design and planning context.
  - Non-obvious detail: not parsed by runtime code.

- `02. Ispiration/03. Context Document/Polymarket Dashboard README.md`
  - Purpose: the main archived context document containing the research summary, model table, dashboard concept, and implementation notes.
  - Imports: none.
  - Exports or exposes: human-readable project context.
  - Non-obvious detail: several exact research claims used in the current docs, including the model-performance table and the note that high-liquidity filtering improved accuracy to `75.7%`, come from this file.

- `02. Ispiration/03. Context Document/roadmap.json`
  - Purpose: staged implementation plan for the refactor, pipeline, API, and frontend.
  - Imports: none.
  - Exports or exposes: JSON-encoded build plan and code snippets.
  - Non-obvious detail: some roadmap items differ from the final implementation, for example the original idea of deriving today's signal from the panel was replaced by the raw-orderbook `build_preopen_panel()` approach.

### Backend package files

- `backend/__init__.py`
  - Purpose: marks `backend/` as a Python package.
  - Imports: none.
  - Exports or exposes: nothing.
  - Non-obvious detail: intentionally empty.

- `backend/config.py`
  - Purpose: central source of truth for paths, assets, API endpoints, thresholds, and runtime constants.
  - Imports: `Path` from `pathlib`.
  - Exports or exposes: named module constants such as `ASSETS`, `DATA_DIR`, `GOLDSKY_URL`, `LIQUIDITY_THRESHOLD`, and `RISK_FREE_ANN`.
  - Non-obvious detail: every module imports from here directly or via a fallback `backend.config` import path to support both script-style and package-style execution.

- `backend/requirements.txt`
  - Purpose: pinned Python dependency list.
  - Imports: none.
  - Exports or exposes: installable dependency spec for `pip`.
  - Non-obvious detail: includes both pipeline libraries (`pandas`, `numpy`, `yfinance`, `statsmodels`) and API/runtime libraries (`fastapi`, `uvicorn`, `python-multipart`).

- `backend/run_daily.py`
  - Purpose: entry point for the daily data pipeline.
  - Imports: standard library modules plus `pandas`, `config`, `pipeline.features`, and `pipeline.orderbook`.
  - Exports or exposes: top-level `run()` plus helper steps like `step1_fetch_raw`, `step2_build_and_save_signals`, and `step4_build_and_save_panel`.
  - Non-obvious detail: writes the pre-open signal file before stock attachment, which is the key design fix that kept pre-open rows from disappearing.

- `backend/test_imports.py`
  - Purpose: smoke test for the module split.
  - Imports: `os`, `sys`, `config`, `pipeline.features`, and `pipeline.orderbook`.
  - Exports or exposes: no reusable symbols; it prints verification text when run.
  - Non-obvious detail: this is the first sanity check after refactor or environment setup because it fails fast on broken import chains.

### Backend API files

- `backend/api/__init__.py`
  - Purpose: marks `backend/api` as a package.
  - Imports: none.
  - Exports or exposes: nothing.
  - Non-obvious detail: intentionally empty.

- `backend/api/server.py`
  - Purpose: FastAPI application serving the dashboard data.
  - Imports: `json`, `sys`, `datetime`, `Path`, `numpy`, `pandas`, `pytz`, `FastAPI`, `HTTPException`, `Query`, `CORSMiddleware`, plus `DATA_DIR`, `HEATMAP_MIN_MOVE`, and `LIQUIDITY_THRESHOLD` from `config`.
  - Exports or exposes: `app` plus HTTP endpoints `/health`, `/api/signals/today`, `/api/asset/{ticker}/preopen`, `/api/asset/{ticker}`, and `/api/heatmap`.
  - Non-obvious detail: it normalizes NaN and NumPy scalar types explicitly so FastAPI can serialize pandas-derived values without failing.

### Backend pipeline files

- `backend/pipeline/__init__.py`
  - Purpose: re-export layer for the main pipeline API.
  - Imports: `analyse_sentiment_dynamics`, `build_preopen_panel`, `check_lead_lag`, `collapse_to_windows`, and `Orderbook`.
  - Exports or exposes: those five names through `__all__`.
  - Non-obvious detail: this makes the package ergonomic for `from pipeline import ...` imports during local experimentation.

- `backend/pipeline/orderbook.py`
  - Purpose: raw Polymarket ingestion and stock-data merge logic.
  - Imports: `json`, `time`, `ThreadPoolExecutor`, `datetime`, `timedelta`, `timezone`, `Path`, `numpy`, `pandas`, `pytz`, `requests`, `yfinance`, plus configuration constants.
  - Exports or exposes: the `Orderbook` class.
  - Non-obvious detail: `fetch_raw_orderbook()` resets internal state on each call specifically so `run_daily.py` can loop asset by asset without contamination from previous iterations.

- `backend/pipeline/features.py`
  - Purpose: feature engineering and research analytics.
  - Imports: `datetime`, `numpy`, `pandas`, `pytz`, `statsmodels.api`, `norm` from `scipy.stats`, plus signal-related constants from `config`.
  - Exports or exposes: `collapse_to_windows`, `check_lead_lag`, `analyse_sentiment_dynamics`, and `build_preopen_panel`.
  - Non-obvious detail: `build_preopen_panel()` is the architectural fix that decouples the daily signal from stock-market availability.

### Backend model files

- `backend/models/__init__.py`
  - Purpose: re-export layer for backtest functions.
  - Imports: `beta_backtest`, `pro_backtest`.
  - Exports or exposes: those two functions through `__all__`.
  - Non-obvious detail: this is where the refactor deliberately preserved the second `pro_backtest` implementation and dropped the earlier duplicate.

- `backend/models/backtest.py`
  - Purpose: historical backtesting utilities retained from the original notebook.
  - Imports: `numpy`, `pandas`.
  - Exports or exposes: `pro_backtest` and `beta_backtest`.
  - Non-obvious detail: these are research utilities, not part of the dashboard runtime path, but they remain useful for evaluating signal behavior offline.

### Backend runtime data files

- `backend/data/.gitkeep`
  - Purpose: keeps the empty data directory under version control.
  - Imports: none.
  - Exports or exposes: nothing.
  - Non-obvious detail: the first real pipeline run will create actual data files alongside it.

- `backend/data/signals_today.csv`
  - Purpose: one-row-per-asset pre-open snapshot used by the metrics block and daily summary logic.
  - Imports: read by `backend/api/server.py`.
  - Exports or exposes: current signal rows for the tracked universe.
  - Non-obvious detail: in development it is a synthetic fixture; in production it is overwritten by `run_daily.py`.

- `backend/data/panel_15m.csv`
  - Purpose: intraday feature panel used by the asset page and heatmap.
  - Imports: read by `backend/api/server.py`.
  - Exports or exposes: per-window feature rows across assets and dates.
  - Non-obvious detail: despite the filename, the current panel is built at 5-minute resolution because `INTRADAY_WINDOW_MINUTES=5`.

- `backend/data/orderbook_latest.csv`
  - Purpose: latest raw orderbook export used by the `/api/asset/{ticker}/preopen` endpoint.
  - Imports: read by `backend/api/server.py`.
  - Exports or exposes: the raw or mock orderbook rows needed to rebuild the overnight probability segment.
  - Non-obvious detail: the checked-in mock version is intentionally reduced to four columns (`KEY`, `TIMESTAMP`, `PRICE_UP`, `USDC`), but the live pipeline writes a much richer raw export.

- `backend/data/last_run.json`
  - Purpose: metadata describing the most recent pipeline run.
  - Imports: read by `backend/api/server.py` and surfaced by `StaleBanner.tsx`.
  - Exports or exposes: timestamp, date, asset success/failure lists, and row counts.
  - Non-obvious detail: the stale banner uses this file indirectly by polling `/health`, not by reading JSON directly from the filesystem.

### Backend log files

- `backend/logs/.gitkeep`
  - Purpose: keeps the log directory under version control.
  - Imports: none.
  - Exports or exposes: nothing.
  - Non-obvious detail: safe placeholder.

- `backend/logs/pipeline_2026-04-03.log`
  - Purpose: example runtime log from a pipeline execution.
  - Imports: none.
  - Exports or exposes: human-readable execution log.
  - Non-obvious detail: future runs create new files by date, and reruns on the same day append through the standard logging handlers.

### Frontend environment and configuration files

- `frontend/.env.local`
  - Purpose: local frontend environment variable file.
  - Imports: read by Next.js at build and dev-server time.
  - Exports or exposes: `NEXT_PUBLIC_API_URL=http://localhost:8000`.
  - Non-obvious detail: because it is a `NEXT_PUBLIC_` variable, the value is exposed to browser code as well as server-rendered code.

- `frontend/.gitignore`
  - Purpose: ignore rules for Next.js and npm artifacts.
  - Imports: consumed by Git.
  - Exports or exposes: ignore patterns only.
  - Non-obvious detail: it ignores `.env*`, which is correct for secrets but means collaborators must recreate `.env.local` manually.

- `frontend/AGENTS.md`
  - Purpose: local guidance note for coding agents.
  - Imports: none.
  - Exports or exposes: human-readable instruction to consult Next.js docs because this version differs from older conventions.
  - Non-obvious detail: useful because the project uses Next.js 16, whose route-parameter behavior differs from older App Router expectations.

- `frontend/CLAUDE.md`
  - Purpose: alias file pointing readers to `AGENTS.md`.
  - Imports: none.
  - Exports or exposes: a one-line reference.
  - Non-obvious detail: avoids duplication of agent instructions.

- `frontend/README.md`
  - Purpose: default create-next-app readme retained from scaffold generation.
  - Imports: none.
  - Exports or exposes: general Next.js scaffold instructions.
  - Non-obvious detail: it describes the default scaffold, not the Polymarket dashboard specifically.

- `frontend/next-env.d.ts`
  - Purpose: Next.js-generated TypeScript ambient declarations.
  - Imports: `./.next/dev/types/routes.d.ts`.
  - Exports or exposes: ambient type information for Next.js.
  - Non-obvious detail: the import from `.next/dev/types/routes.d.ts` is a Next.js 16 artifact and should not be hand-edited.

- `frontend/next.config.ts`
  - Purpose: Next.js configuration entry point.
  - Imports: `NextConfig` type from `next`.
  - Exports or exposes: default `nextConfig` object.
  - Non-obvious detail: currently minimal, so most behavior is framework default.

- `frontend/package.json`
  - Purpose: frontend package manifest.
  - Imports: none directly; npm uses it to resolve packages and scripts.
  - Exports or exposes: scripts (`dev`, `build`, `start`) and dependency declarations.
  - Non-obvious detail: uses Next.js `16.2.2`, React `19.2.4`, Recharts `3.8.1`, and `lucide-react` `1.7.0`.

- `frontend/package-lock.json`
  - Purpose: exact npm dependency lockfile.
  - Imports: used by npm.
  - Exports or exposes: locked dependency tree and resolved versions.
  - Non-obvious detail: critical for reproducible installs; the frontend runtime issue encountered during development was solved by deleting `node_modules` and reinstalling from this lockfile.

- `frontend/postcss.config.mjs`
  - Purpose: PostCSS configuration.
  - Imports: none.
  - Exports or exposes: default config enabling `@tailwindcss/postcss`.
  - Non-obvious detail: this replaces the separate Tailwind config pattern used in older Tailwind versions.

- `frontend/tsconfig.json`
  - Purpose: TypeScript compiler configuration.
  - Imports: none.
  - Exports or exposes: compiler settings and include/exclude patterns.
  - Non-obvious detail: defines the `@/*` path alias and includes `.next` dev-route types so route imports stay type-safe.

### Frontend App Router files

- `frontend/app/favicon.ico`
  - Purpose: browser favicon.
  - Imports: none.
  - Exports or exposes: icon asset for the app.
  - Non-obvious detail: retained from the Next.js scaffold.

- `frontend/app/globals.css`
  - Purpose: global CSS tokens and baseline styles.
  - Imports: Tailwind base/components/utilities directives.
  - Exports or exposes: CSS variables and document-level styling.
  - Non-obvious detail: the dashboard theme is driven by CSS custom properties rather than Tailwind utility classes.

- `frontend/app/layout.tsx`
  - Purpose: root layout for every route.
  - Imports: `Metadata` from `next`, `./globals.css`, `NavBar`, and `StaleBanner`.
  - Exports or exposes: `metadata` and `RootLayout`.
  - Non-obvious detail: the layout always mounts the stale-data banner above the navbar, so stale backend state is visible globally.

- `frontend/app/page.tsx`
  - Purpose: root route.
  - Imports: `redirect` from `next/navigation`.
  - Exports or exposes: default component that redirects to `/asset/AAPL`.
  - Non-obvious detail: no content is rendered directly on `/`; navigation always lands on the default asset.

- `frontend/app/asset/[ticker]/page.tsx`
  - Purpose: asset-detail page for Page 2.
  - Imports: API helpers, ticker list, and all asset page components.
  - Exports or exposes: `generateStaticParams()` and the default async page component.
  - Non-obvious detail: because this is Next.js 16, it awaits `params` and `searchParams` as promises; it also uses `Promise.allSettled` so failure in the pre-open fetch does not block the main page render.

- `frontend/app/heatmap/page.tsx`
  - Purpose: client entry point for the Page 3 heatmap.
  - Imports: React state/effect hooks, `fetchHeatmap`, `HeatmapEntry` type, and all heatmap components.
  - Exports or exposes: default client component.
  - Non-obvious detail: this page is client-rendered because the day-range filter changes purely on the client and does not need server routing.

### Frontend shared library files

- `frontend/lib/types.ts`
  - Purpose: shared TypeScript contracts for API responses and UI props.
  - Imports: none.
  - Exports or exposes: interfaces such as `HealthStatus`, `SignalToday`, `AssetDetail`, `HeatmapEntry`, and the `ALL_TICKERS` constant.
  - Non-obvious detail: the types closely mirror the API but do not perfectly capture every extra field the backend returns, such as `open_bet`, `high_bet`, and `low_bet` in `probability_series`.

- `frontend/lib/api.ts`
  - Purpose: typed fetch wrapper for the frontend.
  - Imports: shared types from `./types`.
  - Exports or exposes: `fetchHealth`, `fetchSignalsToday`, `fetchAsset`, `fetchAssetPreopen`, and `fetchHeatmap`.
  - Non-obvious detail: all fetches use `cache: 'no-store'` to prevent stale Next.js caching from freezing the dashboard.

### Frontend layout components

- `frontend/components/layout/NavBar.tsx`
  - Purpose: top navigation with the current asset dropdown and heatmap link.
  - Imports: `Link`, `usePathname`, `useRouter`, `ALL_TICKERS`, and `Ticker`.
  - Exports or exposes: default `NavBar` component.
  - Non-obvious detail: it uppercases the route segment and casts it to `Ticker` so the `<select>` value exactly matches the option values.

- `frontend/components/layout/StaleBanner.tsx`
  - Purpose: client banner warning when backend data is stale or missing.
  - Imports: `useEffect`, `useState`, and `fetchHealth`.
  - Exports or exposes: default `StaleBanner` component.
  - Non-obvious detail: it polls every 60 seconds and treats both `stale` and `no_data` as reasons to display the banner.

### Frontend asset-page components

- `frontend/components/asset/AssetDaySelector.tsx`
  - Purpose: client time-range selector for `1D`, `7D`, and `30D`.
  - Imports: `usePathname`, `useRouter`, and `useSearchParams`.
  - Exports or exposes: default `AssetDaySelector`.
  - Non-obvious detail: it pushes a new query string rather than mutating local page state, which preserves server-side data fetching for the asset page.

- `frontend/components/asset/AssetHeader.tsx`
  - Purpose: summary card for the asset page.
  - Imports: `Suspense` and `AssetDaySelector`.
  - Exports or exposes: default `AssetHeader`.
  - Non-obvious detail: it wraps `AssetDaySelector` in `Suspense` because the selector reads `useSearchParams()`.

- `frontend/components/asset/ProbabilityChart.tsx`
  - Purpose: combined probability-and-volume chart for Page 2.
  - Imports: Recharts `Area`, `Bar`, `CartesianGrid`, `ComposedChart`, `ReferenceLine`, `ResponsiveContainer`, `Tooltip`, `XAxis`, `YAxis`, plus `ProbabilityPoint`.
  - Exports or exposes: default `ProbabilityChart`.
  - Non-obvious detail: it merges `preopenData` and intraday `data`, converts timestamps to numeric milliseconds for a time axis, compresses the right-side volume axis to keep bars near the bottom, and fabricates fallback reference positions if a clean midnight or close marker is absent.

- `frontend/components/asset/StockChart.tsx`
  - Purpose: stock-price line chart for Page 2.
  - Imports: Recharts `CartesianGrid`, `Line`, `LineChart`, `ReferenceLine`, `ResponsiveContainer`, `Tooltip`, `XAxis`, `YAxis`, plus `StockPoint`.
  - Exports or exposes: default `StockChart`.
  - Non-obvious detail: the Y-axis domain is computed only from finite `close` values, which fixed the earlier distorted axis range issue.

- `frontend/components/asset/TrueSentimentChart.tsx`
  - Purpose: true-sentiment bar chart for Page 2.
  - Imports: Recharts `Bar`, `BarChart`, `CartesianGrid`, `Cell`, `ReferenceLine`, `ResponsiveContainer`, `Tooltip`, `XAxis`, `YAxis`, plus `SentimentPoint`.
  - Exports or exposes: default `TrueSentimentChart`.
  - Non-obvious detail: it filters out all-null sentiment rows before rendering and returns an empty-state card if nothing remains.

- `frontend/components/asset/SignalMetricsBlock.tsx`
  - Purpose: metrics and quality-score cards for the asset page.
  - Imports: `SignalToday` type.
  - Exports or exposes: default `SignalMetricsBlock`.
  - Non-obvious detail: it computes "conviction" from `true_sentiment` because the current `signals_today.csv` schema does not carry an explicit `abs_sentiment` field.

### Frontend heatmap components

- `frontend/components/heatmap/TimeFilterBar.tsx`
  - Purpose: client day-range buttons for the heatmap.
  - Imports: none.
  - Exports or exposes: default `TimeFilterBar`.
  - Non-obvious detail: the allowed UI ranges are `7`, `30`, and `60` days even though the API itself accepts any integer day count from `1` to `60`.

- `frontend/components/heatmap/QuadrantLegend.tsx`
  - Purpose: legend explaining the heatmap colors.
  - Imports: none.
  - Exports or exposes: default `QuadrantLegend`.
  - Non-obvious detail: uses hard-coded colors matching the backend quadrant logic.

- `frontend/components/heatmap/AlignmentGrid.tsx`
  - Purpose: clickable daily alignment table.
  - Imports: `useRouter` and `HeatmapEntry`.
  - Exports or exposes: default `AlignmentGrid`.
  - Non-obvious detail: uses a native HTML `<table>` rather than CSS grid so column alignment remains stable as the date count changes.

- `frontend/components/heatmap/AlignmentSummaryStats.tsx`
  - Purpose: client-side rollup statistics for the heatmap.
  - Imports: `HeatmapEntry`.
  - Exports or exposes: default `AlignmentSummaryStats`.
  - Non-obvious detail: calculates best and worst asset entirely on the client from the currently displayed heatmap data slice.

### Frontend static asset files

- `frontend/public/file.svg`
  - Purpose: default scaffold SVG asset.
  - Imports: none.
  - Exports or exposes: static icon.
  - Non-obvious detail: currently unused by the dashboard UI.

- `frontend/public/globe.svg`
  - Purpose: default scaffold SVG asset.
  - Imports: none.
  - Exports or exposes: static icon.
  - Non-obvious detail: currently unused.

- `frontend/public/next.svg`
  - Purpose: default Next.js logo asset.
  - Imports: none.
  - Exports or exposes: static logo.
  - Non-obvious detail: currently unused.

- `frontend/public/vercel.svg`
  - Purpose: default Vercel logo asset.
  - Imports: none.
  - Exports or exposes: static logo.
  - Non-obvious detail: currently unused.

- `frontend/public/window.svg`
  - Purpose: default scaffold SVG asset.
  - Imports: none.
  - Exports or exposes: static icon.
  - Non-obvious detail: currently unused.

### Generated Python cache files currently present in the workspace

- `backend/__pycache__/__init__.cpython-313.pyc`
  - Purpose: compiled bytecode cache for `backend/__init__.py`.
  - Imports: none.
  - Exports or exposes: none.
  - Non-obvious detail: safe to delete; recreated by Python automatically.

- `backend/__pycache__/config.cpython-313.pyc`
  - Purpose: compiled bytecode cache for `backend/config.py`.
  - Imports: none.
  - Exports or exposes: none.
  - Non-obvious detail: regenerated automatically.

- `backend/__pycache__/run_daily.cpython-313.pyc`
  - Purpose: compiled bytecode cache for `backend/run_daily.py`.
  - Imports: none.
  - Exports or exposes: none.
  - Non-obvious detail: regenerated automatically.

- `backend/__pycache__/test_imports.cpython-313.pyc`
  - Purpose: compiled bytecode cache for `backend/test_imports.py`.
  - Imports: none.
  - Exports or exposes: none.
  - Non-obvious detail: regenerated automatically.

- `backend/api/__pycache__/__init__.cpython-313.pyc`
  - Purpose: compiled bytecode cache for `backend/api/__init__.py`.
  - Imports: none.
  - Exports or exposes: none.
  - Non-obvious detail: regenerated automatically.

- `backend/api/__pycache__/server.cpython-313.pyc`
  - Purpose: compiled bytecode cache for `backend/api/server.py`.
  - Imports: none.
  - Exports or exposes: none.
  - Non-obvious detail: regenerated automatically.

- `backend/models/__pycache__/__init__.cpython-313.pyc`
  - Purpose: compiled bytecode cache for `backend/models/__init__.py`.
  - Imports: none.
  - Exports or exposes: none.
  - Non-obvious detail: regenerated automatically.

- `backend/models/__pycache__/backtest.cpython-313.pyc`
  - Purpose: compiled bytecode cache for `backend/models/backtest.py`.
  - Imports: none.
  - Exports or exposes: none.
  - Non-obvious detail: regenerated automatically.

- `backend/pipeline/__pycache__/__init__.cpython-313.pyc`
  - Purpose: compiled bytecode cache for `backend/pipeline/__init__.py`.
  - Imports: none.
  - Exports or exposes: none.
  - Non-obvious detail: regenerated automatically.

- `backend/pipeline/__pycache__/features.cpython-313.pyc`
  - Purpose: compiled bytecode cache for `backend/pipeline/features.py`.
  - Imports: none.
  - Exports or exposes: none.
  - Non-obvious detail: regenerated automatically.

- `backend/pipeline/__pycache__/orderbook.cpython-313.pyc`
  - Purpose: compiled bytecode cache for `backend/pipeline/orderbook.py`.
  - Imports: none.
  - Exports or exposes: none.
  - Non-obvious detail: regenerated automatically.

## 2. `config.py` Complete Reference

Every constant in `backend/config.py` is listed below with its current value and effect.

| Name | Type | Value | What it controls | What breaks or changes if you change it |
| --- | --- | --- | --- | --- |
| `BASE_DIR` | `Path` | `Path(__file__).parent` | Backend root path resolution. | All relative data/log paths shift with it. |
| `DATA_DIR` | `Path` | `BASE_DIR / "data"` | Where CSV/JSON output files are written. | API and pipeline file IO fail if this no longer matches the actual data directory. |
| `LOG_DIR` | `Path` | `BASE_DIR / "logs"` | Where pipeline log files are written. | Logging file handler fails or writes to the wrong location. |
| `ASSETS` | `list[tuple[str, str]]` | `[("nflx","new york"), ("tsla","new york"), ("aapl","new york"), ("nvda","new york"), ("googl","new york"), ("meta","new york"), ("msft","new york"), ("amzn","new york")]` | Universe of tracked assets and their market time zones. | The pipeline loops over this list; changing it changes everything from ingestion to UI availability. |
| `TICKER_MAP` | `dict[str, str]` | maps lowercase slugs to Yahoo Finance tickers | Symbol translation for stock pulls. | Stock-data merge fails for any slug not mapped correctly. |
| `DAYS_BACK` | `int` | `60` | Historical lookback window for Polymarket market discovery. | Fewer days reduce sample depth; more days increase API cost and runtime. |
| `INTRADAY_WINDOW_MINUTES` | `int` | `5` | Window size for stock pull tolerance and feature aggregation. | Panel resolution changes, volatility window changes, UI density changes, and some helper logic assumptions shift. |
| `MAX_WORKERS` | `int` | `10` | Number of concurrent Goldsky fetch workers. | Too low makes the pipeline slower; too high increases risk of rate limits and timeouts. |
| `START_DAY_FROM_NOW` | `int` | `0` | How many days back from "today" the pull starts. | Useful for replaying past dates; incorrect values can skip current-day markets. |
| `LIQUIDITY_THRESHOLD` | `int` | `500` | Threshold for high-liquidity classification and heatmap gray/yellow logic. | Signal-quality scoring, heatmap quadrants, and metrics badges change. |
| `FIREWALL_HOUR_NY` | `int` | `9` | New York hour for pre-open cutoff. | Pre-open signal scope changes. |
| `FIREWALL_MINUTE_NY` | `int` | `30` | New York minute for pre-open cutoff. | Same as above; this is what makes the firewall `09:30`. |
| `RISK_FREE_ANN` | `float` | `0.04` | Annual risk-free rate used in the Black-Scholes benchmark and backtests. | `bs_neutral_prob`, `true_sentiment`, and some backtest carrying-cost calculations move. |
| `SQ_VOLUME_HIGH` | `int` | `500` | Threshold for the top volume score bucket in `_compute_signal_quality()`. | Signal quality scores shift upward or downward for liquid observations. |
| `SQ_VOLUME_MED` | `int` | `100` | Threshold for the middle volume score bucket in `_compute_signal_quality()`. | Low-to-medium quality scoring changes. |
| `SQ_SPREAD_TIGHT` | `float` | `0.01` | Reserved placeholder for future spread-based scoring. | Currently nothing breaks because the value is unused. |
| `SQ_SPREAD_MED` | `float` | `0.03` | Reserved placeholder for future spread-based scoring. | Currently unused. |
| `HEATMAP_MIN_MOVE` | `float` | `0.005` | Minimum absolute stock move to count as directional in the heatmap. | Heatmap color mix changes; higher values make more gray cells. |
| `GAMMA_API` | `str` | `https://gamma-api.polymarket.com/events/slug` | Base URL for Polymarket event metadata by slug. | Raw market-token discovery fails if this is wrong or deprecated. |
| `GOLDSKY_URL` | `str` | Goldsky public GraphQL endpoint | Endpoint for order-filled-event history. | Raw orderbook ingestion fails if wrong. |
| `TIMEZONE_MAP` | `dict[str, str]` | maps `"new york"`, `"london"`, `"tokyo"`, `"europe"` to IANA names | Time-zone conversion for market-date logic and firewall filtering. | Market-date assignments and expiry-hour calculations become wrong. |

## 3. `pipeline/orderbook.py` Complete Reference

`backend/pipeline/orderbook.py` houses the `Orderbook` class, which is responsible for discovering Polymarket daily markets, reconstructing raw trade history from Goldsky, and attaching stock data from Yahoo Finance.

### Class: `Orderbook`

#### Constructor

```python
Orderbook(
    days_back=DAYS_BACK,
    max_workers=MAX_WORKERS,
    start_day_from_now=START_DAY_FROM_NOW,
    intraday_minutes=INTRADAY_WINDOW_MINUTES,
)
```

Parameters:

- `days_back: int`
  - Valid range: positive integer.
  - Meaning: how many calendar days of Polymarket daily markets to look back when discovering slugs.

- `max_workers: int`
  - Valid range: integer `>= 1`.
  - Meaning: concurrency level for Goldsky chunk fetches.

- `start_day_from_now: int`
  - Valid range: integer `>= 0`.
  - Meaning: offset from "today" when constructing daily market slugs.

- `intraday_minutes: int`
  - Valid range: positive divisor-like value that Yahoo Finance supports as an interval, currently `5`.
  - Meaning: stock-bar interval and merge tolerance.

Internal state initialized:

- `self.days_back`
- `self.start_day_from_now`
- `self.intraday_minutes`
- `self.max_workers`
- `self.gamma_api`
- `self.goldsky_url`
- `self.timezone_map`
- `self.asset_keys`
- `self.df`
- `self.orderbook`

#### `fetch_raw_orderbook(keys)`

Signature:

```python
fetch_raw_orderbook(self, keys) -> pd.DataFrame
```

Expected input:

- `keys`: typically a list of tuples like `[("aapl", "new york")]` or a broader list across assets.

What it does:

1. Resets `self.df` and `self.orderbook` to empty DataFrames.
2. Calls `_get_multiple_tokens(keys)` to discover Polymarket token IDs for the requested asset/day combinations.
3. Calls `_process_all_orderfills()` to query Goldsky and assemble the raw trade history.
4. If rows exist, normalizes `TIMESTAMP` to timezone-aware UTC pandas timestamps.
5. Sorts by `KEY` and `TIMESTAMP` ascending.
6. Returns a copy of the raw orderbook.

Return value:

- A pandas DataFrame representing raw orderbook fills, including columns such as `KEY`, `REL_HOUR`, `TIME_TO_EXP`, `UP_DOWN`, `TIMESTAMP`, `MAKER`, `TAKER`, `SHARES`, `USDC`, `PRICE`, `PRICE_UP`, `BUY_SELL`, `id`, `log_odds`, and `country`.

Edge cases:

- If no markets are discovered or no fills are returned, the method returns an empty DataFrame.
- The explicit state reset is crucial because `run_daily.py` calls this method once per asset; without the reset, later iterations would accumulate earlier assets' rows.

#### `attach_stock_data(orderbook=None)`

Signature:

```python
attach_stock_data(self, orderbook=None) -> pd.DataFrame
```

Parameters:

- `orderbook: pd.DataFrame | None`
  - Optional raw orderbook input. If supplied, it replaces the class's internal `self.orderbook` before merging stock data.

What it does step by step:

1. If `orderbook` is provided, copies it into `self.orderbook`.
2. If there are no rows, returns an empty copy immediately.
3. Defines `get_outcome_date(row)` to compute the daily market's "market date."
4. Converts each trade timestamp into the asset's local timezone.
5. Assigns a `market_date` equal to the local calendar date, except for overnight trades with `0 <= REL_HOUR < 8`, which are pushed to the next day.
6. Calls `_pull_stock_close()` to fetch daily open and close values for valid dates.
7. Merges the daily stock open/close fields into the raw orderbook.
8. Converts `TIMESTAMP` to UTC pandas timestamps and sorts.
9. Calls `_pull_stock_minutes()` to fetch 5-minute stock bars and volatility.
10. If minute bars exist, performs `pd.merge_asof(...)` on `TIMESTAMP` and `KEY` with `direction="backward"` and `tolerance=5 minutes`.
11. If minute bars do not exist, creates NaN columns for the expected stock-minute fields.
12. Drops temporary `date` and `market_date` columns and returns a sorted copy.

What `merge_asof(..., direction="backward", tolerance=pd.Timedelta("5min"))` means:

- For each Polymarket trade row, pandas finds the latest stock bar for the same `KEY` whose timestamp is less than or equal to the trade timestamp and no more than 5 minutes earlier.
- This is a conservative join. It prevents future stock information from leaking into the trade row and avoids matching trades to very stale bars.

Edge cases:

- If Yahoo minute data is unavailable, the returned DataFrame still exists but stock-minute columns are NaN, which later causes those rows to be dropped from the intraday panel.

#### `get_data(keys)`

Signature:

```python
get_data(self, keys) -> pd.DataFrame
```

What it does:

1. Calls `fetch_raw_orderbook(keys)`.
2. Passes the result into `attach_stock_data(raw_orderbook)`.
3. Returns the enriched DataFrame.

This is a convenience method. The production pipeline no longer relies on it directly because it needs the raw-orderbook and pre-open path separated from the stock-enriched path.

#### `save_raw(path: Path)`

Signature:

```python
save_raw(self, path: Path) -> None
```

What it does:

1. Copies `self.orderbook`.
2. Removes timezone info from any timezone-aware datetime columns.
3. Writes the CSV to the requested path.

Why it exists:

- CSVs are easier to work with in downstream tools when timezone suffixes have been normalized away.

#### `_get_market_tokens(key_tuple)`

Signature:

```python
_get_market_tokens(self, key_tuple) -> pd.DataFrame
```

Expected input:

- A tuple `(slug_prefix, country)` such as `("aapl", "new york")`.

What it does:

1. Converts the human-readable market region to an IANA timezone through `TIMEZONE_MAP`.
2. Computes the local current time minus any configured `start_day_from_now` offset.
3. Loops backward for `days_back` days.
4. For each target day, builds a Polymarket slug of the form:

```text
{key}-up-or-down-on-{month-day-year}
```

5. Calls the Gamma API endpoint `/events/slug/{slug}`.
6. If the response contains markets, extracts:
   - `conditionId`
   - the two token IDs from `clobTokenIds`
7. Returns a DataFrame with columns:
   - `key`
   - `ts`
   - `up_token`
   - `down_token`
   - `condition_id`
   - `country`

Edge cases:

- If a daily market does not exist or the request fails, the loop simply skips that day.

#### `_get_multiple_tokens(keys)`

Signature:

```python
_get_multiple_tokens(self, keys) -> pd.DataFrame
```

What it does:

1. Iterates through all requested keys.
2. Appends uppercase asset names to `self.asset_keys`.
3. Calls `_get_market_tokens(...)` for each asset.
4. Concatenates the results into `self.df`.
5. Sorts by `ts` and `key`.

Return value:

- Combined token-discovery DataFrame, also stored as `self.df`.

#### `_get_single_orderfills(asset_id, start_dt, end_dt, up_down_key)`

Signature:

```python
_get_single_orderfills(self, asset_id, start_dt, end_dt, up_down_key) -> pd.DataFrame
```

Parameters:

- `asset_id: str`
  - Token ID for either the YES or NO side.
- `start_dt: datetime`
  - Inclusive lower time boundary.
- `end_dt: datetime`
  - Inclusive upper time boundary.
- `up_down_key: str`
  - Either `"UP"` or `"DOWN"` to tell the method whether the token corresponds to the YES or NO side of the binary market.

Goldsky GraphQL query structure:

The query requests `orderFilledEvents` where either:

- the token is the taker asset and USDC (`"0"`) is the maker asset, or
- the token is the maker asset and USDC is the taker asset.

Requested fields:

- `id`: unique fill identifier used later for deduplication
- `timestamp`: event time in seconds since epoch
- `maker`, `taker`: wallet or actor identifiers
- `takerAssetId`, `makerAssetId`: asset IDs, used to infer whether the trade bought or sold shares
- `makerAmountFilled`, `takerAmountFilled`: filled amounts, used to reconstruct price and size

What it does after the query:

1. Converts timestamps to integers.
2. Posts the query to Goldsky with a 15-second timeout.
3. If the response is missing data or contains no events, returns an empty DataFrame.
4. For each fill:
   - Determines whether the action is effectively `BUY` or `SELL`.
   - Converts maker/taker amounts from six-decimal token units to float units.
   - Computes `PRICE` as USDC per share or its reciprocal depending on side.
   - Converts that into `PRICE_UP`, which always represents the implied probability of the UP outcome, even for the DOWN token.
   - Computes `log_odds = log(price / (1-price))` where valid.
5. Returns a normalized DataFrame.

Edge cases:

- Any exception returns an empty DataFrame rather than crashing the entire batch.
- Prices of exactly `0` or `1` get `log_odds = NaN`.

#### `_process_all_orderfills()`

Signature:

```python
_process_all_orderfills(self) -> pd.DataFrame
```

What it does:

1. Initializes an empty `tasks` list.
2. Computes `now_utc` as the current UTC time minus any configured day offset.
3. Loops through every token-discovery row in `self.df`.
4. For each daily market:
   - Determines the local midnight for the target market date.
   - Subtracts 8 hours to get the prior local close anchor.
   - Converts that anchor to UTC as `market_start_utc`.
5. Breaks the next 24 hours into chunks of `0.2` hours, which is 12 minutes.
6. Creates one task per chunk per token side.
7. Runs those tasks through a `ThreadPoolExecutor(max_workers=self.max_workers)`.
8. In each worker:
   - Calls `_get_single_orderfills(...)`.
   - Sleeps for `0.1` seconds after each request.
   - Adds `KEY` and `country` columns if rows exist.
9. Filters out empty results.
10. Concatenates results.
11. Drops duplicate `id` values.
12. Computes `REL_HOUR` and `TIME_TO_EXP`.
13. Reorders columns and saves the result to `self.orderbook`.

Why the 12-minute chunk strategy exists:

- Goldsky queries can return many fills, and the original notebook comments note the need to stay under roughly a 1000-order practical limit per call.
- Smaller time chunks reduce the risk of response truncation and make retries or failures less catastrophic.

Why the `time.sleep(0.1)` exists:

- It is a crude rate-limit mitigation tactic.
- It makes the full 60-day pipeline slower, but it materially lowers the chance of hammering the endpoint with concurrent requests too aggressively.

`REL_HOUR` computation:

```python
(local_time.hour + local_time.minute / 60 + local_time.second / 3600 + 8) % 24
```

Interpretation:

- The project defines "relative hour" as the number of hours since the previous local close anchor, shifted so that the daily market timeline runs cleanly across the overnight period.
- Adding 8 and then taking modulo 24 effectively treats the prior close as the origin for the next day's contract lifecycle.

`TIME_TO_EXP`:

```python
24.0 - REL_HOUR
```

Interpretation:

- Remaining contract life, in hours, within the project's daily-market clock.

#### `_pull_stock_close()`

Signature:

```python
_pull_stock_close(self) -> pd.DataFrame
```

What it does:

1. Determines the set of `KEY` values present in the orderbook.
2. Determines the min and max timestamps present.
3. Calls `yf.download(...)` for daily data with `auto_adjust=True`.
4. Retains `Open` and `Close`.
5. Stacks multi-ticker data into long format.
6. Renames columns to:
   - `date`
   - `KEY`
   - `close`
   - `open`
7. Computes a `stock_up` label:
   - `1` if `close > open`
   - `0` if `close < open`
   - `0.5` otherwise
8. Renames:
   - `open -> stock_open_day`
   - `close -> stock_close_day`
9. Filters to only the dates actually needed by the orderbook.

Return value:

- DataFrame with columns `KEY`, `date`, `stock_open_day`, `stock_close_day`.

#### `_pull_stock_minutes(minutes=5, window_size=5)`

Signature:

```python
_pull_stock_minutes(self, minutes=5, window_size=5) -> pd.DataFrame
```

Parameters:

- `minutes: int`
  - Stock bar interval; currently `5`.
- `window_size: int`
  - Number of bars in the rolling volatility estimate. In production it is called as `120 // intraday_minutes`, which equals `24` for 5-minute bars and therefore represents roughly two hours of recent returns.

What it does:

1. Determines the tickers and overall orderbook time range.
2. Sets a `cutoff` of `now - 59 days` because Yahoo intraday history is limited.
3. Uses `fetch_start = max(start, cutoff)` to respect the Yahoo limit.
4. Fetches `High`, `Low`, `Close`, `Open`, and `Volume` from Yahoo Finance at the requested interval.
5. Normalizes both multi-ticker and single-ticker download shapes into a long DataFrame.
6. Creates:
   - `stock_close_5m`
   - `stock_high_5m`
   - `stock_low_5m`
   - `stock_open_5m`
   - `stock_volume_5m`
7. Computes `stock_avg_5m` as the average of high, low, and close.
8. Normalizes timestamps to UTC.
9. Computes log returns by ticker.
10. Annualizes rolling volatility:

```python
ann_factor = sqrt((60 / minutes * 6.5) * 252)
stock_vol_5m = rolling_std(returns, window=window_size) * ann_factor
```

Why that annualization factor:

- `60 / minutes * 6.5` = number of bars per trading day
- `252` = trading days per year
- square root because standard deviation scales with the square root of time

Return value:

- Long DataFrame of stock-minute bars and derived rolling volatility.

## 4. `pipeline/features.py` Complete Reference

### `collapse_to_windows(df, minutes=INTRADAY_WINDOW_MINUTES, risk_free_ann=RISK_FREE_ANN)`

Purpose:

- Collapse the stock-enriched orderbook into regular time windows and compute the model-based benchmark needed for `true_sentiment`.

Aggregation inputs:

- `TIME_TO_EXP -> last`
- `PRICE_UP -> first, last, mean, max, min`
- `USDC -> sum`
- `SHARES -> count`
- `vol_bull -> sum`
- `vol_bear -> sum`
- `stock_open_day -> last`
- `stock_close_5m -> last`
- `stock_avg_5m -> mean`
- `stock_vol_5m -> last`

Derived output columns:

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

How `vol_bull` and `vol_bear` are defined:

- `vol_bull` counts USDC associated with economically bullish activity.
- `vol_bear` counts USDC associated with economically bearish activity.
- The rules are side-aware so buying the DOWN token is counted as bearish, while selling it is counted as bullish.

Why `S = stock_close` and `K = stock_open_day`:

- The binary contract resolves true if the stock finishes above its opening level.
- The live stock price inside the window is therefore the natural spot price `S`.
- The day's open is the threshold the stock must beat by the close, so it serves as strike `K`.

Black-Scholes-style benchmark inside the function:

```python
stock_price = collapsed["stock_close"]
strike = collapsed["stock_open_day"]
sigma = collapsed["stock_vol"]
time_to_expiry = ((collapsed["time_to_exp"] / 24) / 252).clip(lower=1e-9)
d2 = (log(S/K) + (r - 0.5*sigma**2) * T) / (sigma * sqrt(T))
bs_neutral_prob = norm.cdf(d2.fillna(0))
true_sentiment = avg_price_up - bs_neutral_prob
```

Why `dropna()` removes pre-market rows:

- The function requires `avg_price_up`, `stock_open_day`, `stock_close`, and `stock_vol`.
- Before the cash market opens, the enriched orderbook generally lacks `stock_close` and `stock_vol`.
- Those rows are therefore dropped.

What was done to address that problem:

- The project no longer tries to build `signals_today.csv` from this panel.
- Instead it introduced `build_preopen_panel()` to operate directly on raw orderbook data before stock data is required.

### `check_lead_lag(df)`

Purpose:

- Add forward-looking diagnostics to the intraday panel and print directional correlation statistics.

Derived columns:

- `next_stock_move`
  - Formula:
    ```python
    log(next stock_close / current stock_close)
    ```
  - Interpretation: log return of the next window's stock close relative to the current window.

- `curr_stock_move`
  - Formula:
    ```python
    log(current stock_close / previous stock_close)
    ```
  - Interpretation: most recent realized stock move into the current window.

- `next_true_sent`
  - Formula:
    ```python
    next true_sentiment - current true_sentiment
    ```
  - Interpretation: change in conviction in the next window.

- `abs_sentiment`
  - Formula:
    ```python
    abs(true_sentiment)
    ```
  - Interpretation: signal magnitude or conviction irrespective of direction.

Why the `time_to_exp > 0.5` filter exists:

- The function computes diagnostic correlations on a subset called `valid`.
- Restricting to `time_to_exp > 0.5` removes windows extremely close to expiry where contract dynamics can collapse mechanically and obscure the more informative part of the relationship.
- The full DataFrame is still returned; the filter is used only for the printed diagnostics.

Printed diagnostics:

- overall lead correlation
- per-asset lead correlation
- overall lag correlation
- per-asset lag correlation

### `build_preopen_panel(orderbook: pd.DataFrame, target_date=None)`

Purpose:

- Compute the daily signal snapshot directly from raw Polymarket trades without any stock dependency.

Why it differs from `collapse_to_windows()`:

- `collapse_to_windows()` needs stock open, stock close, and rolling volatility.
- `build_preopen_panel()` only needs raw Polymarket `TIMESTAMP`, `PRICE_UP`, `USDC`, `BUY_SELL`, and `UP_DOWN`.
- That makes it safe to run before market open and safe to write even if stock attachment fails later.

How it works:

1. If `target_date` is not provided, chooses "today" in New York time.
2. Computes:
   - New York midnight in UTC
   - New York `09:30` firewall in UTC
3. Converts orderbook timestamps to UTC-aware pandas timestamps.
4. Filters rows to midnight <= timestamp < firewall.
5. Creates `vol_bull` using the same bullish-volume logic as the intraday panel.
6. Groups by `KEY`.
7. For each ticker, computes:
   - `pre_open_implied_prob = last PRICE_UP`
   - `midnight_prob = first PRICE_UP`
   - `overnight_prob_change = last - first`
   - `pre_open_pm_volume = sum(USDC)`
   - `pre_open_buy_ratio = bull_volume / total_volume`
   - `is_high_liquidity = pre_open_pm_volume >= LIQUIDITY_THRESHOLD`
   - `signal_direction = "UP"` if `overnight_prob_change >= 0` else `"DOWN"`
   - `signal_quality_score = _compute_signal_quality(volume, abs(overnight_prob_change))`
   - `true_sentiment = None`

Why `true_sentiment` is null here:

- True sentiment requires the Black-Scholes benchmark.
- The Black-Scholes benchmark requires stock close and volatility.
- Those values do not exist reliably in the pre-open raw-only stage.

### `_compute_signal_quality(volume: float, conviction_proxy: float)`

Purpose:

- Assign a simple 0-to-10 score using only pre-open fields available before stock attachment.

Scoring formula:

- Baseline:
  - always starts at `2.0`
- Volume:
  - `+4` if `volume >= 500`
  - `+2` if `volume >= 100`
  - `+0` otherwise
- Conviction proxy:
  - `+4` if `conviction_proxy >= 0.05`
  - `+2` if `conviction_proxy >= 0.02`
  - `+0` otherwise

Maximum score:

- `10.0`

How to reach it:

- High volume (`>= 500`) and strong conviction proxy (`>= 0.05`) on top of the baseline.

Reserved future logic:

- `SQ_SPREAD_TIGHT` and `SQ_SPREAD_MED` are imported and assigned to `_` so the function is ready for future spread-based scoring once depth data is added.

### `analyse_sentiment_dynamics(df)`

Purpose:

- Research-only diagnostic function not used by the dashboard.

What it produces:

- hit-rate tables by conviction percentile
- per-asset OLS regressions of next stock move on sentiment and control features
- per-asset logistic regressions for direction
- hourly hit-rate summary

Why HAC standard errors are used:

- Time-series residuals can be heteroskedastic and autocorrelated.
- The function fits OLS with `cov_type="HAC"` so inference is more robust than plain OLS standard errors.

Why `maxlags = int(len(X) ** (1 / 3))`:

- This follows the Luetkepohl `n^(1/3)` rule of thumb for choosing a reasonable lag length in time-series covariance estimation.

## 5. `run_daily.py` Complete Reference

### Exact execution sequence

The live execution order is:

1. `setup_logging()`
2. create `Orderbook(...)`
3. `step1_fetch_raw(ob)`
4. `step2_build_and_save_signals(raw, dry_run)`
5. `save_raw_orderbook(raw, dry_run)`
6. `step3_attach_stock(ob, raw)`
7. `step4_build_and_save_panel(enriched, dry_run)` if stock attachment succeeded
8. `step5_save_metadata(...)`

Why this order matters:

- `signals_today.csv` must exist even if stock attachment fails.
- `orderbook_latest.csv` must be saved before the API can serve the overnight probability segment.
- `last_run.json` should still be written even if the panel step fails, because the frontend needs a truthful health state.

### `setup_logging(run_date: str)`

Behavior:

- ensures `LOG_DIR` exists
- writes logs to `backend/logs/pipeline_{YYYY-MM-DD}.log`
- streams logs to stdout
- calls `logging.basicConfig(..., force=True)`

Why `force=True` matters:

- Without it, rerunning the script in the same Python process can silently leave the old logging configuration in place.
- That is common during notebook or IDE-driven development.

### `step1_fetch_raw(ob: Orderbook)`

Behavior:

- Loops through `ASSETS` one asset at a time.
- Calls `ob.fetch_raw_orderbook([asset])` with a single-item list.
- Appends successful DataFrames to a list and records failures separately.

Why per-asset isolation exists:

- If one asset fails because a market is missing or a network call breaks, the rest of the assets still complete.
- This is the reason `fetch_raw_orderbook()` had to reset internal state on every call.

Failure behavior:

- If a single asset fails, it is appended to `assets_failed` and the loop continues.
- If all assets fail, the function raises `RuntimeError("all assets failed in step1 - aborting")`.

### `step2_build_and_save_signals(raw, dry_run)`

Behavior:

- Calls `build_preopen_panel(raw)`.
- Logs whether the result is empty.
- Writes `backend/data/signals_today.csv` unless `dry_run` is true.

Why it happens before stock attachment:

- The pre-open signal is meaningful on its own.
- This guarantees the dashboard can still show the signal metrics even if the stock-data phase fails later.

### `save_raw_orderbook(raw, dry_run)`

Behavior:

- Copies the raw orderbook.
- Removes timezone info from timezone-aware datetime columns.
- Writes `backend/data/orderbook_latest.csv`.

Why it exists:

- The asset probability chart now prepends the overnight path from this file via `/api/asset/{ticker}/preopen`.

### `step3_attach_stock(ob, raw)`

Behavior:

- Calls `ob.attach_stock_data(raw)`.
- Logs the number of enriched rows.

Failure behavior:

- Any exception is caught in `run()`, logged, and results in `panel_15m.csv` not being updated for that run.

### `step4_build_and_save_panel(enriched, dry_run)`

Behavior:

- Calls `collapse_to_windows(enriched, minutes=INTRADAY_WINDOW_MINUTES)`.
- Calls `check_lead_lag(panel)`.
- Strips timezone info from datetime columns.
- Writes `backend/data/panel_15m.csv` unless `dry_run` is true.

Why it happens after stock attachment:

- The panel requires `stock_open_day`, `stock_close`, and `stock_vol`, all of which come from Yahoo Finance.

### `step5_save_metadata(...)`

Behavior:

- Constructs:
  - `timestamp`
  - `date`
  - `assets_ok`
  - `assets_failed`
  - `panel_rows`
  - `signals_rows`
- Writes `backend/data/last_run.json` unless `dry_run` is true.

### `--dry-run` flag behavior

What it does:

- Executes all fetch and transform logic.
- Skips writing:
  - `signals_today.csv`
  - `orderbook_latest.csv`
  - `panel_15m.csv`
  - `last_run.json`

What it does not do:

- It does not disable network calls.
- It does not bypass expensive computation.

### Files written by the live run

- `backend/data/signals_today.csv`
- `backend/data/orderbook_latest.csv`
- `backend/data/panel_15m.csv`
- `backend/data/last_run.json`
- `backend/logs/pipeline_{run_date}.log`

## 6. `api/server.py` Complete Reference

### Helpers

#### `load_csv(filename: str) -> pd.DataFrame`

Behavior:

- Reads `DATA_DIR / filename`.
- If the file does not exist, raises:

```json
{
  "detail": "<filename> not found - pipeline may not have run yet"
}
```

with HTTP status `503`.

Why this matters:

- The frontend gets a meaningful service-state response instead of a Python traceback.

#### `nan_safe(val)`

Behavior:

- Converts:
  - NumPy booleans to plain `bool`
  - NumPy integers to plain `int`
  - NumPy floats to plain `float`
  - `NaN` and `inf` to `None`
  - pandas missing values to `None`

Why it is necessary:

- pandas and NumPy often carry NaN-like values and specialized scalar types that do not serialize cleanly to JSON.

#### `parse_timestamps(df: pd.DataFrame) -> pd.Series`

Behavior:

- Parses `TIMESTAMP`.
- Localizes to UTC if naive.
- Converts to UTC if already timezone-aware.

#### `with_market_dates(df: pd.DataFrame) -> pd.DataFrame`

Behavior:

- Adds a `market_date` column derived from `TIMESTAMP` converted to `America/New_York`.

#### `filter_last_market_days(df: pd.DataFrame, days: int) -> pd.DataFrame`

Behavior:

- Uses unique New York `market_date` values rather than simple rolling 24-hour windows.
- Keeps the most recent `days` market dates.

Why that is better than subtracting timedeltas:

- It preserves complete market days even when there are overnight/pre-open rows and timezone conversions.

#### `serialize_signal_row(row: pd.Series) -> dict`

Behavior:

- Converts a signal row from `signals_today.csv` into the exact JSON shape used by `/api/signals/today` and `latest_signal`.

### CORS configuration

Current setting:

```python
allow_origins=["http://localhost:3000"]
```

Why:

- The frontend dev server runs on port `3000`.
- Restricting origins is safer than allowing all origins by default.

Current limitation:

- This is hardcoded and will need environment-variable control for deployment.

### Endpoint: `GET /health`

Files read:

- `backend/data/last_run.json`

Query parameters:

- none

Success response shape:

```json
{
  "status": "ok" | "stale" | "no_data",
  "timestamp": "2026-04-03T09:02:00Z" | null,
  "date": "2026-04-03" | null,
  "hours_ago": 1.2 | null,
  "assets_ok": ["AAPL", "..."],
  "assets_failed": [],
  "panel_rows": 1896,
  "signals_rows": 8
}
```

Status logic:

- `no_data` if `last_run.json` does not exist
- `stale` if `hours_ago > 26`
- `ok` otherwise

Status code:

- always `200` for these three states

### Endpoint: `GET /api/signals/today`

Files read:

- `backend/data/signals_today.csv`

Query parameters:

- none

Response shape:

```json
{
  "data": [
    {
      "ticker": "AAPL",
      "date": "2026-04-03",
      "pre_open_implied_prob": 0.58,
      "overnight_prob_change": 0.041,
      "pre_open_pm_volume": 720.0,
      "pre_open_buy_ratio": 0.62,
      "is_high_liquidity": true,
      "signal_direction": "UP",
      "signal_quality_score": 8.0,
      "true_sentiment": null
    }
  ],
  "count": 8
}
```

Error behavior:

- returns `503` if the CSV is missing

### Endpoint: `GET /api/asset/{ticker}/preopen`

Files read:

- `backend/data/orderbook_latest.csv`

Path parameter:

- `ticker: str`
  - uppercased inside the handler

Query parameters:

- none

Behavior:

1. Reads the raw orderbook export.
2. Filters rows by `KEY == ticker`.
3. Parses timestamps as UTC.
4. Converts them to New York time.
5. Filters to the current New York date and times before `09:30`.
6. Resamples to 5-minute buckets:
   - probability = `last PRICE_UP`
   - volume = `sum USDC`

Response shape:

```json
{
  "ticker": "MSFT",
  "preopen_series": [
    {
      "timestamp": "2026-04-03T08:00:00+00:00",
      "price_up": 0.527,
      "volume": 40.0
    }
  ]
}
```

Empty response behavior:

- If the file is empty, the ticker has no rows, or no current-date pre-open rows exist, returns:

```json
{
  "ticker": "MSFT",
  "preopen_series": []
}
```

Non-obvious caveat:

- This endpoint keys off the **current New York date**, not `last_run.json`, so stale mock data will eventually stop producing a pre-open series when the calendar advances.

### Endpoint: `GET /api/asset/{ticker}`

Files read:

- `backend/data/panel_15m.csv`
- `backend/data/signals_today.csv` when available

Path parameter:

- `ticker: str`

Query parameters:

- `days: int = 1`
  - valid range `1 <= days <= 60`

Behavior:

1. Reads the panel.
2. Filters by `KEY == ticker.upper()`.
3. Raises `404` if no panel rows exist for that ticker.
4. Uses `filter_last_market_days(asset_panel, days)` to keep the most recent market dates.
5. Sorts by `TIMESTAMP`.
6. Builds:
   - `probability_series`
   - `stock_series`
   - `true_sentiment_series`
7. Attempts to load a matching `latest_signal` from `signals_today.csv`.

Response shape:

```json
{
  "ticker": "AAPL",
  "days": 3,
  "row_count": 237,
  "latest_signal": {
    "ticker": "AAPL",
    "date": "2026-04-03",
    "pre_open_implied_prob": 0.58,
    "overnight_prob_change": 0.041,
    "pre_open_pm_volume": 720.0,
    "pre_open_buy_ratio": 0.62,
    "is_high_liquidity": true,
    "signal_direction": "UP",
    "signal_quality_score": 8.0,
    "true_sentiment": null
  },
  "probability_series": [
    {
      "timestamp": "2026-04-03T13:30:00+00:00",
      "price_up": 0.4385,
      "volume": 303.85,
      "open_bet": 0.4325,
      "high_bet": 0.4432,
      "low_bet": 0.4286
    }
  ],
  "stock_series": [
    {
      "timestamp": "2026-04-03T13:30:00+00:00",
      "close": 194.27
    }
  ],
  "true_sentiment_series": [
    {
      "timestamp": "2026-04-03T13:30:00+00:00",
      "true_sentiment": 0.0261,
      "abs_sentiment": 0.0261,
      "bs_neutral_prob": 0.4128
    }
  ]
}
```

Error behavior:

- `404` if the ticker is absent from `panel_15m.csv`
- `503` if `panel_15m.csv` is missing

Non-obvious detail:

- When no matching signal row exists, the backend currently returns `{}` for `latest_signal`, not `null`. The frontend uses optional chaining, so this does not break rendering, but it is slightly looser than the TypeScript contract.

### Endpoint: `GET /api/heatmap`

Files read:

- `backend/data/panel_15m.csv`

Query parameters:

- `days: int = 30`
  - valid range `1 <= days <= 60`

Behavior:

1. Reads the panel.
2. Filters it to the most recent market dates through `filter_last_market_days`.
3. Groups by `(KEY, market_date)`.
4. For each group with at least two rows:
   - `prob_change = last close_bet - first open_bet`
   - `prob_direction = 1 if prob_change > 0 else -1`
   - `price_move = (last stock_close - first stock_close) / first stock_close`
   - `price_direction = 1 if price_move > 0 else -1`
   - `volume = sum(total_volume)`
5. Applies quadrant rules:
   - `gray` if `volume < 500` or `abs(price_move) < 0.5%`
   - `green` if probability and price are both up
   - `red` if probability and price are both down
   - `yellow` otherwise

Response shape:

```json
{
  "days": 30,
  "count": 24,
  "data": [
    {
      "ticker": "AAPL",
      "date": "2026-04-03",
      "prob_direction": 1,
      "price_direction": -1,
      "prob_change": 0.0142,
      "price_move": -0.0031,
      "volume": 6281.42,
      "quadrant": "yellow"
    }
  ]
}
```

## 7. Frontend Architecture

### Why Next.js App Router was chosen

The frontend uses Next.js App Router because it gives a clean split between server-rendered route files and client-rendered interaction components. That is a good fit for this project because the asset page benefits from server-side data fetching, while the heatmap filter and stale banner are better expressed as small client components.

### Server vs client component split

Server components:

- `frontend/app/layout.tsx`
- `frontend/app/page.tsx`
- `frontend/app/asset/[ticker]/page.tsx`

Why:

- layout and root redirect are naturally server-side
- the asset page fetches data on the server and renders a deterministic initial view for a given ticker and `days` query param

Client components:

- `frontend/app/heatmap/page.tsx`
- `frontend/components/layout/NavBar.tsx`
- `frontend/components/layout/StaleBanner.tsx`
- `frontend/components/asset/AssetDaySelector.tsx`
- `frontend/components/asset/ProbabilityChart.tsx`
- `frontend/components/asset/StockChart.tsx`
- `frontend/components/asset/TrueSentimentChart.tsx`
- `frontend/components/heatmap/AlignmentGrid.tsx`

Why:

- they use hooks such as `useState`, `useEffect`, `useRouter`, `usePathname`, or `useSearchParams`
- charting via Recharts is client-side
- the heatmap filter is interactive

### `lib/api.ts` fetch wrapper

`apiFetch<T>(path)` uses:

```typescript
fetch(`${BASE}${path}`, { cache: 'no-store' })
```

Why `cache: 'no-store'` matters:

- Next.js aggressively caches server fetches by default.
- For a dashboard that should reflect fresh pipeline outputs and current health state, stale framework caching is the wrong default.
- `no-store` ensures every request hits the backend directly.

### `lib/types.ts` contract

Purpose:

- provide one source of truth for the frontend's expected response shapes
- improve autocomplete and component safety

Important nuance:

- the types mirror the API closely, but not perfectly:
  - `ProbabilityPoint` omits the extra `open_bet`, `high_bet`, and `low_bet` fields the backend currently includes
  - `AssetDetail.latest_signal` is typed as `SignalToday | null`, but the backend currently returns `{}` when no signal row exists

### `Promise.allSettled` in the asset page

The asset page fetches:

- the main asset panel via `fetchAsset`
- the pre-open overnight series via `fetchAssetPreopen`

using `Promise.allSettled(...)` rather than `Promise.all(...)`.

Why:

- the main page should still render if the overnight endpoint fails
- the pre-open overlay is additive, not mandatory
- this prevents a minor auxiliary failure from blanking the entire page

### `await params` in Next.js 16

The asset route defines:

```typescript
params: Promise<{ ticker: string }>
searchParams: Promise<{ days?: string }>
```

and then awaits them.

Why:

- Next.js 16 route parameters are promise-based in this setup
- older App Router examples often assume synchronous `params`
- using the old pattern caused runtime issues during implementation

### `generateStaticParams()`

`frontend/app/asset/[ticker]/page.tsx` exports:

```typescript
generateStaticParams() {
  return ALL_TICKERS.map(t => ({ ticker: t }))
}
```

What it does:

- tells Next.js the known dynamic path segment values at build time
- improves route handling for the finite asset universe

## 8. Component Reference

### `frontend/components/layout/NavBar.tsx`

Props:

- none

Renders:

- app title `PM Signals`
- asset dropdown
- heatmap link

Hooks and dependencies:

- `usePathname`
- `useRouter`
- `next/link`

Non-obvious detail:

- the dropdown bug was fixed by ensuring `currentTicker` is uppercased and exactly matches the values in `ALL_TICKERS`.

### `frontend/components/layout/StaleBanner.tsx`

Props:

- none

Renders:

- yellow warning bar when backend data is stale or absent

Hooks and dependencies:

- `useEffect`
- `useState`
- `fetchHealth`

Non-obvious detail:

- on fetch failure, it errs on the side of warning and sets `stale=true`.

### `frontend/components/asset/AssetHeader.tsx`

Props:

- `ticker: string`
- `overnightChange: number | null`
- `signalDirection: 'UP' | 'DOWN' | null`
- `impliedProb: number | null`
- `days: number`

Renders:

- ticker block
- overnight change block
- pre-open probability block
- day selector
- buy/sell badge if direction exists

Dependencies:

- `Suspense`
- `AssetDaySelector`

Non-obvious detail:

- `days` is only used to seed `AssetDaySelector` via `initialDays`; the selector itself reads the live query string from `useSearchParams()`.

### `frontend/components/asset/AssetDaySelector.tsx`

Props:

- `initialDays?: number`

Renders:

- `1D`, `7D`, `30D` buttons

Hooks and dependencies:

- `useRouter`
- `usePathname`
- `useSearchParams`

Non-obvious detail:

- state lives in the URL, not in React state, so clicking a button triggers a route update and lets the server page refetch.

### `frontend/components/asset/ProbabilityChart.tsx`

Props:

- `data: ProbabilityPoint[]`
- `preopenData?: ProbabilityPoint[]`

Renders:

- chart shell card
- Recharts `ComposedChart`
- green probability area
- gray volume bars
- reference lines for midnight, market open, market close, and the 50% level

Dependencies:

- Recharts `Area`, `Bar`, `ComposedChart`, `ReferenceLine`, `ResponsiveContainer`, `Tooltip`, `XAxis`, `YAxis`, `CartesianGrid`

Non-obvious implementation details:

- merges pre-open and intraday series, then sorts them chronologically
- uses numeric timestamps (`ts`) for a time scale
- keeps volume bars visually subdued with opacity `0.12` and a right-axis domain multiplier of `6`
- disables animation on both area and bars to avoid first-paint glitches
- if exact reference timestamps are missing, it uses sensible fallbacks so the chart remains readable

### `frontend/components/asset/StockChart.tsx`

Props:

- `data: StockPoint[]`

Renders:

- chart shell card
- Recharts `LineChart`
- single blue line for stock close
- vertical market-open reference line

Dependencies:

- Recharts `LineChart`, `Line`, `ReferenceLine`, `ResponsiveContainer`, `Tooltip`, `XAxis`, `YAxis`, `CartesianGrid`

Non-obvious implementation details:

- contains no bars, no right-hand axis, and no volume series
- filters out non-finite values before computing the domain
- domain padding uses `8%` above and below the observed min/max and rounds to cents

### `frontend/components/asset/TrueSentimentChart.tsx`

Props:

- `data: SentimentPoint[]`

Renders:

- card shell with title and explanatory subtitle
- Recharts `BarChart`
- one bar per point, green for positive and red for negative
- zero reference line

Dependencies:

- Recharts `BarChart`, `Bar`, `Cell`, `ReferenceLine`, `ResponsiveContainer`, `Tooltip`, `XAxis`, `YAxis`, `CartesianGrid`

Non-obvious implementation details:

- filters out null sentiment rows before render
- returns an empty-state card if everything is null

### `frontend/components/asset/SignalMetricsBlock.tsx`

Props:

- `signal: SignalToday | null`

Renders:

- left metrics card
- right score card

Dependencies:

- `SignalToday` type only; no external libraries

Non-obvious implementation details:

- computes conviction from `true_sentiment` because `signals_today.csv` does not contain an explicit `abs_sentiment`
- if `true_sentiment` is null, conviction renders as `-`

### `frontend/components/heatmap/TimeFilterBar.tsx`

Props:

- `selected: number`
- `onChange: (days: number) => void`

Renders:

- button group for `7D`, `30D`, `60D`

Dependencies:

- none beyond React

Non-obvious detail:

- purely presentational; actual data loading happens in the page component.

### `frontend/components/heatmap/QuadrantLegend.tsx`

Props:

- none

Renders:

- four color legend entries

Dependencies:

- none beyond React

Non-obvious detail:

- descriptions match the backend quadrant logic exactly.

### `frontend/components/heatmap/AlignmentGrid.tsx`

Props:

- `data: HeatmapEntry[]`

Renders:

- empty state when there are no dates
- otherwise a horizontally scrollable HTML table

Dependencies:

- `useRouter`
- `HeatmapEntry`

Non-obvious implementation details:

- fixed ticker order:
  - `AAPL`, `MSFT`, `NVDA`, `GOOGL`, `META`, `AMZN`, `NFLX`, `TSLA`
- uses native HTML `title` tooltips rather than custom tooltip components
- missing ticker/date combinations render as low-opacity background cells

### `frontend/components/heatmap/AlignmentSummaryStats.tsx`

Props:

- `data: HeatmapEntry[]`

Renders:

- four stat cards:
  - overall alignment
  - high-liquidity alignment
  - best asset
  - worst asset

Dependencies:

- `HeatmapEntry`

Non-obvious implementation details:

- calculates rates entirely client-side
- best/worst asset ranking excludes gray cells by first filtering to non-gray entries

## 9. Data Schema Reference

### `signals_today.csv`

Purpose:

- one pre-open row per asset

Current columns:

| Column | Type | Source computation | Nullable | Example |
| --- | --- | --- | --- | --- |
| `ticker` | `string` | group key from raw orderbook `KEY` | no | `AAPL` |
| `date` | `string` | target New York date in `YYYY-MM-DD` format | no | `2026-04-03` |
| `pre_open_implied_prob` | `float` | last `PRICE_UP` before firewall | no | `0.58` |
| `overnight_prob_change` | `float` | last `PRICE_UP - first PRICE_UP` in the overnight window | no | `0.041` |
| `pre_open_pm_volume` | `float` | sum of `USDC` in the overnight window | no | `720.0` |
| `pre_open_buy_ratio` | `float` | bullish volume divided by total volume | yes when total volume is zero | `0.62` |
| `is_high_liquidity` | `bool` | `pre_open_pm_volume >= 500` | no | `true` |
| `signal_direction` | `string` | `"UP"` if `overnight_prob_change >= 0` else `"DOWN"` | no | `UP` |
| `signal_quality_score` | `float` | `_compute_signal_quality(volume, abs(overnight_prob_change))` | no | `8.0` |
| `true_sentiment` | `float` | intentionally not computed at pre-open stage | yes | `null` |

### `panel_15m.csv`

Purpose:

- intraday feature panel used by Page 2 and Page 3

Current columns:

| Column | Type | Source computation | Nullable | Example |
| --- | --- | --- | --- | --- |
| `KEY` | `string` | asset ticker | no | `AAPL` |
| `TIMESTAMP` | `datetime string` | window timestamp, written without timezone suffix in CSV | no | `2026-04-01 13:30:00` |
| `open_bet` | `float` | first `PRICE_UP` in the window | no in valid panel rows | `0.4325` |
| `close_bet` | `float` | last `PRICE_UP` in the window | no | `0.4385` |
| `high_bet` | `float` | max `PRICE_UP` in the window | no | `0.4432` |
| `low_bet` | `float` | min `PRICE_UP` in the window | no | `0.4286` |
| `avg_price_up` | `float` | mean `PRICE_UP` in the window | no | `0.4388` |
| `total_volume` | `float` | sum of `USDC` in the window | no | `303.85` |
| `trade_count` | `int` | count of `SHARES` rows in the window | no | `10` |
| `time_to_exp` | `float` | last `TIME_TO_EXP` in the window | no | `6.5` |
| `stock_close` | `float` | last merged stock close from the 5-minute Yahoo bar | no in valid panel rows | `194.27` |
| `stock_vol` | `float` | last merged annualized rolling stock volatility | no | `0.2317` |
| `bs_neutral_prob` | `float` | `norm.cdf(d2)` risk-neutral benchmark | no | `0.4128` |
| `true_sentiment` | `float` | `avg_price_up - bs_neutral_prob` | no | `0.0261` |
| `abs_sentiment` | `float` | absolute value of `true_sentiment` | yes before `check_lead_lag()`; no after it | `0.0261` |
| `poly_vol_imbalance` | `float` | `(bull_volume / bear_volume) - 1`, with NaNs replaced by `1` | no | `0.0656` |
| `next_stock_move` | `float` | log return of next window's `stock_close` | yes on final row of each ticker sequence | `-0.000748` |

Important naming note:

- The file is called `panel_15m.csv`, but the current production panel is generated from 5-minute windows.

### `last_run.json`

Current fields:

| Field | Type | Meaning | When written |
| --- | --- | --- | --- |
| `timestamp` | `string` | UTC ISO timestamp of the pipeline completion moment | `step5_save_metadata()` |
| `date` | `string` | local script date in `YYYY-MM-DD` format | `step5_save_metadata()` |
| `assets_ok` | `list[str]` | assets that returned non-empty raw orderbook data | `step5_save_metadata()` |
| `assets_failed` | `list[str]` | assets that failed or returned empty raw data | `step5_save_metadata()` |
| `panel_rows` | `int` | number of rows written to `panel_15m.csv` in that run | `step5_save_metadata()` |
| `signals_rows` | `int` | number of rows written to `signals_today.csv` in that run | `step5_save_metadata()` |

Current example:

```json
{
  "timestamp": "2026-04-03T09:02:00Z",
  "date": "2026-04-03",
  "assets_ok": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "NFLX", "TSLA"],
  "assets_failed": [],
  "panel_rows": 1896,
  "signals_rows": 8
}
```

### Auxiliary file: `orderbook_latest.csv`

This file is not one of the two main dashboard data outputs, but it is now operationally important because the frontend uses it to prepend the overnight series on the probability chart.

Current checked-in mock columns:

- `KEY`
- `TIMESTAMP`
- `PRICE_UP`
- `USDC`

Live pipeline behavior:

- `run_daily.py` will overwrite the mock with the full raw orderbook export from `save_raw_orderbook(...)`.

### Mock data note

The checked-in CSV and JSON files in `backend/data/` are synthetic development fixtures. They exist so the API and frontend can be tested immediately without waiting for a real data pull. The first real successful pipeline run will overwrite them.

## 10. The Black-Scholes Computation In Detail

The central modeling move in this project is to treat the Polymarket "stock up today" contract as approximately analogous to a European cash-or-nothing call option that pays if the stock closes above the opening level.

### Cash-or-nothing call analogy

A cash-or-nothing call pays a fixed amount if the underlying ends above the strike at expiry and zero otherwise. That matches the economic structure of a binary daily up/down contract surprisingly well:

- payout if close > open
- no payout if close <= open

The analogy is not exact because Polymarket is a prediction market with its own frictions and participant constraints, but it is close enough to motivate a benchmark fair probability.

### Why `K = stock_open_day`

The daily Polymarket contract resolves YES if the stock closes above its opening price for that day. That means the opening price is the threshold the final close must exceed. In option language, that is the strike.

### Current implementation of time to expiry

The code uses:

```python
T = ((time_to_exp / 24) / 252).clip(lower=1e-9)
```

Interpretation:

- `time_to_exp` is measured in hours in the project's relative daily clock
- dividing by `24` converts hours into a fraction of a calendar day
- dividing by `252` converts that into a rough trading-year fraction

This is a simplified convention. A more strictly market-hours-based approach might divide by `6.5` trading hours per day before annualizing. The current implementation is internally consistent with the rest of the panel but should be remembered as a modeling choice rather than a theorem.

### Full `d2` formula

The implementation computes:

```text
d2 = (ln(S/K) + (r - 0.5*sigma^2)T) / (sigma*sqrt(T))
```

where:

- `S` = current stock close in the matched window
- `K` = stock open for the day
- `r` = `RISK_FREE_ANN = 0.04`
- `sigma` = rolling annualized volatility from 5-minute returns
- `T` = remaining time to expiry in trading-year fraction

Then:

```text
bs_neutral_prob = N(d2)
true_sentiment = avg_price_up - bs_neutral_prob
```

### Volatility annualization

Upstream in `_pull_stock_minutes()`:

```python
returns = log(stock_close_t / stock_close_t-1)
ann_factor = sqrt((60 / minutes * 6.5) * 252)
stock_vol_5m = rolling_std(returns, window=window_size) * ann_factor
```

Why this works:

- `60 / minutes` = bars per hour
- `* 6.5` = bars per trading day
- `* 252` = bars per trading year
- square root converts variance-time scaling into standard-deviation scaling

### Rolling window choice

`window_size` is passed as:

```python
120 // intraday_minutes
```

At the current `5` minutes:

- `120 // 5 = 24`

Interpretation:

- the volatility estimate uses about the last two hours of 5-minute returns

### Why `clip(lower=1e-9)` is applied to `T`

As expiry approaches, `T` can get extremely small. Dividing by `sigma*sqrt(T)` would explode numerically if `T` were allowed to hit zero. Clipping it to a tiny positive value prevents division by zero and keeps the calculation stable.

### Why `d2.fillna(0)` is used before `norm.cdf(...)`

If `sigma` is missing or a division degenerates, `d2` can become NaN. Replacing NaN with `0` maps the neutral benchmark probability to `0.5` because `N(0)=0.5`. That is a pragmatic fallback: when the model cannot determine a skew, it falls back to an even chance rather than crashing.

### Core assumption being made

The whole benchmark assumes that the daily binary up/down market can be treated like a frictionless European cash-or-nothing option on the stock's close relative to the open. Real Polymarket contracts do not satisfy every Black-Scholes assumption. The benchmark is therefore best understood as a disciplined fair-value proxy, not a literal replication identity.

## 11. Known Issues And Technical Debt

1. The original monolith contained two different `pro_backtest` implementations. The refactor intentionally kept only the second one, but this history matters because notebook outputs may refer to logic that no longer exists exactly in the runtime module.

2. The `time.sleep(0.1)` rate-limit mitigation in `orderbook.py` makes full 60-day runs slow. This is one reason the daily pipeline can take 20 to 40 minutes.

3. `--dry-run` still performs live network work. In sandboxed or DNS-restricted environments that means it can fail for reasons unrelated to code correctness.

4. The checked-in mock data covers only three trading days. The heatmap's `7D`, `30D`, and `60D` buttons therefore work mechanically, but the visual difference is subtle until real data accumulates.

5. `true_sentiment` is intentionally `null` in `signals_today.csv` because pre-open signal generation does not depend on stock data. The metrics block handles this by rendering `-`.

6. `StaleBanner.tsx` polls `/health` every 60 seconds from the client. That is acceptable for a demo but not an ideal production pattern.

7. CORS in `server.py` is hardcoded to `http://localhost:3000`. Deployment will require making this configurable.

8. `orderbook_latest.csv` is overwritten on every run, and the current implementation does **not** also write a dated raw archive copy. Historical raw orderbook recovery is therefore not preserved.

9. The file `panel_15m.csv` is a legacy name. The current contents are generated with 5-minute windows. This does not break the app, but it is confusing and should eventually be renamed.

10. Archived research notes sometimes refer to a `09:00` signal snapshot, while the live implementation uses a `09:30` firewall. The code is authoritative, but the documents can confuse new readers if this mismatch is not explained.

11. Archived research notes mention a 10-asset universe including indices, while the current production config tracks 8 single-name equities. Results from the earlier broader universe should not be assumed to apply identically to the live dashboard universe.

12. `/api/asset/{ticker}` currently returns `latest_signal: {}` when no matching row exists, while the TypeScript contract models `latest_signal` as `SignalToday | null`. The frontend tolerates this, but the contract is not perfectly aligned.

13. `ProbabilityPoint` in `frontend/lib/types.ts` is narrower than the actual API payload, which also includes `open_bet`, `high_bet`, and `low_bet`. This is harmless in the current UI because those extra fields are not consumed directly by the typed components, but it is still a drift between backend and frontend contracts.

14. The checked-in mock `orderbook_latest.csv` is intentionally thinner than the real raw export. That is fine for development, but a new developer should not mistake its four-column shape for the live raw-orderbook schema.

15. `/api/asset/{ticker}/preopen` filters against the current New York date, not the pipeline run date. If the dataset becomes stale, the overnight overlay can disappear even while the rest of the dashboard still renders historical intraday data.

## 12. Deployment Notes

### Backend deployment

A lightweight deployment target such as Railway or Render is a reasonable next step for the backend.

What the deployed backend would need:

- Python runtime with the packages from `backend/requirements.txt`
- persistent writable storage for:
  - `data/`
  - `logs/`
- an environment-variable driven CORS origin list
- a scheduled job to run `python run_daily.py`

How to schedule the pipeline in deployment:

- Railway:
  - use Railway cron or a separate scheduled service that runs `python backend/run_daily.py`
- Render:
  - use a cron job service or a background worker
- alternative:
  - embed a scheduler such as APScheduler in the FastAPI app, though that adds operational coupling between the API process and the data-refresh process

### Frontend deployment

Vercel is the natural deployment target for the Next.js app.

Required environment variable:

```text
NEXT_PUBLIC_API_URL=https://<deployed-backend-url>
```

Without that change, the deployed frontend will keep trying to call `http://localhost:8000`.

### Data persistence

The current backend writes flat files into `backend/data/`. For deployment, that directory must persist between container restarts. Two practical options are:

1. use a mounted persistent volume
2. migrate the outputs into SQLite or another small durable store

If persistence is not solved, every restart will lose:

- `signals_today.csv`
- `panel_15m.csv`
- `orderbook_latest.csv`
- `last_run.json`

### CORS updates

`allow_origins=["http://localhost:3000"]` is correct for local development only. A deployed system would need the production frontend URL added, for example the Vercel domain, ideally through environment variables rather than a hardcoded list.

### Suggested deployment split

- Backend:
  - Railway or Render
  - scheduled daily pipeline job
  - mounted volume or SQLite-backed persistence
- Frontend:
  - Vercel
  - `NEXT_PUBLIC_API_URL` pointing to the backend

That is enough to make the project usable beyond localhost without changing the basic architecture.
