from __future__ import annotations

import argparse
import csv
import re
import sys
import threading
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import matplotlib.dates as mdates
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from matplotlib.animation import FuncAnimation
from matplotlib.lines import Line2D

try:
    import yfinance as yf
except Exception as exc:
    raise RuntimeError("yfinance is required. Install with: pip install yfinance") from exc

try:
    from config import ASSET_UNIVERSE, CATEGORY_ORDER, RISK_FREE_ANN
except ImportError:
    from backend.config import ASSET_UNIVERSE, CATEGORY_ORDER, RISK_FREE_ANN

try:
    from config import (
        EQUITY_TICKERS as _ET,
        POLYMARKET_RIGHT_PANEL as _PRP,
        POLYMARKET_YF_SYMBOL_MAP as _PYF,
    )
except ImportError:
    from backend.config import (
        EQUITY_TICKERS as _ET,
        POLYMARKET_RIGHT_PANEL as _PRP,
        POLYMARKET_YF_SYMBOL_MAP as _PYF,
    )

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    import polymarket_runtime as poly
except ImportError:
    try:
        import pipeline as poly
    except ImportError:
        from backend import pipeline as poly  # type: ignore[no-redef]

ASSETS: List[Tuple[str, str, str]] = [
    (a["category"], a["label"], a["yf_symbol"])
    for a in ASSET_UNIVERSE
]

OUT_DIR = Path(__file__).resolve().parent.parent / "polymarket-dashboard-heatmap" / "outputs_yf_heatmap"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# One-time pre-collection defaults (configurable via CLI).
DEFAULT_COLLECT_DAILY_DAYS = 10
DEFAULT_COLLECT_INTRADAY_INTERVALS = "5m,10m"
DEFAULT_COLLECT_INTRADAY_PERIOD = "10d"
DEFAULT_COLLECT_STD_WINDOW_DAILY = 10
DEFAULT_COLLECT_STD_WINDOW_INTRADAY = 30


def human_num(x: float) -> str:
    if pd.isna(x):
        return "N/A"
    x = float(x)
    if abs(x) >= 1e12:
        return f"{x/1e12:.2f}T"
    if abs(x) >= 1e9:
        return f"{x/1e9:.2f}B"
    if abs(x) >= 1e6:
        return f"{x/1e6:.2f}M"
    if abs(x) >= 1e3:
        return f"{x/1e3:.2f}K"
    return f"{x:.0f}"


def human_price(x: float) -> str:
    if pd.isna(x):
        return "N/A"
    x = float(x)
    if abs(x) >= 1000:
        return f"{x:,.2f}"
    if abs(x) >= 1:
        return f"{x:.2f}"
    return f"{x:.4f}"


def mix_hex(c1: str, c2: str, t: float) -> str:
    t = max(0.0, min(1.0, float(t)))
    a = tuple(int(c1[i : i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(c2[i : i + 2], 16) for i in (1, 3, 5))
    m = tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))
    return f"#{m[0]:02x}{m[1]:02x}{m[2]:02x}"


def get_market_cap(ticker: str) -> float:
    """Best-effort market cap fetch. Returns NaN on failure."""
    try:
        tk = yf.Ticker(ticker)
        fi = getattr(tk, "fast_info", None)
        if fi is not None:
            mc = fi.get("marketCap", np.nan)
            if pd.notna(mc) and float(mc) > 0:
                return float(mc)
        info = tk.info
        mc = info.get("marketCap", np.nan)
        if pd.notna(mc) and float(mc) > 0:
            return float(mc)
    except Exception:
        pass
    return np.nan


def _extract_ohlcv(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Extract per-ticker OHLCV frame from yfinance download output."""
    if raw.empty:
        return pd.DataFrame()

    if isinstance(raw.columns, pd.MultiIndex):
        if ticker not in raw.columns.get_level_values(0):
            return pd.DataFrame()
        sub = raw[ticker].copy()
    else:
        sub = raw.copy()

    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in sub.columns]
    if not keep:
        return pd.DataFrame()
    sub = sub[keep].copy()
    idx = pd.to_datetime(sub.index)
    sub.index = idx.tz_convert(None) if idx.tz is not None else idx.tz_localize(None)
    sub = sub.sort_index()
    return sub


def build_feature_frame(
    assets: List[Tuple[str, str, str]],
    interval: str,
    period: str,
    std_window: int,
    tail_rows: int | None = None,
) -> pd.DataFrame:
    """
    Build feature table:
    - return (%), volume, dollar volume (close*volume)
    - rolling std of return/volume/dollar volume
    """
    tickers = [t for _, _, t in assets]
    download_interval = interval
    needs_resample_10m = False
    if interval == "10m":
        # Yahoo often rejects 10m directly; use 5m then aggregate to 10m.
        download_interval = "5m"
        needs_resample_10m = True

    raw = yf.download(
        tickers=tickers,
        period=period,
        interval=download_interval,
        auto_adjust=False,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    if raw.empty:
        return pd.DataFrame()

    rows: List[pd.DataFrame] = []
    for category, label, ticker in assets:
        sub = _extract_ohlcv(raw, ticker)
        if sub.empty or "Close" not in sub.columns:
            continue

        if needs_resample_10m:
            agg = {
                "Open": "first",
                "High": "max",
                "Low": "min",
                "Close": "last",
                "Volume": "sum",
            }
            sub = sub.resample("10min").agg(agg).dropna(subset=["Close"])
            if sub.empty:
                continue

        close = sub["Close"].astype(float)
        vol = sub["Volume"].astype(float) if "Volume" in sub.columns else pd.Series(index=sub.index, dtype=float)
        ret_pct = close.pct_change(fill_method=None) * 100.0
        dollar_vol = close * vol

        feat = pd.DataFrame(
            {
                "datetime": sub.index,
                "category": category,
                "label": label,
                "ticker": ticker,
                "close": close.values,
                "ret_pct": ret_pct.values,
                "volume": vol.values,
                "dollar_volume": dollar_vol.values,
            }
        )
        feat["ret_std"] = feat["ret_pct"].rolling(std_window, min_periods=max(2, std_window // 3)).std()
        feat["volume_std"] = feat["volume"].rolling(std_window, min_periods=max(2, std_window // 3)).std()
        feat["dollar_volume_std"] = feat["dollar_volume"].rolling(std_window, min_periods=max(2, std_window // 3)).std()

        if tail_rows is not None and tail_rows > 0:
            feat = feat.tail(tail_rows).copy()
        rows.append(feat)

    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True)
    return out.sort_values(["ticker", "datetime"]).reset_index(drop=True)


def collect_preload_data(
    assets: List[Tuple[str, str, str]],
    daily_days: int,
    intraday_intervals: List[str],
    intraday_period: str,
    std_window_daily: int,
    std_window_intraday: int,
) -> Dict[str, pd.DataFrame]:
    """Collect one-time data at startup (not refreshed every 10 seconds)."""
    collected: Dict[str, pd.DataFrame] = {}

    # Daily: gather enough history then keep latest N trading days per ticker.
    daily_df = build_feature_frame(
        assets=assets,
        interval="1d",
        period="6mo",
        std_window=std_window_daily,
        tail_rows=daily_days,
    )
    collected[f"daily_{daily_days}d"] = daily_df

    for iv in intraday_intervals:
        iv = iv.strip()
        if not iv:
            continue
        key = f"intraday_{iv}"
        collected[key] = build_feature_frame(
            assets=assets,
            interval=iv,
            period=intraday_period,
            std_window=std_window_intraday,
            tail_rows=None,
        )
    return collected


def print_precollect_summary(collected: Dict[str, pd.DataFrame]) -> None:
    print("[PRECOLLECT] one-time data build complete")
    for name, df in collected.items():
        if df.empty:
            print(f" - {name}: empty")
            continue
        tick_n = int(df["ticker"].nunique()) if "ticker" in df.columns else 0
        row_n = len(df)
        last_dt = pd.to_datetime(df["datetime"]).max() if "datetime" in df.columns else pd.NaT
        last_s = last_dt.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(last_dt) else "N/A"
        print(f" - {name}: rows={row_n}, tickers={tick_n}, last={last_s}")


def fetch_latest_metrics(assets: List[Tuple[str, str, str]]) -> pd.DataFrame:
    tickers = [t for _, _, t in assets]
    raw = yf.download(
        tickers=tickers,
        period="3mo",
        interval="1d",
        auto_adjust=False,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    if raw.empty:
        raise RuntimeError("No data downloaded from Yahoo Finance.")

    equity_tickers = [t for c, _, t in assets if c == "US Equities"]
    cap_map = {t: get_market_cap(t) for t in equity_tickers}

    rows: List[Dict[str, object]] = []
    for category, label, ticker in assets:
        close = None
        vol = None

        if isinstance(raw.columns, pd.MultiIndex):
            if ticker in raw.columns.get_level_values(0):
                close = raw[ticker]["Close"].dropna() if "Close" in raw[ticker] else None
                vol = raw[ticker]["Volume"].dropna() if "Volume" in raw[ticker] else None
        else:
            close = raw["Close"].dropna() if "Close" in raw.columns else None
            vol = raw["Volume"].dropna() if "Volume" in raw.columns else None

        if close is None or len(close) < 2:
            rows.append(
                {
                    "category": category,
                    "label": label,
                    "ticker": ticker,
                    "date": pd.NaT,
                    "prev_close": np.nan,
                    "last_close": np.nan,
                    "chg_abs": np.nan,
                    "ret_pct": np.nan,
                    "volume": np.nan,
                    "vol_avg20": np.nan,
                    "vol_ratio": np.nan,
                    "market_cap": cap_map.get(ticker, np.nan),
                }
            )
            continue

        idx = pd.to_datetime(close.index).tz_localize(None)
        close.index = idx

        if vol is None or len(vol) == 0:
            vol_s = pd.Series(index=idx, dtype=float)
        else:
            vol_s = pd.Series(vol.values, index=pd.to_datetime(vol.index).tz_localize(None), dtype=float)
            vol_s = vol_s.reindex(idx)

        ret = close.pct_change(fill_method=None) * 100.0
        vol_avg20 = vol_s.rolling(20, min_periods=10).mean()

        last_dt = idx[-1]
        rows.append(
            {
                "category": category,
                "label": label,
                "ticker": ticker,
                "date": last_dt,
                "prev_close": float(close.iloc[-2]) if pd.notna(close.iloc[-2]) else np.nan,
                "last_close": float(close.iloc[-1]) if pd.notna(close.iloc[-1]) else np.nan,
                "chg_abs": float(close.iloc[-1] - close.iloc[-2]) if pd.notna(close.iloc[-1]) and pd.notna(close.iloc[-2]) else np.nan,
                "ret_pct": float(ret.loc[last_dt]) if pd.notna(ret.loc[last_dt]) else np.nan,
                "volume": float(vol_s.loc[last_dt]) if pd.notna(vol_s.loc[last_dt]) else np.nan,
                "vol_avg20": float(vol_avg20.loc[last_dt]) if pd.notna(vol_avg20.loc[last_dt]) else np.nan,
                "vol_ratio": float(vol_s.loc[last_dt] / vol_avg20.loc[last_dt]) if pd.notna(vol_s.loc[last_dt]) and pd.notna(vol_avg20.loc[last_dt]) and vol_avg20.loc[last_dt] != 0 else np.nan,
                "market_cap": cap_map.get(ticker, np.nan),
            }
        )

    return pd.DataFrame(rows)


def tile_color(category: str, ret_pct: float, vol_ratio: float) -> str:
    # Discrete return buckets for all asset classes:
    # <=-3, -2, -1, 0, 1, 2, >=3
    if pd.isna(ret_pct):
        return "#1f2937"
    r = float(ret_pct)
    if r <= -3.0:
        return "#b80f2f"
    if r <= -2.0:
        return "#c41e3a"
    if r <= -1.0:
        return "#d9435f"
    if r < 1.0:
        return "#374151"
    if r < 2.0:
        return "#0f766e"
    if r < 3.0:
        return "#0b8f7f"
    return "#0ea58f"


def _ordered_treemap_layout(
    sizes: List[float], x: float, y: float, w: float, h: float
) -> List[Tuple[float, float, float, float]]:
    """
    Ordered treemap:
    - items are assumed to be sorted descending
    - largest starts at top-left
    - placement proceeds top->bottom in left column first,
      then next column (TL -> BL -> TR -> BR)
    """
    if not sizes:
        return []
    n = len(sizes)
    total = float(sum(sizes))
    if total <= 0:
        total = float(n)
        sizes = [1.0] * n

    # Column packing target to preserve TL->BL->TR->BR ordering.
    n_cols = max(1, int(round(np.sqrt(n))))
    target_per_col = total / n_cols
    cols: List[List[float]] = []
    current: List[float] = []
    current_sum = 0.0

    for i, s in enumerate(sizes):
        remaining_items = n - i
        remaining_cols = max(1, n_cols - len(cols))
        force_break = (remaining_items == remaining_cols and current)
        if (current_sum >= target_per_col and len(cols) < n_cols - 1) or force_break:
            cols.append(current)
            current = []
            current_sum = 0.0
        current.append(float(s))
        current_sum += float(s)
    if current:
        cols.append(current)

    rects: List[Tuple[float, float, float, float]] = []
    x_cursor = x
    for col in cols:
        col_sum = float(sum(col))
        col_w = w * (col_sum / total) if total > 0 else w / len(cols)
        y_top = y + h
        for s in col:
            rh = h * (s / col_sum) if col_sum > 0 else h / len(col)
            y_top -= rh
            rects.append((x_cursor, y_top, col_w, rh))
        x_cursor += col_w
    return rects


def draw_equity_treemap_panel(
    ax, row_df: pd.DataFrame, x0: float, y0: float, panel_w: float, panel_h: float
) -> None:
    """Draw equities in 3 columns with market-cap-proportional area."""
    if row_df.empty:
        return

    row = row_df.copy().sort_values("market_cap", ascending=False, na_position="last").reset_index(drop=True)
    caps = pd.to_numeric(row["market_cap"], errors="coerce").fillna(0.0)
    if float(caps.sum()) <= 0:
        caps = pd.Series([1.0] * len(row))

    # Requested shape: 3-column feel with 2,2,3 baseline.
    # If more names exist, extras are appended to the 3rd column.
    n = len(row)
    col1_end = min(2, n)
    col2_end = min(4, n)
    groups = [
        row.iloc[:col1_end].copy(),
        row.iloc[col1_end:col2_end].copy(),
        row.iloc[col2_end:].copy(),
    ]
    groups = [g for g in groups if not g.empty]

    total_cap = float(pd.to_numeric(row["market_cap"], errors="coerce").fillna(0.0).sum())
    if total_cap <= 0:
        total_cap = float(len(row))

    # Column widths are proportional to total market cap in each column.
    x_cursor = x0
    for g in groups:
        g_caps = pd.to_numeric(g["market_cap"], errors="coerce").fillna(0.0)
        g_sum = float(g_caps.sum())
        if g_sum <= 0:
            g_sum = float(len(g))
            g_caps = pd.Series([1.0] * len(g))

        col_w = panel_w * (g_sum / total_cap)

        # Inside each column, heights are proportional to each name's market cap.
        y_top = y0 + panel_h
        for _, rec in g.iterrows():
            s = float(rec["market_cap"]) if pd.notna(rec["market_cap"]) and float(rec["market_cap"]) > 0 else 1.0
            rh = panel_h * (s / g_sum)
            y_top -= rh
            rx, ry, rw = x_cursor, y_top, col_w

            tile = patches.Rectangle(
                (rx + 0.02, ry + 0.06),
                max(0.0, rw - 0.04),
                max(0.0, rh - 0.10),
                linewidth=0.8,
                edgecolor="#1f2937",
                facecolor=tile_color("US Equities", rec["ret_pct"], rec["vol_ratio"]),
            )
            ax.add_patch(tile)

            ticker = str(rec["ticker"])
            ret_txt = f"{rec['ret_pct']:+.2f}%" if pd.notna(rec["ret_pct"]) else "N/A"

            text_x = rx + 0.05
            text_y_top = ry + rh - 0.07
            area = rw * rh
            if area < 0.9:
                ax.text(text_x, text_y_top, ticker, ha="left", va="top", color="#f9fafb", fontsize=8, fontweight="bold")
                ax.text(text_x, text_y_top - 0.22, ret_txt, ha="left", va="top", color="#f8fafc", fontsize=8)
            elif area < 2.0:
                ax.text(text_x, text_y_top, ticker, ha="left", va="top", color="#f9fafb", fontsize=10, fontweight="bold")
                ax.text(text_x, text_y_top - 0.20, ret_txt, ha="left", va="top", color="#f8fafc", fontsize=9)
            else:
                ax.text(text_x, text_y_top, ticker, ha="left", va="top", color="#f9fafb", fontsize=12, fontweight="bold")
                ax.text(text_x, text_y_top - 0.38, ret_txt, ha="left", va="top", color="#f8fafc", fontsize=10)

        x_cursor += col_w

    # If numeric drift leaves a tiny gap on right edge, ignore visually.
    # (matplotlib rounding + padding can create sub-pixel seams)


def draw_equal_tiles_row(
    ax, row_df: pd.DataFrame, x0: float, y0: float, panel_w: float, panel_h: float
) -> None:
    row = row_df.reset_index(drop=True)
    n_cols = len(row)
    if n_cols <= 0:
        return
    unit = panel_w / n_cols

    for c in range(n_cols):
        x = x0 + c * unit
        base_rect = patches.Rectangle((x + 0.02, y0 + 0.04), max(0.0, unit - 0.04), max(0.0, panel_h - 0.08), linewidth=0.8, edgecolor="#1f2937", facecolor="#111827")
        ax.add_patch(base_rect)

        if c >= len(row):
            continue

        rec = row.iloc[c]
        tile = patches.Rectangle((x + 0.02, y0 + 0.04), max(0.0, unit - 0.04), max(0.0, panel_h - 0.08), linewidth=0.8, edgecolor="#1f2937", facecolor=tile_color(str(rec["category"]), rec["ret_pct"], rec["vol_ratio"]))
        ax.add_patch(tile)

        ty = y0 + panel_h - 0.14
        display_name = str(rec["label"]) if "label" in rec and pd.notna(rec["label"]) and str(rec["label"]).strip() else str(rec["ticker"])
        ax.text(x + 0.06, ty, display_name, ha="left", va="top", color="#f9fafb", fontsize=10, fontweight="bold")
        ret_txt = f"{rec['ret_pct']:+.2f}%" if pd.notna(rec["ret_pct"]) else "N/A"
        ax.text(x + 0.06, ty - 0.25, ret_txt, ha="left", va="top", color="#f8fafc", fontsize=9)


def draw_equal_tiles_split_rows(
    ax,
    row_df: pd.DataFrame,
    x0: float,
    y0: float,
    panel_w: float,
    panel_h: float,
    splits: List[int],
) -> None:
    row = row_df.reset_index(drop=True)
    if not splits or row.empty:
        return

    n_rows = len(splits)
    gap = 0.08
    row_h = (panel_h - gap * (n_rows - 1)) / n_rows
    start = 0

    for i, count in enumerate(splits):
        if start >= len(row):
            break
        end = min(len(row), start + max(0, int(count)))
        block = row.iloc[start:end].copy()
        start = end
        if block.empty:
            continue

        y = y0 + (n_rows - 1 - i) * (row_h + gap)
        n_cols = len(block)
        unit = panel_w / n_cols

        for c in range(n_cols):
            x = x0 + c * unit
            base_rect = patches.Rectangle(
                (x + 0.02, y + 0.03),
                max(0.0, unit - 0.04),
                max(0.0, row_h - 0.06),
                linewidth=0.8,
                edgecolor="#1f2937",
                facecolor="#111827",
            )
            ax.add_patch(base_rect)

            rec = block.iloc[c]
            tile = patches.Rectangle(
                (x + 0.02, y + 0.03),
                max(0.0, unit - 0.04),
                max(0.0, row_h - 0.06),
                linewidth=0.8,
                edgecolor="#1f2937",
                facecolor=tile_color(str(rec["category"]), rec["ret_pct"], rec["vol_ratio"]),
            )
            ax.add_patch(tile)

            ty = y + row_h - 0.08
            display_name = str(rec["label"]) if "label" in rec and pd.notna(rec["label"]) and str(rec["label"]).strip() else str(rec["ticker"])
            ax.text(x + 0.05, ty, display_name, ha="left", va="top", color="#f9fafb", fontsize=8, fontweight="bold")
            ret_txt = f"{rec['ret_pct']:+.2f}%" if pd.notna(rec["ret_pct"]) else "N/A"
            ax.text(x + 0.05, ty - 0.18, ret_txt, ha="left", va="top", color="#f8fafc", fontsize=7)


def _render_dashboard(ax, df: pd.DataFrame, fetched_at_text: str = "") -> None:
    """Render one frame of the dashboard on an existing axis."""
    ax.clear()
    ax.set_facecolor("#0b1220")

    grouped = {c: df[df["category"] == c].copy() for c in CATEGORY_ORDER}

    # Coordinate space for precise layout control.
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)

    left_x, left_w = 0.2, 9.4
    right_x, right_w = 10.0, 5.8
    base_y = 0.35
    body_h = 7.8
    eq_y = base_y
    eq_h = body_h

    # Right panel split into 3 rows.
    gap = 0.16
    row_h = (body_h - 2 * gap) / 3.0
    idx_y = base_y + 2 * (row_h + gap)
    cry_y = base_y + 1 * (row_h + gap)
    com_y = base_y

    # Reserve a header strip in each panel so section labels never overlap tiles.
    eq_header_h = 0.34
    rhs_header_h = 0.28

    ax.text(left_x + 0.10, eq_y + eq_h - 0.08, "Stocks", ha="left", va="top", color="#d1d5db", fontsize=13, fontweight="bold")
    draw_equity_treemap_panel(
        ax,
        grouped["US Equities"],
        x0=left_x,
        y0=eq_y,
        panel_w=left_w,
        panel_h=max(0.6, eq_h - eq_header_h),
    )

    ax.text(right_x + 0.08, idx_y + row_h - 0.06, "Indices", ha="left", va="top", color="#d1d5db", fontsize=12, fontweight="bold")
    draw_equal_tiles_split_rows(
        ax,
        grouped["Indices"],
        x0=right_x,
        y0=idx_y,
        panel_w=right_w,
        panel_h=max(0.5, row_h - rhs_header_h),
        splits=[4, 3],
    )

    ax.text(right_x + 0.08, cry_y + row_h - 0.06, "Crypto", ha="left", va="top", color="#d1d5db", fontsize=12, fontweight="bold")
    draw_equal_tiles_row(
        ax,
        grouped["Crypto"],
        x0=right_x,
        y0=cry_y,
        panel_w=right_w,
        panel_h=max(0.5, row_h - rhs_header_h),
    )

    ax.text(right_x + 0.08, com_y + row_h - 0.06, "Commodities", ha="left", va="top", color="#d1d5db", fontsize=12, fontweight="bold")
    draw_equal_tiles_row(
        ax,
        grouped["Commodities"],
        x0=right_x,
        y0=com_y,
        panel_w=right_w,
        panel_h=max(0.5, row_h - rhs_header_h),
    )

    ax.axis("off")

    latest = pd.to_datetime(df["date"].dropna().max()).strftime("%Y-%m-%d") if df["date"].notna().any() else datetime.now().strftime("%Y-%m-%d")
    title = f"Yahoo-Style Daily Tiles ({latest})"
    subtitle = "Stocks, indices, crypto, and commodities colored by previous-close return (%)"
    ax.text(0.2, 8.65, title, ha="left", va="bottom", color="#f3f4f6", fontsize=18, fontweight="bold")
    ax.text(0.2, 8.30, subtitle, ha="left", va="bottom", color="#9ca3af", fontsize=11)
    if fetched_at_text:
        ax.text(0.2, 8.02, fetched_at_text, ha="left", va="bottom", color="#94a3b8", fontsize=10)

    # Return bucket legend
    lx, ly = 6.2, 8.50
    bw, bh = 1.00, 0.16
    legend = [
        ("<= -3", "#b80f2f"),
        ("-2", "#c41e3a"),
        ("-1", "#d9435f"),
        ("0", "#374151"),
        ("1", "#0f766e"),
        ("2", "#0b8f7f"),
        (">= 3", "#0ea58f"),
    ]
    for i, (label, col) in enumerate(legend):
        bx = lx + i * bw
        rect = patches.Rectangle((bx, ly), bw - 0.03, bh, linewidth=0.0, edgecolor=col, facecolor=col)
        ax.add_patch(rect)
        ax.text(bx + (bw - 0.03) / 2, ly - 0.06, label, ha="center", va="top", color="#cbd5e1", fontsize=8, fontweight="bold")

    ax.axis("off")


def draw_tiles(
    df: pd.DataFrame,
    save: bool = True,
    show: bool = False,
    fetched_at_text: str = "",
    refresh_seconds: int = 0,
) -> Path | None:
    fig_w = 17.0
    fig_h = 9.3
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=150)
    fig.patch.set_facecolor("#0b1220")

    _render_dashboard(ax, df, fetched_at_text=fetched_at_text)

    latest = pd.to_datetime(df["date"].dropna().max()).strftime("%Y-%m-%d") if df["date"].notna().any() else datetime.now().strftime("%Y-%m-%d")
    out_png = OUT_DIR / f"yahoo_style_tiles_{latest}.png"
    plt.tight_layout(pad=0.8)
    if save:
        fig.savefig(out_png, bbox_inches="tight", facecolor=fig.get_facecolor())

    # Auto-refresh loop: while window is open, fetch and redraw every N seconds.
    if show and refresh_seconds > 0:
        plt.show(block=False)
        while plt.fignum_exists(fig.number):
            plt.pause(max(1, int(refresh_seconds)))
            if not plt.fignum_exists(fig.number):
                break
            fresh_df = fetch_latest_metrics(ASSETS)
            refreshed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _render_dashboard(ax, fresh_df, fetched_at_text=f"Fetched from Yahoo Finance at: {refreshed_at}")
            fig.canvas.draw_idle()
            if save:
                latest_refresh = pd.to_datetime(fresh_df["date"].dropna().max()).strftime("%Y-%m-%d") if fresh_df["date"].notna().any() else datetime.now().strftime("%Y-%m-%d")
                out_png = OUT_DIR / f"yahoo_style_tiles_{latest_refresh}.png"
                fig.savefig(out_png, bbox_inches="tight", facecolor=fig.get_facecolor())
    elif show:
        plt.show()

    plt.close(fig)
    return out_png if save else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true", help="Also save CSV/PNG files.")
    parser.add_argument("--no-show", action="store_true", help="Do not open chart window.")
    parser.add_argument("--refresh-seconds", type=int, default=0, help="Auto-refresh while window is open (e.g., 10).")
    parser.add_argument("--skip-precollect", action="store_true", help="Skip startup one-time data collection.")
    parser.add_argument("--collect-daily-days", type=int, default=DEFAULT_COLLECT_DAILY_DAYS, help="Daily lookback trading days for startup collection.")
    parser.add_argument(
        "--collect-intraday-intervals",
        type=str,
        default=DEFAULT_COLLECT_INTRADAY_INTERVALS,
        help="Comma-separated intervals for startup collection, e.g. '5m,10m'.",
    )
    parser.add_argument(
        "--collect-intraday-period",
        type=str,
        default=DEFAULT_COLLECT_INTRADAY_PERIOD,
        help="Yahoo period for intraday pre-collection, e.g. '10d', '30d'.",
    )
    parser.add_argument("--collect-std-window-daily", type=int, default=DEFAULT_COLLECT_STD_WINDOW_DAILY, help="Rolling std window for daily pre-collection.")
    parser.add_argument("--collect-std-window-intraday", type=int, default=DEFAULT_COLLECT_STD_WINDOW_INTRADAY, help="Rolling std window for intraday pre-collection.")
    args = parser.parse_args()

    if not args.skip_precollect:
        intraday_intervals = [x.strip() for x in args.collect_intraday_intervals.split(",") if x.strip()]
        collected = collect_preload_data(
            assets=ASSETS,
            daily_days=max(1, int(args.collect_daily_days)),
            intraday_intervals=intraday_intervals,
            intraday_period=args.collect_intraday_period,
            std_window_daily=max(2, int(args.collect_std_window_daily)),
            std_window_intraday=max(2, int(args.collect_std_window_intraday)),
        )
        print_precollect_summary(collected)

        # Keep this commented by default (no save).
        # Uncomment when you want immediate export.
        # def save_collected_data(collected_data: Dict[str, pd.DataFrame], out_dir: Path = OUT_DIR) -> None:
        #     out_dir.mkdir(parents=True, exist_ok=True)
        #     stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        #     for key, frame in collected_data.items():
        #         if frame.empty:
        #             continue
        #         frame.to_csv(out_dir / f"{key}_{stamp}.csv", index=False)
        #
        # save_collected_data(collected)

    df = fetch_latest_metrics(ASSETS)
    latest = pd.to_datetime(df["date"].dropna().max()).strftime("%Y-%m-%d") if df["date"].notna().any() else datetime.now().strftime("%Y-%m-%d")
    fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fetched_at_text = f"Fetched from Yahoo Finance at: {fetched_at}"

    show_chart = not args.no_show

    if args.save:
        out_csv = OUT_DIR / f"daily_tiles_metrics_{latest}.csv"
        df.to_csv(out_csv, index=False)
        out_png = draw_tiles(
            df,
            save=True,
            show=show_chart,
            fetched_at_text=fetched_at_text,
            refresh_seconds=args.refresh_seconds,
        )

        print("[OK] Saved files:")
        print(f" - CSV: {out_csv}")
        print(f" - PNG: {out_png}")
        if show_chart:
            print("[OK] Chart window displayed.")
        return

    draw_tiles(
        df,
        save=False,
        show=show_chart,
        fetched_at_text=fetched_at_text,
        refresh_seconds=args.refresh_seconds,
    )
    if show_chart:
        print("[OK] Chart window displayed (no file saved).")
    else:
        print("[OK] Run completed (no save, no show).")


if __name__ == "__main__":
    main()


base = sys.modules[__name__]

POLYMARKET_STOCK_TICKERS = _ET
POLYMARKET_RIGHT_PANEL_SPECS = _PRP
POLYMARKET_RIGHT_PANEL_YF_SYMBOLS = {
    (cat, sym.upper()): yf_sym
    for (cat, sym), yf_sym in _PYF.items()
}
# ─────────────────────────────────────────────────────────────────────────────

CATEGORY_ORDER = ["US Equities", "Indices", "Crypto", "Commodities"]
VIEW_CHOICES = ("heatmap", "table")
POLYMARKET_ENABLED = True
POLYMARKET_INCLUDE_OPTIONAL = False

# ── Background refresh state ──────────────────────────────────────────────────
_data_lock = threading.Lock()
_shared_state: Dict[str, Any] = {
    "df": pd.DataFrame(),
    "history": {},
    "last_fetched": "",
}
# ─────────────────────────────────────────────────────────────────────────────

CRYPTO_WS_SYMBOLS = ("BTC-USD", "ETH-USD", "SOL-USD")


def _right_panel_yf_symbol(category: str, symbol: str) -> str:
    return POLYMARKET_RIGHT_PANEL_YF_SYMBOLS.get((category, str(symbol).upper()), str(symbol).upper())


def _as_float(value: Any) -> float:
    try:
        if value is None:
            return np.nan
        value = float(value)
        return value if np.isfinite(value) else np.nan
    except Exception:
        return np.nan


def _fast_info_value(fast_info: Any, *keys: str) -> float:
    if fast_info is None:
        return np.nan
    for key in keys:
        try:
            if isinstance(fast_info, dict):
                value = fast_info.get(key, np.nan)
            else:
                value = getattr(fast_info, key, np.nan)
                if pd.isna(value) and hasattr(fast_info, "get"):
                    value = fast_info.get(key, np.nan)
            out = _as_float(value)
            if pd.notna(out):
                return out
        except Exception:
            continue
    return np.nan


def _yahoo_quote_page_snapshot(symbol: str) -> Dict[str, Any]:
    """
    Fallback for assets whose Yahoo data is visible on the quote page but flaky
    through yfinance.
    """
    url = f"https://finance.yahoo.com/quote/{symbol}?p={symbol}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        html = resp.text
    except Exception:
        return {}

    patterns = {
        "last_close": [
            r'"regularMarketPrice":\{"raw":(?P<value>-?\d+(?:\.\d+)?)',
            r'"currentPrice":\{"raw":(?P<value>-?\d+(?:\.\d+)?)',
        ],
        "prev_close": [
            r'"regularMarketPreviousClose":\{"raw":(?P<value>-?\d+(?:\.\d+)?)',
            r'"previousClose":\{"raw":(?P<value>-?\d+(?:\.\d+)?)',
        ],
        "date": [
            r'"regularMarketTime":(?P<value>\d+)',
        ],
    }

    out: Dict[str, Any] = {}
    for key, regexes in patterns.items():
        for pattern in regexes:
            match = re.search(pattern, html)
            if not match:
                continue
            raw = match.group("value")
            if key == "date":
                try:
                    out[key] = pd.to_datetime(int(raw), unit="s", utc=True).tz_convert(None)
                except Exception:
                    out[key] = pd.NaT
            else:
                out[key] = _as_float(raw)
            break

    last_price = out.get("last_close", np.nan)
    prev_close = out.get("prev_close", np.nan)
    if pd.notna(last_price) and pd.notna(prev_close) and prev_close != 0:
        out["chg_abs"] = float(last_price - prev_close)
        out["ret_pct"] = ((float(last_price) / float(prev_close)) - 1.0) * 100.0
    else:
        out["chg_abs"] = np.nan
        out["ret_pct"] = np.nan
    out["quote_source"] = "quote_page"
    return out


def _stooq_live_snapshot(symbol: str) -> Dict[str, Any]:
    """
    Fetch a live-ish snapshot from Stooq.

    This is used for commodity contracts where Yahoo's available ticker is not
    the same underlying instrument Polymarket resolves against.
    """
    raw_symbol = str(symbol).strip()
    symbol_key = raw_symbol.split(":", 1)[1] if raw_symbol.lower().startswith("stooq:") else raw_symbol
    url = f"https://stooq.com/q/a2/d/?s={symbol_key}&i=1"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        text = resp.text
    except Exception:
        return {
            "date": pd.NaT,
            "prev_close": np.nan,
            "last_close": np.nan,
            "chg_abs": np.nan,
            "ret_pct": np.nan,
            "quote_source": "stooq_error",
        }

    marker = "Date,Time,Open,High,Low,Close,Vol,OI,Annotation"
    idx = text.find(marker)
    if idx == -1:
        return {
            "date": pd.NaT,
            "prev_close": np.nan,
            "last_close": np.nan,
            "chg_abs": np.nan,
            "ret_pct": np.nan,
            "quote_source": "stooq_unparseable",
        }

    csv_text = text[idx:]
    reader = csv.DictReader(csv_text.splitlines())
    rows: List[dict[str, str]] = [row for row in reader if row.get("Date") and row.get("Close")]
    if not rows:
        return {
            "date": pd.NaT,
            "prev_close": np.nan,
            "last_close": np.nan,
            "chg_abs": np.nan,
            "ret_pct": np.nan,
            "quote_source": "stooq_empty",
        }

    def _row_ts(row: dict[str, str]) -> pd.Timestamp:
        return pd.to_datetime(f"{row.get('Date', '')} {row.get('Time', '')}", format="%Y%m%d %H%M%S", errors="coerce")

    rows = [row for row in rows if pd.notna(_row_ts(row))]
    if not rows:
        return {
            "date": pd.NaT,
            "prev_close": np.nan,
            "last_close": np.nan,
            "chg_abs": np.nan,
            "ret_pct": np.nan,
            "quote_source": "stooq_empty",
        }

    rows.sort(key=_row_ts)
    latest = rows[-1]
    latest_ts = _row_ts(latest)
    latest_close = _as_float(latest.get("Close"))
    latest_day = str(latest.get("Date"))

    prev_close = np.nan
    for row in reversed(rows[:-1]):
        if str(row.get("Date")) != latest_day:
            prev_close = _as_float(row.get("Close"))
            break

    if pd.isna(prev_close):
        same_day_rows = [row for row in rows if str(row.get("Date")) == latest_day]
        day_open = _as_float(same_day_rows[0].get("Open")) if same_day_rows else np.nan
        prev_close = day_open

    chg_abs = np.nan
    ret_pct = np.nan
    if pd.notna(latest_close) and pd.notna(prev_close) and prev_close != 0:
        chg_abs = float(latest_close - prev_close)
        ret_pct = ((latest_close / prev_close) - 1.0) * 100.0

    return {
        "date": latest_ts,
        "prev_close": prev_close,
        "last_close": latest_close,
        "chg_abs": chg_abs,
        "ret_pct": ret_pct,
        "quote_source": "stooq_intraday",
    }


def _latest_intraday_close(symbol: str) -> Tuple[float, pd.Timestamp]:
    for period, interval in (("1d", "1m"), ("5d", "5m")):
        for fetcher in ("history", "download"):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    if fetcher == "history":
                        hist = yf.Ticker(symbol).history(
                            period=period,
                            interval=interval,
                            prepost=True,
                            auto_adjust=False,
                            actions=False,
                        )
                    else:
                        hist = yf.download(
                            tickers=symbol,
                            period=period,
                            interval=interval,
                            prepost=True,
                            auto_adjust=False,
                            progress=False,
                            threads=False,
                            group_by="column",
                        )
            except Exception:
                continue
            if hist is None or hist.empty or "Close" not in hist.columns:
                continue
            close = pd.to_numeric(hist["Close"], errors="coerce").dropna()
            if close.empty:
                continue
            last_dt = pd.to_datetime(close.index[-1])
            if getattr(last_dt, "tzinfo", None) is not None:
                last_dt = last_dt.tz_convert(None)
            return float(close.iloc[-1]), pd.Timestamp(last_dt)
    return np.nan, pd.NaT


def _yf_live_snapshot(symbol: str) -> Dict[str, Any]:
    """
    Best-effort live Yahoo quote.

    Uses intraday bars when available so premarket and 24/7 assets can show
    current values instead of the prior daily close.
    """
    if str(symbol).lower().startswith("stooq:"):
        return _stooq_live_snapshot(symbol)

    ticker_obj = yf.Ticker(symbol)
    last_price = np.nan
    last_dt = pd.NaT
    prev_close = np.nan
    open_price = np.nan
    quote_source = "none"

    try:
        fast_info = getattr(ticker_obj, "fast_info", None)
        last_price = _fast_info_value(fast_info, "lastPrice", "last_price", "regularMarketPrice")
        prev_close = _fast_info_value(fast_info, "previousClose", "previous_close", "regularMarketPreviousClose")
        if pd.notna(last_price):
            quote_source = "fast_info"
    except Exception:
        pass

    intraday_price, intraday_dt = _latest_intraday_close(symbol)
    if pd.notna(intraday_price):
        last_price = intraday_price
        last_dt = intraday_dt
        quote_source = "intraday"

    if pd.isna(prev_close) or prev_close == 0:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                daily = ticker_obj.history(
                    period="10d",
                    interval="1d",
                    auto_adjust=False,
                    actions=False,
                )
            if daily is not None and not daily.empty and "Close" in daily.columns:
                close = pd.to_numeric(daily["Close"], errors="coerce").dropna()
                if len(close) >= 2:
                    prev_close = float(close.iloc[-2])
                elif len(close) == 1:
                    prev_close = float(close.iloc[-1])
                if pd.isna(last_price) and len(close) >= 1:
                    last_price = float(close.iloc[-1])
                    if pd.isna(last_dt):
                        last_dt = pd.to_datetime(close.index[-1])
                        if getattr(last_dt, "tzinfo", None) is not None:
                            last_dt = last_dt.tz_convert(None)
        except Exception:
            pass

    # Extract today's open price (available after 09:30 ET on trading days)
    try:
        fast_info = getattr(ticker_obj, "fast_info", None)
        if fast_info is not None:
            open_price = _fast_info_value(
                fast_info,
                "open",
                "regularMarketOpen",
                "open_price",
            )
        if not np.isfinite(open_price) or open_price == 0:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                daily = yf.Ticker(symbol).history(
                    period="1d",
                    interval="1d",
                    auto_adjust=True,
                    actions=False,
                )
            if daily is not None and not daily.empty and "Open" in daily.columns:
                op = pd.to_numeric(daily["Open"], errors="coerce").dropna()
                if not op.empty:
                    open_price = float(op.iloc[-1])
    except Exception:
        pass

    if (pd.isna(last_price) or pd.isna(prev_close)) and symbol.upper() == "BTC-USD":
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                daily = yf.download(
                    tickers=symbol,
                    period="10d",
                    interval="1d",
                    auto_adjust=False,
                    progress=False,
                    threads=False,
                    group_by="column",
                )
            if daily is not None and not daily.empty and "Close" in daily.columns:
                close = pd.to_numeric(daily["Close"], errors="coerce").dropna()
                if len(close) >= 2:
                    prev_close = float(close.iloc[-2])
                elif len(close) == 1:
                    prev_close = float(close.iloc[-1])
                if pd.isna(last_price) and len(close) >= 1:
                    last_price = float(close.iloc[-1])
                    if pd.isna(last_dt):
                        last_dt = pd.to_datetime(close.index[-1])
                        if getattr(last_dt, "tzinfo", None) is not None:
                            last_dt = last_dt.tz_convert(None)
                if pd.notna(last_price):
                    quote_source = "download"
        except Exception:
            pass

    if symbol.upper() == "BTC-USD" and (pd.isna(last_price) or pd.isna(prev_close)):
        page_snap = _yahoo_quote_page_snapshot(symbol)
        if page_snap:
            if pd.isna(last_price):
                last_price = page_snap.get("last_close", last_price)
            if pd.isna(prev_close):
                prev_close = page_snap.get("prev_close", prev_close)
            if pd.isna(last_dt):
                last_dt = page_snap.get("date", last_dt)
            if page_snap.get("quote_source") == "quote_page":
                quote_source = "quote_page"

    ret_pct = np.nan
    chg_abs = np.nan
    if pd.notna(last_price) and pd.notna(prev_close) and prev_close != 0:
        chg_abs = float(last_price - prev_close)
        ret_pct = ((last_price / prev_close) - 1.0) * 100.0

    return {
        "date": last_dt,
        "prev_close": prev_close,
        "last_close": last_price,
        "chg_abs": chg_abs,
        "ret_pct": ret_pct,
        "quote_source": quote_source,
        "open_price": open_price if np.isfinite(open_price) else np.nan,
    }


def _quick_yf_ret_pct(symbol: str) -> float:
    try:
        return float(_yf_live_snapshot(symbol).get("ret_pct", np.nan))
    except Exception:
        return np.nan


def _live_intraday_vol(
    ticker: str,
    minutes: int = 5,
    window: int = 24,
) -> float | None:
    """
    Fetch the last ~2 hours of intraday bars and compute annualized
    rolling volatility using log returns.

    window=24 matches the research notebook's 120-minute rolling window
    (24 bars × 5 minutes = 120 minutes).
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            hist = yf.Ticker(ticker).history(
                period="1d",
                interval=f"{minutes}m",
                prepost=False,
                auto_adjust=True,
                actions=False,
            )
        if hist is None or hist.empty or "Close" not in hist.columns:
            return None
        close = pd.to_numeric(hist["Close"], errors="coerce").dropna()
        if len(close) < window + 1:
            return None
        close = close.tail(window + 1)
        log_returns = np.log(close / close.shift(1)).dropna()
        if len(log_returns) < window:
            return None
        std = float(log_returns.std())
        if not np.isfinite(std) or std == 0:
            return None
        annualized_vol = float(std * np.sqrt((60 / minutes * 6.5) * 252))
        if not np.isfinite(annualized_vol) or not (0.05 <= annualized_vol <= 5.0):
            return None
        return round(annualized_vol, 6)
    except Exception:
        return None


def _compute_live_true_sentiment(
    avg_price_up: float,
    S: float,
    K: float,
    sigma: float,
    risk_free_ann: float = 0.04,
) -> tuple[float | None, float | None]:
    """
    Compute live true_sentiment and bs_neutral_prob using the same
    cash-or-nothing Black-Scholes framing as the research pipeline.
    """
    try:
        from scipy.stats import norm as _norm

        if not (np.isfinite(S) and S > 0):
            return None, None
        if not (np.isfinite(K) and K > 0):
            return None, None
        if not (np.isfinite(sigma) and sigma > 0):
            return None, None
        if not (np.isfinite(avg_price_up) and 0 <= avg_price_up <= 1):
            return None, None

        ny_tz = ZoneInfo("America/New_York")
        now_ny = datetime.now(ny_tz)
        if now_ny.weekday() >= 5:
            return None, None
        close_today = now_ny.replace(hour=16, minute=0, second=0, microsecond=0)
        if now_ny >= close_today:
            return None, None

        hours_remaining = (close_today - now_ny).total_seconds() / 3600
        T = max((hours_remaining / 24) / 252, 1e-9)
        d2 = (
            np.log(S / K)
            + (risk_free_ann - 0.5 * sigma**2) * T
        ) / (sigma * np.sqrt(T))

        bs_neutral = round(float(_norm.cdf(float(d2))), 4)
        ts = round(float(avg_price_up) - bs_neutral, 4)
        if not np.isfinite(ts):
            return None, None
        return ts, bs_neutral
    except Exception:
        return None, None


def get_prev_close(symbol: str) -> float:
    try:
        t = yf.Ticker(symbol)
        df = t.history(period="5d", interval="1d", auto_adjust=False)
        if df is None or df.empty or "Close" not in df.columns:
            return np.nan

        close = pd.to_numeric(df["Close"], errors="coerce").dropna()
        if close.empty:
            return np.nan

        idx = pd.to_datetime(close.index, errors="coerce")
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_convert("UTC")
        else:
            idx = idx.tz_localize("UTC")

        latest_bar_date = idx[-1].date()
        today_utc = datetime.now(timezone.utc).date()

        if latest_bar_date == today_utc and len(close) >= 2:
            return float(close.iloc[-2])
        return float(close.iloc[-1])
    except Exception:
        return np.nan


def yahoo_style_move(symbol: str) -> dict:
    try:
        t = yf.Ticker(symbol)
        fi = t.fast_info
        last = pd.to_numeric(
            fi.get("last_price", fi.get("lastPrice", fi.get("regularMarketPrice", np.nan))),
            errors="coerce",
        )
        open_price = pd.to_numeric(
            fi.get("open", fi.get("open_price", fi.get("regularMarketOpen", np.nan))),
            errors="coerce",
        )
        prev_close = pd.to_numeric(get_prev_close(symbol), errors="coerce")
        change = np.nan
        pct_change = np.nan
        if pd.notna(last) and pd.notna(prev_close) and prev_close != 0:
            change = float(last - prev_close)
            pct_change = float((last / prev_close - 1.0) * 100.0)
        return {
            "symbol": symbol,
            "last_price": float(last) if pd.notna(last) else np.nan,
            "open": float(open_price) if pd.notna(open_price) else np.nan,
            "prev_close": float(prev_close) if pd.notna(prev_close) else np.nan,
            "change": change,
            "pct_change": pct_change,
        }
    except Exception:
        return {
            "symbol": symbol,
            "last_price": np.nan,
            "open": np.nan,
            "prev_close": np.nan,
            "change": np.nan,
            "pct_change": np.nan,
        }


def print_crypto_yahoo_style_moves(symbols: Optional[List[str]] = None) -> None:
    symbols = [s.upper() for s in (symbols or list(CRYPTO_WS_SYMBOLS))]
    for symbol in symbols:
        move = yahoo_style_move(symbol)
        last_txt = base.human_price(move["last_price"]) if pd.notna(move["last_price"]) else "N/A"
        open_txt = base.human_price(move["open"]) if pd.notna(move["open"]) else "N/A"
        prev_txt = base.human_price(move["prev_close"]) if pd.notna(move["prev_close"]) else "N/A"
        chg_txt = base.human_price(move["change"]) if pd.notna(move["change"]) else "N/A"
        pct_txt = f"{float(move['pct_change']):+.2f}%" if pd.notna(move["pct_change"]) else "N/A"
        print(
            f"{symbol:<8} "
            f"last={last_txt:>12}  "
            f"open={open_txt:>12}  "
            f"prev_close={prev_txt:>12}  "
            f"chg={chg_txt:>10}  "
            f"pct={pct_txt}"
        )


def _infer_poly_market_end_at(category: str, target_date: pd.Timestamp | datetime | str) -> str:
    parsed = pd.to_datetime(target_date, errors="coerce")
    if pd.isna(parsed):
        return ""
    target = parsed.date()
    et = ZoneInfo("America/New_York")

    if category == "Crypto":
        end_dt = datetime(target.year, target.month, target.day, 12, 0, tzinfo=et)
    elif category == "Commodities":
        end_dt = datetime(target.year, target.month, target.day, 17, 0, tzinfo=et)
    else:
        end_dt = datetime(target.year, target.month, target.day, 16, 0, tzinfo=et)
    return end_dt.isoformat()

OUT_DIR = Path(__file__).resolve().parent.parent / "polymarket-dashboard-heatmap" / "outputs_yf_heatmap"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FALLBACK_DIRS = [
    OUT_DIR,
    Path(__file__).resolve().parent.parent / "outputs_yf_heatmap",
]


def _load_polymarket_lookup() -> Dict[str, dict]:
    if not POLYMARKET_ENABLED:
        return {}
    try:
        df = poly.get_probabilities_for_tickers(
            POLYMARKET_STOCK_TICKERS,
            include_optional=POLYMARKET_INCLUDE_OPTIONAL,
        )
    except Exception:
        return {}
    if df.empty or "ticker" not in df.columns:
        return {}
    df = df.copy()
    df["ticker"] = df["ticker"].astype(str).str.upper()
    return df.set_index("ticker").to_dict("index")


def _poly_fields_for_ticker(ticker: str, poly_lookup: Dict[str, dict]) -> dict:
    entry = poly_lookup.get(str(ticker).upper(), {}) if poly_lookup else {}
    payload = {
        "poly_target_date": entry.get("target_date"),
        "poly_up_probability": pd.to_numeric(entry.get("up_probability", np.nan), errors="coerce"),
    }
    if POLYMARKET_INCLUDE_OPTIONAL:
        payload.update(
            {
                "poly_question": entry.get("question"),
                "poly_market_slug": entry.get("market_slug"),
                "poly_market_id": entry.get("market_id"),
                "poly_yes_token_id": entry.get("yes_token_id"),
                "poly_yes_midpoint": entry.get("yes_midpoint"),
                "poly_best_bid_yes": entry.get("best_bid_yes"),
                "poly_best_ask_yes": entry.get("best_ask_yes"),
                "poly_orderbook_yes": entry.get("orderbook_yes"),
            }
        )
    return payload


def _fetch_right_panel_market(category: str, label: str, symbol: str, target_date) -> dict:
    """
    Try slug lookup first. Fall back to event search when a recurring market
    uses a different naming convention than build_up_down_slug().
    """
    slug = poly.build_up_down_slug(symbol, target_date)
    snap = poly.get_market_probabilities_by_slug(slug, include_optional=False)
    if snap.get("up_probability") is not None:
        return snap

    search_results = poly.search_events(
        f"{label} up {target_date.strftime('%B %d')}",
        limit=5,
    )
    for result in search_results:
        probability = pd.to_numeric(result.get("probability", np.nan), errors="coerce")
        if pd.notna(probability):
            return {
                "market_slug": result.get("market_slug") or result.get("event_slug"),
                "question": result.get("title"),
                "market_id": result.get("event_id"),
                "market_created_at": None,
                "market_updated_at": None,
                "market_end_at": result.get("end_date"),
                "fetched_at": datetime.now(ZoneInfo("America/New_York")).isoformat(),
                "up_probability": probability,
                "probability_source": "gamma_search_fallback",
            }
    return snap


def _poly_market_rows() -> pd.DataFrame:
    rows: List[dict] = []
    for category, specs in POLYMARKET_RIGHT_PANEL_SPECS.items():
        for label, symbol in specs:
            if category == "Crypto":
                target_date = poly.get_effective_crypto_market_date()
            else:
                target_date = poly.get_effective_nyse_market_date()
            snap = _fetch_right_panel_market(category, label, symbol, target_date)
            market_end_at = snap.get("market_end_at") or _infer_poly_market_end_at(category, target_date)
            yf_symbol = _right_panel_yf_symbol(category, symbol)
            snapshot = _yf_live_snapshot(yf_symbol)
            prev_close = pd.to_numeric(snapshot.get("prev_close", np.nan), errors="coerce")
            last_close = pd.to_numeric(snapshot.get("last_close", np.nan), errors="coerce")
            chg_abs = pd.to_numeric(snapshot.get("chg_abs", np.nan), errors="coerce")
            ret_pct = pd.to_numeric(snapshot.get("ret_pct", np.nan), errors="coerce")
            rows.append(
                {
                    "category": category,
                    "label": label,
                    "ticker": symbol.upper(),
                    "yf_symbol": yf_symbol,
                    "date": snapshot.get("date", pd.NaT),
                    "prev_close": prev_close,
                    "last_close": last_close,
                    "chg_abs": chg_abs,
                    "ret_pct": ret_pct,
                    "volume": np.nan,
                    "vol_avg20": np.nan,
                    "vol_ratio": np.nan,
                    "market_cap": np.nan,
                    # Keep the Yahoo-prefixed aliases for the older matplotlib table
                    # and any transitional callers that still read those names.
                    "yf_ret_pct": ret_pct,
                    "yf_live_price": last_close,
                    "yf_open_price": np.nan,
                    "yf_prev_close": prev_close,
                    "market_day": target_date.isoformat(),
                    "poly_target_date": target_date.isoformat(),
                    "market_slug": snap.get("market_slug"),
                    "question": snap.get("question"),
                    "market_id": snap.get("market_id"),
                    "market_created_at": snap.get("market_created_at"),
                    "market_updated_at": snap.get("market_updated_at"),
                    "market_end_at": market_end_at,
                    "fetched_at": snap.get("fetched_at"),
                    "poly_up_probability": pd.to_numeric(snap.get("up_probability", np.nan), errors="coerce"),
                    "poly_probability_source": snap.get("probability_source"),
                    "open_price": np.nan,
                    "true_sentiment": np.nan,
                    "bs_neutral_prob": np.nan,
                    "sigma_live": np.nan,
                }
            )
            remaining_txt = _format_remaining(market_end_at)
            print(
                f"[POLY-RIGHT] {category} | {label} | day={target_date.isoformat()} | "
                f"remaining={remaining_txt} | slug={snap.get('market_slug')}"
            )
    return pd.DataFrame(rows)


def _stock_live_rows(stock_assets: List[Tuple[str, str, str]], poly_lookup: Dict[str, dict]) -> List[dict]:
    rows: List[dict] = []
    for category, label, ticker in stock_assets:
        snapshot = _yf_live_snapshot(ticker)
        poly_fields = _poly_fields_for_ticker(ticker, poly_lookup)
        # Use a daily history for the sparkline, but the displayed price comes from
        # the latest intraday or fast_info quote above.
        hist = fetch_history_for_ticker(ticker, period="3mo", interval="1d")
        vol = hist["Volume"].astype(float) if not hist.empty and "Volume" in hist.columns else pd.Series(dtype=float)
        idx = pd.to_datetime(hist["Close"].index).tz_localize(None) if not hist.empty and "Close" in hist.columns else pd.DatetimeIndex([])
        if not vol.empty:
            vol_s = pd.Series(vol.values, index=pd.to_datetime(vol.index).tz_localize(None), dtype=float).reindex(idx)
        else:
            vol_s = pd.Series(index=idx, dtype=float)
        vol_avg20 = vol_s.rolling(20, min_periods=10).mean() if not vol_s.empty else pd.Series(dtype=float)
        last_volume = float(vol_s.iloc[-1]) if not vol_s.empty and pd.notna(vol_s.iloc[-1]) else np.nan
        last_vol_avg20 = float(vol_avg20.iloc[-1]) if not vol_avg20.empty and pd.notna(vol_avg20.iloc[-1]) else np.nan
        vol_ratio = (
            float(last_volume / last_vol_avg20)
            if pd.notna(last_volume) and pd.notna(last_vol_avg20) and last_vol_avg20 != 0
            else np.nan
        )

        sigma = _live_intraday_vol(ticker)
        open_price = pd.to_numeric(snapshot.get("open_price", np.nan), errors="coerce")
        last_close = pd.to_numeric(snapshot.get("last_close", np.nan), errors="coerce")
        poly_prob = pd.to_numeric(poly_fields.get("poly_up_probability", np.nan), errors="coerce")
        snapshot_dt = pd.to_datetime(snapshot.get("date"), errors="coerce")
        if pd.notna(snapshot_dt):
            snapshot_ts = pd.Timestamp(snapshot_dt)
            if snapshot_ts.tzinfo is None:
                snapshot_ts = snapshot_ts.tz_localize("UTC")
            else:
                snapshot_ts = snapshot_ts.tz_convert("UTC")
            snapshot_ny_date = snapshot_ts.tz_convert("America/New_York").date()
        else:
            snapshot_ny_date = None
        now_ny_date = datetime.now(ZoneInfo("America/New_York")).date()
        is_current_market_day = snapshot_ny_date == now_ny_date

        live_true_sentiment = None
        live_bs_neutral = None
        if (
            is_current_market_day
            and pd.notna(sigma)
            and pd.notna(poly_prob)
            and pd.notna(last_close)
            and pd.notna(open_price)
            and float(open_price) > 0
            and float(last_close) > 0
        ):
            live_true_sentiment, live_bs_neutral = _compute_live_true_sentiment(
                avg_price_up=float(poly_prob),
                S=float(last_close),
                K=float(open_price),
                sigma=float(sigma),
                risk_free_ann=RISK_FREE_ANN,
            )

        rows.append(
            {
                "category": category,
                "label": label,
                "ticker": ticker,
                "date": snapshot.get("date", pd.NaT),
                "prev_close": pd.to_numeric(snapshot.get("prev_close", np.nan), errors="coerce"),
                "last_close": pd.to_numeric(snapshot.get("last_close", np.nan), errors="coerce"),
                "chg_abs": pd.to_numeric(snapshot.get("chg_abs", np.nan), errors="coerce"),
                "ret_pct": pd.to_numeric(snapshot.get("ret_pct", np.nan), errors="coerce"),
                "volume": last_volume,
                "vol_avg20": last_vol_avg20,
                "vol_ratio": vol_ratio,
                "market_cap": base.get_market_cap(ticker) if category == "US Equities" else np.nan,
                "open_price": float(open_price) if pd.notna(open_price) else np.nan,
                "true_sentiment": live_true_sentiment,
                "bs_neutral_prob": live_bs_neutral,
                "sigma_live": float(sigma) if sigma is not None else np.nan,
                **poly_fields,
            }
        )
    return rows


def _extract_ohlcv(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        if ticker not in raw.columns.get_level_values(0):
            return pd.DataFrame()
        sub = raw[ticker].copy()
    else:
        sub = raw.copy()

    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in sub.columns]
    if not keep:
        return pd.DataFrame()
    sub = sub[keep].copy()
    idx = pd.to_datetime(sub.index)
    sub.index = idx.tz_convert(None) if idx.tz is not None else idx.tz_localize(None)
    return sub.sort_index()


def fetch_history_for_ticker(ticker: str, period: str = "3mo", interval: str = "1d") -> pd.DataFrame:
    """Fetch a single ticker history more defensively than a large batch download."""
    for attempt in range(3):
        try:
            hist = yf.Ticker(ticker).history(
                period=period,
                interval=interval,
                auto_adjust=False,
                actions=False,
            )
            if hist is not None and not hist.empty:
                return _extract_ohlcv(hist, ticker)
        except Exception:
            pass
        try:
            fallback = yf.download(
                tickers=ticker,
                period=period,
                interval=interval,
                auto_adjust=False,
                progress=False,
                threads=False,
                group_by="column",
            )
            if fallback is not None and not fallback.empty:
                if isinstance(fallback.columns, pd.MultiIndex):
                    fallback = fallback[ticker] if ticker in fallback.columns.get_level_values(0) else fallback
                fidx = pd.to_datetime(fallback.index)
                fallback.index = fidx.tz_convert(None) if fidx.tz is not None else fidx.tz_localize(None)
                return fallback.sort_index()
        except Exception:
            pass
        time.sleep(0.5 * (attempt + 1))
    return pd.DataFrame()


def load_cached_snapshot() -> Optional[pd.DataFrame]:
    candidates: List[Path] = []
    for root in FALLBACK_DIRS:
        if not root.exists():
            continue
        candidates.extend(sorted(root.glob("daily_returns_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True))
        candidates.extend(sorted(root.glob("daily_tiles_metrics_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True))

    for path in candidates:
        try:
            cached = pd.read_csv(path)
            if cached.empty:
                continue
            needed = {"category", "label", "ticker"}
            if not needed.issubset(cached.columns):
                continue
            if "last_close" not in cached.columns and {"prev_close", "ret_pct"}.issubset(cached.columns):
                prev = pd.to_numeric(cached["prev_close"], errors="coerce")
                ret = pd.to_numeric(cached["ret_pct"], errors="coerce")
                cached["last_close"] = prev * (1.0 + ret / 100.0)
            if "chg_abs" not in cached.columns and {"prev_close", "last_close"}.issubset(cached.columns):
                cached["chg_abs"] = pd.to_numeric(cached["last_close"], errors="coerce") - pd.to_numeric(cached["prev_close"], errors="coerce")
            if "vol_avg20" not in cached.columns:
                cached["vol_avg20"] = np.nan
            if "vol_ratio" not in cached.columns:
                cached["vol_ratio"] = np.nan
            if "market_cap" not in cached.columns:
                cached["market_cap"] = np.nan
            return cached
        except Exception:
            continue
    return None


def load_market_bundle() -> Tuple[pd.DataFrame, Dict[str, pd.Series], str]:
    poly_lookup = _load_polymarket_lookup()
    stock_assets = [row for row in base.ASSETS if row[0] == "US Equities"]

    # Probe one ticker first. If Yahoo is down, fall back to today's cached snapshot.
    probe_ticker = stock_assets[0][2]
    probe = _yf_live_snapshot(probe_ticker)
    probe_ok = pd.notna(probe.get("last_close", np.nan))
    if not probe_ok:
        cached = load_cached_snapshot()
        if cached is None:
            raise RuntimeError("No Yahoo Finance data and no cached snapshot available.")

        cached = cached.copy()
        cached["ticker"] = cached["ticker"].astype(str)
        cached_map = cached.set_index("ticker").to_dict("index")
        fallback_rows: List[dict] = []
        for category, label, ticker in stock_assets:
            row = cached_map.get(ticker.upper()) or cached_map.get(ticker) or {}
            fallback_rows.append(
                {
                    "category": category,
                    "label": label,
                    "ticker": ticker,
                    "date": pd.to_datetime(row.get("date", pd.NaT), errors="coerce"),
                    "prev_close": pd.to_numeric(row.get("prev_close", np.nan), errors="coerce"),
                    "last_close": pd.to_numeric(row.get("last_close", np.nan), errors="coerce"),
                    "chg_abs": pd.to_numeric(row.get("chg_abs", np.nan), errors="coerce"),
                    "ret_pct": pd.to_numeric(row.get("ret_pct", np.nan), errors="coerce"),
                    "volume": pd.to_numeric(row.get("volume", np.nan), errors="coerce"),
                    "vol_avg20": pd.to_numeric(row.get("vol_avg20", np.nan), errors="coerce"),
                    "vol_ratio": pd.to_numeric(row.get("vol_ratio", np.nan), errors="coerce"),
                    "market_cap": pd.to_numeric(row.get("market_cap", np.nan), errors="coerce"),
                    "open_price": pd.to_numeric(row.get("open_price", np.nan), errors="coerce"),
                    "true_sentiment": pd.to_numeric(row.get("true_sentiment", np.nan), errors="coerce"),
                    "bs_neutral_prob": pd.to_numeric(row.get("bs_neutral_prob", np.nan), errors="coerce"),
                    "sigma_live": pd.to_numeric(row.get("sigma_live", np.nan), errors="coerce"),
                    **_poly_fields_for_ticker(ticker, poly_lookup),
                }
            )
        fallback_rows.extend(_poly_market_rows().to_dict(orient="records"))
        out = pd.DataFrame(fallback_rows)
        history_map = {str(ticker): pd.Series(dtype=float) for ticker in out["ticker"].astype(str)}
        return out.sort_values(["category", "ticker"]).reset_index(drop=True), history_map, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    history_map: Dict[str, pd.Series] = {}
    rows: List[dict] = []
    for category, label, ticker in stock_assets:
        hist = fetch_history_for_ticker(ticker, period="3mo", interval="1d")
        close = hist["Close"].astype(float) if not hist.empty and "Close" in hist.columns else pd.Series(dtype=float)
        history_map[ticker] = close.tail(24).copy()

    rows.extend(_stock_live_rows(stock_assets, poly_lookup))
    rows.extend(_poly_market_rows().to_dict(orient="records"))
    
    out = pd.DataFrame(rows)
    return out.sort_values(["category", "ticker"]).reset_index(drop=True), history_map, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _refresh_worker(interval_seconds: int) -> None:
    while True:
        try:
            df, history, last_fetched = load_market_bundle()
            with _data_lock:
                _shared_state["df"] = df
                _shared_state["history"] = history
                _shared_state["last_fetched"] = last_fetched
        except Exception as exc:
            import traceback
            traceback.print_exc()
            print(f"[REFRESH ERROR] {exc}")
        time.sleep(interval_seconds)


def start_background_refresh(interval_seconds: int = 10) -> None:
    t = threading.Thread(
        target=_refresh_worker,
        args=(interval_seconds,),
        daemon=True,
    )
    t.start()


def poly_up_color(up_prob: float) -> str:
    if pd.isna(up_prob):
        return "#334155"
    up = max(0.0, min(1.0, float(up_prob)))
    mid = "#334155"
    red = "#ef4444"
    green = "#22c55e"
    if up <= 0.5:
        return base.mix_hex(red, mid, up / 0.5)
    return base.mix_hex(mid, green, (up - 0.5) / 0.5)


def _short_market_label(text: str, limit: int = 18) -> str:
    text = str(text).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _format_market_day(value: str | None) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return ""
    return f"{parsed.strftime('%b')} {parsed.day}"


def _format_remaining(value: str | None) -> str:
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        return ""
    now = pd.Timestamp.now(tz="UTC")
    delta = parsed - now
    if delta.total_seconds() <= 0:
        return "ended"
    total_minutes = int(delta.total_seconds() // 60)
    days, rem_minutes = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(rem_minutes, 60)
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h" if minutes == 0 else f"{hours}h {minutes}min"
    return f"{minutes}min"


def _format_et_clock(value: str | None) -> str:
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        return ""
    try:
        et = parsed.tz_convert("America/New_York")
    except Exception:
        return ""
    clock = et.strftime("%I:%M %p ET")
    return clock[1:] if clock.startswith("0") else clock


def draw_poly_tile(ax, x: float, y: float, w: float, h: float, rec: pd.Series) -> None:
    category = str(rec.get("category", ""))
    up_prob = rec.get("poly_up_probability", np.nan)
    yf_ret_pct = rec.get("yf_ret_pct", np.nan)
    base_color = base.tile_color("US Equities", yf_ret_pct, np.nan)
    right_color = poly_up_color(up_prob)
    left_tri = patches.Polygon([(x, y), (x, y + h), (x + w, y + h)], closed=True, facecolor=base_color, edgecolor="none")
    right_tri = patches.Polygon([(x, y), (x + w, y), (x + w, y + h)], closed=True, facecolor=right_color, edgecolor="none", alpha=0.95)
    border = patches.Rectangle((x, y), w, h, linewidth=0.8, edgecolor="#1f2937", facecolor="none")
    diag = Line2D([x, x + w], [y, y + h], color="#0f172a", linewidth=1.0, alpha=0.9)

    ax.add_patch(left_tri)
    ax.add_patch(right_tri)
    ax.add_patch(border)
    ax.add_line(diag)

    label = _short_market_label(str(rec.get("label", rec.get("ticker", ""))))
    yf_txt = f"{float(yf_ret_pct):+.1f}%" if pd.notna(yf_ret_pct) else "N/A"
    pct_txt = f"Poly Up {float(up_prob) * 100:.0f}%" if pd.notna(up_prob) else "Poly N/A"
    day_txt = _format_market_day(str(rec.get("market_day", "")))
    center_txt = ""
    if category == "Crypto":
        live_price = pd.to_numeric(rec.get("yf_live_price", np.nan), errors="coerce")
        center_txt = base.human_price(live_price) if pd.notna(live_price) else ""

    ax.text(x + 0.05, y + h - 0.08, label, ha="left", va="top", color="#f9fafb", fontsize=9.4, fontweight="bold", clip_on=True)
    ax.text(x + w - 0.05, y + h - 0.08, day_txt, ha="right", va="top", color="#cbd5e1", fontsize=8.2, fontweight="bold", clip_on=True)
    ax.text(x + 0.05, y + h - 0.24, yf_txt, ha="left", va="top", color="#f8fafc", fontsize=9.0, fontweight="bold", clip_on=True)
    ax.text(x + w - 0.05, y + 0.11, pct_txt, ha="right", va="bottom", color="#f8fafc", fontsize=9.0, fontweight="bold", clip_on=True)
    if center_txt:
        ax.text(
            x + w / 2.0,
            y + h / 2.0,
            center_txt,
            ha="center",
            va="center",
            color="#f8fafc",
            fontsize=11.5,
            fontweight="bold",
            clip_on=True,
        )


def draw_poly_split_rows(
    ax,
    row_df: pd.DataFrame,
    x0: float,
    y0: float,
    panel_w: float,
    panel_h: float,
    splits: List[int],
) -> None:
    row = row_df.reset_index(drop=True)
    if row.empty:
        return
    if not splits:
        splits = [len(row)]

    n_rows = len(splits)
    gap = 0.08
    row_h = (panel_h - gap * (n_rows - 1)) / n_rows
    start = 0
    for i, count in enumerate(splits):
        if start >= len(row):
            break
        end = min(len(row), start + max(0, int(count)))
        block = row.iloc[start:end].copy()
        start = end
        if block.empty:
            continue
        y = y0 + (n_rows - 1 - i) * (row_h + gap)
        n_cols = len(block)
        unit = panel_w / n_cols
        for c in range(n_cols):
            x = x0 + c * unit
            draw_poly_tile(ax, x, y, unit, row_h, block.iloc[c])


def draw_banner(ax, df: pd.DataFrame, history_map: Dict[str, pd.Series], frame_idx: int) -> None:
    ax.clear()
    ax.set_facecolor("#0b1220")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    if df.empty:
        return

    def _short_banner_name(text: str, limit: int = 16) -> str:
        text = str(text).strip()
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 1)].rstrip() + "…"

    items = df[df["category"] == "US Equities"].copy().reset_index(drop=True)
    visible = min(7, len(items))
    if visible <= 0:
        return
    start = frame_idx % len(items)
    order = pd.concat([items.iloc[start:], items.iloc[:start]], ignore_index=True)

    card_w = 1.0 / visible
    for i, rec in order.iloc[:visible].iterrows():
        x = i * card_w
        pad_x = 0.008
        pad_y = 0.06
        inner_w = card_w - 2 * pad_x
        inner_h = 0.88

        rect = patches.FancyBboxPatch(
            (x + pad_x, pad_y),
            inner_w,
            inner_h,
            boxstyle="round,pad=0.008,rounding_size=0.012",
            linewidth=0.8,
            edgecolor="#223044",
            facecolor="#111827",
        )
        ax.add_patch(rect)

        ticker = str(rec["ticker"])
        series = history_map.get(ticker, pd.Series(dtype=float))
        if not series.empty and len(series) > 1:
            vals = series.values.astype(float)
            vals = vals[np.isfinite(vals)]
            if len(vals) > 1:
                lo, hi = float(np.min(vals)), float(np.max(vals))
                rng = hi - lo if hi > lo else 1.0
                xs = np.linspace(x + pad_x + 0.03, x + pad_x + inner_w - 0.03, len(vals))
                ys = pad_y + 0.18 + ((vals - lo) / rng) * 0.28
                ax.plot(xs, ys, color="#22c55e" if float(rec.get("ret_pct", 0.0) or 0.0) >= 0 else "#ef4444", linewidth=1.2, alpha=0.95)

        ax.text(
            x + pad_x + 0.005,
            0.84,
            _short_banner_name(str(rec["label"])),
            ha="left",
            va="top",
            fontsize=9.2,
            color="#f8fafc",
            fontweight="bold",
            clip_on=True,
        )
        ret_txt = f"{rec['ret_pct']:+.2f}%" if pd.notna(rec["ret_pct"]) else "N/A"
        ax.text(
            x + pad_x + inner_w - 0.005,
            0.84,
            ret_txt,
            ha="right",
            va="top",
            fontsize=9.2,
            color="#e2e8f0",
            clip_on=True,
        )
        ax.text(
            x + pad_x + 0.02,
            0.22,
            str(rec["category"]),
            ha="left",
            va="top",
            fontsize=7.5,
            color="#94a3b8",
        )


def _draw_equity_tile(ax, x: float, y: float, w: float, h: float, rec: pd.Series) -> None:
    base_color = base.tile_color("US Equities", rec["ret_pct"], rec["vol_ratio"])
    up_prob = rec.get("poly_up_probability", np.nan)
    right_color = poly_up_color(up_prob)

    left_tri = patches.Polygon([(x, y), (x, y + h), (x + w, y + h)], closed=True, facecolor=base_color, edgecolor="none")
    right_tri = patches.Polygon([(x, y), (x + w, y), (x + w, y + h)], closed=True, facecolor=right_color, edgecolor="none", alpha=0.95)
    border = patches.Rectangle((x, y), w, h, linewidth=0.8, edgecolor="#1f2937", facecolor="none")
    diag = Line2D([x, x + w], [y, y + h], color="#0f172a", linewidth=1.1, alpha=0.9)

    ax.add_patch(left_tri)
    ax.add_patch(right_tri)
    ax.add_patch(border)
    ax.add_line(diag)

    ticker = str(rec["ticker"])
    ret_txt = f"{rec['ret_pct']:+.2f}%" if pd.notna(rec["ret_pct"]) else "N/A"
    poly_txt = f"Poly Up {float(up_prob) * 100:.0f}%" if pd.notna(up_prob) else "N/A"
    ax.text(
        x + 0.04,
        y + h - 0.05,
        ticker,
        ha="left",
        va="top",
        color="#f9fafb",
        fontsize=12,
        fontweight="bold",
    )
    ax.text(
        x + 0.04,
        y + h - 0.35,
        ret_txt,
        ha="left",
        va="top",
        color="#f8fafc",
        fontsize=9.5,
    )
    ax.text(
        x + w - 0.04,
        y + 0.10,
        poly_txt,
        ha="right",
        va="bottom",
        color="#f8fafc",
        fontsize=9.0,
        fontweight="bold",
    )


def draw_heatmap(ax, df: pd.DataFrame) -> None:
    ax.clear()
    ax.set_facecolor("#0b1220")
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)

    grouped = {c: df[df["category"] == c].copy() for c in CATEGORY_ORDER}
    left_x, left_w = 0.2, 9.4
    right_x, right_w = 10.0, 5.8
    base_y = 0.35
    body_h = 7.8
    eq_header_h = 0.34
    rhs_header_h = 0.28
    header_y = body_h + base_y - 0.08

    def _section_remaining_text(section: str) -> str:
        if section == "US Equities":
            et = ZoneInfo("America/New_York")
            market_date = poly.get_effective_nyse_market_date()
            end_at = datetime(market_date.year, market_date.month, market_date.day, 16, 0, tzinfo=et)
            return _format_remaining(end_at.isoformat())

        section_df = grouped.get(section, pd.DataFrame())
        if section_df.empty or "market_end_at" not in section_df.columns:
            return ""
        end_val = section_df["market_end_at"].dropna()
        if end_val.empty:
            return ""
        return _format_remaining(str(end_val.iloc[0]))

    ax.text(left_x + 0.10, header_y, "Stocks", ha="left", va="top", color="#d1d5db", fontsize=13, fontweight="bold")
    stock_end_txt = _section_remaining_text("US Equities")
    if stock_end_txt:
        ax.text(left_x + left_w - 0.08, header_y, stock_end_txt, ha="right", va="top", color="#94a3b8", fontsize=10.0, fontweight="bold")
    stock_df = grouped["US Equities"].copy().sort_values("market_cap", ascending=False, na_position="last").reset_index(drop=True)
    if not stock_df.empty:
        n = len(stock_df)
        col1_end = min(2, n)
        col2_end = min(4, n)
        groups = [stock_df.iloc[:col1_end].copy(), stock_df.iloc[col1_end:col2_end].copy(), stock_df.iloc[col2_end:].copy()]
        groups = [g for g in groups if not g.empty]
        total_cap = float(pd.to_numeric(stock_df["market_cap"], errors="coerce").fillna(0.0).sum())
        if total_cap <= 0:
            total_cap = float(len(stock_df))
        x_cursor = left_x
        for g in groups:
            g_caps = pd.to_numeric(g["market_cap"], errors="coerce").fillna(0.0)
            g_sum = float(g_caps.sum()) if float(g_caps.sum()) > 0 else float(len(g))
            col_w = left_w * (g_sum / total_cap)
            y_top = base_y + body_h - eq_header_h
            for _, rec in g.iterrows():
                s = float(rec["market_cap"]) if pd.notna(rec["market_cap"]) and float(rec["market_cap"]) > 0 else 1.0
                rh = (body_h - eq_header_h) * (s / g_sum)
                y_top -= rh
                _draw_equity_tile(ax, x_cursor, y_top, col_w, rh, rec)
            x_cursor += col_w

    row_h = (body_h - 2 * 0.16) / 3.0
    idx_y = base_y + 2 * (row_h + 0.16)
    cry_y = base_y + 1 * (row_h + 0.16)
    com_y = base_y

    def _draw_section_header(title: str, y: float, section_key: str) -> None:
        end_txt = _section_remaining_text(section_key)
        ax.text(right_x + 0.08, y, title, ha="left", va="top", color="#d1d5db", fontsize=12, fontweight="bold")
        if end_txt:
            ax.text(right_x + right_w - 0.08, y, end_txt, ha="right", va="top", color="#94a3b8", fontsize=10.0, fontweight="bold")

    _draw_section_header("Indices", idx_y + row_h - 0.06, "Indices")
    _draw_section_header("Crypto", cry_y + row_h - 0.06, "Crypto")
    _draw_section_header("Commodities", com_y + row_h - 0.06, "Commodities")

    draw_poly_split_rows(
        ax,
        grouped["Indices"],
        x0=right_x,
        y0=idx_y,
        panel_w=right_w,
        panel_h=max(0.5, row_h - rhs_header_h),
        splits=[3, 3],
    )
    draw_poly_split_rows(
        ax,
        grouped["Crypto"],
        x0=right_x,
        y0=cry_y,
        panel_w=right_w,
        panel_h=max(0.5, row_h - rhs_header_h),
        splits=[3],
    )
    draw_poly_split_rows(
        ax,
        grouped["Commodities"],
        x0=right_x,
        y0=com_y,
        panel_w=right_w,
        panel_h=max(0.5, row_h - rhs_header_h),
        splits=[3],
    )

    latest = pd.to_datetime(df["date"].dropna().max()).strftime("%Y-%m-%d") if df["date"].notna().any() else datetime.now().strftime("%Y-%m-%d")
    title = f"Yahoo + Polymarket Dashboard ({latest})"
    subtitle = "Stocks from Yahoo Finance, right-side markets from Polymarket"
    ax.text(0.2, 8.65, title, ha="left", va="bottom", color="#f3f4f6", fontsize=18, fontweight="bold")
    ax.text(0.2, 8.30, subtitle, ha="left", va="bottom", color="#9ca3af", fontsize=11)
    ax.axis("off")


def draw_table(ax, df: pd.DataFrame) -> None:
    ax.clear()
    ax.set_facecolor("#0b1220")
    ax.axis("off")

    show = df[df["category"] == "US Equities"].copy()
    show["yf_ret_pct"] = show["ret_pct"].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A")
    show["yf_close"] = show["last_close"].apply(lambda x: base.human_price(x) if pd.notna(x) else "N/A")
    cols = ["category", "label", "yf_close", "yf_ret_pct"]
    table_df = show[cols].rename(
        columns={
            "category": "Category",
            "label": "Name",
            "yf_close": "YF Close",
            "yf_ret_pct": "YF Ret",
        }
    )

    ax.text(0.02, 0.98, "Table View", transform=ax.transAxes, ha="left", va="top", fontsize=18, fontweight="bold", color="#f3f4f6")
    ax.text(0.02, 0.94, "Yahoo Finance snapshot", transform=ax.transAxes, ha="left", va="top", fontsize=10.5, color="#9ca3af")

    cell_text = table_df.values.tolist()
    table = ax.table(
        cellText=cell_text,
        colLabels=list(table_df.columns),
        cellLoc="left",
        colLoc="left",
        loc="upper left",
        bbox=[0.02, 0.04, 0.96, 0.85],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8.5)
    table.scale(1.0, 1.35)

    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#223044")
        if r == 0:
            cell.set_facecolor("#111827")
            cell.get_text().set_color("#e5e7eb")
            cell.get_text().set_weight("bold")
        else:
            row = table_df.iloc[r - 1]
            if row["Category"] == "US Equities":
                cell.set_facecolor("#0f172a" if r % 2 == 0 else "#111827")
            elif row["Category"] == "Indices":
                cell.set_facecolor("#132238" if r % 2 == 0 else "#111827")
            elif row["Category"] == "Crypto":
                cell.set_facecolor("#132430" if r % 2 == 0 else "#111827")
            else:
                cell.set_facecolor("#241f2e" if r % 2 == 0 else "#111827")
            cell.get_text().set_color("#f8fafc")

def build_status_text(df: pd.DataFrame, view: str, last_fetched: str, next_refresh: int) -> str:
    stock_n = int((df["category"] == "US Equities").sum()) if not df.empty else 0
    return f"view={view} | stocks={stock_n} | fetched={last_fetched} | next refresh in ~{next_refresh}s"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--view", choices=VIEW_CHOICES, default="heatmap", help="Initial view to show.")
    parser.add_argument("--refresh-seconds", type=int, default=10, help="Reload live data every N seconds.")
    parser.add_argument("--banner-seconds", type=int, default=2, help="Rotate the banner every N seconds.")
    parser.add_argument("--no-show", action="store_true", help="Do not open the chart window.")
    args = parser.parse_args()

    state: Dict[str, Any] = {
        "view": args.view,
        "frame": 0,
        "last_fetch_ts": 0.0,
        "df": pd.DataFrame(),
        "history": {},
        "last_fetched": "",
        "status": "warming up",
    }

    # Start background refresh thread before showing the window.
    start_background_refresh(args.refresh_seconds)

    fig = plt.figure(figsize=(18, 10), facecolor="#0b1220")
    gs = fig.add_gridspec(2, 1, height_ratios=[0.15, 0.85], hspace=0.02)
    ax_banner = fig.add_subplot(gs[0])
    ax_main = fig.add_subplot(gs[1])

    def redraw() -> None:
        with _data_lock:
            df = _shared_state["df"].copy()
            history = _shared_state["history"].copy()
            last_fetched = _shared_state["last_fetched"]

        state["df"] = df
        state["history"] = history
        state["last_fetched"] = last_fetched

        if df.empty:
            ax_main.clear()
            ax_main.set_facecolor("#0b1220")
            ax_main.text(0.5, 0.5, "Loading...", ha="center", va="center", color="#f8fafc", fontsize=14)
            ax_main.axis("off")
            ax_banner.axis("off")
            return

        draw_banner(ax_banner, df, history, state["frame"])
        if state["view"] == "heatmap":
            draw_heatmap(ax_main, df)
        else:
            draw_table(ax_main, df)

        fig.suptitle(
            build_status_text(df, state["view"], last_fetched, args.refresh_seconds),
            fontsize=10,
            color="#cbd5e1",
            y=0.995,
        )

    def on_key(event) -> None:
        key = str(event.key).lower() if event.key else ""
        if key in {"h", "1"}:
            state["view"] = "heatmap"
            redraw()
            fig.canvas.draw_idle()
        elif key in {"t", "2"}:
            state["view"] = "table"
            redraw()
            fig.canvas.draw_idle()

    fig.canvas.mpl_connect("key_press_event", on_key)

    def update(frame_idx: int):
        state["frame"] = frame_idx
        # Read from shared state instead of calling load_market_bundle() directly.
        with _data_lock:
            df = _shared_state["df"].copy()
            history = _shared_state["history"].copy()
            last_fetched = _shared_state["last_fetched"]

        state["df"] = df
        state["history"] = history
        state["last_fetched"] = last_fetched
        state["status"] = build_status_text(df, state["view"], last_fetched, args.refresh_seconds)

        redraw()
        return []

    redraw()
    anim = FuncAnimation(fig, update, interval=max(1000, args.banner_seconds * 1000), blit=False, cache_frame_data=False)
    _ = anim

    if not args.no_show:
        plt.show()


if __name__ == "__main__":
    main()
