"""Run the full analysis and write outputs/ (charts, metrics.json, tables)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.model import (CATEGORIES, DEFAULT_VALUES, break_even_point_value, evaluate, load_cards)
import charts

OUT = Path(__file__).resolve().parent / "outputs"
OUT.mkdir(exist_ok=True)
SEED, N_SIM = 7, 20000

# Monthly spend in COP, in the order of CATEGORIES:
# food, transport, entertainment, clothing, education, health, travel, usd_online, falabella_group, taxes
PERSONAS = {
    "University student": [500_000, 400_000, 150_000, 100_000, 0, 80_000, 0, 70_000, 0, 0],
    "Young professional": [1_000_000, 600_000, 300_000, 250_000, 100_000, 200_000, 300_000, 300_000, 150_000, 0],
    "Frequent traveller": [1_500_000, 700_000, 400_000, 400_000, 0, 300_000, 1_500_000, 1_200_000, 200_000, 0],
    "High spender": [3_000_000, 1_500_000, 1_000_000, 1_000_000, 500_000, 700_000, 2_000_000, 2_000_000,
                     800_000, 1_500_000],
}
BASE_MIX = np.array(PERSONAS["Young professional"], float)
BASE_MIX /= BASE_MIX.sum()
SIM_RANGES = {"puntos_colombia": (5, 7), "puntos_bbva": (10, 30), "davipuntos": (10, 15),
              "one_rewards": (10, 20), "cmr_puntos": (10, 20), "avg_ticket": (30_000, 150_000)}


def label(cards, i, j):
    ids = list(cards.id)
    return ids[i] if i == j else f"{ids[i]} + {ids[j]}"


def main():
    cards = load_cards()
    ids = list(cards.id)
    rng = np.random.default_rng(SEED)

    # 1. Personas at the default point values
    banks = cards.bank.to_numpy()
    persona_out, rows = {}, []
    for name, spend in PERSONAS.items():
        single, pv, pidx, route = evaluate(cards, spend)
        v = single[0]
        for cid, val in zip(ids, v):
            rows.append({"persona": name, "card": cid, "net_annual_cop": round(float(val))})
        order = np.argsort(-v)
        persona_out[name] = {
            "monthly_spend_cop": int(sum(spend)),
            "top3": [{"card": ids[k], "net_annual_cop": round(float(v[k]))} for k in order[:3]],
            "tied_best": [ids[k] for k in range(len(v)) if v[k] >= v.max() - 1],
            "best_per_bank": {b: {"card": ids[int(np.flatnonzero(banks == b)[v[banks == b].argmax()])],
                                  "net_annual_cop": round(float(v[banks == b].max()))}
                              for b in cards.bank.unique()},
            "best_pair": label(cards, *pidx[0]),
            "best_pair_value_cop": round(float(pv[0])),
            "routing": {c: ids[route[0, i]] for i, c in enumerate(CATEGORIES) if spend[i] > 0},
            "bbva_point_value_needed_for_bbva_to_win": break_even_point_value(
                cards, spend, "bbva_platinum", "puntos_bbva"),
        }
    pd.DataFrame(rows).to_csv(OUT / "persona_values.csv", index=False)

    # 2. Without BBVA's published 30 COP per point: what wins at a conservative 10?
    conservative = {}
    for name, spend in PERSONAS.items():
        v = evaluate(cards, spend, {"puntos_bbva": 10.0}, pairs=False)[0]
        conservative[name] = {"best_card": ids[int(v.argmax())], "net_annual_cop": round(float(v.max()))}

    # 3. Monte Carlo over households and point values
    total = rng.lognormal(np.log(3_000_000), 0.7, N_SIM)
    mix = rng.dirichlet(BASE_MIX * 25 + 0.05, N_SIM)
    spend = mix * total[:, None]
    vals = {k: rng.uniform(a, b, N_SIM) for k, (a, b) in SIM_RANGES.items()}
    single, pv, pidx, _ = evaluate(cards, spend, vals)
    winner = single.argmax(1)
    fees = cards.fee_month_cop.to_numpy() > 0
    sims = pd.DataFrame({"monthly_spend": total, "winner": [ids[k] for k in winner],
                         "winner_bank": banks[winner], "best_single": single.max(1), "best_pair": pv,
                         "pair": [label(cards, a, b) for a, b in pidx], **vals})
    sims.to_csv(OUT / "simulations.csv.gz", index=False)
    by_spend = (sims.assign(bucket=pd.cut(sims.monthly_spend, [0, 1.5e6, 3e6, 6e6, 12e6, np.inf],
                                          labels=["<1.5M", "1.5-3M", "3-6M", "6-12M", ">12M"]))
                .groupby("bucket", observed=True).winner.agg(lambda w: w.value_counts(normalize=True).round(4).head(3).to_dict()))
    bbva_bins = pd.cut(sims.puntos_bbva, [10, 15, 20, 25, 30])
    bbva_share = (sims.winner_bank == "BBVA").groupby(bbva_bins, observed=True).mean().round(4)

    metrics = {
        "cards": len(cards),
        "cards_with_assumed_values": int((cards.assumed != "").sum()),
        "valuation_defaults": DEFAULT_VALUES,
        "personas": persona_out,
        "personas_if_bbva_point_is_worth_10_cop": conservative,
        "monte_carlo": {
            "n": N_SIM,
            "ranges": {k: list(v) for k, v in SIM_RANGES.items()},
            "median_monthly_spend_cop": round(float(np.median(total))),
            "win_share_by_card": {k: round(float(v), 4) for k, v in sims.winner.value_counts(normalize=True).items()},
            "win_share_by_bank": {k: round(float(v), 4) for k, v in sims.winner_bank.value_counts(normalize=True).items()},
            "winner_has_no_fee_share": round(float((~fees[winner] | (single.max(1) > 0)).mean()), 4),
            "winner_has_listed_fee_share": round(float(fees[winner].mean()), 4),
            "top_winners_by_spend": {str(k): v for k, v in by_spend.items()},
            "bbva_win_share_by_point_value": {str(k): float(v) for k, v in bbva_share.items()},
            "median_gain_second_card_cop": round(float(np.median(pv - single.max(1)))),
            "share_where_second_card_adds_value": round(float((pv - single.max(1) > 1).mean()), 4),
            "top_pairs": {k: round(float(v), 4) for k, v in sims.pair.value_counts(normalize=True).head(6).items()},
        },
    }
    del metrics["monte_carlo"]["winner_has_no_fee_share"]
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2))
    charts.make_all(OUT, cards, PERSONAS, BASE_MIX, metrics, sims)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
