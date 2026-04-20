# Polymarket Dashboard - Visual Architecture

## 🏛️ Complete System Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│                          USER'S BROWSER                                      │
│                     (Portfolio Manager Views)                                │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                                                                      │    │
│  │              REACT DASHBOARD (Next.js Frontend)                     │    │
│  │                   http://localhost:3000                             │    │
│  │                                                                      │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │    │
│  │  │   Page 1:    │  │   Page 2:    │  │   Page 3:    │             │    │
│  │  │   Market     │  │   Asset      │  │  Performance │             │    │
│  │  │   Overview   │  │   Detail     │  │  Dashboard   │             │    │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘             │    │
│  │         │                  │                  │                      │    │
│  │         └──────────────────┴──────────────────┘                      │    │
│  │                            │                                         │    │
│  │                            ↓                                         │    │
│  │                  ┌─────────────────────┐                            │    │
│  │                  │  React Components   │                            │    │
│  │                  ├─────────────────────┤                            │    │
│  │                  │ • MarketHeatmap     │                            │    │
│  │                  │ • SignalTable       │                            │    │
│  │                  │ • ProbabilityChart  │                            │    │
│  │                  │ • ModelCard         │                            │    │
│  │                  └──────────┬──────────┘                            │    │
│  │                             │                                        │    │
│  │                             ↓                                        │    │
│  │                  ┌─────────────────────┐                            │    │
│  │                  │   API Client        │                            │    │
│  │                  │   (lib/api.ts)      │                            │    │
│  │                  │                     │                            │    │
│  │                  │  fetchMarkets()     │                            │    │
│  │                  │  fetchMarketDetail()│                            │    │
│  │                  │  fetchPredictions() │                            │    │
│  │                  │  fetchPerformance() │                            │    │
│  │                  └──────────┬──────────┘                            │    │
│  │                             │                                        │    │
│  └─────────────────────────────┼────────────────────────────────────────┘    │
│                                │                                             │
└────────────────────────────────┼─────────────────────────────────────────────┘
                                 │
                                 │ HTTP Requests (JSON)
                                 │ GET /api/markets
                                 │ GET /api/markets/AAPL
                                 │ GET /api/predictions
                                 │
                                 ↓
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│                      PYTHON BACKEND SERVER                                   │
│                   (FastAPI - api_server.py)                                  │
│                     http://localhost:8000                                    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                         API ENDPOINTS                               │    │
│  │                                                                      │    │
│  │  GET  /api/markets              → List all markets                 │    │
│  │  GET  /api/markets/{ticker}     → Get AAPL/TSLA/etc details       │    │
│  │  GET  /api/predictions          → Get model predictions            │    │
│  │  GET  /api/performance          → Get model accuracy metrics       │    │
│  │  POST /api/sync                 → Trigger daily data refresh       │    │
│  │                                                                      │    │
│  └──────────────────────────┬───────────────────────────────────────────┘    │
│                             │                                              │
│                             ↓                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                    DATA PROCESSING LAYER                            │    │
│  │                                                                      │    │
│  │  1. Load CSV:  /tmp/expanded_feature_panel.csv                     │    │
│  │  2. Filter data by ticker/date/category                            │    │
│  │  3. Transform to JSON format                                        │    │
│  │  4. Return to frontend                                              │    │
│  │                                                                      │    │
│  └──────────────────────────┬───────────────────────────────────────────┘    │
│                             │                                              │
│                             ↓                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │              YOUR EXISTING PYTHON CODE (Reused!)                    │    │
│  │                                                                      │    │
│  │  • FML_Experiment_2_Class_Based.py  (Polymarket API wrapper)       │    │
│  │  • Feature Engineering Pipeline.py   (Data processing)             │    │
│  │  • Predictive_Modeling.py           (ML models)                    │    │
│  │                                                                      │    │
│  └──────────────────────────┬───────────────────────────────────────────┘    │
│                             │                                              │
└─────────────────────────────┼──────────────────────────────────────────────┘
                              │
                              │ Reads/Writes
                              ↓
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│                           DATA STORAGE                                       │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                                                                      │    │
│  │   /tmp/expanded_feature_panel.csv                                   │    │
│  │                                                                      │    │
│  │   Columns:                                                           │    │
│  │   • asset, date, closed_up                                          │    │
│  │   • pre_open_implied_prob, overnight_prob_change                    │    │
│  │   • pre_open_pm_volume, is_high_liquidity                           │    │
│  │   • overnight_gap_return, prior_day_close_to_close                  │    │
│  │   • rolling_volatility_5d                                           │    │
│  │                                                                      │    │
│  │   399 rows × 10 assets × 60 days                                    │    │
│  │                                                                      │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

