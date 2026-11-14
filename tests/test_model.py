import numpy as np

from src.model import (CATEGORIES, DEFAULT_VALUES, annual_fees, break_even_point_value, evaluate,
                       load_cards, rate_tensor)

CARDS = load_cards()
IDS = list(CARDS.id)


def spend(total, cat="food"):
    s = np.zeros(len(CATEGORIES))
    s[CATEGORIES.index(cat)] = total
    return s


def test_bancolombia_amex_platinum_rate_matches_published_ratio():
    r = rate_tensor(CARDS)[0, IDS.index("bcol_amex_platinum"), 0]
    assert np.isclose(r, 6 / 3800 * DEFAULT_VALUES["puntos_colombia"], rtol=1e-3)


def test_usd_programs_scale_with_trm_and_point_value():
    k = IDS.index("bbva_platinum")
    a = rate_tensor(CARDS, values={"trm": 3000, "puntos_bbva": 30})[0, k, 0]
    assert np.isclose(a, 3 * 30 / 3000)


def test_taxes_never_earn():
    assert np.allclose(rate_tensor(CARDS)[0, :, CATEGORIES.index("taxes")], 0)


def test_davivienda_billing_waiver_full_partial_none():
    k = IDS.index("davi_mc_black")
    on = np.zeros((3, len(CARDS)))
    on[:, k] = [2_100_000, 1_600_000, 900_000]
    f = annual_fees(CARDS, on)[:, k]
    assert np.allclose(f, [0, 46000 * 6, 46000 * 12])


def test_davibank_purchase_waiver_uses_average_ticket():
    k = IDS.index("davibank_infinite")
    on = np.zeros((2, len(CARDS)))
    on[:, k] = 600_000
    f = annual_fees(CARDS, on, {"avg_ticket": np.array([60_000, 61_000])})[:, k]
    assert f[0] == 0 and f[1] == 55730 * 12


def test_pair_is_never_worse_than_best_single():
    rng = np.random.default_rng(1)
    s = rng.dirichlet(np.ones(len(CATEGORIES)), 200) * rng.uniform(3e5, 2e7, (200, 1))
    single, pv, _, _ = evaluate(CARDS, s)
    assert np.all(pv >= single.max(1) - 1e-6)


def test_break_even_point_value_is_consistent():
    s = spend(3_000_000)
    pv = break_even_point_value(CARDS, s, "bbva_platinum", "puntos_bbva")
    above = evaluate(CARDS, s, {"puntos_bbva": pv + 0.5}, pairs=False)[0]
    below = evaluate(CARDS, s, {"puntos_bbva": pv - 0.5}, pairs=False)[0]
    assert IDS[above.argmax()] == "bbva_platinum" and IDS[below.argmax()] != "bbva_platinum"
