"""Cross-market (SGS vs MGS), FX-hedged pickup and credit spreads."""
import numpy as np
import pandas as pd

from .curves import interp_par


def hedge_cost(r_myr: float, r_sgd: float, tau: float) -> float:
    """Annualised CIP forward premium of MYR vs SGD (decimal).

    F/S = (1 + r_MYR tau) / (1 + r_SGD tau)  (S, F in MYR per SGD)
    => (F - S) / (S tau) = (r_MYR - r_SGD) / (1 + r_SGD tau)
    Approximation: r_MYR, r_SGD are local short-rate proxies (bills), not traded
    NDF/onshore implied yields, so cross-currency basis is ignored.
    """
    return (r_myr - r_sgd) / (1 + r_sgd * tau)


def cross_market_table(mgs, sgs, hedge: float, tenors=(2, 5, 7, 10, 15, 20, 30)) -> pd.DataFrame:
    rows = []
    for T in tenors:
        y_m = float(interp_par(*mgs, T))
        y_s = float(interp_par(*sgs, T))
        rows.append({
            "tenor": T, "mgs_pct": y_m * 100, "sgs_pct": y_s * 100,
            "spread_bp": (y_m - y_s) * 1e4,
            "mgs_hedged_sgd_pct": (y_m - hedge) * 100,
            "hedged_pickup_bp": (y_m - hedge - y_s) * 1e4,
            "sgs_interpolated": T not in set(sgs[0]),
        })
    return pd.DataFrame(rows)


def credit_table(aaa, mgs) -> pd.DataFrame:
    t, y = aaa
    y_m = interp_par(*mgs, t)
    return pd.DataFrame({"tenor": t, "aaa_pct": y * 100, "mgs_pct": y_m * 100,
                         "spread_bp": (y - y_m) * 1e4})
