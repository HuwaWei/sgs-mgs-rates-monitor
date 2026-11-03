"""Load the single-date market snapshot and scenario assumptions."""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def load_snapshot(path: Path = DATA / "market_snapshot.csv") -> pd.DataFrame:
    return pd.read_csv(path)


def curve(snap: pd.DataFrame, instrument: str) -> tuple[np.ndarray, np.ndarray]:
    """Return (tenors in years, yields in decimal) sorted by tenor."""
    d = snap[snap.instrument == instrument].sort_values("tenor_years")
    return d.tenor_years.to_numpy(float), d.value.to_numpy(float) / 100.0


def scalar(snap: pd.DataFrame, instrument: str, tenor_label: str | None = None) -> float:
    d = snap[snap.instrument == instrument]
    if tenor_label is not None:
        d = d[d.tenor_label == tenor_label]
    if len(d) != 1:
        raise KeyError(f"{instrument} {tenor_label}: expected 1 row, got {len(d)}")
    return float(d.value.iloc[0])


def load_scenarios(path: Path = DATA / "mpc_scenarios.csv") -> pd.DataFrame:
    return pd.read_csv(path)


def scenario_shift(scen: pd.DataFrame, name: str, curve_name: str, tenor: float) -> float:
    """Shift in bp at a tenor, linearly interpolated (flat extrapolation) between nodes."""
    d = scen[(scen.scenario == name) & (scen.curve == curve_name)].sort_values("tenor_years")
    return float(np.interp(tenor, d.tenor_years, d.shift_bp))


def load_benchmarks(path: Path = DATA / "benchmarks.csv") -> pd.DataFrame:
    """Benchmark bond terms; adds `years`, the Actual/365 year fraction from as-of date to maturity."""
    b = pd.read_csv(path, parse_dates=["maturity", "as_of"])
    b["years"] = (b.maturity - b.as_of).dt.days / 365.0
    return b.set_index("name")
