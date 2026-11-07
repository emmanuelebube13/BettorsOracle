"""Walk-forward backtest: each season is predicted by a model trained only on earlier seasons."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, rules
from .markets import build_markets
from .model import RESULT_CLASSES, OracleModel, implied_probs

MARKET_WINS = {
    "Home win": lambda h, a: h > a,
    "Draw": lambda h, a: h == a,
    "Away win": lambda h, a: a > h,
    "Home or draw (1X)": lambda h, a: h >= a,
    "Away or draw (X2)": lambda h, a: a >= h,
    "Home or away (12)": lambda h, a: h != a,
    "Over 2.5 goals": lambda h, a: h + a > 2.5,
    "Under 2.5 goals": lambda h, a: h + a < 2.5,
    "BTTS - Yes": lambda h, a: h > 0 and a > 0,
    "BTTS - No": lambda h, a: not (h > 0 and a > 0),
}


def _scores(P: np.ndarray, y: np.ndarray) -> dict:
    onehot = np.eye(3)[y]
    eps = 1e-12
    return {
        "accuracy": round(float((P.argmax(1) == y).mean()), 4),
        "log_loss": round(float(-np.log(np.clip(P[np.arange(len(y)), y], eps, 1)).mean()), 4),
        "brier": round(float(((P - onehot) ** 2).sum(1).mean()), 4),
    }


def _bet_summary(bets: list[tuple[float, bool]]) -> dict:
    if not bets:
        return {"bets": 0, "hit_rate": None, "roi": None, "profit_units": 0.0}
    odds = np.array([b[0] for b in bets])
    won = np.array([b[1] for b in bets])
    profit = np.where(won, odds - 1, -1.0).sum()
    return {
        "bets": len(bets),
        "hit_rate": round(float(won.mean()), 4),
        "roi": round(float(profit / len(bets)), 4),
        "profit_units": round(float(profit), 2),
    }


def evaluate_season(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    model = OracleModel().fit(train)
    preds = model.predict(test)
    y = test["result"].map({c: i for i, c in enumerate(RESULT_CLASSES)}).to_numpy()
    P = preds[["p_H", "p_D", "p_A"]].to_numpy()

    # Market baseline (only rows with odds).
    mk = [implied_probs(r.odds_h, r.odds_d, r.odds_a) for r in test.itertuples()]
    has_mk = np.array([m is not None for m in mk])
    M = np.array([m for m in mk if m is not None])

    rule_picks = [rules.evaluate(r)["pick"] for r in test.to_dict("records")]
    rule_acc = float(np.mean([p == t for p, t in zip(rule_picks, test["result"])]))

    top, value = [], []
    calib = []
    for (_, row), (_, pr) in zip(test.iterrows(), preds.iterrows()):
        hg, ag = int(row.hg), int(row.ag)
        for m in build_markets(pr.to_dict(), row.to_dict()):
            won = MARKET_WINS[m["market"]](hg, ag)
            calib.append((m["prob"], won))
            if not m["odds"]:
                continue
            if m["prob"] >= config.TOP_BET_MIN_PROB:
                top.append((m["odds"], won))
            if m["edge"] is not None and m["edge"] > 0.05:
                value.append((m["odds"], won))

    cal = pd.DataFrame(calib, columns=["p", "won"])
    cal["bin"] = pd.cut(cal.p, np.linspace(0, 1, 11), include_lowest=True)
    calibration = [
        {"predicted": round(float(g.p.mean()), 3), "actual": round(float(g.won.mean()), 3), "n": int(len(g))}
        for _, g in cal.groupby("bin", observed=True) if len(g) >= 30
    ]

    return {
        "matches": int(len(test)),
        "model": _scores(P, y),
        "market": _scores(M, y[has_mk]) if len(M) else None,
        "rules_accuracy": round(rule_acc, 4),
        "top_bets": _bet_summary(top),
        "value_bets": _bet_summary(value),
        "calibration": calibration,
    }


def run(feats: pd.DataFrame, n_test_seasons: int = 4) -> dict:
    from . import features as F

    hist = feats[~feats["is_fixture"] & F.usable(feats) & feats["result"].isin(RESULT_CLASSES)]
    seasons = sorted(hist["season"].unique())
    results = []
    for s in seasons[-n_test_seasons:]:
        train = hist[hist["season"] < s]
        test = hist[hist["season"] == s]
        if len(train) < 1000 or len(test) < 50:
            continue
        r = evaluate_season(train, test)
        r["season"] = f"20{s[:2]}/{s[2:]}"
        results.append(r)
    return {"seasons": results, "top_bet_threshold": config.TOP_BET_MIN_PROB}
