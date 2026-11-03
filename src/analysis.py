"""Builds every number used in the reports from data/ (single entry point for analytics)."""
import numpy as np
import pandas as pd

from .carry import carry_roll_table
from .curves import bootstrap_zeros, fit_nelson_siegel, forward_rates, fwd_between, interp_par
from .history import run_history
from .data import curve, load_benchmarks, load_scenarios, load_snapshot, scalar
from .rv import credit_table, cross_market_table, hedge_cost
from .trades import Leg, Trade, cash_neutral, dv01_neutral, scenario_pnl, trade_summary

NOTIONAL = 10e6
# Desk-subjective MPC probabilities (judgement, not market-implied: no MYR OIS/IRS in snapshot)
SCENARIO_PROBS = {"hold": 0.70, "hike25": 0.25, "cut25": 0.05}
KEY_FWDS = {"1y1y": (1, 2), "2y1y": (2, 3), "3y2y": (3, 5), "5y5y": (5, 10), "10y5y": (10, 15), "10y10y": (10, 20)}


def run() -> dict:
    snap, scen = load_snapshot(), load_scenarios()
    mgs, sgs, aaa = curve(snap, "MGS"), curve(snap, "SGS"), curve(snap, "AAA")
    # MGS bootstrap uses the 6M T-bill as the 0.5Y anchor (FMIP matrix starts at 1Y)
    mgs_boot = (np.concatenate([[0.5], mgs[0]]), np.concatenate([[scalar(snap, "BILL", "6M") / 100], mgs[1]]))
    curves = {"MGS": mgs, "SGS": sgs}

    r_myr = scalar(snap, "BILL", "3M") / 100        # MYR 3M funding / hedge proxy
    r_sgd = scalar(snap, "SGS", "6M") / 100         # SGD funding / hedge proxy (no SORA in snapshot)
    funding = {"MGS": r_myr, "SGS": r_sgd}
    hc_3m = hedge_cost(r_myr, r_sgd, 0.25)
    hc_1y = hedge_cost(scalar(snap, "BILL", "12M") / 100, scalar(snap, "SGS", "1Y") / 100, 1.0)

    out = {"snap": snap, "scen": scen, "curves": curves, "aaa": aaa, "funding": funding,
           "hedge_3m": hc_3m, "hedge_1y": hc_1y, "usdmyr": scalar(snap, "USDMYR")}

    # 1. curve shape
    zf = []
    for name, c in [("MGS", mgs_boot), ("SGS", sgs)]:
        g, df, z = bootstrap_zeros(*c)
        s, f = forward_rates(g, df, 1.0)
        zf.append(pd.DataFrame({"curve": name, "t": g, "par_pct": interp_par(*c, g) * 100,
                                "zero_pct": z * 100, "df": df,
                                "fwd1y_pct": pd.Series(dict(zip(s, f * 100))).reindex(g).values}))
    out["zeros"] = pd.concat(zf, ignore_index=True)
    kf = []
    for name, c in [("MGS", mgs_boot), ("SGS", sgs)]:
        g, df, _ = bootstrap_zeros(*c)
        for lab, (a, b) in KEY_FWDS.items():
            kf.append({"curve": name, "forward": lab, "rate_pct": fwd_between(g, df, a, b) * 100})
    out["key_fwds"] = pd.DataFrame(kf)
    out["ns"] = {k: fit_nelson_siegel(*v) for k, v in curves.items()}
    out["rich_cheap"] = pd.concat([
        pd.DataFrame({"curve": k, "tenor": curves[k][0], "yield_pct": curves[k][1] * 100,
                      "ns_fit_pct": f["fitted"] * 100, "resid_bp": f["resid_bp"]})
        for k, f in out["ns"].items()], ignore_index=True)

    # 2-3. carry, roll, risk
    out["carry_roll"] = pd.concat([carry_roll_table(*mgs, r_myr, "MGS"),
                                   carry_roll_table(*sgs, r_sgd, "SGS")], ignore_index=True)

    # 4-5. cross-market and credit
    out["xmkt"] = cross_market_table(mgs, sgs, hc_3m)
    out["credit"] = credit_table(aaa, mgs)

    # 6. trades and scenarios
    # Primary: sized on the FMIP benchmark bonds actually traded (DV01-neutral, short RM10m 10Y)
    bm = load_benchmarks()
    bench = {k: Leg("MGS", r.years, coupon=r.coupon_pct / 100, yld=r.yield_pct / 100, label=f"{k} {r.coupon_pct:.3f}% {r.maturity:%d.%m.%Y}")
             for k, r in bm.iterrows()}
    primary = Trade("Primary: MGS 5s10s steepener",
                    dv01_neutral(curves, bench["MGS 4/2011"], bench["MGS 4/2026"], NOTIONAL, anchor="short"))
    # Alternative: SGD real-money switch, cash-neutral, matched 7Y tenor (SGS 7Y interpolated).
    # Carry = hedged yield difference: MGS leg "funded" at the hedge cost, SGS leg forgoes its coupon (no repo).
    alt = Trade("Alternative: FX-hedged MGS 7Y vs SGS 7Y",
                cash_neutral(curves, Leg("MGS", 7, hedged=True), Leg("SGS", 7), NOTIONAL),
                funding={"MGS": hc_3m, "SGS": 0.0})
    out["trades"] = [primary, alt]
    out["trade_legs"] = {t.name: trade_summary(t, curves, funding) for t in out["trades"]}
    out["scenario_pnl"] = pd.concat([scenario_pnl(t, curves, funding, scen) for t in out["trades"]],
                                    ignore_index=True)

    sp = out["scenario_pnl"]
    out["expected_pnl"] = (sp.assign(w=sp.scenario.map(SCENARIO_PROBS))
                           .assign(mpc_day=lambda d: d.w * d.mpc_day_pnl, total_3m=lambda d: d.w * d.pnl_3m_total)
                           .groupby("trade", sort=False)[["mpc_day", "total_3m"]].sum())

    # headline levels used in the pitch
    y = lambda c, t: float(interp_par(*curves[c], t)) * 1e4
    out["levels"] = {
        "mgs_5s10s_bp": y("MGS", 10) - y("MGS", 5),
        "mgs_2s10s_bp": y("MGS", 10) - y("MGS", 2),
        "mgs_7s10s_bp": y("MGS", 10) - y("MGS", 7),
        "mgs_5s10s_ns_fair_bp": float(np.diff(out["ns"]["MGS"]["fitted"][[4, 9]])[0] * 1e4),
        "mgs_5s10s_benchmark_bp": (bm.yield_pct["MGS 4/2026"] - bm.yield_pct["MGS 4/2011"]) * 100,
        "mgs7_sgs7_bp": y("MGS", 7) - y("SGS", 7),
        "hedged_mgs7_vs_sgs7_bp": y("MGS", 7) - hc_3m * 1e4 - y("SGS", 7),
    }

    # 7. history: 5s10s level, z-score, AR(1) half-life, steepener backtest (FMIP daily benchmarks)
    out["history"] = run_history(out["levels"]["mgs_5s10s_benchmark_bp"])

    # 8. live primary levels: target from history (3Y mean + 1 sd), stop unchanged; NS fair value is context only
    entry, pr = out["levels"]["mgs_5s10s_benchmark_bp"], out["history"]["params"]
    legs = out["trade_legs"][primary.name]
    dv01 = float(legs.dv01[legs.dv01 > 0].sum())          # RM/bp per leg (DV01-neutral)
    carry_roll = float((legs.carry_3m + legs.roll_3m).sum())
    reward, risk_ = pr["target_bp"] - entry, entry - pr["stop_bp"]
    out["live_trade"] = {
        "entry_bp": entry, "target_bp": pr["target_bp"], "stop_bp": pr["stop_bp"],
        "ns_fair_bp": out["levels"]["mgs_5s10s_ns_fair_bp"],
        "reward_bp": reward, "risk_bp": risk_, "reward_risk": reward / risk_,
        "dv01_rm": dv01, "pnl_at_target_rm": dv01 * reward, "pnl_at_stop_rm": -dv01 * risk_,
        "breakeven_hit_pct": risk_ / (reward + risk_) * 100,   # ignores carry and time exits
        "carry_roll_3m_rm": carry_roll, "carry_roll_3m_bp": carry_roll / dv01,
        "target_plus_carry_rm": dv01 * reward + carry_roll,
    }
    return out
