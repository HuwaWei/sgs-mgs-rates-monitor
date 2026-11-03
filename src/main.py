"""Reproduce all analytics, tables and charts: `python -m src.main`."""
import json

import pandas as pd

from .analysis import run
from .charts import make_all
from .data import ROOT

OUT = ROOT / "output"


def main():
    res = run()
    tab = OUT / "tables"
    tab.mkdir(parents=True, exist_ok=True)
    res["zeros"].round(5).to_csv(tab / "zeros_forwards.csv", index=False)
    res["key_fwds"].round(3).to_csv(tab / "key_forwards.csv", index=False)
    res["rich_cheap"].round(2).to_csv(tab / "rich_cheap.csv", index=False)
    res["carry_roll"].round(3).to_csv(tab / "carry_roll_risk.csv", index=False)
    res["xmkt"].round(2).to_csv(tab / "cross_market.csv", index=False)
    res["credit"].round(2).to_csv(tab / "credit_spreads.csv", index=False)
    res["scenario_pnl"].round(0).to_csv(tab / "scenario_pnl.csv", index=False)
    pd.concat([d.assign(trade=k) for k, d in res["trade_legs"].items()]).round(2).to_csv(tab / "trade_legs.csv", index=False)
    h = res["history"]
    h["trades"].round(2).to_csv(tab / "backtest_trades.csv", index=False)
    h["grid"].round(2).to_csv(tab / "backtest_grid.csv", index=False)
    h["daily"][["y5", "y10", "bill3m", "s", "m", "switch", "in_pos", "pnl_spread", "pnl_carry",
                "cum_pnl"]].round(4).to_csv(tab / "history_5s10s_daily.csv")
    h["crosscheck"].round(2).to_csv(tab / "history_crosscheck_abo.csv")
    summary = {
        "levels_bp": {k: round(v, 2) for k, v in res["levels"].items()},
        "hedge_cost_bp": {"3m_rolling": round(res["hedge_3m"] * 1e4, 1), "1y_matched": round(res["hedge_1y"] * 1e4, 1)},
        "nelson_siegel": {k: {"lambda": round(f["lam"], 2), "beta_pct": [round(b * 100, 3) for b in f["beta"]],
                              "rmse_bp": round(f["rmse_bp"], 2)} for k, f in res["ns"].items()},
        "trades": {k: {"net_dv01_rm": round(float(d.dv01.sum()), 1),
                       "carry_roll_3m_rm": round(float((d.carry_3m + d.roll_3m).sum()), 0),
                       "net_cash_rm": round(float(d.cash.sum()), 0),
                       "legs": d[["bond", "notional", "yield_pct", "dv01"]].round(2).to_dict("records")}
                   for k, d in res["trade_legs"].items()},
    }
    hist = {"stats": h["stats"], "params": h["params"], "signal_today": h["signal_today"],
            "backtest": h["headline"], "live_setup_odds": h["live_setup"], "below_line_odds": h["below_line"],
            "all_days_odds": h["all_days"]}
    summary["history_5s10s"] = json.loads(json.dumps(hist, default=float), parse_float=lambda x: round(float(x), 3))
    summary["live_trade"] = {k: round(v, 2) for k, v in res["live_trade"].items()}
    summary["expected_pnl_rm"] = res["expected_pnl"].round(0).to_dict("index")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    make_all(res, OUT)
    pd.set_option("display.width", 160)
    print(json.dumps(summary, indent=2))
    print(res["scenario_pnl"].round(0).to_string(index=False))


if __name__ == "__main__":
    main()
