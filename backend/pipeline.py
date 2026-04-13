from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from datetime import datetime as dt
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytz
import requests
import statsmodels.api as sm
import yfinance as yf
from scipy.stats import norm

try:
    import pandas_market_calendars as mcal  # optional
except Exception:
    mcal = None

try:
    from config import (
        DAYS_BACK,
        GAMMA_API,
        GOLDSKY_URL,
        INTRADAY_WINDOW_MINUTES,
        MAX_WORKERS,
        START_DAY_FROM_NOW,
        TIMEZONE_MAP,
    )
except ImportError:  # pragma: no cover - fallback for package imports
    from backend.config import (
        DAYS_BACK,
        GAMMA_API,
        GOLDSKY_URL,
        INTRADAY_WINDOW_MINUTES,
        MAX_WORKERS,
        START_DAY_FROM_NOW,
        TIMEZONE_MAP,
    )

try:
    from config import (
        FIREWALL_HOUR_NY,
        FIREWALL_MINUTE_NY,
        LIQUIDITY_THRESHOLD,
        RISK_FREE_ANN,
        SQ_SPREAD_MED,
        SQ_SPREAD_TIGHT,
        SQ_VOLUME_HIGH,
        SQ_VOLUME_MED,
    )
except ImportError:  # pragma: no cover - fallback for package imports
    from backend.config import (
        FIREWALL_HOUR_NY,
        FIREWALL_MINUTE_NY,
        LIQUIDITY_THRESHOLD,
        RISK_FREE_ANN,
        SQ_SPREAD_MED,
        SQ_SPREAD_TIGHT,
        SQ_VOLUME_HIGH,
        SQ_VOLUME_MED,
    )

try:
    from config import EQUITY_TICKERS as _CONFIG_EQUITY_TICKERS
except ImportError:
    try:
        from backend.config import EQUITY_TICKERS as _CONFIG_EQUITY_TICKERS
    except ImportError:
        _CONFIG_EQUITY_TICKERS = None

class Orderbook:
    def __init__(
        self,
        days_back=DAYS_BACK,
        max_workers=MAX_WORKERS,
        start_day_from_now=START_DAY_FROM_NOW,
        intraday_minutes=INTRADAY_WINDOW_MINUTES,
    ):
        self.days_back = days_back
        self.start_day_from_now = start_day_from_now
        self.intraday_minutes = intraday_minutes
        self.max_workers = max_workers
        self.gamma_api = GAMMA_API
        self.goldsky_url = GOLDSKY_URL
        self.timezone_map = TIMEZONE_MAP
        self.asset_keys = []
        self.df = pd.DataFrame()
        self.orderbook = pd.DataFrame()

    def fetch_raw_orderbook(self, keys):
        self.df = pd.DataFrame()
        self.orderbook = pd.DataFrame()
        self._get_multiple_tokens(keys)
        self._process_all_orderfills()
        if self.orderbook.empty:
            return self.orderbook.copy()
        self.orderbook["TIMESTAMP"] = pd.to_datetime(self.orderbook["TIMESTAMP"], utc=True)
        self.orderbook = self.orderbook.sort_values(by=["KEY", "TIMESTAMP"], ascending=[True, True]).reset_index(drop=True)
        return self.orderbook.copy()

    def attach_stock_data(self, orderbook=None):
        if orderbook is not None:
            self.orderbook = orderbook.copy()
        if self.orderbook.empty:
            return self.orderbook.copy()

        def get_outcome_date(row):
            base_date = row["TIMESTAMP"].astimezone(
                pytz.timezone(self.timezone_map.get(row["country"].lower(), "UTC"))
            ).date()
            return base_date + timedelta(days=1) if 0 <= row["REL_HOUR"] < 8 else base_date

        self.orderbook["market_date"] = self.orderbook.apply(get_outcome_date, axis=1)
        stock_df = self._pull_stock_close()
        self.orderbook = self.orderbook.merge(
            stock_df,
            left_on=["KEY", "market_date"],
            right_on=["KEY", "date"],
            how="left",
        )
        self.orderbook["TIMESTAMP"] = pd.to_datetime(self.orderbook["TIMESTAMP"], utc=True)
        self.orderbook = self.orderbook.sort_values("TIMESTAMP")

        stock_min = self._pull_stock_minutes(
            minutes=self.intraday_minutes,
            window_size=120 // self.intraday_minutes,
        )

        if not stock_min.empty:
            stock_min["TIMESTAMP"] = pd.to_datetime(stock_min["TIMESTAMP"], utc=True)
            stock_min = stock_min.sort_values("TIMESTAMP")
            self.orderbook = pd.merge_asof(
                self.orderbook,
                stock_min,
                on="TIMESTAMP",
                by="KEY",
                direction="backward",
                tolerance=pd.Timedelta(f"{self.intraday_minutes}min"),
            )
        else:
            suffix = f"_{self.intraday_minutes}m"
            for column in [
                f"stock_close{suffix}",
                f"stock_high{suffix}",
                f"stock_low{suffix}",
                f"stock_open{suffix}",
                f"stock_volume{suffix}",
                f"stock_avg{suffix}",
                f"stock_vol{suffix}",
            ]:
                self.orderbook[column] = np.nan

        self.orderbook = self.orderbook.drop(columns=["date", "market_date"], errors="ignore").reset_index(drop=True)
        self.orderbook = self.orderbook.sort_values(by=["KEY", "TIMESTAMP"], ascending=[True, True])
        return self.orderbook.copy()

    def get_data(self, keys):
        raw_orderbook = self.fetch_raw_orderbook(keys)
        return self.attach_stock_data(raw_orderbook)

    def save_raw(self, path: Path) -> None:
        """Save the raw orderbook to CSV, stripping timezone info for compatibility."""
        df = self.orderbook.copy()
        for col in df.select_dtypes(include=["datetimetz"]).columns:
            df[col] = df[col].dt.tz_localize(None)
        df.to_csv(path, index=False)

    def _get_market_tokens(self, key_tuple):
        key = key_tuple[0]
        country = key_tuple[1].lower()
        local_timezone = pytz.timezone(self.timezone_map.get(country, "UTC"))
        now_local = dt.now(local_timezone) - timedelta(days=self.start_day_from_now)
        data = []
        for i in range(self.days_back):
            target = now_local - timedelta(days=i)
            slug = f"{key}-up-or-down-on-{target.strftime('%B-%-d-%Y').lower()}"
            try:
                response = requests.get(f"{self.gamma_api}/{slug}")
                if response.status_code == 200:
                    res_json = response.json()
                    if res_json.get("markets"):
                        market = res_json["markets"][0]
                        condition_id = market.get("conditionId")
                        tokens = json.loads(market.get("clobTokenIds", "[]"))
                        data.append([key.upper(), target.date(), tokens[0], tokens[1], condition_id, country])
            except Exception as exc:
                print(f"error fetching {slug}: {exc}")
        return pd.DataFrame(data, columns=["key", "ts", "up_token", "down_token", "condition_id", "country"])

    def _get_multiple_tokens(self, keys):
        self.asset_keys = []
        all_dfs = []
        for key in keys:
            asset_name = key[0] if isinstance(key, tuple) else key
            self.asset_keys.append(asset_name.upper())
            print(f"--- collecting & processing: {asset_name.upper()} ---")
            raw = self._get_market_tokens(key if isinstance(key, tuple) else (key, "new york"))
            all_dfs.append(raw)

        if not all_dfs:
            return pd.DataFrame()
        self.df = pd.concat(all_dfs).sort_values(["ts", "key"]).reset_index(drop=True)
        return self.df

    def _get_single_orderfills(self, asset_id, start_dt, end_dt, up_down_key):
        query = """query($a: String!, $g: BigInt!, $l: BigInt!) {
            orderFilledEvents(
              where: {
                or: [
                  {
                    timestamp_gte: $g,
                    timestamp_lte: $l,
                    takerAssetId: $a,
                    makerAssetId: "0"
                  },
                  {
                    timestamp_gte: $g,
                    timestamp_lte: $l,
                    makerAssetId: $a,
                    takerAssetId: "0"
                  }
                ]
              }
              orderBy: timestamp
              orderDirection: desc
            ) {
              id
              timestamp
              maker
              taker
              takerAssetId
              makerAssetId
              makerAmountFilled
              takerAmountFilled
            }
        }"""
        ts_gte = int(start_dt.timestamp())
        ts_lte = int(end_dt.timestamp())
        try:
            response = requests.post(
                self.goldsky_url,
                json={"query": query, "variables": {"a": asset_id, "g": str(ts_gte), "l": str(ts_lte)}},
                timeout=15,
            )
            if response.status_code != 200 or "data" not in response.json():
                return pd.DataFrame()
            events = response.json()["data"]["orderFilledEvents"]
            if not events:
                return pd.DataFrame()
            data = []
            for event in events:
                buy_shares = "BUY" if str(event["takerAssetId"]) == "0" else "SELL"
                maker_amount = int(event["makerAmountFilled"]) / 1e6
                taker_amount = int(event["takerAmountFilled"]) / 1e6
                price = (
                    taker_amount / maker_amount
                    if event["takerAssetId"] == "0"
                    else maker_amount / taker_amount
                ) if maker_amount != 0 else 0
                price_up = round(price, 4) if up_down_key == "UP" else round(1 - price, 4)
                if price in (0, 1):
                    log_odds = np.nan
                else:
                    log_odds = round(np.log(price / (1 - price)), 4)
                data.append(
                    {
                        "UP_DOWN": up_down_key,
                        "TIMESTAMP": dt.fromtimestamp(int(event["timestamp"]), tz=timezone.utc),
                        "MAKER": event["maker"],
                        "TAKER": event["taker"],
                        "SHARES": round(maker_amount, 4),
                        "USDC": round(taker_amount, 4),
                        "PRICE": round(price, 4),
                        "PRICE_UP": price_up,
                        "BUY_SELL": buy_shares,
                        "id": event["id"],
                        "log_odds": log_odds,
                    }
                )
            return pd.DataFrame(data)
        except Exception:
            return pd.DataFrame()

    def _process_all_orderfills(self):
        tasks = []
        now_utc = dt.now(timezone.utc) - timedelta(days=self.start_day_from_now)

        for _, row in self.df.iterrows():
            tz_name = self.timezone_map.get(row["country"], "UTC")
            local_tz = pytz.timezone(tz_name)
            target_midnight = local_tz.localize(dt.combine(row["ts"], dt.min.time()))
            prev_close_local = target_midnight - timedelta(hours=8)
            market_start_utc = prev_close_local.astimezone(pytz.UTC)
            # Hourly chunks are materially faster than 12-minute slices while
            # still keeping individual GraphQL queries at a manageable size.
            hour_step = 1.0
            for side in ["up_token", "down_token"]:
                hour = 0.0
                while hour < 24:
                    chunk_start = market_start_utc + timedelta(hours=hour)
                    if chunk_start >= now_utc:
                        break
                    chunk_end = chunk_start + timedelta(hours=hour_step)
                    tasks.append(
                        {
                            "a": row[side],
                            "s_dt": chunk_start,
                            "e_dt": chunk_end,
                            "side": "UP" if "up" in side else "DOWN",
                            "key": row["key"],
                            "country": row["country"],
                        }
                    )
                    hour += hour_step

        def fetch(task):
            res = self._get_single_orderfills(task["a"], task["s_dt"], task["e_dt"], task["side"])
            if not res.empty:
                res["KEY"] = task["key"]
                res["country"] = task["country"]
            return res

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results = list(executor.map(fetch, tasks))

        if not results:
            return pd.DataFrame()
        results = [result for result in results if not result.empty]
        expected_cols = ["KEY", "UP_DOWN", "TIMESTAMP", "MAKER", "TAKER", "SHARES", "USDC", "PRICE", "PRICE_UP", "BUY_SELL", "id"]
        if not results:
            return pd.DataFrame(columns=expected_cols)
        df = pd.concat(results, ignore_index=True)
        if "id" in df.columns:
            df.drop_duplicates(subset=["id"], keep="first", inplace=True)

        def get_relative_hr(row):
            tz = pytz.timezone(self.timezone_map.get(row["country"].lower(), "UTC"))
            local_time = tz.normalize(row["TIMESTAMP"].astimezone(tz))
            return (local_time.hour + local_time.minute / 60 + local_time.second / 3600 + 8) % 24

        df["REL_HOUR"] = df.apply(get_relative_hr, axis=1)
        df["TIME_TO_EXP"] = (24.0 - df["REL_HOUR"]).clip(lower=0)
        self.orderbook = df.sort_values(by=["KEY", "TIMESTAMP"], ascending=[True, False]).reset_index(drop=True)
        cols = ["KEY", "REL_HOUR", "TIME_TO_EXP"] + [
            column
            for column in self.orderbook.columns
            if column not in ["id", "KEY", "REL_HOUR", "TIME_TO_EXP"]
        ]
        self.orderbook = self.orderbook[cols]
        return self.orderbook

    def _pull_stock_close(self):
        tickers = self.orderbook["KEY"].unique().tolist()
        start = self.orderbook["TIMESTAMP"].min()
        end = self.orderbook["TIMESTAMP"].max()
        df = yf.download(
            tickers,
            start=start.date(),
            end=(end + timedelta(days=1)).date(),
            progress=False,
            auto_adjust=True,
        )
        df = df[["Open", "Close"]].stack(future_stack=True).reset_index()

        df.columns = ["date", "KEY", "close", "open"]
        df["date"] = df["date"].dt.date
        valid_days = self.orderbook.assign(date=self.orderbook["TIMESTAMP"].dt.date)[["KEY", "date"]].drop_duplicates()
        conditions = [df["close"] > df["open"], df["close"] < df["open"]]
        df["stock_up"] = np.select(conditions, [1, 0], default=0.5)
        df = df.rename(columns={"close": "stock_close_day", "open": "stock_open_day"})

        return df.merge(valid_days, on=["KEY", "date"])[["KEY", "date", "stock_open_day", "stock_close_day"]]

    def _pull_stock_minutes(self, minutes=5, window_size=5):
        keys = self.orderbook["KEY"].unique().tolist()
        start = self.orderbook["TIMESTAMP"].min()
        end = self.orderbook["TIMESTAMP"].max()
        cutoff = dt.now(pytz.UTC) - timedelta(days=59)
        fetch_start = max(start, cutoff)

        if fetch_start >= end:
            return pd.DataFrame()
        df = yf.download(
            keys,
            start=fetch_start.date(),
            end=(end + timedelta(days=1)).date(),
            interval=f"{minutes}m",
            progress=False,
            auto_adjust=True,
        )
        suffix = f"_{minutes}m"
        if isinstance(df.columns, pd.MultiIndex):
            df = df[["High", "Low", "Close", "Open", "Volume"]].stack(level=1, future_stack=True).reset_index()
            df.columns = [
                "TIMESTAMP",
                "KEY",
                f"stock_close{suffix}",
                f"stock_high{suffix}",
                f"stock_low{suffix}",
                f"stock_open{suffix}",
                f"stock_volume{suffix}",
            ]
        else:
            df = df[["High", "Low", "Close", "Open", "Volume"]].reset_index()
            df["KEY"] = keys[0]
            df.columns = [
                "TIMESTAMP",
                f"stock_close{suffix}",
                f"stock_high{suffix}",
                f"stock_low{suffix}",
                f"stock_open{suffix}",
                f"stock_volume{suffix}",
                "KEY",
            ]

        df[f"stock_avg{suffix}"] = (
            df[f"stock_high{suffix}"] + df[f"stock_low{suffix}"] + df[f"stock_close{suffix}"]
        ) / 3
        if df["TIMESTAMP"].dt.tz is None:
            df["TIMESTAMP"] = df["TIMESTAMP"].dt.tz_localize("UTC")
        else:
            df["TIMESTAMP"] = df["TIMESTAMP"].dt.tz_convert("UTC")
        df = df.sort_values(["KEY", "TIMESTAMP"])
        df["returns"] = df.groupby("KEY")[f"stock_close{suffix}"].transform(lambda x: np.log(x / x.shift(1)))
        ann_factor = np.sqrt((60 / minutes * 6.5) * 252)
        df[f"stock_vol{suffix}"] = df.groupby("KEY")["returns"].transform(
            lambda x: x.rolling(window=window_size).std() * ann_factor
        )
        return df.sort_values("TIMESTAMP")


def collapse_to_windows(df, minutes=INTRADAY_WINDOW_MINUTES, risk_free_ann=RISK_FREE_ANN):
    if df.empty:
        return pd.DataFrame()

    window = f"{minutes}Min"
    df = df.copy()
    df["vol_bull"] = np.where(
        ((df["BUY_SELL"] == "BUY") & (df["UP_DOWN"] == "UP"))
        | ((df["BUY_SELL"] == "SELL") & (df["UP_DOWN"] == "DOWN")),
        df["USDC"],
        0,
    )

    df["vol_bear"] = np.where(
        ((df["BUY_SELL"] == "SELL") & (df["UP_DOWN"] == "UP"))
        | ((df["BUY_SELL"] == "BUY") & (df["UP_DOWN"] == "DOWN")),
        df["USDC"],
        0,
    )

    df = df.set_index("TIMESTAMP")
    suffix = f"_{minutes}m"
    agg_dict = {
        "TIME_TO_EXP": "last",
        "PRICE_UP": ["first", "last", "mean", "max", "min"],
        "USDC": "sum",
        "SHARES": "count",
        "vol_bull": "sum",
        "vol_bear": "sum",
        "stock_open_day": "last",
        f"stock_close{suffix}": "last",
        f"stock_avg{suffix}": "mean",
        f"stock_vol{suffix}": "last",
    }

    collapsed = df.groupby("KEY").resample(window).agg(agg_dict)
    collapsed.columns = [
        "time_to_exp",
        "open_bet",
        "close_bet",
        "avg_price_up",
        "high_bet",
        "low_bet",
        "total_volume",
        "trade_count",
        "bull_volume",
        "bear_volume",
        "stock_open_day",
        "stock_close",
        "stock_avg_period",
        "stock_vol",
    ]

    collapsed["poly_vol_imbalance"] = (collapsed["bull_volume"] / collapsed["bear_volume"]) - 1
    collapsed["poly_vol_imbalance"] = np.where(
        collapsed["poly_vol_imbalance"].isna(),
        1,
        collapsed["poly_vol_imbalance"],
    )
    collapsed.drop(columns=["bull_volume", "bear_volume"], inplace=True)

    collapsed = collapsed.dropna(
        subset=["avg_price_up", "stock_open_day", "stock_close", "stock_vol"]
    )
    stock_price = collapsed["stock_close"]
    strike = collapsed["stock_open_day"]
    sigma = collapsed["stock_vol"]
    time_to_expiry = ((collapsed["time_to_exp"] / 24) / 252).clip(lower=1e-9)

    d2 = (np.log(stock_price / strike) + (risk_free_ann - 0.5 * sigma**2) * time_to_expiry) / (
        sigma * np.sqrt(time_to_expiry).replace(0, np.nan)
    )
    collapsed["bs_neutral_prob"] = norm.cdf(d2.fillna(0))
    collapsed["true_sentiment"] = collapsed["avg_price_up"] - collapsed["bs_neutral_prob"]
    return collapsed.reset_index()


def check_lead_lag(df):
    if df.empty:
        return df.copy()

    df = df.sort_values(["KEY", "TIMESTAMP"]).copy()
    df["next_stock_move"] = np.log(df.groupby("KEY")["stock_close"].shift(-1) / df["stock_close"])
    df["curr_stock_move"] = np.log(df["stock_close"] / df.groupby("KEY")["stock_close"].shift(1))
    df["next_true_sent"] = df.groupby("KEY")["true_sentiment"].shift(-1) - df["true_sentiment"]
    df["abs_sentiment"] = df["true_sentiment"].abs()
    valid = df[df["time_to_exp"] > 0.5].dropna()
    overall_lead = valid["true_sentiment"].corr(valid["next_stock_move"])
    asset_lead = valid.groupby("KEY").apply(
        lambda x: x["true_sentiment"].corr(x["next_stock_move"]),
        include_groups=False,
    )
    overall_lag = valid["curr_stock_move"].corr(valid["next_true_sent"])
    asset_lag = valid.groupby("KEY").apply(
        lambda x: x["curr_stock_move"].corr(x["next_true_sent"]),
        include_groups=False,
    )

    print(f"Overall lead correlation: {overall_lead:.4f}")
    print("Lead correlation by asset:")
    print(asset_lead, "\n")
    print("-" * 30, "\n")
    print(f"Overall lag correlation: {overall_lag:.4f}")
    print("Lag correlation by asset:")
    print(asset_lag)
    return df


def analyse_sentiment_dynamics(df):
    cols = ["time_to_exp", "true_sentiment", "next_stock_move", "abs_sentiment", "curr_stock_move"]
    df = df.copy()
    df[cols] = df[cols].apply(pd.to_numeric, errors="coerce")
    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=cols)
    upper_limit = df["abs_sentiment"].quantile(0.95)
    df = df[df["abs_sentiment"] < upper_limit].copy()
    df["is_hit"] = (np.sign(df["true_sentiment"]) == np.sign(df["next_stock_move"])).astype(int)
    df["avg_trade"] = df["total_volume"] / df["trade_count"]
    df = df.dropna()

    print(f"{'percentile':<15} | {'min abs conviction':<20} | {'hit rate (%)':<12} | N")
    print("-" * 60)
    for percentile in [0.0, 0.5, 0.75, 0.90, 0.95]:
        thresh = df["abs_sentiment"].quantile(percentile)
        sub = df[df["abs_sentiment"] >= thresh]
        label = f"top {int((1 - percentile) * 100)}%" if percentile > 0 else "all signals"
        print(f"{label:<15} | {thresh:>20.4f} | {sub['is_hit'].mean() * 100:>11.2f}% | {len(sub)}")

    features = ["true_sentiment", "poly_vol_imbalance", "avg_trade", "stock_vol"]
    for var_num in [len(features) + 1]:
        print("\n" + "=" * 30 + "\nresults from polymarket sentiment on price change OLS:\n")
        results = []
        feature_subset = features[0:var_num]
        for asset, data in df.groupby("KEY"):
            data = data.dropna(subset=["next_stock_move"] + feature_subset)
            X = sm.add_constant(data[feature_subset])
            res = sm.OLS(data["next_stock_move"], X).fit(
                cov_type="HAC",
                cov_kwds={"maxlags": int(len(X) ** (1 / 3))},
            )
            results.append(
                {
                    "Asset": asset,
                    **res.params.to_dict(),
                    **res.tvalues.add_suffix("_t-stat").to_dict(),
                    "R2%": res.rsquared * 100,
                    "MAE": res.resid.abs().mean(),
                }
            )
        final_df = pd.DataFrame(results).set_index("Asset").drop(columns="const_t-stat")
        print(final_df)
        print("\ncoefficients*100 are pp increases in stock price following a 1 unit increase in polymarket conviction measure")

    print("\n" + "=" * 30 + "\nlogit for direction (up signal --> up move):\n")
    logit_results = []
    df["sig_up"] = (df["true_sentiment"] > 0).astype(int)
    df["mov_up"] = (df["next_stock_move"] > 0).astype(int)

    for asset, data in df.groupby("KEY"):
        data = data.dropna(subset=["mov_up", "sig_up"] + feature_subset)
        if len(data) < 20:
            continue
        X = sm.add_constant(data[["sig_up"] + features[1:]])
        try:
            res = sm.Logit(data["mov_up"], X).fit(disp=0)
            p_dn = 1 / (1 + np.exp(-res.params["const"]))
            p_up = 1 / (1 + np.exp(-(res.params["const"] + res.params["sig_up"])))
            logit_results.append(
                {
                    "asset": asset,
                    "z-Stat": res.tvalues["sig_up"],
                    "P(up|sig_down)%": p_dn * 100,
                    "P(up|sig_up)%": p_up * 100,
                    "P(up|sig_up) - P(up|sig_down)%": (p_up - p_dn) * 100,
                    "n": len(data),
                }
            )
        except Exception:
            continue
    print(pd.DataFrame(logit_results).set_index("asset"))

    print("\n" + "=" * 30)
    df["hour"] = pd.to_datetime(df["TIMESTAMP"]).dt.hour
    print("\nhit rate by hour:")
    print(df.groupby("hour")["is_hit"].mean())


def build_preopen_panel(orderbook: pd.DataFrame, target_date=None) -> pd.DataFrame:
    """
    Compute pre-open PM statistics directly from the raw orderbook.
    No stock data is required, so this remains valid before market open.
    """
    columns = [
        "ticker",
        "date",
        "pre_open_implied_prob",
        "overnight_prob_change",
        "pre_open_pm_volume",
        "pre_open_buy_ratio",
        "is_high_liquidity",
        "signal_direction",
        "signal_quality_score",
        "true_sentiment",
    ]
    if orderbook.empty:
        return pd.DataFrame(columns=columns)

    if target_date is None:
        target_date = dt.now(pytz.timezone("America/New_York")).date()

    ny_tz = pytz.timezone("America/New_York")
    firewall_dt = ny_tz.localize(
        dt.combine(
            target_date,
            dt.min.time().replace(hour=FIREWALL_HOUR_NY, minute=FIREWALL_MINUTE_NY),
        )
    ).astimezone(pytz.UTC)
    midnight_dt = ny_tz.localize(
        dt.combine(target_date, dt.min.time())
    ).astimezone(pytz.UTC)

    ts = pd.to_datetime(orderbook["TIMESTAMP"])
    if ts.dt.tz is None:
        ts = ts.dt.tz_localize("UTC")
    else:
        ts = ts.dt.tz_convert("UTC")

    today = orderbook.loc[(ts >= midnight_dt) & (ts < firewall_dt)].copy()
    if today.empty:
        return pd.DataFrame(columns=columns)

    today["vol_bull"] = np.where(
        ((today["BUY_SELL"] == "BUY") & (today["UP_DOWN"] == "UP"))
        | ((today["BUY_SELL"] == "SELL") & (today["UP_DOWN"] == "DOWN")),
        today["USDC"],
        0,
    )

    rows = []
    for ticker, group in today.groupby("KEY"):
        group = group.sort_values("TIMESTAMP")
        pre_open_implied_prob = group["PRICE_UP"].iloc[-1]
        midnight_prob = group["PRICE_UP"].iloc[0]
        overnight_prob_change = pre_open_implied_prob - midnight_prob
        pre_open_pm_volume = float(group["USDC"].sum())
        bull_volume = float(group["vol_bull"].sum())
        pre_open_buy_ratio = bull_volume / pre_open_pm_volume if pre_open_pm_volume > 0 else np.nan
        is_high_liquidity = pre_open_pm_volume >= LIQUIDITY_THRESHOLD
        signal_direction = "UP" if overnight_prob_change >= 0 else "DOWN"
        signal_quality_score = _compute_signal_quality(
            volume=pre_open_pm_volume,
            conviction_proxy=abs(overnight_prob_change),
        )

        rows.append(
            {
                "ticker": ticker,
                "date": str(target_date),
                "pre_open_implied_prob": round(pre_open_implied_prob, 4),
                "overnight_prob_change": round(overnight_prob_change, 4),
                "pre_open_pm_volume": round(pre_open_pm_volume, 2),
                "pre_open_buy_ratio": round(pre_open_buy_ratio, 4) if pd.notna(pre_open_buy_ratio) else np.nan,
                "is_high_liquidity": is_high_liquidity,
                "signal_direction": signal_direction,
                "signal_quality_score": signal_quality_score,
                "true_sentiment": None,
            }
        )

    return pd.DataFrame(rows, columns=columns).sort_values("ticker").reset_index(drop=True)


def _compute_signal_quality(volume: float, conviction_proxy: float) -> float:
    """
    Score signal quality 0-10 using fields available in the pre-open panel.
    Spread thresholds are reserved for later once depth data is added.
    """
    _ = (SQ_SPREAD_TIGHT, SQ_SPREAD_MED)

    score = 2.0

    if volume >= SQ_VOLUME_HIGH:
        score += 4
    elif volume >= SQ_VOLUME_MED:
        score += 2

    if conviction_proxy >= 0.05:
        score += 4
    elif conviction_proxy >= 0.02:
        score += 2

    return round(score, 1)


GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"
GAMMA_EVENTS_URL = "https://gamma-api.polymarket.com/events"
CLOB_PRICES_HISTORY_URL = "https://clob.polymarket.com/prices-history"
GAMMA_SEARCH_URL = "https://gamma-api.polymarket.com/public-search"
CLOB_BOOK_URL = "https://clob.polymarket.com/book"
GEOPOLITICAL_TAG_ID = 100265
MACRO_TAG_IDS = [2, 120]
TAG_FETCH_ORDER = [
    (120, 20),
    (2, 8),
    (GEOPOLITICAL_TAG_ID, 8),
]
MACRO_PRIORITY_KEYWORDS = [
    "fed",
    "rate",
    "inflation",
    "gdp",
    "tariff",
    "oil",
    "yield",
    "recession",
    "powell",
    "cpi",
]
PRIORITY_MACRO_TOPICS = [
    ("Fed rate cuts in 2026", "Fed rate cut 2026", "Rates", ["NVDA", "MSFT", "AAPL", "AMZN", "GOOGL", "META"]),
    ("Fed rate in December 2026", "federal funds rate december", "Rates", ["NVDA", "MSFT", "AAPL"]),
    ("ECB rate cut 2026", "ECB rate cut 2026", "Rates", ["GOOGL", "META", "AMZN"]),
    ("US inflation below 3%", "US inflation below 3 2026", "Rates", ["NVDA", "MSFT", "AAPL", "AMZN", "GOOGL", "META", "TSLA", "NFLX"]),
    ("US recession in 2026", "US recession 2026", "Rates", ["NVDA", "MSFT", "AAPL", "AMZN", "GOOGL", "META", "TSLA", "NFLX"]),
    ("US-China tariff deal", "US China tariff 2026", "Trade", ["AAPL", "NVDA", "AMZN", "TSLA"]),
    ("US tariff rate on China", "tariff rate China", "Trade", ["AAPL", "NVDA", "AMZN", "TSLA"]),
    ("US trade deficit", "US trade deficit", "Trade", ["AMZN", "AAPL"]),
    ("S&P 500 level end of 2026", "S&P 500 end 2026", "Markets", ["NVDA", "MSFT", "AAPL", "GOOGL", "META", "AMZN", "TSLA", "NFLX"]),
    ("Bitcoin above 100k", "Bitcoin above 100000 2026", "Markets", []),
    ("Oil price WTI above 80", "WTI above 80 2026", "Markets", ["TSLA"]),
    ("Ukraine ceasefire 2026", "Ukraine ceasefire 2026", "Conflict", ["MSFT", "GOOGL"]),
    ("Russia-Ukraine peace deal", "Russia Ukraine peace", "Conflict", ["MSFT", "GOOGL"]),
    ("Taiwan military conflict", "China invade Taiwan 2026", "Conflict", ["NVDA", "AAPL", "MSFT"]),
    ("Iran nuclear deal", "Iran nuclear deal 2026", "Conflict", ["TSLA"]),
    ("Middle East escalation", "Israel war 2026", "Conflict", []),
    ("Trump impeachment", "Trump impeach 2026", "Politics", ["NVDA", "MSFT", "AAPL", "GOOGL", "META", "AMZN", "TSLA", "NFLX"]),
    ("US election 2026 midterms", "US midterm election 2026", "Politics", ["NVDA", "MSFT", "AAPL", "GOOGL", "META", "AMZN", "TSLA", "NFLX"]),
    ("EU regulation AI", "EU AI Act regulation", "Politics", ["GOOGL", "META", "MSFT", "NVDA"]),
    ("Elon Musk DOGE", "DOGE Elon Musk 2026", "Politics", ["TSLA"]),
]
NOISE_KEYWORDS = [
    "lyman",
    "kostyantynivka",
    "bakhmut",
    "city by",
    "microstrategy sells",
    "sells any bitcoin",
    "who will be the next",
    "held by",
    "will russia capture",
    "will ukraine retake",
    "by what date",
]

DEFAULT_TIMEOUT = 15

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": "Mozilla/5.0 PolymarketRuntime/1.0",
        "Accept": "application/json",
    }
)

TICKER_ALIASES: Dict[str, List[str]] = {
    "NVDA": ["nvidia", "nvda", "nvidia corporation"],
    "GOOGL": ["alphabet", "google", "googl", "alphabet inc"],
    "AMZN": ["amazon", "amzn", "amazon.com"],
    "AAPL": ["apple", "aapl", "apple inc"],
    "MSFT": ["microsoft", "msft", "microsoft corp", "microsoft corporation"],
    "TSLA": ["tesla", "tsla", "tesla inc"],
    "NFLX": ["netflix", "nflx", "netflix inc"],
    "META": ["meta", "facebook", "meta platforms", "meta platforms inc"],
    "PLTR": ["palantir", "pltr", "palantir technologies"],
    "COIN": ["coinbase", "coin", "coinbase global"],
}


def _request_json(url: str, params: Optional[dict] = None, timeout: int = DEFAULT_TIMEOUT) -> Any:
    resp = SESSION.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _load_jsonish_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def _normalize_ticker(ticker: str) -> str:
    return str(ticker).strip().upper()


def _normalize_slug_piece(value: str) -> str:
    out: List[str] = []
    prev_dash = False
    for ch in str(value).lower().strip():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    return "".join(out).strip("-")


def _coerce_date(value: date | str | None) -> date:
    if value is None:
        return get_effective_nyse_trading_date()
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"Invalid target date: {value!r}")
    return parsed.date()


def _today_ny() -> date:
    return datetime.now(ZoneInfo("America/New_York")).date()


def _now_ny() -> datetime:
    return datetime.now(ZoneInfo("America/New_York"))


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    if month == 12:
        first_next = date(year + 1, 1, 1)
    else:
        first_next = date(year, month + 1, 1)
    cur = first_next - timedelta(days=1)
    while cur.weekday() != weekday:
        cur -= timedelta(days=1)
    return cur


def _observed_fixed_holiday(year: int, month: int, day: int) -> date:
    d = date(year, month, day)
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def _good_friday(year: int) -> date:
    # Anonymous Gregorian algorithm for Easter Sunday, then subtract 2 days.
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    easter = date(year, month, day)
    return easter - timedelta(days=2)


def _nyse_holidays(year: int) -> set[date]:
    return {
        _observed_fixed_holiday(year, 1, 1),
        _nth_weekday_of_month(year, 1, 0, 3),
        _nth_weekday_of_month(year, 2, 0, 3),
        _good_friday(year),
        _last_weekday_of_month(year, 5, 0),
        _observed_fixed_holiday(year, 6, 19),
        _observed_fixed_holiday(year, 7, 4),
        _nth_weekday_of_month(year, 9, 0, 1),
        _nth_weekday_of_month(year, 11, 3, 4),
        _observed_fixed_holiday(year, 12, 25),
    }


def _is_nyse_trading_day_fallback(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    return d not in _nyse_holidays(d.year)


def _next_nyse_trading_day_fallback(d: date) -> date:
    cur = d
    while not _is_nyse_trading_day_fallback(cur):
        cur += timedelta(days=1)
    return cur


def get_effective_nyse_trading_date(today: date | None = None) -> date:
    """
    Resolve the effective Polymarket lookup date from today's NY time.

    If today is an NYSE trading day, use today.
    Otherwise use the next NYSE trading day.
    """
    if today is None:
        today = _today_ny()
    if not isinstance(today, date):
        today = _coerce_date(today)

    if mcal is not None:
        try:
            cal = mcal.get_calendar("NYSE")
            sched = cal.schedule(start_date=today, end_date=today)
            if not sched.empty:
                return today
            nxt = today + timedelta(days=1)
            while True:
                sched = cal.schedule(start_date=nxt, end_date=nxt)
                if not sched.empty:
                    return nxt
                nxt += timedelta(days=1)
        except Exception:
            pass

    if _is_nyse_trading_day_fallback(today):
        return today
    return _next_nyse_trading_day_fallback(today)


def get_effective_nyse_market_date(now: datetime | None = None) -> date:
    """
    Resolve the market date for NYSE-like assets.

    If the market is already closed today, use the next trading day.
    Otherwise use today when it is a trading day.
    """
    et = ZoneInfo("America/New_York")
    if now is None:
        now = _now_ny()
    elif now.tzinfo is None:
        now = now.replace(tzinfo=et)
    else:
        now = now.astimezone(et)

    today = now.date()

    if mcal is not None:
        try:
            cal = mcal.get_calendar("NYSE")
            cur = today
            for _ in range(14):
                sched = cal.schedule(start_date=cur, end_date=cur)
                if not sched.empty:
                    market_close = pd.to_datetime(sched.iloc[0]["market_close"]).tz_convert(et)
                    if now < market_close:
                        return cur
                cur += timedelta(days=1)
        except Exception:
            pass

    if _is_nyse_trading_day_fallback(today):
        if now.hour < 16:
            return today
        return _next_nyse_trading_day_fallback(today + timedelta(days=1))
    return _next_nyse_trading_day_fallback(today)


def get_effective_crypto_market_date(now: datetime | None = None) -> date:
    """
    Resolve the market date for crypto up/down markets.

    The current market day rolls over at 12:00 ET.
    """
    et = ZoneInfo("America/New_York")
    if now is None:
        now = _now_ny()
    elif now.tzinfo is None:
        now = now.replace(tzinfo=et)
    else:
        now = now.astimezone(et)

    return now.date() if now.hour < 12 else now.date() + timedelta(days=1)


def build_up_down_slug(symbol: str, target_date: date) -> str:
    ticker = _normalize_ticker(symbol)
    aliases = TICKER_ALIASES.get(ticker)
    if aliases and len(aliases) > 0:
        piece = _normalize_slug_piece(aliases[0])
    else:
        piece = _normalize_slug_piece(symbol)
    month_long = target_date.strftime("%B").lower()
    return f"{piece}-up-or-down-on-{month_long}-{target_date.day}-{target_date.year}"


def _date_variants(trade_date: date) -> List[str]:
    month_long = trade_date.strftime("%B").lower()
    month_short = trade_date.strftime("%b").lower()
    day = trade_date.day
    year = trade_date.year
    return [
        trade_date.isoformat(),
        f"{month_long} {day}",
        f"{month_short} {day}",
        f"{month_long} {day}, {year}",
        f"{month_short} {day}, {year}",
        f"{month_long} {day} {year}",
        f"{month_short} {day} {year}",
        f"{month_long}-{day}-{year}",
        f"{month_short}-{day}-{year}",
        f"{day} {month_long}",
        f"{day} {month_short}",
    ]


def _up_down_phrase_variants(trade_date: date) -> List[str]:
    month_long = trade_date.strftime("%B").lower()
    month_short = trade_date.strftime("%b").lower()
    day = trade_date.day
    return [
        f"up or down on {month_long} {day}?",
        f"up or down on {month_short} {day}?",
    ]


def _slug_candidates(ticker: str, trade_date: date) -> List[str]:
    ticker_piece = _normalize_slug_piece(ticker)
    month_long = trade_date.strftime("%B").lower()
    month_short = trade_date.strftime("%b").lower()
    day = str(trade_date.day)
    year = str(trade_date.year)
    return [
        f"{ticker_piece}-up-or-down-on-{month_long}-{day}-{year}",
        f"{ticker_piece}-up-or-down-on-{month_short}-{day}-{year}",
    ]


def _text_of_record(record: dict) -> str:
    parts = [
        record.get("question", ""),
        record.get("title", ""),
        record.get("slug", ""),
        record.get("description", ""),
        record.get("closeTime", ""),
        record.get("endDate", ""),
    ]
    return " ".join(str(p or "") for p in parts).lower()


def _is_strict_up_down_stock_market(record: dict, ticker: str, target_date: date) -> bool:
    ticker = _normalize_ticker(ticker)
    aliases = [ticker.lower()] + TICKER_ALIASES.get(ticker, [])
    slug = str(record.get("slug", "") or "").lower()
    question = str(record.get("question", "") or "").lower()
    title = str(record.get("title", "") or "").lower()
    up_down_variants = _up_down_phrase_variants(target_date)
    exact_phrase_hits = any(phrase in question or phrase in title for phrase in up_down_variants)

    alias_hit = any(alias in question or alias in title or alias in slug for alias in aliases)
    up_down_hit = exact_phrase_hits
    slug_hit = any(cand == slug or slug.startswith(cand) for cand in _slug_candidates(ticker, target_date))

    return alias_hit and up_down_hit and slug_hit


def _fetch_active_markets(limit: int = 200, max_pages: int = 8) -> List[dict]:
    rows: List[dict] = []
    for page in range(max_pages):
        params = {
            "active": "true",
            "closed": "false",
            "limit": limit,
            "offset": page * limit,
        }
        data = _request_json(GAMMA_MARKETS_URL, params=params)
        if not isinstance(data, list):
            raise ValueError("Unexpected response from Polymarket markets API")
        if not data:
            break
        rows.extend(data)
    return rows


def _fetch_active_events(limit: int = 200, max_pages: int = 20) -> List[dict]:
    rows: List[dict] = []
    for page in range(max_pages):
        params = {
            "active": "true",
            "closed": "false",
            "limit": limit,
            "offset": page * limit,
        }
        data = _request_json(GAMMA_EVENTS_URL, params=params)
        if not isinstance(data, list):
            raise ValueError("Unexpected response from Polymarket events API")
        if not data:
            break
        rows.extend(data)
    return rows


def _fetch_event_detail(event_id: Any) -> dict:
    data = _request_json(f"{GAMMA_EVENTS_URL}/{event_id}")
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected event response for event_id={event_id}")
    return data


def _fetch_market_by_slug(slug: str) -> Optional[dict]:
    try:
        data = _request_json(f"{GAMMA_MARKETS_URL}/slug/{slug}")
    except Exception:
        return None
    if isinstance(data, dict) and data:
        return data
    return None


def _get_daily_market_context(ticker: str, target_date: date) -> dict:
    ticker = _normalize_ticker(ticker)
    for cand in _slug_candidates(ticker, target_date):
        market = _fetch_market_by_slug(cand)
        if market is None:
            continue

        token_ids = extract_token_ids(market)
        return {
            "ticker": ticker,
            "target_date": target_date.isoformat(),
            "market_slug": market.get("slug"),
            "market_id": market.get("id"),
            "question": market.get("question"),
            "market_created_at": market.get("createdAt"),
            "market_updated_at": market.get("updatedAt"),
            "fetched_at": datetime.now(ZoneInfo("America/New_York")).isoformat(),
            "market": market,
            "yes_token_id": token_ids.get("yes_token_id"),
        }

    return {
        "ticker": ticker,
        "target_date": target_date.isoformat(),
        "market_slug": None,
        "market_id": None,
        "question": None,
        "market_created_at": None,
        "market_updated_at": None,
        "fetched_at": datetime.now(ZoneInfo("America/New_York")).isoformat(),
        "market": None,
        "yes_token_id": None,
    }


def _score_record(record: dict, ticker: str, target_date: date) -> tuple:
    ticker = _normalize_ticker(ticker)
    aliases = [ticker.lower()] + TICKER_ALIASES.get(ticker, [])
    slug = str(record.get("slug", "") or "").lower()
    text = _text_of_record(record)
    date_variants = _date_variants(target_date)
    slug_variants = _slug_candidates(ticker, target_date)

    alias_hits = sum(1 for alias in aliases if alias in text or alias in slug)
    date_hits = sum(1 for phrase in date_variants if phrase in text or phrase in slug)
    up_down_hits = int("up" in text or "up" in slug) + int("down" in text or "down" in slug)
    slug_hits = sum(1 for cand in slug_variants if cand == slug or slug.startswith(cand))

    vol = record.get("volume") or record.get("volumeNum") or 0.0
    liq = record.get("liquidity") or record.get("liquidityNum") or 0.0
    try:
        vol = float(vol)
    except Exception:
        vol = 0.0
    try:
        liq = float(liq)
    except Exception:
        liq = 0.0

    return slug_hits, alias_hits, date_hits, up_down_hits, vol, liq


def _best_market_from_records(records: Iterable[dict], ticker: str, target_date: date) -> Optional[dict]:
    scored: List[tuple[tuple, dict]] = []
    for record in records:
        if not _is_strict_up_down_stock_market(record, ticker, target_date):
            continue
        score = _score_record(record, ticker, target_date)
        scored.append((score, record))

    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _get_active_universe() -> tuple[List[dict], List[dict]]:
    markets = _fetch_active_markets()
    events = _fetch_active_events()
    return markets, events


def _find_market_from_event(event: dict, ticker: str, target_date: date) -> Optional[dict]:
    markets = event.get("markets")
    if isinstance(markets, list) and markets:
        market = _best_market_from_records(markets, ticker, target_date)
        if market is not None:
            return market
    event_id = event.get("id")
    if event_id is None:
        return None
    try:
        detail = _fetch_event_detail(event_id)
        detail_markets = detail.get("markets")
        if isinstance(detail_markets, list) and detail_markets:
            market = _best_market_from_records(detail_markets, ticker, target_date)
            if market is not None:
                return market
    except Exception:
        return None
    return None


def _find_polymarket_stock_market_from_universe(
    ticker: str,
    target_date: date,
    markets: Optional[List[dict]] = None,
    events: Optional[List[dict]] = None,
) -> dict | None:
    context = _get_daily_market_context(ticker, target_date)
    return context.get("market")


def find_polymarket_stock_market(ticker: str, target_date: str) -> dict | None:
    trade_date = _coerce_date(target_date)
    return _find_polymarket_stock_market_from_universe(ticker, trade_date)


def extract_token_ids(market: dict) -> dict:
    yes_id = None

    for key in ("yesTokenId", "yes_token_id", "yesTokenID"):
        if market.get(key) is not None:
            yes_id = str(market.get(key))
            break

    if yes_id is None:
        tokens = market.get("tokens", [])
        if isinstance(tokens, list):
            for token in tokens:
                outcome = str(token.get("outcome", "")).strip().lower()
                token_id = token.get("token_id") or token.get("id") or token.get("asset_id")
                if outcome == "yes" and token_id is not None:
                    yes_id = str(token_id)

    if yes_id is None:
        for field in ("clobTokenIds", "tokenIds"):
            value = market.get(field)
            if not value:
                continue
            parts = [str(x) for x in _load_jsonish_list(value) if x is not None]
            if len(parts) >= 1:
                yes_id = yes_id or parts[0]

    return {"yes_token_id": yes_id}


def _extract_market_probabilities(market: dict) -> tuple[Optional[float], Optional[float]]:
    outcomes = market.get("outcomes")
    prices = market.get("outcomePrices")
    if not outcomes or not prices:
        return None, None

    outcomes = _load_jsonish_list(outcomes)
    prices = _load_jsonish_list(prices)
    if not outcomes or not prices:
        return None, None

    mapping: Dict[str, float] = {}
    for outcome, price in zip(outcomes, prices):
        try:
            mapping[str(outcome).strip().lower()] = float(price)
        except Exception:
            continue

    up = mapping.get("up")
    if up is None:
        up = mapping.get("yes")
    down = mapping.get("down")
    if down is None:
        down = mapping.get("no")
    return up, down


def _extract_up_probability_from_market(market: dict) -> Optional[float]:
    up_prob, _down_prob = _extract_market_probabilities(market)
    return up_prob


def _best_market_by_volume(markets: Any) -> Optional[dict]:
    if not isinstance(markets, list):
        return None
    best_market = None
    best_volume = -1.0
    for market in markets:
        try:
            vol = float(
                market.get("volume24hr")
                or market.get("volume_24hr")
                or market.get("volumeNum")
                or market.get("volume")
                or 0
            )
        except Exception:
            vol = 0.0
        if vol > best_volume:
            best_volume = vol
            best_market = market
    return best_market


def _geo_relevance_score(event: dict) -> float:
    title = str(event.get("title") or event.get("question") or "").lower()
    score = float(event.get("volume_24hr") or event.get("volume24hr") or 0)
    keyword_boost = sum(1 for keyword in MACRO_PRIORITY_KEYWORDS if keyword in title)
    if keyword_boost:
        score += 10_000_000 * keyword_boost
    return score


def _parse_geo_event(event: dict) -> dict:
    markets = event.get("markets", [])
    best_market = _best_market_by_volume(markets)

    probability = None
    yes_token_id = None
    end_date = None
    market_slug = None
    leading_outcome = None
    market_type = "binary"

    if best_market:
        prices = _load_jsonish_list(best_market.get("outcomePrices", []))
        outcomes = _load_jsonish_list(best_market.get("outcomes", []))
        tokens = _load_jsonish_list(best_market.get("clobTokenIds", []))
        market_type = "categorical" if len(outcomes) > 2 else "binary"
        leading_index = 0

        outcome_map: Dict[str, float] = {}
        for outcome, price in zip(outcomes, prices):
            try:
                outcome_map[str(outcome).strip().lower()] = float(price)
            except Exception:
                continue

        probability = outcome_map.get("yes")
        if probability is None:
            probability = outcome_map.get("up")
        if probability is None and prices:
            try:
                float_prices = [float(price) for price in prices]
                probability = max(float_prices)
                leading_index = float_prices.index(probability)
                if leading_index < len(outcomes):
                    leading_outcome = str(outcomes[leading_index])
            except Exception:
                probability = None

        if leading_outcome is None and probability is not None and market_type == "binary":
            if probability >= 0.5:
                leading_outcome = "Yes"
            else:
                leading_outcome = "No"

        if tokens:
            token_index = min(leading_index, len(tokens) - 1)
            yes_token_id = str(tokens[token_index])
        end_date = best_market.get("endDate") or best_market.get("endDateIso")
        market_slug = best_market.get("slug")

    tags = []
    for tag in event.get("tags", []) or []:
        if isinstance(tag, dict):
            slug = tag.get("slug")
            if slug:
                tags.append(str(slug))

    return {
        "event_id": event.get("id"),
        "event_slug": event.get("slug") or market_slug,
        "market_slug": market_slug,
        "title": event.get("title") or event.get("question"),
        "subtitle": event.get("subtitle"),
        "probability": probability,
        "leading_outcome": leading_outcome,
        "market_type": market_type,
        "volume_24hr": event.get("volume_24hr") or event.get("volume24hr"),
        "liquidity": event.get("liquidity"),
        "end_date": end_date,
        "yes_token_id": yes_token_id,
        "market_count": len(markets) if isinstance(markets, list) else 0,
        "tags": tags,
        "source": "live",
    }


def _extract_probability_robust(market: dict) -> tuple[float | None, str | None, str]:
    raw_prices = market.get("outcomePrices", "[]")
    raw_outcomes = market.get("outcomes", "[]")

    try:
        prices = json.loads(raw_prices) if isinstance(raw_prices, str) else (raw_prices or [])
        outcomes = json.loads(raw_outcomes) if isinstance(raw_outcomes, str) else (raw_outcomes or [])
    except (json.JSONDecodeError, TypeError):
        prices, outcomes = [], []

    if not prices:
        for field in ("lastTradePrice", "bestBid"):
            value = market.get(field)
            try:
                if value is not None:
                    return float(value), None, "binary"
            except (TypeError, ValueError):
                continue
        return None, None, "unknown"

    try:
        float_prices = [float(price) for price in prices]
    except (TypeError, ValueError):
        return None, None, "unknown"

    outcome_lower = [str(outcome).strip().lower() for outcome in outcomes]
    if len(float_prices) == 2:
        for yes_kw in ("yes", "up", "true"):
            if yes_kw in outcome_lower:
                return float_prices[outcome_lower.index(yes_kw)], None, "binary"
        return float_prices[0], None, "binary"

    max_idx = float_prices.index(max(float_prices))
    leading_label = str(outcomes[max_idx]) if max_idx < len(outcomes) else None
    return float_prices[max_idx], leading_label, "categorical"


def _extract_yes_token(market: dict) -> str | None:
    raw = market.get("clobTokenIds", "[]")
    try:
        tokens = json.loads(raw) if isinstance(raw, str) else (raw or [])
        return str(tokens[0]) if tokens else None
    except (json.JSONDecodeError, IndexError, TypeError):
        return None


def _tags_from_record(record: dict) -> list[str]:
    tags: list[str] = []
    for tag in record.get("tags", []) or []:
        if isinstance(tag, dict):
            slug = tag.get("slug")
            if slug:
                tags.append(str(slug))
    return tags


def _derive_outcome_label_from_question(question: str) -> str | None:
    text = str(question or "").strip()
    if not text:
        return None
    lowered = text.lower()
    prefixes = ["will ", "what will ", "is ", "does "]
    for prefix in prefixes:
        if lowered.startswith(prefix):
            text = text[len(prefix):]
            lowered = text.lower()
            break
    for suffix in [
        " happen in 2026?",
        " happen by end of 2026?",
        " happen?",
        " by end of 2026?",
        " by december 2026?",
        "?",
    ]:
        if lowered.endswith(suffix):
            text = text[: -len(suffix)]
            break
    return text.strip().capitalize() if text.strip() else None


def _parse_grouped_binary_event(markets: list[dict]) -> tuple[float | None, str | None, str, str | None, str | None]:
    best_probability = None
    best_label = None
    best_token_id = None
    best_slug = None
    for market in markets:
        probability, _leading, market_type = _extract_probability_robust(market)
        if probability is None or market_type != "binary":
            continue
        label = _derive_outcome_label_from_question(market.get("question") or market.get("title") or "")
        if best_probability is None or probability > best_probability:
            best_probability = probability
            best_label = label
            best_token_id = _extract_yes_token(market)
            best_slug = market.get("slug")
    if best_probability is None:
        return None, None, "unknown", None, None
    return best_probability, best_label, "categorical", best_token_id, best_slug


def _topic_match_score(text: str, query: str, display_label: str) -> int:
    haystack = f"{text} {display_label}".lower()
    tokens = [token.lower() for token in re.findall(r"[a-z0-9]+", f"{query} {display_label}") if len(token) >= 3]
    if not tokens:
        return 0
    return sum(1 for token in tokens if token in haystack)


def _parse_geo_event_v2(event: dict, fallback_category: str | None = None) -> dict | None:
    markets = event.get("markets", [])
    best_market = _best_market_by_volume(markets) if isinstance(markets, list) and markets else None
    market = best_market or event

    probability = None
    leading_outcome = None
    market_type = "unknown"
    yes_token_id = None
    market_slug = market.get("slug")

    if isinstance(markets, list) and len(markets) > 1:
        grouped = _parse_grouped_binary_event(markets)
        probability, leading_outcome, market_type, yes_token_id, grouped_slug = grouped
        if grouped_slug:
            market_slug = grouped_slug

    if probability is None:
        probability, leading_outcome, market_type = _extract_probability_robust(market)
        yes_token_id = _extract_yes_token(market)

    if probability is None:
        return None

    tags = _tags_from_record(event)
    title = event.get("title") or event.get("question") or market.get("question") or market.get("title")
    category = fallback_category or "Markets"
    if any(token in " ".join(tags).lower() for token in ["fed", "rate", "inflation", "economy"]):
        category = "Rates"
    elif any(token in " ".join(tags).lower() for token in ["tariff", "trade", "china", "sanctions"]):
        category = "Trade"
    elif any(token in " ".join(tags).lower() for token in ["war", "geopolitics", "ukraine", "military", "ceasefire"]):
        category = "Conflict"
    elif any(token in " ".join(tags).lower() for token in ["politics", "election", "regulation"]):
        category = "Politics"

    return {
        "event_id": event.get("id") or market.get("id"),
        "event_slug": event.get("slug") or market_slug,
        "market_slug": market_slug,
        "display_label": title,
        "title": title,
        "subtitle": event.get("subtitle"),
        "probability": probability,
        "leading_outcome": leading_outcome,
        "market_type": market_type,
        "volume_24hr": event.get("volume24hr") or event.get("volume_24hr") or market.get("volume24hr") or market.get("volume_24hr"),
        "liquidity": event.get("liquidity") or market.get("liquidity"),
        "end_date": market.get("endDate") or market.get("endDateIso") or event.get("endDate"),
        "yes_token_id": yes_token_id,
        "market_count": len(markets) if isinstance(markets, list) else 0,
        "tags": tags,
        "category": category,
        "source": "dynamic_search",
    }


def find_best_market_for_topic(
    search_query: str,
    category: str,
    equity_tickers: list[str],
    display_label: str,
) -> dict | None:
    try:
        resp = _request_json(
            GAMMA_SEARCH_URL,
            params={"q": search_query, "limit": 10},
        )
    except Exception:
        return None

    items = resp.get("events", []) if isinstance(resp, dict) else []
    candidates: list[dict] = []
    for item in items:
        if item.get("closed") or item.get("archived"):
            continue
        if item.get("markets") or item.get("conditionId") or item.get("question") or item.get("title"):
            candidates.append(item)

    if not candidates:
        return None

    best = None
    best_score = (-1, -1.0)
    for candidate in candidates:
        title = str(candidate.get("title") or candidate.get("question") or "")
        text = f"{title} {candidate.get('slug') or ''}"
        match_score = _topic_match_score(text, search_query, display_label)
        if match_score <= 0:
            continue
        try:
            vol = float(candidate.get("volume24hr") or candidate.get("volume_24hr") or 0)
        except (TypeError, ValueError):
            vol = 0.0
        candidate_score = (match_score, vol)
        if candidate_score > best_score:
            best_score = candidate_score
            best = candidate

    if not best:
        return None

    parsed = _parse_geo_event_v2(best, fallback_category=category)
    if not parsed or parsed.get("probability") is None:
        return None

    parsed.update(
        {
            "display_label": display_label,
            "equity_exposure": {ticker: "HIGH" for ticker in equity_tickers},
            "category": category,
            "source": "curated_search",
        }
    )
    return parsed


def fetch_macro_geopolitical_markets(
    max_curated: int = 20,
    max_dynamic: int = 10,
) -> list[dict]:
    results: list[dict] = []
    seen_slugs: set[str] = set()

    def fetch_topic(topic: tuple[str, str, str, list[str]]) -> dict | None:
        label, query, category, tickers = topic
        return find_best_market_for_topic(query, category, tickers, label)

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(fetch_topic, topic) for topic in PRIORITY_MACRO_TOPICS[:max_curated]]
        for future in as_completed(futures):
            try:
                result = future.result(timeout=10)
            except Exception:
                continue
            if not result or result.get("probability") is None:
                continue
            slug = str(result.get("event_slug") or result.get("market_slug") or result.get("display_label"))
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            results.append(result)

    dynamic_tags = [
        (120, "Rates"),
        (2, "Politics"),
        (100265, "Conflict"),
    ]
    required_keywords = {
        "Rates": ["fed", "rate", "inflation", "recession", "cpi", "gdp", "ecb", "yield"],
        "Trade": ["tariff", "trade", "china", "sanction", "export"],
        "Conflict": ["ukraine", "russia", "taiwan", "iran", "israel", "war", "ceasefire", "military"],
        "Politics": ["trump", "election", "midterm", "regulation", "congress", "impeach", "eu", "ai"],
    }
    for tag_id, fallback_category in dynamic_tags:
        try:
            raw = _request_json(
                GAMMA_EVENTS_URL,
                params={
                    "tag_id": tag_id,
                    "related_tags": "true",
                    "active": "true",
                    "closed": "false",
                    "order": "volume_24hr",
                    "ascending": "false",
                    "limit": 30,
                },
            )
        except Exception:
            continue
        for event in (raw if isinstance(raw, list) else []):
            slug = str(event.get("slug") or "")
            if slug in seen_slugs:
                continue
            title = str(event.get("title") or event.get("question") or "").lower()
            if any(keyword in title for keyword in NOISE_KEYWORDS):
                continue
            needed = required_keywords.get(fallback_category, [])
            if needed and not any(keyword in title for keyword in needed):
                continue
            try:
                vol = float(event.get("volume_24hr") or event.get("volume24hr") or 0)
            except (TypeError, ValueError):
                continue
            if vol < 1000:
                continue
            parsed = _parse_geo_event_v2(event, fallback_category=fallback_category)
            if not parsed or parsed.get("probability") is None:
                continue
            seen_slugs.add(slug)
            results.append(parsed)
            if len(results) >= max_curated + max_dynamic:
                break
        if len(results) >= max_curated + max_dynamic:
            break

    cat_order = {"Rates": 0, "Trade": 1, "Markets": 2, "Conflict": 3, "Politics": 4}
    results.sort(
        key=lambda record: (
            1 if record.get("source") == "curated_search" else 2,
            cat_order.get(str(record.get("category", "")), 9),
            -float(record.get("volume_24hr") or 0),
        )
    )
    return results


def fetch_top_geopolitical_events(
    limit: int = 30,
    include_finance: bool = True,
) -> list[dict]:
    """
    Fetch top active geopolitical and macro events sorted by 24h volume.
    """
    all_events: list[dict] = []
    tag_fetch_order = TAG_FETCH_ORDER if include_finance else [(GEOPOLITICAL_TAG_ID, limit)]

    for tag_id, tag_limit in tag_fetch_order:
        try:
            resp = _request_json(
                GAMMA_EVENTS_URL,
                params={
                    "tag_id": tag_id,
                    "related_tags": "true",
                    "active": "true",
                    "closed": "false",
                    "order": "volume_24hr",
                    "ascending": "false",
                    "limit": min(limit, tag_limit),
                },
            )
        except Exception:
            continue
        if isinstance(resp, list):
            all_events.extend(resp)

    seen: set[str] = set()
    unique: list[dict] = []
    for event in all_events:
        event_id = event.get("id")
        if event_id is None:
            continue
        event_id_str = str(event_id)
        if event_id_str in seen:
            continue
        seen.add(event_id_str)
        unique.append(event)

    parsed = [_parse_geo_event(event) for event in unique]
    parsed.sort(
        key=_geo_relevance_score,
        reverse=True,
    )
    return parsed


def fetch_probability_change_24h(yes_token_id: str) -> Optional[float]:
    """
    Fetch the 24-hour change in implied probability for a market.
    """
    if not yes_token_id:
        return None
    try:
        resp = _request_json(
            CLOB_PRICES_HISTORY_URL,
            params={
                "market": str(yes_token_id),
                "interval": "1d",
                "fidelity": 60,
            },
        )
    except Exception:
        return None

    history = resp.get("history", []) if isinstance(resp, dict) else []
    if len(history) < 2:
        return None
    try:
        current = float(history[-1]["p"])
        previous = float(history[0]["p"])
    except Exception:
        return None
    return round(current - previous, 4)


def search_events(query: str, limit: int = 10) -> list[dict]:
    """
    Full-text search for Polymarket events by topic keyword.
    """
    try:
        resp = _request_json(
            GAMMA_SEARCH_URL,
            params={"q": query, "limit": limit},
        )
    except Exception:
        return []

    if isinstance(resp, list):
        events = resp
    elif isinstance(resp, dict):
        events = resp.get("events", [])
    else:
        events = []

    parsed = []
    for event in events:
        if event.get("markets"):
            parsed.append(_parse_geo_event(event))
    return parsed


def fetch_token_market_details(token_id: str) -> dict:
    """
    Fetch CLOB token-level details.

    Current UI only uses probabilities, but these fields are kept here so future
    views can consume midpoint, bid/ask, and the raw order book without changing
    the discovery flow.
    """
    book = _request_json(CLOB_BOOK_URL, params={"token_id": str(token_id)})
    bids = book.get("bids", []) or []
    asks = book.get("asks", []) or []

    best_bid = None
    best_ask = None
    try:
        if bids:
            best_bid = float(bids[0].get("price"))
    except Exception:
        best_bid = None
    try:
        if asks:
            best_ask = float(asks[0].get("price"))
    except Exception:
        best_ask = None

    midpoint = None
    if best_bid is not None and best_ask is not None:
        midpoint = (best_bid + best_ask) / 2.0

    last_trade = book.get("last_trade_price")
    try:
        last_trade = float(last_trade) if last_trade is not None else None
    except Exception:
        last_trade = None

    return {
        "token_id": str(token_id),
        "midpoint": midpoint,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "last_trade": last_trade,
        "orderbook": book,
    }


def fetch_token_probability(token_id: str) -> Optional[float]:
    details = fetch_token_market_details(token_id)
    for key in ("last_trade", "best_ask", "best_bid", "midpoint"):
        value = details.get(key)
        if value is not None:
            try:
                prob = float(value)
                if 0.0 <= prob <= 1.0:
                    return prob
            except Exception:
                continue
    return None


def _get_market_probabilities_from_universe(
    ticker: str,
    target_date: date,
    include_optional: bool = False,
) -> dict:
    ticker = _normalize_ticker(ticker)
    context = _get_daily_market_context(ticker, target_date)
    market = context.get("market")

    result: Dict[str, Any] = {
        "ticker": ticker,
        "target_date": target_date.isoformat(),
        "up_probability": None,
        "yes_token_id": None,
        "market_created_at": context.get("market_created_at"),
        "market_updated_at": context.get("market_updated_at"),
        "fetched_at": context.get("fetched_at"),
        "question": context.get("question"),
        "market_slug": context.get("market_slug"),
        "market_id": context.get("market_id"),
    }

    if market is None:
        if include_optional:
            result.update(
                {
                    "market_created_at": context.get("market_created_at"),
                    "market_updated_at": context.get("market_updated_at"),
                    "fetched_at": context.get("fetched_at"),
                    "yes_token_id": context.get("yes_token_id"),
                    "yes_midpoint": None,
                    "best_bid_yes": None,
                    "best_ask_yes": None,
                    "orderbook_yes": None,
                }
            )
        return result

    yes_token_id = context.get("yes_token_id")

    up_prob = None
    prob_source = None

    if market is not None:
        up_prob = _extract_up_probability_from_market(market)
        if up_prob is not None:
            prob_source = "gamma_outcome_prices"

    result["up_probability"] = up_prob
    result["yes_token_id"] = yes_token_id
    result["probability_source"] = prob_source

    if include_optional:
        result.update(
            {
                "market_created_at": context.get("market_created_at"),
                "market_updated_at": context.get("market_updated_at"),
                "fetched_at": context.get("fetched_at"),
                "yes_token_id": yes_token_id,
                "probability_source": prob_source,
                "yes_midpoint": None,
                "best_bid_yes": None,
                "best_ask_yes": None,
                "orderbook_yes": None,
            }
        )

    return result


def get_market_probabilities(
    ticker: str,
    target_date: str | None = None,
    include_optional: bool = False,
) -> dict:
    """
    Return a single ticker record ready for visualization.

    Currently used by the UI:
    - ticker
    - target_date
    - up_probability

    Optional / future expansion fields are only fetched when requested.
    """
    target_dt = _coerce_date(target_date)
    return _get_market_probabilities_from_universe(ticker, target_dt, include_optional=include_optional)


def get_up_probability(
    ticker: str,
    target_date: str | None = None,
) -> Optional[float]:
    """
    Convenience helper for callers that only need the live Up probability.
    """
    target_dt = _coerce_date(target_date)
    result = _get_market_probabilities_from_universe(ticker, target_dt, include_optional=False)
    value = result.get("up_probability")
    return float(value) if value is not None and pd.notna(value) else None


def get_market_probabilities_by_slug(
    slug: str,
    include_optional: bool = False,
) -> dict:
    """
    Return a live Polymarket market snapshot directly from an explicit slug.
    """
    market = _fetch_market_by_slug(slug)
    fetched_at = datetime.now(ZoneInfo("America/New_York")).isoformat()
    result: Dict[str, Any] = {
        "market_slug": slug,
        "question": None,
        "market_id": None,
        "market_created_at": None,
        "market_updated_at": None,
        "market_end_at": None,
        "fetched_at": fetched_at,
        "up_probability": None,
        "probability_source": None,
    }
    if market is None:
        return result

    up_prob = _extract_up_probability_from_market(market)
    result.update(
        {
            "market_slug": market.get("slug", slug),
            "question": market.get("question") or market.get("title"),
            "market_id": market.get("id"),
            "market_created_at": market.get("createdAt"),
            "market_updated_at": market.get("updatedAt"),
            "market_end_at": market.get("endDate") or market.get("endDateIso"),
            "up_probability": up_prob,
            "probability_source": "gamma_outcome_prices" if up_prob is not None else None,
        }
    )
    if include_optional:
        result.update(
            {
                "market": market,
            }
        )
    return result


def get_probabilities_for_tickers(
    tickers: list[str],
    target_date: str | None = None,
    include_optional: bool = False,
) -> pd.DataFrame:
    target_dt = _coerce_date(target_date)
    print(f"[POLY] effective_target_date={target_dt.isoformat()}")
    records = [
        _get_market_probabilities_from_universe(
            ticker,
            target_dt,
            include_optional=include_optional,
        )
        for ticker in tickers
    ]
    for rec in records:
        print(
            f"[POLY] {str(rec.get('ticker', '')).upper()} | date={rec.get('target_date')} | "
            f"up={rec.get('up_probability')} | market_slug={rec.get('market_slug')} | "
            f"question={rec.get('question')} | src={rec.get('probability_source')} | "
            f"market_updated_at={rec.get('market_updated_at')} | fetched_at={rec.get('fetched_at')}"
        )
    return pd.DataFrame(records)


__all__ = [
    "Orderbook",
    "collapse_to_windows",
    "check_lead_lag",
    "analyse_sentiment_dynamics",
    "build_preopen_panel",
    "get_up_probability",
    "get_probabilities_for_tickers",
    "get_effective_nyse_trading_date",
    "get_effective_nyse_market_date",
    "get_effective_crypto_market_date",
    "build_up_down_slug",
    "get_market_probabilities_by_slug",
    "fetch_macro_geopolitical_markets",
    "fetch_probability_change_24h",
    "search_events",
]
