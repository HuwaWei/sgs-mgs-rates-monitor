import numpy as np
import pandas as pd
import pytest

from src.analysis import run
from src.bonds import clean_price, dirty_price, par_bond_risk, pnl_reprice
from src.curves import bootstrap_zeros, fit_nelson_siegel, ns_loadings
from src.data import load_scenarios, scenario_shift
from src.history import ar1, backtest, load_history, max_drawdown
from src.rv import hedge_cost


@pytest.fixture(scope="module")
def res():
    return run()


def test_par_bond_prices_at_par():
    for T in (1, 5, 10, 30):
        assert dirty_price(0.039, 0.039, T) == pytest.approx(100, abs=1e-9)


def test_dv01_matches_duration_formula():
    rk = par_bond_risk(0.039, 10)
    # analytic modified duration of a semi-annual par bond: (1 - (1+y/2)^-2T) / y
    analytic = (1 - (1 + 0.039 / 2) ** -20) / 0.039
    assert rk["mod_duration"] == pytest.approx(analytic, rel=1e-4)
    assert rk["convexity"] > 0


def test_clean_price_has_no_jump_on_coupon_date():
    # clean price at the same yield should be ~continuous through a fractional period
    assert clean_price(0.04, 0.04, 4.75) == pytest.approx(100, abs=0.02)


def test_pnl_sign_and_convexity():
    up = pnl_reprice(10e6, 0.039, 0.039, 0.040, 10)
    dn = pnl_reprice(10e6, 0.039, 0.039, 0.038, 10)
    assert up < 0 < dn and dn > -up  # long convexity


def test_bootstrap_flat_curve_gives_flat_zeros():
    g, df, z = bootstrap_zeros(np.array([1.0, 10.0]), np.array([0.04, 0.04]))
    assert np.allclose(z, 0.04, atol=1e-10)


def test_bootstrap_reprices_par_bonds(res):
    z = res["zeros"]; d = z[z.curve == "MGS"]
    for T in (2, 5, 10, 30):
        sub = d[d.t <= T]
        c = sub.par_pct.iloc[-1] / 100
        assert (c / 2 * sub.df.sum() + sub.df.iloc[-1]) == pytest.approx(1, abs=1e-12)


def test_nelson_siegel_recovers_known_curve():
    t = np.array([1, 2, 3, 5, 7, 10, 15, 20, 30.0])
    y = ns_loadings(t, 2.5) @ np.array([0.045, -0.015, 0.01])
    f = fit_nelson_siegel(t, y)
    assert f["rmse_bp"] < 0.05 and f["lam"] == pytest.approx(2.5, abs=0.02)


def test_hedge_cost_cip():
    assert hedge_cost(0.03, 0.02, 0.25) == pytest.approx(0.01 / 1.005)
    assert hedge_cost(0.02, 0.02, 1) == 0


def test_scenario_interpolation():
    sc = load_scenarios()
    assert scenario_shift(sc, "hike25", "MGS", 4) == pytest.approx(10)  # between 3Y 12 and 5Y 8
    assert scenario_shift(sc, "hold", "SGS", 7) == 0


def test_primary_dv01_neutral_alt_cash_neutral(res):
    legs = res["trade_legs"]
    prim = legs["Primary: MGS 5s10s steepener"]
    alt = legs["Alternative: FX-hedged MGS 7Y vs SGS 7Y"]
    assert abs(prim.dv01.sum()) < 1e-6
    assert abs(alt.cash.sum()) < 1e-6


def test_alt_carry_is_hedged_yield_difference(res):
    alt = res["trade_legs"]["Alternative: FX-hedged MGS 7Y vs SGS 7Y"]
    hedged_pickup = res["levels"]["hedged_mgs7_vs_sgs7_bp"] / 1e4
    assert alt.carry_3m.sum() == pytest.approx(10e6 * hedged_pickup * 0.25, rel=1e-9)


def test_headline_levels(res):
    lv = res["levels"]
    assert lv["mgs_5s10s_bp"] == pytest.approx(22)
    assert lv["mgs_2s10s_bp"] == pytest.approx(60)
    assert lv["mgs_5s10s_benchmark_bp"] == pytest.approx(23)
    assert res["hedge_3m"] * 1e4 == pytest.approx(106.5, abs=0.1)


def test_primary_trade_positive_3m_in_all_scenarios(res):
    s = res["scenario_pnl"]
    prim = s[s.trade.str.startswith("Primary")]
    assert (prim.pnl_3m_total > 0).all()
    assert prim.set_index("scenario").mpc_day_pnl["hike25"] < 0  # known risk: bear flattener


# ---- history and backtest -------------------------------------------------

def _synthetic(spreads, y5=3.6, bill=3.0):
    idx = pd.bdate_range("2024-01-01", periods=len(spreads))
    s = np.asarray(spreads, float)
    d = pd.DataFrame({"y5": y5, "y10": y5 + s / 100, "y3": y5, "y7": y5 + s / 100, "bill3m": bill,
                      "mat5": "A", "mat10": "B", "s": s, "switch": False}, index=idx)
    return d


def test_ar1_recovers_half_life():
    rng = np.random.default_rng(0)
    phi, s = 0.95, [0.0]
    for _ in range(20000):
        s.append(20 * (1 - phi) + phi * s[-1] + rng.normal())
    a = ar1(pd.Series(s))
    assert a["phi"] == pytest.approx(phi, abs=0.01)
    assert a["half_life"] == pytest.approx(np.log(0.5) / np.log(phi), rel=0.2)


def test_backtest_target_exit_pnl_is_dv01_times_move_plus_carry():
    s = [30.0] * 5 + [20.0] + [25.0, 32.0]          # window 5: mean 30, entry at 20 (<= 25), exit at 32 (+12)
    tr, daily = backtest(_synthetic(s), x_bp=5, target=10, stop=7, max_hold=63, window=5)
    assert len(tr) == 1 and tr.reason.iloc[0] == "target" and tr.days_held.iloc[0] == 2
    t = tr.iloc[0]
    assert t.pnl_spread == pytest.approx(t.dv01 * 12)
    assert t.pnl == pytest.approx(t.pnl_spread + t.pnl_carry)
    assert daily.cum_pnl.iloc[-1] == pytest.approx(t.pnl)


def test_backtest_stop_and_benchmark_switch_books_no_pnl():
    s = [30.0] * 5 + [20.0, 40.0, 12.0]
    d = _synthetic(s)
    d.loc[d.index[6], "switch"] = True              # +20bp jump is a benchmark change, not a market move
    tr, _ = backtest(d, x_bp=5, target=10, stop=7, max_hold=63, window=5)
    t = tr.iloc[0]
    assert t.reason == "stop" and t.move_bp == pytest.approx(-28)
    assert t.pnl_spread == pytest.approx(t.dv01 * -28)


def test_max_drawdown():
    assert max_drawdown(pd.Series([1.0, 3.0, 0.5, 2.0, -1.0, 4.0])) == pytest.approx(-4.0)


def test_history_data_integrity(res):
    d = load_history()
    assert d.index.is_unique and d.index.is_monotonic_increasing
    assert (d.index[-1] - d.index[0]).days >= 2 * 365
    # latest FMIP close agrees with the benchmark snapshot used for the trade
    assert d.s.iloc[-1] == pytest.approx(res["levels"]["mgs_5s10s_benchmark_bp"])
    assert d[["y5", "y10", "bill3m"]].notna().all().all()


def test_live_target_from_history_not_nelson_siegel(res):
    lt, st, pr = res["live_trade"], res["history"]["stats"], res["history"]["params"]
    assert lt["target_bp"] == round(st["mean_bp"] + st["sd_bp"]) == 28
    assert lt["stop_bp"] == 16 and lt["entry_bp"] == pytest.approx(23)
    assert lt["target_bp"] < lt["ns_fair_bp"]                      # NS fair value is context, not the target
    assert lt["reward_risk"] == pytest.approx(5 / 7)
    assert lt["pnl_at_target_rm"] == pytest.approx(5 * lt["dv01_rm"])
    assert lt["pnl_at_stop_rm"] == pytest.approx(-7 * lt["dv01_rm"])
    # the backtest uses the live bracket
    assert (pr["target"], pr["stop"]) == pytest.approx((5, 7))
