"""Reward valuation for the Colombian credit cards in my bank spreadsheets.

Every card is reduced to one number per spending category: pesos returned per
peso spent. Net annual value = sum(spend * rate) - fees after any waiver.
"""
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

CATEGORIES = ["food", "transport", "entertainment", "clothing", "education", "health",
              "travel", "usd_online", "falabella_group", "taxes"]
LABELS = {
    "food": "Food and groceries", "transport": "Transport", "entertainment": "Entertainment",
    "clothing": "Clothing", "education": "Education", "health": "Health and personal care",
    "travel": "Travel (flights, hotels)", "usd_online": "Online / abroad in USD",
    "falabella_group": "Falabella, Homecenter", "taxes": "Taxes",
}
PROGRAMS = ["puntos_colombia", "puntos_bbva", "davipuntos", "one_rewards", "cmr_puntos"]
DEFAULT_VALUES = {"trm": 3240.0, "puntos_colombia": 6.0, "puntos_bbva": 30.0,
                  "davipuntos": 15.0, "one_rewards": 15.0, "cmr_puntos": 19.2,
                  "avg_ticket": 60_000.0}


def load_cards(path=None):
    path = path or Path(__file__).resolve().parents[1] / "data" / "cards.csv"
    return pd.read_csv(path).fillna({"assumed": ""})


def _values(n, values):
    v = {**DEFAULT_VALUES, **(values or {})}
    return {k: np.broadcast_to(np.asarray(x, float), (n,)) for k, x in v.items()}


def rate_tensor(cards, n=1, values=None):
    """Pesos returned per peso spent, shape (n, cards, categories)."""
    v = _values(n, values)
    raw = cards[CATEGORIES].to_numpy(float)
    per_point = np.zeros((n, len(cards)))
    for p in PROGRAMS:
        per_point[:, (cards.program == p).to_numpy()] = v[p][:, None]
    unit = np.where(cards.unit.to_numpy() == "per_usd", 1.0, 0.0)[None, :]
    scale = unit / v["trm"][:, None] + (1 - unit) / 1000.0        # points per peso
    return raw[None] * (scale * per_point)[:, :, None]


def annual_fees(cards, monthly_on_card, values=None):
    """Annual fee after waivers. monthly_on_card: (n, cards) pesos billed per month."""
    n = monthly_on_card.shape[0]
    v = _values(n, values)
    fee = cards.fee_month_cop.to_numpy(float)[None] * np.ones((n, 1))
    full = cards.waiver_full.to_numpy(float)[None]
    part = cards.waiver_partial.to_numpy(float)[None]
    kind = cards.waiver.to_numpy()[None]
    purchases = monthly_on_card / v["avg_ticket"][:, None]
    waived_p = (kind == "purchases") & (purchases >= full)
    billing = kind == "billing"
    fee = np.where(waived_p, 0.0, fee)
    fee = np.where(billing & (monthly_on_card >= full), 0.0,
                   np.where(billing & (monthly_on_card >= part), fee * 0.5, fee))
    return fee * 12


def evaluate(cards, monthly_spend, values=None, pairs=True):
    """Net annual value of every card, and of the best two-card wallet.

    monthly_spend: (n, categories). Returns single (n, cards) and, when pairs is
    True, the best pair value (n,), its card indices (n, 2) and routing (n, categories).
    """
    s = np.atleast_2d(np.asarray(monthly_spend, float))
    n = len(s)
    rates = rate_tensor(cards, n, values)
    total = s.sum(1)
    single = 12 * np.einsum("nc,nkc->nk", s, rates) \
        - annual_fees(cards, np.repeat(total[:, None], len(cards), 1), values)
    if not pairs:
        return single
    best_val = single.max(1).copy()
    k0 = single.argmax(1)
    best_idx = np.stack([k0, k0], 1)
    best_route = np.repeat(k0[:, None], s.shape[1], 1)
    fee_m = cards.fee_month_cop.to_numpy(float)
    for i, j in combinations(range(len(cards)), 2):
        to_i = rates[:, i] >= rates[:, j]
        r = np.where(to_i, rates[:, i], rates[:, j])
        si = (s * to_i).sum(1)
        sj = total - si
        on = np.zeros((n, len(cards)))
        on[:, i], on[:, j] = si, sj
        fees = annual_fees(cards, on, values)
        val = 12 * (s * r).sum(1) - fees[:, i] - fees[:, j]
        # a card that receives no spend is not opened, so it charges nothing
        val += np.where(si == 0, fees[:, i], 0) + np.where(sj == 0, fees[:, j], 0)
        better = val > best_val + 1e-6
        best_val[better] = val[better]
        best_idx[better] = (i, j)
        best_route[better] = np.where(to_i[better], i, j)
    return single, best_val, best_idx, best_route


def break_even_point_value(cards, monthly_spend, card_id, program, values=None, lo=0.0, hi=100.0):
    """Lowest point value (COP) at which `card_id` becomes the best single card."""
    k = list(cards.id).index(card_id)
    for _ in range(40):
        mid = (lo + hi) / 2
        single = evaluate(cards, monthly_spend, {**(values or {}), program: mid}, pairs=False)[0]
        if single.argmax() == k:
            hi = mid
        else:
            lo = mid
    return hi if hi < 99.99 else None
