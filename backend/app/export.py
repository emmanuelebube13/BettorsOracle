"""Export predictions as static JSON for the serverless (GitHub Pages) build.

Everything the UI shows is pre-computed here by the same code that powers the API:
fixtures, the backtest report, and predictions for every pairing of current-season
teams within each league (for the head-to-head predictor).
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from itertools import permutations
from pathlib import Path

import pandas as pd

from . import config, data, features, service

log = logging.getLogger(__name__)


def _dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(",", ":"), allow_nan=False), encoding="utf-8")


def export(out_dir: Path) -> dict:
    if not service.ready():
        raise RuntimeError("No data loaded - run a refresh first.")
    out_dir = Path(out_dir)
    model = service._state["model"]

    fixtures = service.fixtures()
    _dump(out_dir / "fixtures.json", fixtures)
    _dump(out_dir / "backtest.json", service.backtest_report() or {"seasons": [], "top_bet_threshold": 0.7})

    teams = service.teams()
    _dump(out_dir / "teams.json", teams)

    # Predictor: every ordered pair of current-season teams per league, as if played today.
    matches = data.load_matches()
    today = date.today().isoformat()
    n_pairs = 0
    for league, names in teams.items():
        pairs = pd.DataFrame(
            [{"league": league, "date": today, "time": None, "home": h, "away": a}
             for h, a in permutations(names, 2)]
        )
        feats = features.add_diffs(features.build_features(matches, pairs))
        rows = feats[feats["is_fixture"]]
        analysed = service._analyse(rows)
        _dump(out_dir / "predict" / f"{league}.json", {f"{r['home']}|{r['away']}": r for r in analysed})
        n_pairs += len(analysed)

    meta = {
        "status": "ok",
        "ready": True,
        "static": True,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "history_updated": data.get_meta("history_updated"),
        "fixtures_updated": data.get_meta("fixtures_updated"),
        "trained_through": model.trained_through,
        "trained_on": model.n_train,
        "leagues": [{"code": k, "name": v} for k, v in config.LEAGUES.items()],
    }
    _dump(out_dir / "meta.json", meta)
    log.info("Exported %d fixtures and %d predictor pairs to %s", len(fixtures), n_pairs, out_dir)
    return {"fixtures": len(fixtures), "predictor_pairs": n_pairs, "out_dir": str(out_dir)}
