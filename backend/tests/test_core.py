import itertools
import random

import numpy as np
import pandas as pd
import pytest

from app import features, markets, rules


def synthetic_matches(n_rounds=30, seed=1):
    """A small league where team strength is known."""
    rng = random.Random(seed)
    teams = [f"T{i}" for i in range(8)]
    strength = {t: i for i, t in enumerate(teams)}
    rows, day = [], pd.Timestamp("2023-08-01")
    for r in range(n_rounds):
        for h, a in itertools.combinations(teams, 2):
            if rng.random() < 0.5:
                h, a = a, h
            hg = max(0, int(rng.gauss(1.2 + 0.2 * strength[h] - 0.1 * strength[a], 1)))
            ag = max(0, int(rng.gauss(1.0 + 0.2 * strength[a] - 0.1 * strength[h], 1)))
            rows.append({
                "league": "E0", "season": "2324" if r < n_rounds // 2 else "2425",
                "date": (day + pd.Timedelta(days=r * 7)).strftime("%Y-%m-%d"),
                "home": h, "away": a, "hg": hg, "ag": ag,
                "result": "H" if hg > ag else "A" if ag > hg else "D",
                "hst": hg + 3, "ast": ag + 3,
                "odds_h": 2.2, "odds_d": 3.3, "odds_a": 3.2, "odds_o25": 1.9, "odds_u25": 1.9,
            })
    return pd.DataFrame(rows)


def test_features_use_only_past_matches():
    m = synthetic_matches()
    f = features.build_features(m)
    first = f.sort_values("date").groupby("home").head(1)
    # A team's first-ever appearance has no history at all.
    assert (f.loc[f.home_games.isna() | (f.home_games == 0)].shape[0]) >= 1
    # Changing a match result must not change that match's own features.
    m2 = m.copy()
    m2.loc[100, ["hg", "ag"]] = [9, 0]
    f2 = features.build_features(m2)
    cols = ["home_form", "home_avg_scored", "away_avg_conceded"]
    pd.testing.assert_frame_equal(f.loc[[100], cols], f2.loc[[100], cols])
    assert len(first) > 0


def test_fixture_rows_get_features_from_history():
    m = synthetic_matches()
    fx = pd.DataFrame([{"league": "E0", "date": "2030-01-01", "time": "15:00",
                        "home": "T7", "away": "T0"}])
    f = features.add_diffs(features.build_features(m, fx))
    row = f[f.is_fixture].iloc[0]
    assert row.home_games == features.W and row.away_games == features.W
    # The strongest team should look stronger than the weakest.
    assert row.diff_form > 0


def test_kelly():
    assert markets.kelly_fraction(0.5, 1.9) == 0.0          # negative edge
    assert markets.kelly_fraction(0.6, 2.0, fraction=1, cap=1) == pytest.approx(0.2)
    assert markets.kelly_fraction(0.9, 3.0) == 0.05          # capped
    assert markets.kelly_fraction(0.6, None) == 0.0


def test_double_chance_odds():
    assert markets.double_chance_odds(2.0, 2.0) == 1.0
    assert markets.double_chance_odds(None, 3.0) is None


def test_build_markets_probabilities_are_consistent():
    p = {"p_H": 0.5, "p_D": 0.3, "p_A": 0.2, "p_over25": 0.55, "p_btts": 0.6}
    ms = {m["market"]: m for m in markets.build_markets(p, {"odds_h": 2.1, "odds_d": 3.4, "odds_a": 4.0})}
    assert ms["Home or draw (1X)"]["prob"] == pytest.approx(0.8)
    assert ms["Under 2.5 goals"]["prob"] == pytest.approx(0.45)
    assert ms["Home win"]["edge"] == pytest.approx(0.5 * 2.1 - 1)
    assert ms["BTTS - Yes"]["odds"] is None


def test_rules_tiers_and_votes():
    strong = {"home_form": 0.8, "home_avg_scored": 2.4, "home_wins": 9, "home_losses": 1,
              "home_draws": 1, "home_avg_conceded": 0.7, "home_goal_ratio": 3.0, "home_avg_sot": 6,
              "h2h_home_wins": 3, "home_goal_diff": 18,
              "away_form": 0.3, "away_avg_scored": 0.9, "away_wins": 2, "away_losses": 7,
              "away_draws": 2, "away_avg_conceded": 1.9, "away_goal_ratio": 0.5, "away_avg_sot": 3,
              "h2h_away_wins": 0, "away_goal_diff": -10}
    r = rules.evaluate(strong)
    assert r["pick"] == "H"
    assert r["votes"]["home"] > r["votes"]["away"]
    assert r["double_chance"]["home"]["tier"] == "high"
    assert r["double_chance"]["away"]["tier"] == "avoid"
    assert rules.tier(6) == "moderate"


def test_rules_handle_missing_values():
    r = rules.evaluate({"home_form": np.nan, "away_form": 0.5})
    assert r["pick"] in {"H", "D", "A"}


def test_multiple_upcoming_fixtures_share_full_history():
    m = synthetic_matches()
    fx = pd.DataFrame([
        {"league": "E0", "date": "2030-01-01", "time": None, "home": "T7", "away": "T0"},
        {"league": "E0", "date": "2030-01-05", "time": None, "home": "T1", "away": "T7"},
        {"league": "E0", "date": "2030-01-09", "time": None, "home": "T7", "away": "T2"},
    ])
    f = features.build_features(m, fx)
    up = f[f.is_fixture]
    assert (up.home_games.fillna(0) >= features.W).all() and (up.away_games >= features.W).all()
    t7_home = up[up.home == "T7"]
    assert t7_home.home_form.nunique() == 1          # same state for both T7 home fixtures
    assert up.iloc[1].away_form == t7_home.iloc[0].home_form
