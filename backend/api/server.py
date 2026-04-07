import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytz
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DATA_DIR, HEATMAP_MIN_MOVE, LIQUIDITY_THRESHOLD

app = FastAPI(title="Polymarket Signal API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    return {
        "ticker": row["ticker"],
        "date": row["date"],
        "pre_open_implied_prob": nan_safe(row.get("pre_open_implied_prob")),
        "overnight_prob_change": nan_safe(row.get("overnight_prob_change")),
        "pre_open_pm_volume": nan_safe(row.get("pre_open_pm_volume")),
        "pre_open_buy_ratio": nan_safe(row.get("pre_open_buy_ratio")),
        "is_high_liquidity": bool(row.get("is_high_liquidity", False)),
        "signal_direction": row.get("signal_direction", "UNKNOWN"),
        "signal_quality_score": nan_safe(row.get("signal_quality_score")),
        "true_sentiment": nan_safe(row.get("true_sentiment")),
    }


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

    latest_signal = {}
    try:
        signals_df = load_csv("signals_today.csv")
        signal_row = signals_df[signals_df["ticker"] == ticker]
        if not signal_row.empty:
            latest_signal = serialize_signal_row(signal_row.iloc[0])
    except HTTPException:
        latest_signal = {}

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
