"""Turn model probabilities + bookmaker odds into bettable markets and stakes."""
from __future__ import annotations

import math

from . import config


def _num(x) -> float | None:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) and x > 1.0 else None


def double_chance_odds(o1, o2) -> float | None:
    """Price of 'either outcome' implied by two 1X2 prices (keeps the book margin)."""
    o1, o2 = _num(o1), _num(o2)
    if not (o1 and o2):
        return None
    return round(1 / (1 / o1 + 1 / o2), 3)


def kelly_fraction(p: float, odds: float | None,
                   fraction: float = config.KELLY_FRACTION,
                   cap: float = config.MAX_STAKE_PCT) -> float:
    """Fractional Kelly stake as a share of bankroll; 0 when there is no edge."""
    odds = _num(odds)
    if not odds or not (0 < p < 1):
        return 0.0
    b = odds - 1
    k = (b * p - (1 - p)) / b
    return round(max(0.0, min(k * fraction, cap)), 4)


def build_markets(p: dict, odds: dict) -> list[dict]:
    """p: p_H, p_D, p_A, p_over25, p_btts. odds: odds_h, odds_d, odds_a, odds_o25, odds_u25."""
    oh, od, oa = odds.get("odds_h"), odds.get("odds_d"), odds.get("odds_a")
    spec = [
        ("Home win", "1X2", p["p_H"], oh),
        ("Draw", "1X2", p["p_D"], od),
        ("Away win", "1X2", p["p_A"], oa),
        ("Home or draw (1X)", "Double chance", p["p_H"] + p["p_D"], double_chance_odds(oh, od)),
        ("Away or draw (X2)", "Double chance", p["p_A"] + p["p_D"], double_chance_odds(oa, od)),
        ("Home or away (12)", "Double chance", p["p_H"] + p["p_A"], double_chance_odds(oh, oa)),
        ("Over 2.5 goals", "Goals", p["p_over25"], odds.get("odds_o25")),
        ("Under 2.5 goals", "Goals", 1 - p["p_over25"], odds.get("odds_u25")),
        ("BTTS - Yes", "BTTS", p["p_btts"], None),
        ("BTTS - No", "BTTS", 1 - p["p_btts"], None),
    ]
    out = []
    for name, group, prob, o in spec:
        o = _num(o)
        prob = float(prob)
        edge = round(prob * o - 1, 4) if o else None
        out.append({
            "market": name,
            "group": group,
            "prob": round(prob, 4),
            "fair_odds": round(1 / prob, 2) if prob > 0 else None,
            "odds": o,
            "edge": edge,
            "kelly_pct": kelly_fraction(prob, o),
        })
    return out
