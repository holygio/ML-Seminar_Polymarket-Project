import json
import os
import sys
import threading
import time as _time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytz
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).parent))

from config import DATA_DIR, HEATMAP_MIN_MOVE, LIQUIDITY_THRESHOLD
from live_data import (
    start_background_refresh,
    _shared_state,
    _data_lock,
)
from pipeline import (
    fetch_macro_geopolitical_markets,
    fetch_probability_change_24h,
)

app = FastAPI(title="Polymarket Signal API", version="1.0.0")

_cors_origins = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_live_started = False
_live_start_lock = threading.Lock()
_GEO_CACHE = {"data": None, "fetched_at": 0.0}
_GEO_CACHE_TTL = 300

EQUITY_KEYWORDS: dict[str, list[str]] = {
    "NVDA": ["nvidia", "chips", "semiconductor", "ai chip", "export control", "gpu", "china tech"],
    "AAPL": ["apple", "iphone", "china supply chain", "tariff", "trade"],
    "MSFT": ["microsoft", "ai", "cloud", "azure", "regulation"],
    "AMZN": ["amazon", "aws", "trade", "tariff", "ecommerce"],
    "GOOGL": ["google", "alphabet", "antitrust", "regulation", "ai"],
    "META": ["meta", "facebook", "regulation", "social media", "eu"],
    "TSLA": ["tesla", "ev", "electric vehicle", "china", "tariff", "elon"],
    "NFLX": ["netflix", "streaming", "regulation", "content"],
    "PLTR": ["palantir", "defense", "government contract", "surveillance", "intelligence"],
    "COIN": ["coinbase", "crypto exchange", "bitcoin", "ethereum", "crypto regulation"],
}

EXPOSURE_HIGH_KEYWORDS = [
    "sanctions",
    "ban",
    "block",
    "restrict",
    "tariff",
    "export control",
    "invasion",
    "war",
    "ceasefire",
]


def load_csv(filename: str) -> pd.DataFrame:
    """Load a CSV from the data directory. Raise 503 if not found."""
    path = DATA_DIR / filename
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"{filename} not found — pipeline may not have run yet",
        )
    return pd.read_csv(path)


def nan_safe(val):
    """Convert NaN/inf to None so JSON serialization doesn't break."""
    if val is None:
        return None
    if isinstance(val, (bool, np.bool_)):
        return bool(val)
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (np.floating, float)):
        if np.isnan(val) or np.isinf(val):
            return None
        return float(val)
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    return val


def parse_timestamps(df: pd.DataFrame) -> pd.Series:
    ts = pd.to_datetime(df["TIMESTAMP"])
    if ts.dt.tz is None:
        ts = ts.dt.tz_localize("UTC")
    else:
        ts = ts.dt.tz_convert("UTC")
    return ts


def with_market_dates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["TIMESTAMP"] = parse_timestamps(df)
    df["market_date"] = df["TIMESTAMP"].dt.tz_convert("America/New_York").dt.date.astype(str)
    return df


def filter_last_market_days(df: pd.DataFrame, days: int) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    dated = with_market_dates(df)
    unique_dates = sorted(dated["market_date"].unique())
    keep_dates = set(unique_dates[-days:])
    return dated[dated["market_date"].isin(keep_dates)].copy()


def serialize_signal_row(row: pd.Series) -> dict:
    is_high_liquidity_raw = row.get("is_high_liquidity", False)
    if isinstance(is_high_liquidity_raw, str):
        is_high_liquidity = is_high_liquidity_raw.strip().lower() == "true"
    else:
        is_high_liquidity = bool(is_high_liquidity_raw)

    signal_direction = str(row.get("signal_direction", "unknown")).lower()
    return {
        "ticker": row["ticker"],
        "date": row["date"],
        "pre_open_implied_prob": nan_safe(row.get("pre_open_implied_prob")),
        "overnight_prob_change": nan_safe(row.get("overnight_prob_change")),
        "pre_open_pm_volume": nan_safe(row.get("pre_open_pm_volume")),
        "pre_open_buy_ratio": nan_safe(row.get("pre_open_buy_ratio")),
        "is_high_liquidity": is_high_liquidity,
        "signal_direction": signal_direction,
        "signal_quality_score": nan_safe(row.get("signal_quality_score")),
        "true_sentiment": nan_safe(row.get("true_sentiment")),
    }


def _derive_equity_exposure(title: str) -> dict[str, str]:
    title_lower = (title or "").lower()
    exposure: dict[str, str] = {}
    is_high_impact = any(keyword in title_lower for keyword in EXPOSURE_HIGH_KEYWORDS)

    for ticker, keywords in EQUITY_KEYWORDS.items():
        if any(keyword in title_lower for keyword in keywords):
            exposure[ticker] = "HIGH" if is_high_impact else "MED"

    return exposure


def _event_category(event: dict) -> str:
    tag_to_category = {
        "interest-rates": "Rates",
        "federal-reserve": "Rates",
        "inflation": "Rates",
        "central-bank": "Rates",
        "tariffs": "Trade",
        "trade-war": "Trade",
        "sanctions": "Trade",
        "china": "Trade",
        "war": "Conflict",
        "military": "Conflict",
        "ukraine": "Conflict",
        "ceasefire": "Conflict",
        "election": "Politics",
        "politics": "Politics",
        "geopolitics": "Politics",
    }
    for tag in event.get("tags", []) or []:
        category = tag_to_category.get(str(tag).strip().lower())
        if category:
            return category

    title = str(event.get("title", "") or "").lower()
    if any(token in title for token in ["rate", "fed", "ecb", "cpi", "inflation", "interest", "powell", "cut"]):
        return "Rates"
    if any(token in title for token in ["tariff", "trade", "export", "import", "wto", "sanction", "china"]):
        return "Trade"
    if any(token in title for token in ["ukraine", "russia", "nato", "israel", "gaza", "military", "ceasefire", "peace", "war"]):
        return "Conflict"
    return "Politics"


def _build_macro_heat(markets: list[dict]) -> dict[str, dict[str, str]]:
    tickers = ["NVDA", "AAPL", "MSFT", "AMZN", "TSLA", "GOOGL", "META", "NFLX", "PLTR", "COIN"]
    categories = ["Rates", "Trade", "Markets", "Conflict", "Politics"]
    heat: dict[str, dict[str, str]] = {
        ticker: {category: "NEUTRAL" for category in categories}
        for ticker in tickers
    }

    order = {"NEUTRAL": 0, "LOW": 1, "MED": 2, "HIGH": 3}
    for market in markets:
        exposure = market.get("equity_exposure", {}) or {}
        category = market.get("category", "Politics")
        for ticker, level in exposure.items():
            if ticker not in heat or category not in heat[ticker]:
                continue
            if order.get(level, 0) > order.get(heat[ticker][category], 0):
                heat[ticker][category] = level
    return heat


def _interpret_probability(
    title: str,
    probability: float | None,
    change_24h: float | None,
    market_type: str,
    leading_outcome: str | None,
) -> str:
    if probability is None:
        return "No reliable probability is available for this market yet."

    if market_type == "categorical":
        outcome_txt = f"{leading_outcome} " if leading_outcome else ""
        return f"Most likely outcome is {outcome_txt.strip() or 'the leading contract'}with {round(probability * 100)}% crowd support."

    direction = "likely" if probability > 0.6 else "unlikely" if probability < 0.4 else "uncertain"
    trend = ""
    if change_24h is not None and abs(change_24h) >= 0.02:
        pp = round(abs(change_24h) * 100, 1)
        trend = f" Crowd moved {'+' if change_24h > 0 else '-'}{pp}pp over the last 24h."
    return f"Crowd says this is {direction} at {round(probability * 100)}%.{trend}"


def _plain_english_interpretation(
    display_label: str,
    probability: float,
    leading_outcome: str | None,
    market_type: str,
    change_24h: float | None,
) -> str:
    pct = round(probability * 100)
    if market_type == "categorical" and leading_outcome:
        trend = ""
        if change_24h is not None and abs(change_24h) >= 0.01:
            pp = round(abs(change_24h) * 100, 1)
            trend = f", moved {'up' if change_24h > 0 else 'down'} {pp}pp today"
        return f"Most likely: {leading_outcome} ({pct}%){trend}"

    if probability > 0.75:
        verdict = "Crowd strongly expects this"
    elif probability > 0.6:
        verdict = "Crowd leans toward this happening"
    elif probability > 0.45:
        verdict = "Outcome is uncertain"
    elif probability > 0.25:
        verdict = "Crowd leans against this"
    else:
        verdict = "Crowd strongly doubts this"

    trend = ""
    if change_24h is not None and abs(change_24h) >= 0.01:
        pp = round(abs(change_24h) * 100, 1)
        trend = f" — {'+' if change_24h > 0 else '-'}{pp}pp today"
    return f"{verdict} ({pct}%){trend}"


@app.get("/health")
def health():
    """
    Returns last pipeline run metadata.
    Frontend polls this for the 'last updated' indicator.
    """
    path = DATA_DIR / "last_run.json"
    if not path.exists():
        return {
            "status": "no_data",
            "message": "Pipeline has never run",
            "timestamp": None,
            "assets_ok": [],
            "assets_failed": [],
        }

    with open(path) as handle:
        data = json.load(handle)

    last_run_dt = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    hours_ago = (datetime.utcnow() - last_run_dt.replace(tzinfo=None)).total_seconds() / 3600
    is_stale = hours_ago > 26

    return {
        "status": "stale" if is_stale else "ok",
        "timestamp": data["timestamp"],
        "date": data.get("date"),
        "hours_ago": round(hours_ago, 1),
        "assets_ok": data.get("assets_ok", []),
        "assets_failed": data.get("assets_failed", []),
        "panel_rows": data.get("panel_rows"),
        "signals_rows": data.get("signals_rows"),
    }


@app.get("/api/signals/today")
def signals_today():
    """
    Returns one signal object per asset for today's pre-open snapshot.
    """
    df = load_csv("signals_today.csv")
    results = [serialize_signal_row(row) for _, row in df.iterrows()]
    return {"data": results, "count": len(results)}


@app.get("/api/asset/{ticker}/preopen")
def asset_preopen(ticker: str):
    """
    Returns the pre-open probability time series from the raw orderbook.
    """
    ticker = ticker.upper()
    ob = load_csv("orderbook_latest.csv")
    if ob.empty:
        return {"ticker": ticker, "preopen_series": []}

    asset_ob = ob[ob["KEY"] == ticker].copy()
    if asset_ob.empty:
        return {"ticker": ticker, "preopen_series": []}

    asset_ob["TIMESTAMP"] = parse_timestamps(asset_ob)

    ny_tz = pytz.timezone("America/New_York")
    asset_ob["ts_ny"] = asset_ob["TIMESTAMP"].dt.tz_convert(ny_tz)
    today_ny = datetime.now(ny_tz).date()

    mask = (
        (asset_ob["ts_ny"].dt.date == today_ny)
        & (
            (asset_ob["ts_ny"].dt.hour < 9)
            | ((asset_ob["ts_ny"].dt.hour == 9) & (asset_ob["ts_ny"].dt.minute < 30))
        )
    )
    preopen = asset_ob[mask].copy()

    if preopen.empty:
        return {"ticker": ticker, "preopen_series": []}

    preopen = preopen.set_index("TIMESTAMP").sort_index()
    resampled = preopen["PRICE_UP"].resample("5min").last().dropna()
    vol_resampled = preopen["USDC"].resample("5min").sum()

    series = []
    for ts, price_up in resampled.items():
        series.append(
            {
                "timestamp": ts.isoformat(),
                "price_up": nan_safe(price_up),
                "volume": nan_safe(vol_resampled.get(ts, 0)),
            }
        )

    return {"ticker": ticker, "preopen_series": series}


@app.get("/api/asset/{ticker}")
def asset_detail(ticker: str, days: int = Query(default=1, ge=1, le=60)):
    """
    Returns the time series needed for the asset detail page.
    """
    ticker = ticker.upper()
    panel = load_csv("panel_15m.csv")
    asset_panel = panel[panel["KEY"] == ticker].copy()
    if asset_panel.empty:
        raise HTTPException(status_code=404, detail=f"No data for ticker {ticker}")

    asset_panel = filter_last_market_days(asset_panel, days)
    asset_panel = asset_panel.sort_values("TIMESTAMP")

    prob_series = []
    stock_series = []
    sentiment_series = []
    for _, row in asset_panel.iterrows():
        timestamp = row["TIMESTAMP"].isoformat()
        prob_series.append(
            {
                "timestamp": timestamp,
                "price_up": nan_safe(row.get("close_bet")),
                "volume": nan_safe(row.get("total_volume")),
                # open_bet, high_bet, low_bet are returned but not yet in TS ProbabilityPoint
                # They will be added to types.ts in Step 5.
                "open_bet": nan_safe(row.get("open_bet")),
                "high_bet": nan_safe(row.get("high_bet")),
                "low_bet": nan_safe(row.get("low_bet")),
            }
        )
        stock_series.append(
            {
                "timestamp": timestamp,
                "close": nan_safe(row.get("stock_close")),
            }
        )
        sentiment_series.append(
            {
                "timestamp": timestamp,
                "true_sentiment": nan_safe(row.get("true_sentiment")),
                "abs_sentiment": nan_safe(row.get("abs_sentiment")),
                "bs_neutral_prob": nan_safe(row.get("bs_neutral_prob")),
            }
        )

    latest_signal = None
    try:
        signals_df = load_csv("signals_today.csv")
        signal_row = signals_df[signals_df["ticker"] == ticker]
        if not signal_row.empty:
            latest_signal = serialize_signal_row(signal_row.iloc[0])
    except HTTPException:
        latest_signal = None

    if latest_signal is not None and not asset_panel.empty:
        latest_signal["stock_vol_ann"] = nan_safe(asset_panel.iloc[-1].get("stock_vol"))
        latest_signal["bs_neutral_prob"] = nan_safe(asset_panel.iloc[-1].get("bs_neutral_prob"))

    return {
        "ticker": ticker,
        "days": days,
        "row_count": len(asset_panel),
        "latest_signal": latest_signal,
        "probability_series": prob_series,
        "stock_series": stock_series,
        "true_sentiment_series": sentiment_series,
    }


@app.get("/api/heatmap")
def heatmap(days: int = Query(default=30, ge=1, le=60)):
    """
    Returns daily alignment quadrants per asset and day.
    """
    panel = load_csv("panel_15m.csv")
    panel = filter_last_market_days(panel, days)

    results = []
    for (ticker, market_date), group in panel.groupby(["KEY", "market_date"]):
        group = group.sort_values("TIMESTAMP")
        if len(group) < 2:
            continue

        first_prob = group["open_bet"].iloc[0]
        last_prob = group["close_bet"].iloc[-1]
        prob_change = last_prob - first_prob
        prob_direction = 1 if prob_change > 0 else -1

        first_close = group["stock_close"].iloc[0]
        last_close = group["stock_close"].iloc[-1]
        if pd.isna(first_close) or pd.isna(last_close) or first_close == 0:
            continue

        price_move = (last_close - first_close) / first_close
        price_direction = 1 if price_move > 0 else -1
        volume = group["total_volume"].sum()

        move_too_small = abs(price_move) < HEATMAP_MIN_MOVE
        low_liquidity = volume < LIQUIDITY_THRESHOLD

        if low_liquidity or move_too_small:
            quadrant = "gray"
        elif prob_direction == 1 and price_direction == 1:
            quadrant = "green"
        elif prob_direction == -1 and price_direction == -1:
            quadrant = "red"
        else:
            quadrant = "yellow"

        results.append(
            {
                "ticker": ticker,
                "date": market_date,
                "prob_direction": prob_direction,
                "price_direction": price_direction,
                "prob_change": nan_safe(round(prob_change, 4)),
                "price_move": nan_safe(round(price_move, 4)),
                "volume": nan_safe(round(volume, 2)),
                "quadrant": quadrant,
            }
        )

    return {"days": days, "count": len(results), "data": results}


@app.get("/api/live")
def live_market():
    """
    Returns the real-time market bundle used by the live heatmap page.
    Data refreshes every 30 seconds in the background.
    First response may return 503 warming_up while data loads.
    """
    global _live_started
    with _live_start_lock:
        if not _live_started:
            start_background_refresh(interval_seconds=30)
            _live_started = True

    with _data_lock:
        df = _shared_state["df"].copy()
        last_fetched = _shared_state.get("last_fetched", "")

    if df.empty:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "warming_up",
                "message": "Background data fetch in progress. Retry in 30s.",
            },
        )

    records = []
    for _, row in df.iterrows():
        records.append(
            {
                "ticker":              nan_safe(row.get("ticker")),
                "category":            nan_safe(row.get("category")),
                "label":               nan_safe(row.get("label")),
                "last_close":          nan_safe(row.get("last_close")),
                "prev_close":          nan_safe(row.get("prev_close")),
                "ret_pct":             nan_safe(row.get("ret_pct")),
                "chg_abs":             nan_safe(row.get("chg_abs")),
                "market_cap":          nan_safe(row.get("market_cap")),
                "volume":              nan_safe(row.get("volume")),
                "vol_ratio":           nan_safe(row.get("vol_ratio")),
                "poly_up_probability": nan_safe(row.get("poly_up_probability")),
                "poly_target_date":    nan_safe(row.get("poly_target_date")),
                "date":                nan_safe(row.get("date")),
                "last_fetched":        last_fetched,
            }
        )

    return {"count": len(records), "last_fetched": last_fetched, "data": records}

@app.get("/api/geopolitical")
def geopolitical_markets():
    """
    Returns live geopolitical and macro prediction markets from Polymarket,
    cached for 5 minutes to avoid repeated API pressure.
    """
    now = _time.time()
    if _GEO_CACHE["data"] and (now - _GEO_CACHE["fetched_at"]) < _GEO_CACHE_TTL:
        return _GEO_CACHE["data"]

    try:
        markets_raw = fetch_macro_geopolitical_markets(max_curated=20, max_dynamic=10)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Polymarket unavailable: {exc}")

    markets = []
    for event in markets_raw:
        prob = event.get("probability")
        if prob is None or prob == 0.0:
            continue

        change_24h = None
        if event.get("yes_token_id") and len(markets) < 15:
            try:
                change_24h = fetch_probability_change_24h(str(event["yes_token_id"]))
            except Exception:
                change_24h = None

        title = str(event.get("title") or "")
        display_label = str(event.get("display_label") or title)
        end_date_raw = event.get("end_date")
        ends = "TBD"
        if end_date_raw:
            try:
                ends = datetime.fromisoformat(str(end_date_raw).replace("Z", "+00:00")).strftime("%b %d")
            except Exception:
                ends = str(end_date_raw)

        markets.append(
            {
                "event_id": event.get("event_id"),
                "slug": event.get("event_slug"),
                "display_label": display_label,
                "category": event.get("category", "Markets"),
                "label": display_label,
                "title": title,
                "subtitle": event.get("subtitle"),
                "ends": ends,
                "end_date": end_date_raw,
                "probability": nan_safe(prob),
                "prob_24h_change": nan_safe(change_24h),
                "leading_outcome": event.get("leading_outcome"),
                "market_type": event.get("market_type", "binary"),
                "interpretation": _plain_english_interpretation(
                    display_label=display_label,
                    probability=float(prob),
                    leading_outcome=event.get("leading_outcome"),
                    market_type=str(event.get("market_type", "binary")),
                    change_24h=nan_safe(change_24h),
                ),
                "volume_24hr": nan_safe(event.get("volume_24hr")),
                "liquidity": nan_safe(event.get("liquidity")),
                "tags": event.get("tags", []),
                "equity_exposure": event.get("equity_exposure") or _derive_equity_exposure(title),
                "source": event.get("source", "live"),
            }
        )

    macro_heat = _build_macro_heat(markets)
    probabilities = [market["probability"] for market in markets if market["probability"] is not None]
    summary = {
        "bullish_count": sum(1 for prob in probabilities if prob > 0.55),
        "bearish_count": sum(1 for prob in probabilities if prob < 0.45),
        "total_count": len(markets),
        "avg_conviction": nan_safe(sum(probabilities) / len(probabilities)) if probabilities else None,
    }

    payload = {
        "markets": markets,
        "macro_heat": macro_heat,
        "summary": summary,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
    }
    _GEO_CACHE["data"] = payload
    _GEO_CACHE["fetched_at"] = now
    return payload
