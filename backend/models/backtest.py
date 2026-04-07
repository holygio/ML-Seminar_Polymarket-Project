import numpy as np
import pandas as pd


def pro_backtest(
    df,
    initial_capital=10000,
    leverage=1,
    min_confidence=0.8,
    max_bet_pct=0.1,
    pct_cost=0.01,
    min_cash=5000,
    asset=None,
    print_results=True,
    strategy="long-short",
    risk_free_ann=0.04,
):
    risk_free_daily = (1 + risk_free_ann) ** (1 / 252) - 1
    risk_free_min = (1 + risk_free_daily) ** (1 / (24 * 60)) - 1
    original_min_date = df["TIMESTAMP"].min()
    df = df[df["TIMESTAMP"] >= original_min_date + pd.Timedelta(days=1)] if original_min_date.hour > 13 else df
    df = df.dropna(subset=["next_stock_move", "abs_sentiment", "true_sentiment"])
    start_date = df["TIMESTAMP"].min()
    end_date = df["TIMESTAMP"].max()
    if asset:
        df = df[df["KEY"].isin(asset)]
    if strategy == "long-only":
        df = df[df["true_sentiment"] > 0]
    elif strategy == "short-only":
        df = df[df["true_sentiment"] < 0]
    signals = df[df["abs_sentiment"] >= min_confidence].copy()
    if len(signals) == 0:
        print("No signals found :/")
        return
    signals = signals.set_index("TIMESTAMP").sort_index()
    current_cash = initial_capital
    total_idle_interest = 0
    peak = initial_capital
    mdd_tracker = 0
    results = []
    commission = pct_cost / 100

    last_ts = df["TIMESTAMP"].min()
    current_positions = {}

    all_days = pd.date_range(
        start=start_date.normalize() + pd.Timedelta(days=1),
        end=end_date.normalize(),
        freq="D",
    )
    eod_times = pd.date_range(
        start=start_date.normalize(),
        end=end_date.normalize() + pd.Timedelta(days=1),
        freq="D",
    ).map(lambda d: d.replace(hour=20, minute=0))

    all_timestamps = sorted(set(signals.index.tolist() + all_days.tolist() + eod_times.tolist()))

    for ts in all_timestamps:
        if current_cash <= min_cash:
            break
        minutes_passed = (ts - last_ts).total_seconds() / 60
        if minutes_passed > 0:
            pre_interest_cash = current_cash
            current_cash *= (1 + risk_free_min) ** minutes_passed
            interest_gained = current_cash - pre_interest_cash
            total_idle_interest += interest_gained
            results.append(
                {
                    "timestamp": ts,
                    "KEY": "interest_on_cash",
                    "pnl": interest_gained,
                    "equity": current_cash,
                }
            )
        last_ts = ts
        if ts.hour == 20 and ts.minute == 0:
            for _, pos in list(current_positions.items()):
                current_cash -= pos["size"] * commission
            current_positions.clear()
            continue
        if ts not in signals.index:
            continue
        if ts.hour >= 20:
            continue
        group = signals.loc[ts]
        if isinstance(group, pd.Series):
            group = group.to_frame().T

        active_keys = group["KEY"].tolist()
        for current_asset in list(current_positions.keys()):
            if current_asset not in active_keys:
                pos = current_positions.pop(current_asset)
                current_cash -= pos["size"] * commission
        num_trades = len(group)
        total_window_bet = current_cash * max_bet_pct * leverage
        individual_bet = total_window_bet / num_trades

        for _, trade in group.iterrows():
            current_asset = trade["KEY"]
            side = np.sign(trade["true_sentiment"])
            position_size = individual_bet * trade["abs_sentiment"]
            is_new_trade = True
            if current_asset in current_positions:
                if current_positions[current_asset]["side"] == side:
                    is_new_trade = False
                else:
                    current_cash -= current_positions[current_asset]["size"] * commission
            trade_fee = position_size * commission if is_new_trade else 0
            lev_tax = position_size * (0.1 * (leverage - 1) / 10000)
            directional_move = side * trade["next_stock_move"]
            pnl = (position_size * directional_move) - trade_fee - lev_tax

            current_cash += pnl
            current_positions[current_asset] = {"side": side, "size": position_size}

            if current_cash > peak:
                peak = current_cash
            dd = (peak - current_cash) / peak
            mdd_tracker = max(mdd_tracker, dd)
            results.append(
                {
                    "timestamp": ts,
                    "KEY": current_asset,
                    "pnl": pnl,
                    "equity": current_cash,
                }
            )

    res = pd.DataFrame(results)
    res = res.set_index("timestamp")
    trade_res = res[res["KEY"] != "interest_on_cash"]
    print("avg win:  ", trade_res[trade_res["pnl"] > 0]["pnl"].mean())
    print("avg loss: ", trade_res[trade_res["pnl"] < 0]["pnl"].mean())

    daily_pnl = res["pnl"].resample("D").sum().fillna(0)
    daily_equity = daily_pnl.cumsum() + initial_capital
    t_minus_1 = pd.Series([initial_capital], index=[daily_equity.index[0] - pd.Timedelta(days=1)])
    equity_with_start = pd.concat([t_minus_1, daily_equity])
    daily_pct_change = np.log(equity_with_start / equity_with_start.shift(1)).dropna()
    mean_ret = daily_pct_change.mean()
    std_ret = daily_pct_change.std()
    sharpe = ((mean_ret - risk_free_daily) / std_ret) * np.sqrt(252) if std_ret != 0 else 0

    total_ret = (current_cash - initial_capital) / initial_capital
    win_rate = (res["pnl"] > 0).mean()

    backtest_stats = {
        "trade count": len(res),
        "win rate": win_rate,
        "total return": total_ret,
        "initial value": initial_capital,
        "final value": current_cash,
        "max drawdown": mdd_tracker,
        "sharpe ratio": sharpe,
        "leverage": leverage,
        "start date": start_date,
        "end_date": end_date,
    }

    if print_results:
        print(f"=== pro backtest --> min conviction: {int(min_confidence * 100)}% ===")
        print()
        print(f"from {start_date.strftime('%d/%m at %H:%M')} to {end_date.strftime('%d/%m at %H:%M')} ({(end_date - start_date).days} days)")
        print()
        print(f"strategy: {strategy}\n")
        print(f"trade count:   {len(res)}")
        print(f"win rate:      {win_rate:.2%}")
        print(f"total return:  {total_ret:.2%}")
        print(f"final value:   ${current_cash:,.2f}")
        print(f"trading pnl:   ${(current_cash - initial_capital - total_idle_interest):,.2f}")
        print(f"idle interest: ${total_idle_interest:,.2f}")
        print(f"max drawdown:  {mdd_tracker:.2%}")
        print(f"sharpe ratio:  {sharpe:.2f}", end=" ")
        print("(money money ^u^)") if sharpe > 0 else print()
        print(f"leverage:      x{leverage:.1f} | cost: {pct_cost} bps")
        print()
        print("daily risk free rate", round(risk_free_daily * 100, 4), "%")
        print("daily average return", round(mean_ret * 100, 4), "%")
        print("standard deviation", round(std_ret * 100, 4), "%")
        print()
        print("\nreturn by asset (% of init cap):")
        print(res.groupby("KEY")["pnl"].sum() / initial_capital * 100)

    daily_pct_change = daily_pct_change.reset_index().rename(columns={0: "daily_return"})
    return res, backtest_stats, daily_pct_change


def beta_backtest(
    df,
    initial_capital=10000,
    leverage=1,
    min_confidence=0.8,
    trx_fee=0.01,
    asset=None,
    strategy="long-short",
    min_cash=0,
    risk_free_ann=0.04,
    intraday_window_minutes=15,
    max_bet=1,
):
    risk_free_day = (1 + risk_free_ann) ** (1 / 252) - 1
    risk_free_min = (1 + risk_free_day) ** (1 / (24 * 60)) - 1
    trx_cost, lev_cost = trx_fee / 100, 0.01 * (leverage - 1) / 100

    df = df.copy()
    df["TIMESTAMP"] = pd.to_datetime(df["TIMESTAMP"])
    if asset:
        df = df[df["KEY"].isin(asset)]
    if df.empty:
        return pd.DataFrame(), (0, 0)

    df = df[(df["TIMESTAMP"].dt.hour >= 13) & (df["TIMESTAMP"].dt.hour <= 20)].sort_values("TIMESTAMP")
    current_cash, open_positions, history = initial_capital - min_cash, {}, []
    all_time_windows = pd.date_range(
        df["TIMESTAMP"].min(),
        df["TIMESTAMP"].max(),
        freq=f"{intraday_window_minutes}min",
    )

    for time in all_time_windows:
        prev_total = current_cash + sum(p["basis"] + p["current_pnl"] for p in open_positions.values())
        asset_returns = {}
        time_df = df[(df["TIMESTAMP"] == time) & (df["abs_sentiment"] >= min_confidence)]

        if strategy == "long-only":
            time_df = time_df[time_df["true_sentiment"] > 0]
        elif strategy == "short-only":
            time_df = time_df[time_df["true_sentiment"] < 0]

        is_force_exit = time.hour == 20 and time.minute == 0

        for key in list(open_positions.keys()):
            row = time_df[time_df["KEY"] == key]
            if is_force_exit or row.empty or np.sign(row["true_sentiment"].iloc[0]) != open_positions[key]["side"]:
                pos = open_positions.pop(key)
                current_cash += (pos["basis"] + pos["current_pnl"]) * (1 - trx_cost)

        if not is_force_exit:
            for _, row in time_df.iterrows():
                key, side = row["KEY"], np.sign(row["true_sentiment"])
                move_pnl_pct = row["next_stock_move"] * side * leverage
                if key in open_positions:
                    trade_pnl = open_positions[key]["basis"] * move_pnl_pct
                    open_positions[key]["current_pnl"] += trade_pnl
                    asset_returns[f"ret_{key}"] = trade_pnl / prev_total if prev_total != 0 else 0
                else:
                    unlev_bet = current_cash * max_bet
                    fees = unlev_bet * (trx_cost + lev_cost)
                    current_cash -= unlev_bet + fees
                    initial_trade_pnl = unlev_bet * move_pnl_pct
                    open_positions[key] = {"basis": unlev_bet, "side": side, "current_pnl": initial_trade_pnl}
                    asset_returns[f"ret_{key}"] = (initial_trade_pnl - fees) / prev_total if prev_total != 0 else 0

        current_cash += current_cash * ((1 + risk_free_min) ** intraday_window_minutes - 1)
        new_total = current_cash + sum(p["basis"] + p["current_pnl"] for p in open_positions.values())

        if new_total <= 0:
            history.append({"timestamp": time, "total_value": float(min_cash), "window_return": -1.0, "interest": 0})
            break
        record = {
            "timestamp": time,
            "total_value": new_total + min_cash,
            "window_return": (new_total / prev_total - 1) if prev_total != 0 else 0,
            "interest": 0,
        }
        record.update(asset_returns)
        history.append(record)

    results_df = pd.DataFrame(history).fillna(0)
    if results_df.empty:
        return results_df, (0, 0)

    vals = results_df["total_value"].values
    peak = np.maximum.accumulate(vals)
    mdd = np.min((vals - peak) / peak)

    total_windows_year = (24 * 60 / intraday_window_minutes) * 365
    rf_window = (1 + risk_free_ann) ** (1 / total_windows_year) - 1
    trading_windows_day = (24 * 60) / intraday_window_minutes
    trading_windows_year = trading_windows_day * 252

    excess_returns = results_df["window_return"] - rf_window
    sharpe = (excess_returns.mean() / excess_returns.std()) * np.sqrt(trading_windows_year)

    return results_df.round(6), (round(mdd, 6), round(sharpe, 6))
