"""Trade definitions, sizing (DV01-neutral or cash-neutral), carry/roll and MPC scenario P&L.

Each leg has a curve, a maturity in years and a signed notional (RM, or RM-equivalent for
SGS). A leg is either a par bond at the interpolated curve yield, or a specific bond with
its own coupon and yield (e.g. an FMIP benchmark).

Carry over the horizon h (per 100 face) = (y - r) P_dirty h: yield carry, which includes the
pull-to-par of a premium or discount bond (for a par bond it equals (c - r) 100 h). r is the
leg's funding rate. A repo-funded position uses the bill rate. A real-money switch uses r = 0 on the SGS
leg (no repo; the forgone coupon is the cost) and r = hedge cost on the FX-hedged MGS leg,
so the trade's carry is the hedged yield difference.
Roll: the bond's yield moves with the par curve from T to T-h (constant spread to the curve).
Scenario P&L is full revaluation of the MPC-day move; the 3M column adds carry + roll.
"""
from dataclasses import dataclass, field

import pandas as pd

from .bonds import clean_price, pnl_reprice, risk
from .carry import HORIZON
from .curves import interp_par
from .data import scenario_shift


@dataclass
class Leg:
    curve: str                  # "MGS" or "SGS"
    tenor: float                # years to maturity
    notional: float = 0.0       # +long / -short, RM (or RM-equivalent for SGS)
    hedged: bool = False        # MGS leg held by an SGD investor with a rolling 3M FX hedge
    coupon: float | None = None # None: par bond (coupon = curve yield)
    yld: float | None = None    # None: curve yield at `tenor`
    label: str | None = None    # bond name for display

    def yield_(self, curves: dict) -> float:
        return self.yld if self.yld is not None else float(interp_par(*curves[self.curve], self.tenor))

    def coupon_(self, curves: dict) -> float:
        return self.coupon if self.coupon is not None else self.yield_(curves)

    def name(self) -> str:
        return self.label or f"{self.curve} {self.tenor:g}Y"


@dataclass
class Trade:
    name: str
    legs: list = field(default_factory=list)
    funding: dict | None = None  # per-curve funding override (None: use the book's repo proxies)


def leg_risk(leg: Leg, curves: dict) -> dict:
    return risk(leg.coupon_(curves), leg.yield_(curves), leg.tenor)


def dv01_neutral(curves: dict, long: Leg, short: Leg, anchor_notional=10e6, anchor="short") -> list:
    """Size the non-anchor leg so that net DV01 = 0. The anchor leg carries `anchor_notional`."""
    d_long, d_short = leg_risk(long, curves)["dv01_per100"], leg_risk(short, curves)["dv01_per100"]
    if anchor == "short":
        long.notional, short.notional = anchor_notional * d_short / d_long, -anchor_notional
    else:
        long.notional, short.notional = anchor_notional, -anchor_notional * d_long / d_short
    return [long, short]


def cash_neutral(curves: dict, long: Leg, short: Leg, anchor_notional=10e6) -> list:
    """Real-money switch: sell the short leg for the same cash (dirty value) as the long leg costs."""
    p_long, p_short = leg_risk(long, curves)["price"], leg_risk(short, curves)["price"]
    long.notional, short.notional = anchor_notional, -anchor_notional * p_long / p_short
    return [long, short]


def leg_metrics(leg: Leg, curves: dict, funding: dict) -> dict:
    tenors, ylds = curves[leg.curve]
    y, c, T = leg.yield_(curves), leg.coupon_(curves), leg.tenor
    y_roll = y + float(interp_par(tenors, ylds, T - HORIZON) - interp_par(tenors, ylds, T))
    rk = risk(c, y, T)
    carry = (y - funding[leg.curve]) * rk["price"] * HORIZON
    roll = clean_price(c, y_roll, T - HORIZON) - clean_price(c, y, T - HORIZON)
    k = leg.notional / 100
    return {"bond": leg.name(), "curve": leg.curve, "tenor": round(T, 4), "coupon_pct": c * 100,
            "notional": leg.notional, "yield_pct": y * 100, "dirty_price": rk["price"],
            "cash": k * rk["price"], "dv01": k * rk["dv01_per100"], "carry_3m": k * carry,
            "roll_3m": k * roll, "mod_duration": rk["mod_duration"], "convexity": rk["convexity"]}


def trade_summary(trade: Trade, curves: dict, funding: dict) -> pd.DataFrame:
    f = trade.funding or funding
    return pd.DataFrame([leg_metrics(l, curves, f) for l in trade.legs])


def scenario_pnl(trade: Trade, curves: dict, funding: dict, scen: pd.DataFrame,
                 names=("hold", "hike25", "cut25")) -> pd.DataFrame:
    legs = trade_summary(trade, curves, funding)
    cr = float((legs.carry_3m + legs.roll_3m).sum())
    rows = []
    for s in names:
        inst = 0.0
        for leg in trade.legs:
            y = leg.yield_(curves)
            dy = scenario_shift(scen, s, leg.curve, leg.tenor) / 1e4
            inst += pnl_reprice(leg.notional, leg.coupon_(curves), y, y + dy, leg.tenor)
            if leg.hedged:
                # MTM on the short-MYR 3M forward: gains if the MYR-SGD rate differential widens
                d_diff = (scenario_shift(scen, s, "MGS", 0.25) - scenario_shift(scen, s, "SGS", 0.5)) / 1e4
                inst += leg.notional * d_diff * HORIZON
        rows.append({"trade": trade.name, "scenario": s, "mpc_day_pnl": inst,
                     "carry_roll_3m": cr, "pnl_3m_total": inst + cr})
    return pd.DataFrame(rows)
