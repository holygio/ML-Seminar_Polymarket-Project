import argparse
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    ASSETS,
    DATA_DIR,
    DAYS_BACK,
    FIREWALL_HOUR_NY,
    FIREWALL_MINUTE_NY,
    INTRADAY_WINDOW_MINUTES,
    LOG_DIR,
    RISK_FREE_ANN,
)
from pipeline import Orderbook, build_preopen_panel, check_lead_lag, collapse_to_windows


def setup_logging(run_date: str) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / f"pipeline_{run_date}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )


def step1_fetch_raw(ob: Orderbook) -> tuple[pd.DataFrame, list, list]:
    """
    Fetch raw PM orderbook for all assets.
    Returns (raw_df, assets_ok, assets_failed).
    Per-asset try/except: one failure does not abort the rest.
    """
    assets_ok, assets_failed, frames = [], [], []

    for asset in ASSETS:
        ticker = asset[0].upper()
        try:
            logging.info(f"fetching raw PM data: {ticker}")
            df = ob.fetch_raw_orderbook([asset])
            if df.empty:
                logging.warning(f"{ticker}: empty response")
                assets_failed.append(ticker)
            else:
                frames.append(df)
                assets_ok.append(ticker)
                logging.info(f"{ticker}: {len(df)} rows")
        except Exception as exc:
            logging.error(f"{ticker}: FAILED — {exc}")
            assets_failed.append(ticker)

    if not frames:
        raise RuntimeError("all assets failed in step1 — aborting")

    combined = pd.concat(frames, ignore_index=True)
    logging.info(f"raw orderbook total: {len(combined)} rows, {len(assets_ok)} assets")
    return combined, assets_ok, assets_failed


def step2_build_and_save_signals(raw: pd.DataFrame, dry_run: bool) -> pd.DataFrame:
    """
    Build signals_today.csv from raw PM data only.
    Saved immediately — does not depend on stock data.
    Returns the signals dataframe.
    """
    logging.info("building pre-open signals...")
    signals = build_preopen_panel(raw)

    if signals.empty:
        logging.warning("signals_today is empty — no pre-open data found")
    else:
        logging.info(f"signals built for: {signals['ticker'].tolist()}")

    if not dry_run:
        DATA_DIR.mkdir(exist_ok=True)
        path = DATA_DIR / "signals_today.csv"
        signals.to_csv(path, index=False)
        logging.info(f"saved: {path}")

    return signals


def save_raw_orderbook(raw: pd.DataFrame, dry_run: bool) -> None:
    """
    Save the latest raw orderbook for pre-open chart reconstruction.
    """
    if dry_run:
        return

    DATA_DIR.mkdir(exist_ok=True)
    orderbook_clean = raw.copy()
    for col in orderbook_clean.select_dtypes(include=["datetimetz"]).columns:
        orderbook_clean[col] = orderbook_clean[col].dt.tz_localize(None)

    path = DATA_DIR / "orderbook_latest.csv"
    orderbook_clean.to_csv(path, index=False)
    logging.info(f"saved: {path}")


def step3_attach_stock(ob: Orderbook, raw: pd.DataFrame) -> pd.DataFrame:
    """
    Attach Yahoo Finance stock bars to the raw orderbook.
    Returns stock-enriched orderbook.
    """
    logging.info("attaching stock data...")
    enriched = ob.attach_stock_data(raw)
    logging.info(f"enriched orderbook: {len(enriched)} rows")
    return enriched


def step4_build_and_save_panel(enriched: pd.DataFrame, dry_run: bool) -> pd.DataFrame:
    """
    Collapse to 5-min windows, compute true_sentiment and lead-lag columns.
    Saves panel_15m.csv.
    Returns the final panel.
    """
    logging.info("collapsing to windows...")
    panel = collapse_to_windows(enriched, minutes=INTRADAY_WINDOW_MINUTES)
    logging.info(f"panel after collapse: {panel.shape}")

    logging.info("computing lead-lag...")
    panel = check_lead_lag(panel)
    logging.info(f"panel after lead-lag: {panel.shape}")

    if not dry_run:
        panel_clean = panel.copy()
        for col in panel_clean.select_dtypes(include=["datetimetz"]).columns:
            panel_clean[col] = panel_clean[col].dt.tz_localize(None)

        path = DATA_DIR / "panel_15m.csv"
        panel_clean.to_csv(path, index=False)
        logging.info(f"saved: {path}")

    return panel


def step6_backfill_true_sentiment(orderbook_df: pd.DataFrame) -> None:
    """
    Backfill true_sentiment into signals_today.csv using the stock-enriched
    orderbook after market-open fields are available.
    """
    import numpy as np
    import pytz
    from scipy.stats import norm

    signals_path = DATA_DIR / "signals_today.csv"
    if not signals_path.exists():
        logging.warning("signals_today.csv not found, skipping backfill")
        return

    signals = pd.read_csv(signals_path)
    if signals.empty:
        return

    ny_tz = pytz.timezone("America/New_York")
    today = datetime.now(ny_tz).date()
    firewall_dt = ny_tz.localize(
        datetime.combine(
            today,
            datetime.min.time().replace(
                hour=FIREWALL_HOUR_NY,
                minute=FIREWALL_MINUTE_NY,
            ),
        )
    ).astimezone(pytz.UTC)
    midnight_dt = ny_tz.localize(
        datetime.combine(today, datetime.min.time())
    ).astimezone(pytz.UTC)

    updated = False

    for idx, sig_row in signals.iterrows():
        ticker = str(sig_row["ticker"]).upper()
        current_ts = sig_row.get("true_sentiment")
        if pd.notna(current_ts) and str(current_ts).strip() not in ("", "None", "nan"):
            continue

        ticker_ob = orderbook_df[orderbook_df["KEY"] == ticker].copy()
        if ticker_ob.empty:
            continue

        ts_col = pd.to_datetime(ticker_ob["TIMESTAMP"])
        if ts_col.dt.tz is None:
            ts_col = ts_col.dt.tz_localize("UTC")
        else:
            ts_col = ts_col.dt.tz_convert("UTC")

        preopen_mask = (ts_col >= midnight_dt) & (ts_col < firewall_dt)
        preopen_rows = ticker_ob.loc[preopen_mask.values].copy()
        if preopen_rows.empty:
            continue

        usdc = pd.to_numeric(preopen_rows["USDC"], errors="coerce").fillna(0)
        price_up = pd.to_numeric(preopen_rows["PRICE_UP"], errors="coerce")
        total_vol = usdc.sum()
        if total_vol <= 0:
            continue
        avg_price_up = float((price_up * usdc).sum() / total_vol)

        open_series = pd.to_numeric(
            ticker_ob["stock_open_day"].dropna(),
            errors="coerce",
        ).dropna()
        if open_series.empty:
            continue
        K = float(open_series.iloc[0])
        if K <= 0:
            continue

        vol_col = f"stock_vol_{INTRADAY_WINDOW_MINUTES}m"
        if vol_col not in preopen_rows.columns:
            vol_col = "stock_vol"
        if vol_col not in preopen_rows.columns:
            continue

        sigma_series = pd.to_numeric(preopen_rows[vol_col], errors="coerce").dropna()
        if sigma_series.empty:
            continue
        sigma = float(sigma_series.iloc[-1])
        if sigma <= 0 or not np.isfinite(sigma):
            continue

        S = K
        T = max((6.5 / 24) / 252, 1e-9)

        try:
            d2 = (
                np.log(S / K)
                + (RISK_FREE_ANN - 0.5 * sigma**2) * T
            ) / (sigma * np.sqrt(T))
            bs_neutral = float(norm.cdf(float(d2)))
            true_sentiment = round(avg_price_up - bs_neutral, 4)
            if not np.isfinite(true_sentiment):
                continue
        except Exception:
            continue

        signals.at[idx, "true_sentiment"] = true_sentiment
        updated = True
        logging.info(
            f"Backfilled true_sentiment for {ticker}: "
            f"avg_p_up={avg_price_up:.4f}, K={K:.2f}, "
            f"sigma={sigma:.4f}, bs={bs_neutral:.4f}, ts={true_sentiment:.4f}"
        )

    if updated:
        signals.to_csv(signals_path, index=False)
        logging.info("signals_today.csv updated with backfilled true_sentiment")
    else:
        logging.info("No true_sentiment backfill needed or possible")


def step5_save_metadata(
    assets_ok: list,
    assets_failed: list,
    panel: pd.DataFrame,
    signals: pd.DataFrame,
    dry_run: bool,
) -> dict:
    """
    Write last_run.json. This is what GET /health reads.
    """
    last_run = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "date": date.today().isoformat(),
        "assets_ok": assets_ok,
        "assets_failed": assets_failed,
        "panel_rows": len(panel),
        "signals_rows": len(signals),
    }

    if not dry_run:
        path = DATA_DIR / "last_run.json"
        with open(path, "w") as handle:
            json.dump(last_run, handle, indent=2)
        logging.info(f"saved: {path}")

    return last_run


def run(dry_run: bool = False) -> None:
    today_str = date.today().isoformat()
    setup_logging(today_str)

    logging.info("=" * 52)
    logging.info(f"POLYMARKET PIPELINE  {today_str}")
    if dry_run:
        logging.info("MODE: DRY RUN — files will NOT be written")
    logging.info("=" * 52)

    ob = Orderbook(
        days_back=DAYS_BACK,
        start_day_from_now=0,
        intraday_minutes=INTRADAY_WINDOW_MINUTES,
    )

    raw, assets_ok, assets_failed = step1_fetch_raw(ob)
    signals = step2_build_and_save_signals(raw, dry_run)
    save_raw_orderbook(raw, dry_run)

    try:
        enriched = step3_attach_stock(ob, raw)
    except Exception as exc:
        logging.error(f"stock attach failed: {exc}")
        logging.warning("panel_15m.csv will NOT be updated this run")
        enriched = None

    panel = pd.DataFrame()
    if enriched is not None and not enriched.empty:
        try:
            step6_backfill_true_sentiment(enriched)
            panel = step4_build_and_save_panel(enriched, dry_run)
        except Exception as exc:
            logging.error(f"panel build failed: {exc}")

    step5_save_metadata(assets_ok, assets_failed, panel, signals, dry_run)

    logging.info("=" * 52)
    logging.info("PIPELINE COMPLETE")
    logging.info(f"  signals rows:  {len(signals)}")
    logging.info(f"  panel rows:    {len(panel)}")
    logging.info(f"  assets ok:     {assets_ok}")
    if assets_failed:
        logging.warning(f"  assets failed: {assets_failed}")
    logging.info("=" * 52)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Polymarket daily pipeline")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and process data but do not write any files",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run)
