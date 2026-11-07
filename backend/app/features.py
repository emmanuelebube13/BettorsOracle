"""Pre-match team metrics, ported from the original Excel model.

The spreadsheet computed, for each side, over its last 11 matches:
  form index (weighted points), average scored / conceded, wins / draws / losses,
  total goals, goal ratio, goal difference, BTTS rate and head-to-head wins.
Here every metric for a match is computed strictly from matches played *before*
it, so the same code drives training, backtesting and live predictions without
leaking the result.
"""
from __future__ import annotations

from collections import defaultdict, deque

import numpy as np
import pandas as pd

from . import config

W = config.FORM_WINDOW
MIN_GAMES = 5
# Most recent game gets the highest weight (the sheet used 10, 9, 8, ...).
_WEIGHTS = np.arange(1, W + 1, dtype=float)

TEAM_METRICS = [
    "form", "avg_scored", "avg_conceded", "wins", "draws", "losses",
    "goal_ratio", "goal_diff", "btts_rate", "over25_rate", "avg_sot", "venue_ppg",
]


def _weighted_form(points: np.ndarray) -> float:
    w = _WEIGHTS[-len(points):]
    mask = ~np.isnan(points)
    if mask.sum() == 0:
        return np.nan
    return float(np.sum(points[mask] * w[mask]) / (3 * np.sum(w[mask])))


def _long_format(df: pd.DataFrame) -> pd.DataFrame:
    """One row per team per match."""
    base = df[["mid", "league", "date", "home", "away", "hg", "ag", "hst", "ast"]]
    # Form is tracked per (team, league): a promoted side's Championship results
    # say little about how it will do in the Premier League.
    home = pd.DataFrame({
        "mid": base.mid, "date": base.date, "team": base.home + "|" + base.league, "venue": "H",
        "gf": base.hg, "ga": base.ag, "sot": base.hst,
    })
    away = pd.DataFrame({
        "mid": base.mid, "date": base.date, "team": base.away + "|" + base.league, "venue": "A",
        "gf": base.ag, "ga": base.hg, "sot": base.ast,
    })
    long = pd.concat([home, away], ignore_index=True)
    long = long.sort_values(["date", "mid", "venue"], kind="stable").reset_index(drop=True)
    gf, ga = long.gf.astype(float), long.ga.astype(float)
    long["pts"] = np.where(gf.isna(), np.nan, np.where(gf > ga, 3, np.where(gf == ga, 1, 0)))
    long["win"] = np.where(gf.isna(), np.nan, (gf > ga).astype(float))
    long["draw"] = np.where(gf.isna(), np.nan, (gf == ga).astype(float))
    long["loss"] = np.where(gf.isna(), np.nan, (gf < ga).astype(float))
    long["btts"] = np.where(gf.isna(), np.nan, ((gf > 0) & (ga > 0)).astype(float))
    long["o25"] = np.where(gf.isna(), np.nan, ((gf + ga) > 2.5).astype(float))
    long["gf"], long["ga"] = gf, ga
    long["sot"] = long.sot.astype(float)
    return long


def _rolling_team_stats(long: pd.DataFrame, shift: bool = True) -> pd.DataFrame:
    """Rolling metrics per team row.

    shift=True  -> stats *before* each match (training / backtest rows).
    shift=False -> stats *after* each match (a team's state going into its next game).
    """
    g = long.groupby("team", sort=False)
    sh = (lambda s: s.shift(1)) if shift else (lambda s: s)

    def roll(col, fn="sum", window=W, by=g):
        return by[col].transform(
            lambda s: getattr(sh(s).rolling(window, min_periods=1), fn)()
        )

    out = pd.DataFrame({"mid": long.mid, "team": long.team, "venue": long.venue})
    out["games"] = g["pts"].transform(lambda s: sh(s).rolling(W, min_periods=1).count())
    out["form"] = g["pts"].transform(
        lambda s: sh(s).rolling(W, min_periods=1).apply(_weighted_form, raw=True)
    )
    gf_sum, ga_sum = roll("gf"), roll("ga")
    out["avg_scored"] = roll("gf", "mean")
    out["avg_conceded"] = roll("ga", "mean")
    out["wins"] = roll("win")
    out["draws"] = roll("draw")
    out["losses"] = roll("loss")
    out["goal_ratio"] = gf_sum / ga_sum.replace(0, np.nan)
    out["goal_ratio"] = out["goal_ratio"].fillna(gf_sum).clip(upper=5)
    out["goal_diff"] = gf_sum - ga_sum
    out["btts_rate"] = roll("btts", "mean")
    out["over25_rate"] = roll("o25", "mean")
    out["avg_sot"] = roll("sot", "mean")
    gv = long.groupby(["team", "venue"], sort=False)
    out["venue_ppg"] = gv["pts"].transform(lambda s: sh(s).rolling(5, min_periods=1).mean())
    return out


def _h2h(df: pd.DataFrame) -> pd.DataFrame:
    """Wins for each side in their previous meetings (any venue)."""
    hist: dict[frozenset, deque] = defaultdict(lambda: deque(maxlen=config.H2H_WINDOW))
    rows = []
    for r in df.itertuples(index=False):
        key = frozenset((r.home, r.away))
        past = hist[key]
        rows.append((
            r.mid,
            sum(1 for w in past if w == r.home),
            sum(1 for w in past if w == r.away),
            len(past),
        ))
        if not (pd.isna(r.hg) or pd.isna(r.ag)):
            winner = r.home if r.hg > r.ag else r.away if r.ag > r.hg else None
            past.append(winner)
    return pd.DataFrame(rows, columns=["mid", "h2h_home_wins", "h2h_away_wins", "h2h_games"])


def build_features(matches: pd.DataFrame, fixtures: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return one row per match/fixture with home_* / away_* metrics.

    Fixture rows (no score yet) are appended after history so their features are
    computed from everything played so far. Rows are returned with `is_fixture`.
    """
    hist = matches.copy()
    hist["is_fixture"] = False
    frames = [hist]
    if fixtures is not None and len(fixtures):
        fx = fixtures.copy()
        fx["is_fixture"] = True
        for c in ("hg", "ag", "hst", "ast", "result"):
            fx[c] = np.nan
        frames.append(fx)
    df = pd.concat(frames, ignore_index=True)
    df = df.sort_values(["is_fixture", "date"], kind="stable").reset_index(drop=True)
    df["mid"] = np.arange(len(df))

    long = _long_format(df)
    played = long[long.gf.notna()]
    stats = _rolling_team_stats(played, shift=True)

    upcoming = long[long.gf.isna()][["mid", "team", "venue"]]
    if len(upcoming):
        # Every fixture sees the team's state after its latest played match, so a
        # team with several upcoming games doesn't have its form window diluted.
        post = _rolling_team_stats(played, shift=False)
        general = post.groupby("team").tail(1).drop(columns=["mid", "venue", "venue_ppg"])
        venue = post.groupby(["team", "venue"]).tail(1)[["team", "venue", "venue_ppg"]]
        fx_stats = upcoming.merge(general, on="team", how="left").merge(venue, on=["team", "venue"], how="left")
        stats = pd.concat([stats, fx_stats], ignore_index=True)

    metric_cols = ["games"] + TEAM_METRICS
    home = stats[stats.venue == "H"].set_index("mid")[metric_cols].add_prefix("home_")
    away = stats[stats.venue == "A"].set_index("mid")[metric_cols].add_prefix("away_")
    out = df.set_index("mid").join(home).join(away).join(_h2h(df).set_index("mid"))
    return out.reset_index()


def feature_columns() -> list[str]:
    cols = []
    for m in TEAM_METRICS:
        cols += [f"home_{m}", f"away_{m}", f"diff_{m}"]
    cols += ["h2h_home_wins", "h2h_away_wins"]
    return cols


def add_diffs(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for m in TEAM_METRICS:
        df[f"diff_{m}"] = df[f"home_{m}"] - df[f"away_{m}"]
    return df


def usable(df: pd.DataFrame) -> pd.Series:
    """Rows where both teams have enough history to be judged."""
    return (df["home_games"] >= MIN_GAMES) & (df["away_games"] >= MIN_GAMES)
