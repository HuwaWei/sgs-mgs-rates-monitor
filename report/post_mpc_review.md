# Post-MPC Review: BNM, 5 Nov 2026

*Huwa Jia Wei · Written after the 3:00 PM decision on 5 Nov 2026. The original [trade pitch](trade_pitch.md) was committed on 3 Nov 2026, before the decision.*

## 1. The decision

**BNM held the OPR at 2.75%.** This was the final MPC meeting of 2026.

Key wording in the Monetary Policy Statement:

| Theme | Statement | Read |
|---|---|---|
| Stance | The stance is "consistent with the outlook of continued price stability" | Neutral. There is no easing bias and no explicit tightening bias |
| Inflation | Headline and core inflation "expected to edge higher" in 2027 (YTD headline 1.8%, core 1.9%) | Mildly hawkish |
| Guidance | The MPC "will remain vigilant to cost pressures and domestic demand conditions" | Mildly hawkish. It keeps a hike in 2027 on the table without signalling one |
| Growth | 2026 growth expected above 5%; growth "resilient" in 2027, with the external sector a major driver | Supportive of no change |
| Risks | Downside: prolonged Middle East conflict, geopolitical tensions, tighter global financial conditions, market valuations, fiscal vulnerabilities | Matches the pitch's "pressure is external" view |

**Verdict: a hold with a mild hawkish tilt.** That is the pitch's **hold scenario (70%)**, not the hike (25%) or the cut (5%). The statement does not "open the door to hikes" in the sense the pitch named as its first "what would make us wrong" trigger, but it does not close it either.

## 2. What the playbook says to do now

| | Pitch's rule | Now |
|---|---|---|
| **Primary: MGS 5s10s steepener** (buy RM19.1m 6/31, sell RM10m 10/36) | Hold for carry + roll toward 28bp; cut at 16bp; cut on guidance that opens the door to hikes | **Hold.** Target 28bp and stop 16bp unchanged. No trigger was hit. Do not add size: hike risk has not gone away, it has moved to the first meetings of 2027 |
| **Alternative: FX-hedged MGS 7Y vs SGS 7Y** (cash-neutral switch) | Hold for the hedged pickup; target 162bp, stop 187bp | **Hold.** A hold leaves the short-rate differential, and so the hedge cost and the +70bp pickup, unchanged |

**What to watch over the next 3 months:**
- **The front end.** The hold scenario assumed 1–2Y MGS rally 2bp as the hike premium bleeds out. The "vigilant to cost pressures" wording argues that premium may stick. If 1–2Y yields do not fall and 5s10s flattens instead, the stop at 16bp does its job.
- **The next MPC.** The trade's 3M horizon now spans the first meeting of 2027. The hike scenario is still the relevant stress: –RM30.2k on the day, +RM4.4k over 3M including carry.
- **Foreign flows into the belly.** Selling that migrates from the 10Y into 3–5Y would hurt the steepener directly.

## 3. Expected P&L under the scenario that played out

From [`output/tables/scenario_pnl.csv`](../output/tables/scenario_pnl.csv). These figures are the pitch's pre-committed hold-scenario estimates, not realised P&L. Hold scenario curve shifts: 1–2Y –2bp, 3Y –1bp, 5–7Y 0bp, 10Y +1bp ([`data/mpc_scenarios.csv`](../data/mpc_scenarios.csv)).

| Trade | MPC day | 3M carry + roll | 3M total |
|---|---:|---:|---:|
| Primary: MGS 5s10s steepener | **+RM9.6k** | +RM34.6k | **+RM44.2k** |
| Alternative: FX-hedged MGS 7Y vs SGS 7Y | RM0.0k | +RM25.7k | **+RM25.7k** |

The primary's MPC-day gain is small by design: about 1bp of steepening at RM8.2k per bp. Almost all of the expected return is carry + roll. That is consistent with the post-backtest framing: a **carry trade with a catalyst, not a value trade**.

**Mark-to-market:** realised P&L uses the **5 Nov 2026 BNM FMIP closing yields** for MGS 4.232% 6/31 and MGS 3.92% 10/36, and the MGS 7Y and SGS 7Y levels. It will be added here once the close is published.

## 4. What I got right, what I would change

The central call was right: a hold at 2.75%, weighted 70%, and the statement's risk list (Middle East, tighter global financial conditions, fiscal vulnerabilities) matches the pitch's view that the pressure on MGS is external, not from BNM. Recasting the steepener as a carry trade after the backtest also proved the right framing: with a plain hold, the trade's case rests on carry + roll, not on a dramatic repricing. One outcome does not validate the 70/25/5 weights, though. A hold was the consensus, so getting it right says little about the 25% hike weight. What I would change is the single "hold" bucket. The statement was a hawkish-leaning hold, and the hold scenario assumed the 1–2Y hike premium would bleed out. I would have split it into a dovish and a hawkish hold, with the hawkish hold keeping the front end unchanged, because that is the version that played out in the wording and it gives a smaller MPC-day gain. I would also have pre-written the playbook for the next meeting, since a 3M carry trade put on before a November meeting inevitably runs into the first meeting of the next year.

---

*Sources: Monetary Policy Statement, 5 Nov 2026 (Bank Negara Malaysia, [OPR decisions](https://www.bnm.gov.my/monetary-stability/opr-decisions)), as reported by Bernama via [Malay Mail](https://www.malaymail.com/news/money/2026/11/05/no-rate-change-from-bnm-as-years-final-mpc-meeting-wraps-up/242067), [The Star](https://www.thestar.com.my/business/business-news/2026/11/05/bank-negara-keeps-opr-steady-at-275) and [The Sun](https://thesun.my/business/bnm-maintains-opr-at-2-75-as-2026-growth-seen-above-5/), 5 Nov 2026. Scenario P&L: this repo's pre-decision outputs.*
