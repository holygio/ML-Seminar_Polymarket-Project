from datetime import datetime as dt

import numpy as np
import pandas as pd
import pytz
import statsmodels.api as sm
from scipy.stats import norm

try:
    from config import (
        FIREWALL_HOUR_NY,
        FIREWALL_MINUTE_NY,
        INTRADAY_WINDOW_MINUTES,
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
        INTRADAY_WINDOW_MINUTES,
        LIQUIDITY_THRESHOLD,
        RISK_FREE_ANN,
        SQ_SPREAD_MED,
        SQ_SPREAD_TIGHT,
        SQ_VOLUME_HIGH,
        SQ_VOLUME_MED,
    )


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
