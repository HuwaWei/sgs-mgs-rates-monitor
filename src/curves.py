"""Curve construction: par interpolation, zero bootstrap, forwards, Nelson-Siegel fit."""
import numpy as np

from .bonds import FREQ


def interp_par(tenors: np.ndarray, ylds: np.ndarray, t) -> np.ndarray:
    """Linear interpolation of par yields; flat extrapolation."""
    return np.interp(t, tenors, ylds)


def bootstrap_zeros(tenors: np.ndarray, ylds: np.ndarray, t_max: float | None = None):
    """Bootstrap discount factors on a semi-annual grid from linearly interpolated par yields.

    Par condition for a bond maturing at t_n with coupon c_n:
        sum_{i<=n} (c_n/2) DF_i + DF_n = 1
        => DF_n = (1 - c_n/2 * sum_{i<n} DF_i) / (1 + c_n/2)
    Returns grid, discount factors, semi-annual compounded zero rates.
    """
    t_max = t_max or tenors.max()
    grid = np.arange(1, int(round(t_max * FREQ)) + 1) / FREQ
    par = interp_par(tenors, ylds, grid)
    df = np.empty_like(grid)
    for n, c in enumerate(par):
        df[n] = (1 - c / FREQ * df[:n].sum()) / (1 + c / FREQ)
    zero = FREQ * (df ** (-1 / (FREQ * grid)) - 1)
    return grid, df, zero


def forward_rates(grid: np.ndarray, df: np.ndarray, length: float = 1.0):
    """Forward rate (semi-annual compounding) starting at each grid point for `length` years."""
    starts, fwds = [], []
    lookup = {round(t, 6): d for t, d in zip(grid, df)}
    lookup[0.0] = 1.0
    for s in np.concatenate([[0.0], grid]):
        e = round(s + length, 6)
        if e in lookup:
            ratio = lookup[round(s, 6)] / lookup[e]
            fwds.append(FREQ * (ratio ** (1 / (FREQ * length)) - 1))
            starts.append(s)
    return np.array(starts), np.array(fwds)


def fwd_between(grid: np.ndarray, df: np.ndarray, start: float, end: float) -> float:
    """Forward rate (semi-annual compounding) between two grid points, e.g. 5y5y = (5, 10)."""
    lookup = {round(t, 6): d for t, d in zip(grid, df)}
    lookup[0.0] = 1.0
    ratio = lookup[round(start, 6)] / lookup[round(end, 6)]
    return FREQ * (ratio ** (1 / (FREQ * (end - start))) - 1)


def ns_loadings(t: np.ndarray, lam: float) -> np.ndarray:
    x = np.asarray(t, float) / lam
    slope = (1 - np.exp(-x)) / x
    curv = slope - np.exp(-x)
    return np.column_stack([np.ones_like(x), slope, curv])


def fit_nelson_siegel(t: np.ndarray, y: np.ndarray, lam_grid=None) -> dict:
    """Nelson-Siegel fit: grid search on lambda, OLS on betas (no optimiser dependency).

    y(t) = b0 + b1 * (1-e^{-t/lam})/(t/lam) + b2 * [(1-e^{-t/lam})/(t/lam) - e^{-t/lam}]
    Fitted to par yields (approximation: NS strictly describes zero/forward curves).
    """
    lam_grid = np.linspace(0.3, 10.0, 971) if lam_grid is None else lam_grid
    best = None
    for lam in lam_grid:
        X = ns_loadings(t, lam)
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        sse = float(((X @ beta - y) ** 2).sum())
        if best is None or sse < best["sse"]:
            best = {"lam": float(lam), "beta": beta, "sse": sse}
    best["fitted"] = ns_loadings(t, best["lam"]) @ best["beta"]
    best["resid_bp"] = (y - best["fitted"]) * 1e4  # + = cheap (yield above curve)
    best["rmse_bp"] = float(np.sqrt(np.mean(best["resid_bp"] ** 2)))
    return best


def ns_eval(fit: dict, t) -> np.ndarray:
    return ns_loadings(np.atleast_1d(t), fit["lam"]) @ fit["beta"]
