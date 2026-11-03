"""MGS 5s10s history and a rules-based backtest of the DV01-neutral steepener.

Data: daily FMIP benchmark closing yields (data/mgs_benchmark_history.csv, built by
scripts/fetch_fmip_history.py). The 5Y and 10Y series are *generic benchmarks*: between
switches each one follows a single bond, and BNM occasionally moves the benchmark to a new,
longer bond. A switch day jumps for reasons that are not market moves, so the backtest rolls
the position into the new benchmarks at that close and books no P&L from the jump. Because
the series follows the same two bonds between switches, roll-down is already inside the
spread P&L (the 5Y bond shortens and its yield falls along an upward-sloping curve).

Spread    s_t = y10_t - y5_t (bp)
Signal    enter at the close when s_t <= m_t - X, m_t = mean of the last 252 closes (1Y)
Exit      first close at which the position spread is >= entry + target (take profit) or
          <= entry - stop, or after MAX_HOLD trading days (time exit). One position at a time.
          target and stop are the live trade's bracket: target level = round(3Y mean + 1 sd) = 28bp,
          stop level = 16bp, both measured from today's 23bp (so +5 / -7bp).
Sizing    short RM10m 10Y par bond, long the 5Y par bond for the same DV01 D, fixed at entry
P&L       spread (incl. roll-down): D * delta s   (DV01 approximation, switch days excluded)
          carry:  [N5 (y5 - r) - N10 (y10 - r)] * days / 365,  r = 3M MTB (repo proxy, as in the pitch)
"""
import numpy as np
import pandas as pd

from .bonds import par_bond_risk
from .data import DATA

HISTORY_CSV = DATA / "mgs_benchmark_history.csv"
CROSSCHECK_CSV = DATA / "abo_crosscheck.csv"
WINDOW = 252              # rolling 1Y, trading days
ENTRY_X = 5.0             # bp below the rolling mean (headline; sensitivity grid below)
LIVE_STOP_BP = 16.0       # live trade stop level (unchanged); the target level comes from history
MAX_HOLD = 63             # trading days: the pitch's 3M horizon
NOTIONAL = 10e6           # 10Y short leg, as in the live trade
LIVE_BAND = (21.0, 25.0)  # "entry near today's 23bp" for the live-setup odds


def load_history(path=HISTORY_CSV) -> pd.DataFrame:
    """Wide daily frame: y3, y5, y7, y10 (%), 5Y/10Y benchmark maturity, 3M bill, flags."""
    h = pd.read_csv(path, parse_dates=["trade_date"])
    mgs = h[h.instrument == "MGS"]
    y = mgs.pivot(index="trade_date", columns="tenor", values="close_pct")
    y.columns = [f"y{c[:-1]}" for c in y.columns]
    mat = mgs.pivot(index="trade_date", columns="tenor", values="maturity_month")
    stale = mgs.pivot(index="trade_date", columns="tenor", values="last_traded")
    bill = h[(h.instrument == "MTB") & (h.tenor == "3M")].set_index("trade_date").close_pct
    d = y.assign(mat5=mat["5Y"], mat10=mat["10Y"], bill3m=bill,
                 stale5=stale["5Y"].astype(bool), stale10=stale["10Y"].astype(bool),
                 no_trade=stale.all(axis=1).astype(bool)).sort_index()
    # Days on which no MGS benchmark traded (market holidays): FMIP repeats the last print.
    d = d[~d.no_trade].drop(columns="no_trade")
    d["bill3m"] = d.bill3m.ffill()
    d["s"] = ((d.y10 - d.y5) * 100).round(6)
    d["switch"] = (d.mat5 != d.mat5.shift()) | (d.mat10 != d.mat10.shift())
    d.iloc[0, d.columns.get_loc("switch")] = False
    return d


def position_changes(d: pd.DataFrame) -> pd.Series:
    """Daily change in the spread of a held position: switch-day jumps set to zero."""
    return d.s.diff().where(~d.switch, 0.0).fillna(0.0)


def ar1(s: pd.Series) -> dict:
    """OLS of s_t = a + phi s_{t-1} + e. Half-life = ln(0.5)/ln(phi) in observations."""
    x, yv = s.shift().dropna().to_numpy(), s.iloc[1:].to_numpy()
    X = np.column_stack([np.ones_like(x), x])
    beta, *_ = np.linalg.lstsq(X, yv, rcond=None)
    resid = yv - X @ beta
    sigma2 = resid @ resid / (len(yv) - 2)
    se = np.sqrt(np.diag(sigma2 * np.linalg.inv(X.T @ X)))
    a, phi = beta
    return {"a": a, "phi": phi, "se_phi": se[1], "df_t": (phi - 1) / se[1],
            "half_life": np.log(0.5) / np.log(phi) if 0 < phi < 1 else np.inf,
            "long_run_mean": a / (1 - phi) if phi != 1 else np.nan, "resid_sd": np.sqrt(sigma2), "n": len(yv)}


def live_target(s: pd.Series) -> float:
    """Live target level: 3Y mean + 1 sd of 5s10s, rounded to the nearest bp."""
    return float(np.round(s.mean() + s.std()))


def bracket(d: pd.DataFrame, today_bp: float) -> tuple[float, float]:
    """(target, stop) in bp from entry, from the live levels around today's spread."""
    return live_target(d.s) - today_bp, today_bp - LIVE_STOP_BP


def spread_stats(d: pd.DataFrame, today_bp: float) -> dict:
    s = d.s
    last1y = s.iloc[-WINDOW:]
    weekly = s.resample("W-FRI").last().dropna()
    return {
        "start": s.index[0].date().isoformat(), "end": s.index[-1].date().isoformat(), "n_obs": len(s),
        "today_bp": today_bp, "fmip_last_bp": s.iloc[-1],
        "mean_bp": s.mean(), "sd_bp": s.std(), "min_bp": s.min(), "max_bp": s.max(),
        "z_full": (today_bp - s.mean()) / s.std(),
        "pctile_full": (s < today_bp).mean() * 100 + (s == today_bp).mean() * 50,
        "target_bp": live_target(s),
        "share_ge_target_pct": (s >= live_target(s)).mean() * 100,
        "share_le_stop_pct": (s <= LIVE_STOP_BP).mean() * 100,
        "mean_1y_bp": last1y.mean(), "sd_1y_bp": last1y.std(), "z_1y": (today_bp - last1y.mean()) / last1y.std(),
        "ar1_daily": ar1(s), "ar1_weekly": ar1(weekly),
        "n_stale_5y": int(d.stale5.sum()), "n_stale_10y": int(d.stale10.sum()),
        "n_switch_days": int(d.switch.sum()),
        "switch_dates": [x.date().isoformat() for x in d.index[d.switch]],
        "switch_jumps_bp": [float(v) for v in d.s.diff()[d.switch]],
    }


def _sizing(y5: float, y10: float) -> tuple[float, float, float]:
    """(N5, N10, D): long N5 5Y par, short N10 = RM10m 10Y par, DV01 D per leg (RM/bp)."""
    d10 = par_bond_risk(y10 / 100, 10)["dv01_per100"]
    d5 = par_bond_risk(y5 / 100, 5)["dv01_per100"]
    return NOTIONAL * d10 / d5, NOTIONAL, NOTIONAL / 100 * d10


def backtest(d: pd.DataFrame, target: float, stop: float, x_bp: float = ENTRY_X,
             max_hold: int = MAX_HOLD, window: int = WINDOW):
    """Return (trades, daily) frames. Signals and exits on closes; P&L marked daily."""
    d = d.copy()
    d["m"] = d.s.rolling(window).mean()
    d["band"] = d.m - x_bp
    ds = position_changes(d)
    days = d.index.to_series().diff().dt.days.fillna(0).to_numpy()
    idx = d.index
    pnl_spread = np.zeros(len(d)); pnl_carry = np.zeros(len(d))
    in_pos = np.zeros(len(d), bool)
    trades, pos = [], None
    for i in range(len(d)):
        r = d.iloc[i]
        if pos is not None:
            # from close i-1 to close i, on the notionals fixed at entry; carry at i-1 yields and funding
            p = d.iloc[i - 1]
            pnl_spread[i] = pos["D"] * ds.iloc[i]
            pnl_carry[i] = (pos["N5"] * (p.y5 - p.bill3m) - pos["N10"] * (p.y10 - p.bill3m)) / 100 * days[i] / 365
            in_pos[i] = True
            pos["level"] += ds.iloc[i]
            pos["spread"] += pnl_spread[i]; pos["carry"] += pnl_carry[i]
            pos["held"] += 1
            reason = ("target" if pos["level"] >= pos["entry_s"] + target - 1e-9 else
                      "stop" if pos["level"] <= pos["entry_s"] - stop + 1e-9 else
                      "time" if pos["held"] >= max_hold else
                      "open" if i == len(d) - 1 else None)
            if reason:
                trades.append({"entry_date": pos["date"].date(), "exit_date": idx[i].date(), "reason": reason,
                               "entry_bp": pos["entry_s"], "entry_mean_bp": pos["m"], "exit_bp": r.s,
                               "move_bp": pos["level"] - pos["entry_s"], "days_held": pos["held"],
                               "dv01": pos["D"], "pnl_spread": pos["spread"], "pnl_carry": pos["carry"],
                               "pnl": pos["spread"] + pos["carry"]})
                pos = None
                continue
        if pos is None and not np.isnan(r.m) and r.s <= r.band and i < len(d) - 1:
            N5, N10, D = _sizing(r.y5, r.y10)
            pos = {"date": idx[i], "entry_s": r.s, "level": r.s, "m": r.m, "N5": N5, "N10": N10, "D": D,
                   "spread": 0.0, "carry": 0.0, "held": 0}
    daily = d.assign(pnl_spread=pnl_spread, pnl_carry=pnl_carry, in_pos=in_pos)
    daily["pnl"] = daily.pnl_spread + daily.pnl_carry
    daily["cum_pnl"] = daily.pnl.cumsum()
    return pd.DataFrame(trades), daily


def max_drawdown(cum: pd.Series) -> float:
    """Largest peak-to-trough fall of cumulative P&L (RM, reported as a negative number)."""
    peak = np.maximum.accumulate(np.concatenate([[0.0], cum.to_numpy()]))[1:]
    return float((cum - peak).min())


def summarize(trades: pd.DataFrame, daily: pd.DataFrame, x_bp: float) -> dict:
    t = trades[trades.reason != "open"] if len(trades) else trades
    n = len(t)
    out = {"x_bp": x_bp, "n_trades": n, "open_trade": bool(len(trades) and (trades.reason == "open").any()),
           "days_in_market_pct": float(daily.in_pos.mean() * 100),
           "max_dd_rm": max_drawdown(daily.cum_pnl)}
    if n:
        out.update({
            "hit_rate_pct": float((t.pnl > 0).mean() * 100),
            "avg_pnl_rm": float(t.pnl.mean()), "avg_pnl_bp": float((t.pnl / t.dv01).mean()),
            "avg_spread_rm": float(t.pnl_spread.mean()), "avg_carry_rm": float(t.pnl_carry.mean()),
            "total_pnl_rm": float(t.pnl.sum()),
            "avg_win_rm": float(t.pnl[t.pnl > 0].mean()) if (t.pnl > 0).any() else 0.0,
            "avg_loss_rm": float(t.pnl[t.pnl <= 0].mean()) if (t.pnl <= 0).any() else 0.0,
            "worst_rm": float(t.pnl.min()),
            "avg_days": float(t.days_held.mean()), "median_days": float(t.days_held.median()),
            "dv01_rm": float(t.dv01.mean()),
            "n_target": int((t.reason == "target").sum()), "n_stop": int((t.reason == "stop").sum()),
            "n_time": int((t.reason == "time").sum()),
        })
    return out


def first_passage(d: pd.DataFrame, mask, target: float, stop: float, max_hold: int = MAX_HOLD) -> dict:
    """Enter on every day in `mask` (overlapping windows); outcome of target / stop / time exit."""
    ds, s_entry = position_changes(d).to_numpy(), d.s.to_numpy()
    out = []
    for i in np.where(np.asarray(mask))[0]:
        if i + max_hold >= len(d):
            continue
        path = np.cumsum(ds[i + 1:i + 1 + max_hold])
        hit_t = np.argmax(path >= target - 1e-9) if (path >= target - 1e-9).any() else max_hold
        hit_s = np.argmax(path <= -stop + 1e-9) if (path <= -stop + 1e-9).any() else max_hold
        if hit_t < hit_s:
            out.append(("target", hit_t + 1, path[hit_t]))
        elif hit_s < hit_t:
            out.append(("stop", hit_s + 1, path[hit_s]))
        else:
            out.append(("time", max_hold, path[-1]))
    f = pd.DataFrame(out, columns=["reason", "days", "move_bp"])
    share = f.reason.value_counts(normalize=True).reindex(["target", "stop", "time"]).fillna(0) * 100
    return {"n": len(f), "target_pct": float(share["target"]), "stop_pct": float(share["stop"]),
            "time_pct": float(share["time"]), "avg_move_bp": float(f.move_bp.mean()),
            "avg_days": float(f.days.mean())}


def crosscheck(d: pd.DataFrame, path=CROSSCHECK_CSV) -> pd.DataFrame:
    """AsianBondsOnline constant-maturity 5s10s vs FMIP benchmark 5s10s on the same dates."""
    a = pd.read_csv(path, parse_dates=["as_of"]).pivot(index="as_of", columns="tenor", values="yield_pct")
    return pd.DataFrame({"abo_5s10s_bp": (a["10Y"] - a["5Y"]) * 100,
                         "fmip_5s10s_bp": d.s.reindex(a.index)}).assign(diff_bp=lambda x: x.fmip_5s10s_bp - x.abo_5s10s_bp)


def run_history(today_bp: float) -> dict:
    d = load_history()
    stats = spread_stats(d, today_bp)
    tgt, stp = bracket(d, today_bp)
    trades, daily = backtest(d, tgt, stp)
    grid = []
    for x in (0.0, 5.0, 10.0):
        tr, dl = backtest(d, tgt, stp, x_bp=x)
        grid.append(summarize(tr, dl, x))
    m = d.s.rolling(WINDOW).mean()
    lo, hi = LIVE_BAND
    return {
        "params": {"x_bp": ENTRY_X, "target": tgt, "stop": stp, "target_bp": live_target(d.s),
                   "stop_bp": LIVE_STOP_BP, "max_hold": MAX_HOLD, "window": WINDOW, "live_band": list(LIVE_BAND)},
        "data": d, "stats": stats, "trades": trades, "daily": daily,
        "headline": summarize(trades, daily, ENTRY_X), "grid": pd.DataFrame(grid),
        "signal_today": {"rolling_mean_bp": float(m.iloc[-1]), "gap_bp": float(today_bp - m.iloc[-1]),
                         "entry_line_bp": float(m.iloc[-1] - ENTRY_X),
                         "triggered": bool(today_bp <= m.iloc[-1] - ENTRY_X)},
        # The live trade as specified: enter near today's level, live bracket, 3M
        "live_setup": first_passage(d, (d.s >= lo) & (d.s <= hi), tgt, stp),
        "all_days": first_passage(d, np.ones(len(d), bool), tgt, stp),
        "below_line": first_passage(d, (d.s <= m - ENTRY_X).to_numpy(), tgt, stp),
        "crosscheck": crosscheck(d),
    }
