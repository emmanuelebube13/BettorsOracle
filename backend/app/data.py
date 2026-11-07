"""Data ingestion (football-data.co.uk) and SQLite storage."""
from __future__ import annotations

import io
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import pandas as pd
import requests

from . import config

log = logging.getLogger(__name__)

MATCH_COLS = {
    "Div": "league",
    "Date": "date",
    "HomeTeam": "home",
    "AwayTeam": "away",
    "FTHG": "hg",
    "FTAG": "ag",
    "FTR": "result",
    "HST": "hst",
    "AST": "ast",
    # Average market odds (fall back to Bet365 when missing).
    "AvgH": "odds_h",
    "AvgD": "odds_d",
    "AvgA": "odds_a",
    "Avg>2.5": "odds_o25",
    "Avg<2.5": "odds_u25",
}
FALLBACK_ODDS = {
    "odds_h": "B365H",
    "odds_d": "B365D",
    "odds_a": "B365A",
    "odds_o25": "B365>2.5",
    "odds_u25": "B365<2.5",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    league TEXT, season TEXT, date TEXT, home TEXT, away TEXT,
    hg INTEGER, ag INTEGER, result TEXT, hst REAL, ast REAL,
    odds_h REAL, odds_d REAL, odds_a REAL, odds_o25 REAL, odds_u25 REAL,
    PRIMARY KEY (league, date, home, away)
);
CREATE TABLE IF NOT EXISTS fixtures (
    league TEXT, date TEXT, time TEXT, home TEXT, away TEXT,
    odds_h REAL, odds_d REAL, odds_a REAL, odds_o25 REAL, odds_u25 REAL,
    PRIMARY KEY (league, date, home, away)
);
CREATE TABLE IF NOT EXISTS bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    placed_at TEXT NOT NULL,
    match TEXT NOT NULL,
    market TEXT NOT NULL,
    odds REAL NOT NULL,
    stake REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | won | lost | void
    settled_at TEXT
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


@contextmanager
def connect():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _fetch_csv(url: str) -> pd.DataFrame | None:
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": "BettorsOracle/0.1"})
    except requests.RequestException as exc:
        log.warning("Failed to fetch %s: %s", url, exc)
        return None
    if resp.status_code != 200 or not resp.content.strip():
        log.warning("No data at %s (HTTP %s)", url, resp.status_code)
        return None
    text = resp.content.decode("utf-8-sig", errors="replace")
    return pd.read_csv(io.StringIO(text), on_bad_lines="skip")


def normalise(df: pd.DataFrame, with_results: bool = True) -> pd.DataFrame:
    """Map a raw football-data.co.uk frame onto our column names."""
    df = df.dropna(subset=["HomeTeam", "AwayTeam", "Date"]).copy()
    out = pd.DataFrame()
    for src, dst in MATCH_COLS.items():
        if src in df.columns:
            out[dst] = df[src]
        else:
            out[dst] = None
    for dst, src in FALLBACK_ODDS.items():
        if src in df.columns:
            out[dst] = out[dst].fillna(df[src]) if out[dst].notna().any() else df[src]
    if "Time" in df.columns:
        out["time"] = df["Time"]
    out["date"] = pd.to_datetime(out["date"], dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d")
    out = out.dropna(subset=["date"])
    for c in ("home", "away"):
        out[c] = out[c].astype(str).str.strip()
    if with_results:
        out = out.dropna(subset=["hg", "ag"])
        out["hg"] = out["hg"].astype(int)
        out["ag"] = out["ag"].astype(int)
    return out


def ingest_history(leagues=None, seasons=None) -> int:
    leagues = leagues or list(config.LEAGUES)
    seasons = seasons or config.recent_seasons()
    total = 0
    with connect() as conn:
        for season in seasons:
            for league in leagues:
                raw = _fetch_csv(config.HISTORY_URL.format(season=season, league=league))
                if raw is None:
                    continue
                df = normalise(raw)
                df["season"] = season
                cols = ["league", "season", "date", "home", "away", "hg", "ag", "result",
                        "hst", "ast", "odds_h", "odds_d", "odds_a", "odds_o25", "odds_u25"]
                rows = df[cols].astype(object).where(df[cols].notna(), None).values.tolist()
                conn.executemany(
                    f"INSERT OR REPLACE INTO matches ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                    rows,
                )
                total += len(rows)
                log.info("Ingested %s %s: %d matches", league, season, len(rows))
        _set_meta(conn, "history_updated", _now())
    return total


def ingest_fixtures() -> int:
    raw = _fetch_csv(config.FIXTURES_URL)
    if raw is None:
        return 0
    raw = raw[raw["Div"].isin(config.LEAGUES)]
    df = normalise(raw, with_results=False)
    if "time" not in df:
        df["time"] = None
    cols = ["league", "date", "time", "home", "away",
            "odds_h", "odds_d", "odds_a", "odds_o25", "odds_u25"]
    rows = df[cols].astype(object).where(df[cols].notna(), None).values.tolist()
    with connect() as conn:
        conn.execute("DELETE FROM fixtures")
        conn.executemany(
            f"INSERT OR REPLACE INTO fixtures ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            rows,
        )
        _set_meta(conn, "fixtures_updated", _now())
    return len(rows)


def load_matches(league: str | None = None) -> pd.DataFrame:
    with connect() as conn:
        q = "SELECT * FROM matches"
        params: tuple = ()
        if league:
            q += " WHERE league = ?"
            params = (league,)
        df = pd.read_sql_query(q + " ORDER BY date", conn, params=params)
    return df


def load_fixtures() -> pd.DataFrame:
    with connect() as conn:
        return pd.read_sql_query("SELECT * FROM fixtures ORDER BY date, time", conn)


def get_meta(key: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def _set_meta(conn, key: str, value: str) -> None:
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
