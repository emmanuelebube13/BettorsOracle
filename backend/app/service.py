"""Orchestration: refresh data, train, cache predictions."""
from __future__ import annotations

import json
import logging
import threading
from datetime import date

import numpy as np
import pandas as pd

from . import backtest, config, data, features, rules
from .markets import build_markets
from .model import OracleModel

log = logging.getLogger(__name__)
BACKTEST_PATH = config.DATA_DIR / "backtest.json"

_lock = threading.Lock()
_state: dict = {"feats": None, "model": None}


def _clean(v):
    if isinstance(v, (np.floating, float)):
        return None if np.isnan(v) else round(float(v), 4)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.bool_):
        return bool(v)
    return v


def refresh(fetch: bool = True, run_backtest: bool = True) -> dict:
    """Download data, rebuild features, retrain and (optionally) re-run the backtest."""
    with _lock:
        n_hist = data.ingest_history() if fetch else None
        n_fix = data.ingest_fixtures() if fetch else None
        matches, fixtures = data.load_matches(), data.load_fixtures()
        if matches.empty:
            raise RuntimeError("No match history available - check network access.")
        feats = features.add_diffs(features.build_features(matches, fixtures))
        hist = feats[~feats["is_fixture"]]
        model = OracleModel().fit(hist)
        model.save()
        _state.update(feats=feats, model=model)
        if run_backtest:
            bt = backtest.run(feats)
            BACKTEST_PATH.write_text(json.dumps(bt, indent=2))
        return {"history_rows": n_hist, "fixtures": n_fix, "trained_on": model.n_train,
                "trained_through": model.trained_through}


def _ensure_loaded() -> None:
    if _state["feats"] is not None:
        return
    with _lock:
        if _state["feats"] is not None:
            return
        matches, fixtures = data.load_matches(), data.load_fixtures()
        if matches.empty:
            return
        feats = features.add_diffs(features.build_features(matches, fixtures))
        model = OracleModel.load() or OracleModel().fit(feats[~feats["is_fixture"]])
        _state.update(feats=feats, model=model)


def ready() -> bool:
    _ensure_loaded()
    return _state["feats"] is not None


def _analyse(rows: pd.DataFrame) -> list[dict]:
    model: OracleModel = _state["model"]
    if rows.empty:
        return []
    preds = model.predict(rows)
    out = []
    for (_, row), (_, p) in zip(rows.iterrows(), preds.iterrows()):
        r = {k: _clean(v) for k, v in row.to_dict().items()}
        pd_ = p.to_dict()
        out.append({
            "league": r["league"],
            "league_name": config.LEAGUES.get(r["league"], r["league"]),
            "date": r["date"],
            "time": r.get("time"),
            "home": r["home"],
            "away": r["away"],
            "enough_history": bool(features.usable(rows.loc[[row.name]]).iloc[0]),
            "probs": {"home": round(pd_["p_H"], 4), "draw": round(pd_["p_D"], 4),
                      "away": round(pd_["p_A"], 4), "over25": round(pd_["p_over25"], 4),
                      "btts": round(pd_["p_btts"], 4)},
            "markets": build_markets(pd_, r),
            "oracle": rules.evaluate(r),
            "stats": {
                side: {m: r.get(f"{side}_{m}") for m in ["games"] + features.TEAM_METRICS}
                for side in ("home", "away")
            },
            "h2h": {"home_wins": r.get("h2h_home_wins"), "away_wins": r.get("h2h_away_wins"),
                    "games": r.get("h2h_games")},
        })
    return out


def fixtures(league: str | None = None) -> list[dict]:
    if not ready():
        return []
    f = _state["feats"]
    rows = f[f["is_fixture"] & (f["date"] >= date.today().isoformat())]
    if league:
        rows = rows[rows["league"] == league]
    return _analyse(rows)


def top_bets(min_prob: float = config.TOP_BET_MIN_PROB, league: str | None = None) -> list[dict]:
    """One pick per match: the priced market clearing `min_prob` with the best edge."""
    picks = []
    for fx in fixtures(league):
        if not fx["enough_history"]:
            continue
        cands = [m for m in fx["markets"] if m["prob"] >= min_prob and m["odds"]]
        if not cands:
            continue
        m = max(cands, key=lambda m: (m["edge"], m["prob"]))
        picks.append({**{k: fx[k] for k in ("league", "league_name", "date", "time", "home", "away")},
                      **m, "value": m["edge"] > 0})
    picks.sort(key=lambda x: (-(x["edge"] or -1), -x["prob"]))
    return picks


def predict_matchup(home: str, away: str) -> dict | None:
    """Ad-hoc prediction for any two teams in the database, as if played today."""
    if not ready():
        return None
    matches = data.load_matches()
    teams = set(matches.home) | set(matches.away)
    if home not in teams or away not in teams:
        return None
    last = matches[(matches.home == home) | (matches.away == home)].iloc[-1]
    fx = pd.DataFrame([{"league": last.league, "date": pd.Timestamp.today().strftime("%Y-%m-%d"),
                        "time": None, "home": home, "away": away}])
    feats = features.add_diffs(features.build_features(matches, fx))
    return _analyse(feats[feats["is_fixture"]])[0]


def teams() -> dict[str, list[str]]:
    matches = data.load_matches()
    if matches.empty:
        return {}
    latest = matches[matches.season == matches.season.max()]
    out = {}
    for lg, g in latest.groupby("league"):
        out[lg] = sorted(set(g.home) | set(g.away))
    return out


def backtest_report() -> dict | None:
    if BACKTEST_PATH.exists():
        return json.loads(BACKTEST_PATH.read_text())
    return None
