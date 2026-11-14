# Data

`cards.csv` lists the 24 credit cards I track in my own bank spreadsheets (Bancolombia, BBVA, DAVIbank, Davivienda, Banco Falabella and Nu), with their published conditions as of November 2026 and one source URL per row. The `assumed` column flags every value that is not published directly for that card.

## Columns
- **Category columns** (`food` ... `taxes`): points earned. The unit depends on `unit`:
  - `per_usd`: points per US dollar billed.
  - `per_1000cop`: points per 1,000 COP. For example, Bancolombia's "6 Puntos Colombia por cada $3.800" becomes 1.5789.
- **`taxes`**: zero for every card, because the programs exclude tax payments from earning.
- **`fee_month_cop`**: the monthly cuota de manejo after any introductory free months.
- **`waiver`**: how the fee can be waived.
  - `none`: no waiver.
  - `purchases`: the fee is waived with at least `waiver_full` purchases a month (DAVIbank).
  - `billing`: the fee is fully waived when monthly billing on the card reaches `waiver_full`, and half waived from `waiver_partial` (Davivienda). The 50% for the partial waiver is an assumption.

## Point values (defaults in `src/model.py`, editable in the dashboard)

| Program | COP per point | Basis |
|---|---|---|
| Puntos Colombia | 6 | value at redemption (7 at Grupo Exito), Valora Analitik interview with Puntos Colombia |
| Puntos BBVA | 30 | the only peso value BBVA publishes, in its loyalty rules; for personal cards the rate is set at redemption |
| Davipuntos | 15 | Davivienda loyalty rules, June 2026: value of a Davipunto when paying a purchase |
| DAVIbank One Rewards | 15 | DAVIbank: cashback value for Black and Signature |
| CMR Puntos | 19.2 | implied by "a year without cuota de manejo for 20,000 CMR Puntos" (12 x 31,990 / 20,000) |

TRM: 3,240 COP per USD, the automatic TRM in my November 2026 spreadsheets.
