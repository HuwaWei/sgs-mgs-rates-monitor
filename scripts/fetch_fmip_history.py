"""Download daily MGS benchmark closing yields from BNM FMIP into data/mgs_benchmark_history.csv.

Source page: https://financialmarkets.bnm.gov.my/benchmark-yields?date=YYYY-MM-DD
(BNM Financial Markets Information Portal, "Benchmark Yields", MGS - Conventional table).

One request per weekday. FMIP labels each table with the trading date it shows; rows are
de-duplicated on that date, so holidays do not create duplicate observations. The script is
resumable: dates already in the CSV are skipped.

    python3 scripts/fetch_fmip_history.py --start 2023-11-01 --end 2026-11-03
"""
import argparse
import csv
import re
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

URL = "https://financialmarkets.bnm.gov.my/benchmark-yields?date={d}"
OUT = Path(__file__).resolve().parents[1] / "data" / "mgs_benchmark_history.csv"
FIELDS = ["trade_date", "instrument", "tenor", "maturity_month", "coupon_pct", "close_pct", "last_traded",
          "volume_rm_mn", "source"]
SOURCE = "BNM FMIP Benchmark Yields"


def _cells(row):
    return [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S)]


def _num(x):
    x = x.replace("*", "").strip()
    return "" if x in ("", "-") else x


def parse(html: str):
    """Return (trading date, rows). '*' on FMIP means last traded (no trade that day): kept, flagged."""
    m = re.search(r"Trading Date:\s*([0-9]{2} \w{3} [0-9]{4})", html)
    if not m:
        return None, []
    tdate = datetime.strptime(m.group(1), "%d %b %Y").date()
    rows = []
    t = html[html.find('id="mgs-table"'):]
    t = t[:t.find("</table>")]
    for row in re.findall(r"<tr>(.*?)</tr>", t, flags=re.S):
        c = _cells(row)
        if len(c) == 8 and re.fullmatch(r"\d+Y", c[0]):
            rows.append({"instrument": "MGS", "tenor": c[0], "maturity_month": c[1], "coupon_pct": _num(c[2]),
                         "close_pct": _num(c[5]), "last_traded": int("*" in c[5]), "volume_rm_mn": _num(c[6])})
    i = html.find("Short-Term Bills")
    t = html[i:html.find("</table>", i)] if i >= 0 else ""
    for row in re.findall(r"<tr>(.*?)</tr>", t, flags=re.S):
        c = _cells(row)
        if len(c) == 4 and c[0].replace("&#039;", "'") == "M'sian Treasury Bills":
            for tenor, v in zip(["3M", "6M", "12M"], c[1:]):
                if _num(v):
                    rows.append({"instrument": "MTB", "tenor": tenor, "maturity_month": "", "coupon_pct": "",
                                 "close_pct": _num(v), "last_traded": int("*" in v), "volume_rm_mn": ""})
    return tdate, rows


def fetch(d: date, retries: int = 3) -> str:
    req = urllib.request.Request(URL.format(d=d.isoformat()), headers={"User-Agent": "Mozilla/5.0 (research script)"})
    for k in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", errors="ignore")
        except Exception as e:  # network hiccup: back off and retry
            if k == retries - 1:
                raise
            time.sleep(2 ** (k + 1))
            print(f"retry {d}: {e}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    out = Path(a.out)
    start, end = date.fromisoformat(a.start), date.fromisoformat(a.end)

    seen_req, seen_trade = set(), set()
    log = out.with_suffix(".requested")
    if log.exists():
        seen_req = set(log.read_text().split())
    new_file = not out.exists()
    if not new_file:
        with out.open() as f:
            seen_trade = {r["trade_date"] for r in csv.DictReader(f)}

    with out.open("a", newline="") as f, log.open("a") as lg:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        d = start
        while d <= end:
            if d.weekday() < 5 and d.isoformat() not in seen_req:
                tdate, rows = parse(fetch(d))
                if tdate is not None and tdate.isoformat() not in seen_trade and rows:
                    for r in rows:
                        w.writerow({"trade_date": tdate.isoformat(), **r, "source": SOURCE})
                    seen_trade.add(tdate.isoformat())
                    f.flush()
                lg.write(d.isoformat() + "\n"); lg.flush()
                time.sleep(a.sleep)
            d += timedelta(days=1)
    print(f"{len(seen_trade)} trading dates in {out}")


if __name__ == "__main__":
    main()
