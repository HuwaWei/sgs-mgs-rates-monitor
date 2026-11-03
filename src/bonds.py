"""Fixed-coupon bond maths (semi-annual coupons, street yield convention).

MGS and SGS both pay semi-annually. A tenor-T 'par bond' is a bond with coupon
equal to the par yield at T, priced at 100.
"""
import numpy as np

FREQ = 2


def _times(maturity: float) -> np.ndarray:
    """Remaining coupon times (years) for a bond with `maturity` years left."""
    n = int(np.ceil(maturity * FREQ - 1e-9))
    return np.sort(maturity - np.arange(n) / FREQ)


def dirty_price(coupon: float, yld: float, maturity: float) -> float:
    t = _times(maturity)
    df = (1 + yld / FREQ) ** (-FREQ * t)
    return float(100 * (coupon / FREQ * df.sum() + df[-1]))


def accrued(coupon: float, maturity: float) -> float:
    t1 = _times(maturity)[0]
    return 100 * coupon / FREQ * (1 / FREQ - t1) * FREQ


def clean_price(coupon: float, yld: float, maturity: float) -> float:
    return dirty_price(coupon, yld, maturity) - accrued(coupon, maturity)


def risk(coupon: float, yld: float, maturity: float, bump: float = 1e-4) -> dict:
    """DV01 (price per 100 face per 1bp), modified duration, convexity (central differences)."""
    p0 = dirty_price(coupon, yld, maturity)
    up = dirty_price(coupon, yld + bump, maturity)
    dn = dirty_price(coupon, yld - bump, maturity)
    dv01 = (dn - up) / 2
    return {
        "price": p0,
        "dv01_per100": dv01,
        "mod_duration": dv01 / p0 / bump,
        "convexity": (up + dn - 2 * p0) / (p0 * bump**2),
    }


def par_bond_risk(par_yield: float, tenor: float) -> dict:
    return risk(par_yield, par_yield, tenor)


def pnl_reprice(notional: float, coupon: float, y0: float, y1: float, maturity: float) -> float:
    """Full-revaluation P&L of a long `notional` position for a yield move y0 -> y1."""
    return notional / 100 * (dirty_price(coupon, y1, maturity) - dirty_price(coupon, y0, maturity))
