import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime as dt
from datetime import timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytz
import requests
import yfinance as yf

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
            hour_step = 0.2
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
            time.sleep(0.1)
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
