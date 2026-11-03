"""Desk-style static charts. Colour-blind-safe categorical palette: MGS blue, SGS orange, third series aqua."""
from pathlib import Path

import matplotlib
import matplotlib.dates

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .curves import ns_eval

MGS_C, SGS_C, THIRD_C = "#2a78d6", "#eb6834", "#1baf7a"
CHEAP_C, RICH_C = "#2a78d6", "#e34948"
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "font.family": "DejaVu Sans", "font.size": 8.5, "axes.titlesize": 9.5, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.edgecolor": GRID, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True, "axes.axisbelow": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False, "lines.linewidth": 2,
})


def _src(fig, text):
    fig.text(0.01, 0.01, text, fontsize=6.5, color=INK2)


def _bars(ax, x, v, colors, fmt="{:+.1f}", width=0.6):
    bars = ax.bar(x, v, width=width, color=colors, edgecolor=SURF, linewidth=1)
    for b, val in zip(bars, v):
        ax.annotate(fmt.format(val), (b.get_x() + b.get_width() / 2, val),
                    xytext=(0, 3 if val >= 0 else -9), textcoords="offset points",
                    ha="center", fontsize=7, color=INK)
    ax.axhline(0, color=INK2, linewidth=0.8)
    return bars


def curves_chart(res, path):
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4))
    ax = axes[0]
    grid = np.linspace(0.5, 30, 300)
    for name, c in [("MGS", MGS_C), ("SGS", SGS_C)]:
        t, y = res["curves"][name]
        m = t <= 30
        ax.plot(grid, ns_eval(res["ns"][name], grid) * 100, color=c, linewidth=1.5, alpha=0.8)
        ax.plot(t[m], y[m] * 100, "o", color=c, markersize=5, markeredgecolor=SURF, label=f"{name} par (dots), NS fit (line)")
    ax.set_title("Par curves and Nelson-Siegel fits")
    ax.set_xlabel("Tenor (years)"); ax.set_ylabel("Yield (%)"); ax.legend(loc="lower right")
    ax = axes[1]
    kf = res["key_fwds"]
    labs = list(dict.fromkeys(kf.forward)); idx = np.arange(len(labs)); w = 0.38
    for k, (name, c) in enumerate([("MGS", MGS_C), ("SGS", SGS_C)]):
        v = kf[kf.curve == name].rate_pct.to_numpy()
        bars = ax.bar(idx + (k - 0.5) * w, v, w, color=c, edgecolor=SURF, label=f"{name} forward")
        for b, val in zip(bars, v):
            ax.annotate(f"{val:.2f}", (b.get_x() + b.get_width() / 2, val), xytext=(0, 3),
                        textcoords="offset points", ha="center", fontsize=6.5)
    ax.set_xticks(idx, labs); ax.set_ylim(0, kf.rate_pct.max() * 1.18)
    ax.set_title("Key forwards from bootstrapped zeros (%)"); ax.set_ylabel("Rate (%)")
    ax.legend(loc="upper left", ncol=2)
    _src(fig, "Source: BNM FMIP YTM matrix (3 Nov 2026), MAS SGS benchmarks (30 Oct 2026). Par yields linearly interpolated before bootstrap.")
    fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(path, dpi=180); plt.close(fig)


def rich_cheap_chart(res, path):
    rc = res["rich_cheap"]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.0))
    for ax, name in zip(axes, ["MGS", "SGS"]):
        d = rc[rc.curve == name]
        labels = [f"{t:g}Y" if t >= 1 else f"{int(t*12)}M" for t in d.tenor]
        _bars(ax, labels, d.resid_bp, [CHEAP_C if v > 0 else RICH_C for v in d.resid_bp])
        ax.set_title(f"{name}: actual minus NS fit (bp)   + cheap / - rich")
        ax.set_ylim(d.resid_bp.min() - 2, d.resid_bp.max() + 2)
        ax.set_ylabel("bp")
    _src(fig, f"NS RMSE: MGS {res['ns']['MGS']['rmse_bp']:.1f}bp, SGS {res['ns']['SGS']['rmse_bp']:.1f}bp. Fit to par yields (approximation).")
    fig.tight_layout(rect=(0, 0.05, 1, 1)); fig.savefig(path, dpi=180); plt.close(fig)


def carry_roll_chart(res, path):
    cr = res["carry_roll"]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.0), sharey=True)
    for ax, name, col in zip(axes, ["MGS", "SGS"], [MGS_C, SGS_C]):
        d = cr[cr.curve == name]
        x = [f"{t:g}Y" for t in d.tenor]
        roll_be = d.carry_roll_bp - d.carry_bp  # price roll / DV01, so carry + roll stacks to the label
        ax.bar(x, d.carry_bp, color=col, edgecolor=SURF, linewidth=1, label="Carry")
        ax.bar(x, roll_be, bottom=d.carry_bp, color=THIRD_C, edgecolor=SURF, linewidth=1, label="Roll-down")
        for xi, v in zip(x, d.carry_roll_bp):
            ax.annotate(f"{v:.1f}", (xi, max(v, 0)), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=7)
        ax.axhline(0, color=INK2, linewidth=0.8)
        fund = res["funding"][name] * 100
        ax.set_title(f"{name}: 3M carry + roll, bp (funding {fund:.2f}%)")
        ax.set_ylim(min(-2, d.carry_roll_bp.min() - 1), cr.carry_roll_bp.max() * 1.3)
        ax.legend(loc="upper right")
    axes[0].set_ylabel("bp breakeven over 3M")
    _src(fig, "Carry = (coupon - funding) x 0.25 / DV01. Roll = clean-price gain rolling from T to T-3M at an unchanged curve / DV01. MYR funding = 3M T-bill; SGD funding = 6M SGS (proxy).")
    fig.tight_layout(rect=(0, 0.05, 1, 1)); fig.savefig(path, dpi=180); plt.close(fig)


def cross_market_chart(res, path):
    x = res["xmkt"]
    fig, ax = plt.subplots(figsize=(9, 3.0))
    idx = np.arange(len(x)); w = 0.38
    b1 = ax.bar(idx - w / 2, x.spread_bp, w, color=MGS_C, edgecolor=SURF, label="MGS - SGS (unhedged)")
    b2 = ax.bar(idx + w / 2, x.hedged_pickup_bp, w, color=THIRD_C, edgecolor=SURF, label="FX-hedged MGS - SGS (SGD investor)")
    for bars in (b1, b2):
        for b in bars:
            ax.annotate(f"{b.get_height():.0f}", (b.get_x() + b.get_width() / 2, b.get_height()),
                        xytext=(0, 3), textcoords="offset points", ha="center", fontsize=7)
    ax.set_xticks(idx, [f"{t:g}Y" + ("*" if i else "") for t, i in zip(x.tenor, x.sgs_interpolated)])
    ax.set_ylim(0, x.spread_bp.max() * 1.35)
    ax.set_ylabel("bp"); ax.legend(loc="upper left", ncol=2)
    ax.set_title(f"MGS-SGS spread and hedged pickup (3M rolling hedge cost {res['hedge_3m']*1e4:.1f}bp p.a.)")
    _src(fig, "* SGS 7Y interpolated. Hedge cost from CIP using 3M MY T-bill vs 6M SGS as short-rate proxies (approximation; ignores NDF/onshore basis).")
    fig.tight_layout(rect=(0, 0.05, 1, 1)); fig.savefig(path, dpi=180); plt.close(fig)


def credit_chart(res, path):
    c = res["credit"]
    fig, ax = plt.subplots(figsize=(5, 2.8))
    _bars(ax, [f"{t:g}Y" for t in c.tenor], c.spread_bp, [MGS_C] * len(c), fmt="{:.0f}")
    ax.set_ylim(0, c.spread_bp.max() * 1.25)
    ax.set_title("MYR AAA - MGS spread (bp)"); ax.set_ylabel("bp")
    _src(fig, "Source: BNM FMIP YTM matrix, 3 Nov 2026 (AAA corporate and MGS par yields).")
    fig.tight_layout(rect=(0, 0.06, 1, 1)); fig.savefig(path, dpi=180); plt.close(fig)


def scenario_chart(res, path):
    s = res["scenario_pnl"]
    trades = list(dict.fromkeys(s.trade)); scen = ["hold", "hike25", "cut25"]
    labels = {"hold": "Hold 2.75%", "hike25": "+25bp", "cut25": "-25bp"}
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.0), sharey=True)
    for ax, col, title in zip(axes, ["mpc_day_pnl", "pnl_3m_total"], ["MPC-day P&L", "3M horizon P&L (incl. carry + roll)"]):
        idx = np.arange(3); w = 0.38
        for k, (tr, colr) in enumerate(zip(trades, [MGS_C, SGS_C])):
            v = [s[(s.trade == tr) & (s.scenario == sc)][col].iloc[0] / 1e3 for sc in scen]
            bars = ax.bar(idx + (k - 0.5) * w, v, w, color=colr, edgecolor=SURF, label=tr.split(": ")[1])
            for b, val in zip(bars, v):
                ax.annotate(f"{val:+.0f}", (b.get_x() + b.get_width() / 2, val), xytext=(0, 3 if val >= 0 else -9),
                            textcoords="offset points", ha="center", fontsize=7)
        ax.axhline(0, color=INK2, linewidth=0.8)
        ax.set_xticks(idx, [labels[x] for x in scen]); ax.set_title(title)
    axes[0].set_ylabel("RM '000"); axes[0].legend(loc="upper left", fontsize=7)
    _src(fig, "Sizing: primary DV01-neutral on FMIP benchmarks, short RM10m MGS 10/36; alternative cash-neutral RM10m MGS 7Y vs SGS 7Y. Full revaluation; shifts per data/mpc_scenarios.csv.")
    fig.tight_layout(rect=(0, 0.05, 1, 1)); fig.savefig(path, dpi=180); plt.close(fig)


def history_chart(res, path):
    """Sized to stay legible at half page width (trade pitch) and full width (README, note)."""
    h = res["history"]; d = h["daily"]; st = h["stats"]; hd = h["headline"]; tr = h["trades"]; pr = h["params"]
    fig, axes = plt.subplots(2, 1, figsize=(6.4, 3.9), sharex=True, gridspec_kw={"height_ratios": [1.7, 1]})
    ax = axes[0]
    ax.plot(d.index, d.s, color=MGS_C, linewidth=0.9, label="5s10s")
    ax.plot(d.index, d.m, color=INK, linewidth=1.1, label="1Y mean")
    ax.plot(d.index, d.band, color=INK2, linewidth=0.9, linestyle="--", label=f"Entry line (mean - {pr['x_bp']:.0f}bp)")
    for dt in st["switch_dates"]:
        ax.axvline(pd.Timestamp(dt), color=INK2, linewidth=0.6, linestyle=":", alpha=0.6, zorder=0)
    ax.axhline(pr["target_bp"], color=THIRD_C, linewidth=0.9, linestyle="-.", zorder=1,
               label=f"Live target {pr['target_bp']:.0f} / stop {pr['stop_bp']:.0f}bp")
    ax.axhline(pr["stop_bp"], color=RICH_C, linewidth=0.9, linestyle="-.", zorder=1)
    if len(tr):
        e = pd.to_datetime(tr.entry_date); x = pd.to_datetime(tr.exit_date)
        ax.scatter(e, tr.entry_bp, marker="^", s=20, color=THIRD_C, zorder=3, label="Entry")
        for reason, col, mk in [("target", THIRD_C, "o"), ("stop", RICH_C, "x"), ("time", INK2, "s")]:
            m = tr.reason == reason
            if m.any():
                ax.scatter(x[m], tr.exit_bp[m], marker=mk, s=16, color=col, zorder=3, label=f"Exit: {reason}")
    ax.scatter([d.index[-1]], [st["today_bp"]], s=34, color=SGS_C, zorder=4, label="Today")
    sig = h["signal_today"]
    ax.text(0.995, 0.97, f"Today {st['today_bp']:.0f}bp: z {st['z_full']:+.1f} (3Y), {st['z_1y']:+.1f} (1Y)\n"
            f"Entry line {sig['entry_line_bp']:.1f}bp: " + ("signal on" if sig["triggered"] else "no signal"),
            transform=ax.transAxes, ha="right", va="top", fontsize=6.5, color=INK,
            bbox={"boxstyle": "round,pad=0.3", "facecolor": SURF, "edgecolor": GRID})
    ax.set_ylim(d.s.min() - 2, d.s.max() + 13)
    ax.set_ylabel("bp"); ax.legend(loc="upper left", ncol=4, fontsize=6, columnspacing=0.8, handlelength=1.4)
    ax.set_title(f"MGS 5s10s: mean {st['mean_bp']:.1f}bp, sd {st['sd_bp']:.1f}bp, "
                 f"AR(1) half-life {st['ar1_daily']['half_life']:.0f} days")
    ax = axes[1]
    ax.plot(d.index, d.cum_pnl / 1e3, color=THIRD_C, linewidth=1.4, label="Spread + carry")
    ax.plot(d.index, d.pnl_spread.cumsum() / 1e3, color=INK2, linewidth=0.9, linestyle="--", label="Spread only")
    ax.axhline(0, color=INK2, linewidth=0.8)
    ax.set_ylabel("RM '000"); ax.legend(loc="upper left", ncol=2, fontsize=6)
    ax.set_title(f"Backtest P&L: {hd['n_trades']} trades{' + 1 open' if hd['open_trade'] else ''}, "
                 f"hit rate {hd.get('hit_rate_pct', 0):.0f}%, max drawdown RM{-hd['max_dd_rm']/1e3:.0f}k")
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %y"))
    _src(fig, f"Source: BNM FMIP benchmark closes, daily. Dotted: benchmark switches (no P&L). "
              f"Exit +{pr['target']:.0f}/-{pr['stop']:.0f}bp or {pr['max_hold']}d; carry at 3M MTB.")
    fig.tight_layout(rect=(0, 0.035, 1, 1)); fig.savefig(path, dpi=220); plt.close(fig)

def make_all(res, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    curves_chart(res, outdir / "fig1_curves.png")
    rich_cheap_chart(res, outdir / "fig2_rich_cheap.png")
    carry_roll_chart(res, outdir / "fig3_carry_roll.png")
    cross_market_chart(res, outdir / "fig4_cross_market.png")
    credit_chart(res, outdir / "fig5_credit.png")
    scenario_chart(res, outdir / "fig6_scenario_pnl.png")
    history_chart(res, outdir / "fig7_history.png")
