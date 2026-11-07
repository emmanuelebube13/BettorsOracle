"""The original Excel decision rules ("Oracle rules").

Two parts, mirroring the workbook:

* PREDICTION sheet - each metric is compared home vs away and votes for the
  stronger side.
* criteria sheet - each team is checked against absolute thresholds; the number
  met gives a Double Chance confidence tier (>=8 high, 5-7 moderate, <5 avoid).
"""
from __future__ import annotations

import math

# metric -> True if higher is better
VOTE_METRICS: dict[str, bool] = {
    "form": True,
    "avg_scored": True,
    "avg_conceded": False,
    "wins": True,
    "losses": False,
    "draws": False,
    "goal_ratio": True,
    "goal_diff": True,
    "avg_sot": True,
}

# Thresholds from the 'criteria' sheet (over an 11-game window).
# Possession and expected-goals rows are omitted: the free data source lacks them.
CRITERIA: list[tuple[str, str, float, str]] = [
    ("form", ">", 0.60, "Form > 60%"),
    ("avg_scored", ">", 1.5, "Avg scored > 1.5"),
    ("wins", ">", 7, "Wins > 7"),
    ("losses", "<", 4, "Losses < 4"),
    ("draws", ">", 3, "Draws > 3"),
    ("avg_conceded", "<", 1.5, "Avg conceded < 1.5"),
    ("goal_ratio", ">", 2.0, "Goal ratio > 2"),
    ("avg_sot", ">", 4, "Shots on target > 4"),
    ("h2h_wins", ">", 2, "H2H wins > 2"),
    ("goal_diff", ">", 15, "Goal difference > 15"),
]


def _ok(v) -> bool:
    return v is not None and not (isinstance(v, float) and math.isnan(v))


def votes(row: dict) -> dict:
    home = away = 0
    detail = []
    for m, higher in VOTE_METRICS.items():
        h, a = row.get(f"home_{m}"), row.get(f"away_{m}")
        if not (_ok(h) and _ok(a)) or h == a:
            winner = None
        elif (h > a) == higher:
            winner, home = "home", home + 1
        else:
            winner, away = "away", away + 1
        detail.append({"metric": m, "home": h, "away": a, "favours": winner})
    hw, aw = row.get("h2h_home_wins", 0) or 0, row.get("h2h_away_wins", 0) or 0
    if hw != aw:
        if hw > aw:
            home += 1
        else:
            away += 1
    detail.append({"metric": "h2h_wins", "home": hw, "away": aw,
                   "favours": None if hw == aw else ("home" if hw > aw else "away")})
    return {"home": home, "away": away, "detail": detail}


def criteria_met(row: dict, side: str) -> list[str]:
    met = []
    for metric, op, thr, label in CRITERIA:
        if metric == "h2h_wins":
            v = row.get(f"h2h_{side}_wins")
        else:
            v = row.get(f"{side}_{metric}")
        if not _ok(v):
            continue
        if (op == ">" and v > thr) or (op == "<" and v < thr):
            met.append(label)
    return met


def tier(n_met: int) -> str:
    if n_met >= 8:
        return "high"
    if n_met >= 5:
        return "moderate"
    return "avoid"


def evaluate(row: dict) -> dict:
    v = votes(row)
    home_met, away_met = criteria_met(row, "home"), criteria_met(row, "away")
    if v["home"] > v["away"]:
        pick = "H"
    elif v["away"] > v["home"]:
        pick = "A"
    else:
        pick = "D"
    return {
        "pick": pick,
        "votes": {"home": v["home"], "away": v["away"]},
        "metrics": v["detail"],
        "double_chance": {
            "home": {"met": home_met, "tier": tier(len(home_met))},
            "away": {"met": away_met, "tier": tier(len(away_met))},
        },
        "max_criteria": len(CRITERIA),
    }
