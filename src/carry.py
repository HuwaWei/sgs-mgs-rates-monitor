"""3M carry and roll-down for par bonds on a given curve.

Carry (price, per 100)  = (c - r_fund) * h * 100            coupon accrual less repo/funding
Roll  (price, per 100)  = P_clean(T-h, y(T-h)) - P_clean(T-h, y(T))   curve roll at unchanged curve
Breakeven (bp)          = (carry + roll) / DV01             yield rise absorbed over the horizon
"""
import numpy as np
import pandas as pd

from .bonds import clean_price, par_bond_risk
from .curves import interp_par

HORIZON = 0.25


def carry_roll_table(tenors, ylds, fund_rate: float, curve_name: str,
                     points=None, horizon: float = HORIZON, notional: float = 10e6) -> pd.DataFrame:
    points = tenors[tenors >= 1] if points is None else points
    rows = []
    for T in points:
        y = float(interp_par(tenors, ylds, T))
        y_roll = float(interp_par(tenors, ylds, T - horizon))
        rk = par_bond_risk(y, T)
        carry = (y - fund_rate) * horizon * 100
        roll = clean_price(y, y_roll, T - horizon) - clean_price(y, y, T - horizon)
        rows.append({
            "curve": curve_name, "tenor": T, "yield_pct": y * 100,
            "roll_bp": (y - y_roll) * 1e4,
            "carry_bp": carry / rk["dv01_per100"],
            "carry_roll_bp": (carry + roll) / rk["dv01_per100"],
            "carry_price": carry, "roll_price": roll,
            "pnl_3m_per_10m": notional / 100 * (carry + roll),
            "dv01_per_10m": notional / 100 * rk["dv01_per100"],
            "mod_duration": rk["mod_duration"], "convexity": rk["convexity"],
        })
    return pd.DataFrame(rows)
