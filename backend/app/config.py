"""Central configuration for BettorsOracle."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("BO_DATA_DIR", BASE_DIR / "data"))
RAW_DIR = DATA_DIR / "raw"
DB_PATH = Path(os.environ.get("BO_DB_PATH", DATA_DIR / "bettorsoracle.db"))
MODEL_PATH = DATA_DIR / "model.pkl"

# football-data.co.uk league codes -> display names
LEAGUES: dict[str, str] = {
    "E0": "Premier League",
    "E1": "Championship",
    "SP1": "La Liga",
    "D1": "Bundesliga",
    "I1": "Serie A",
    "F1": "Ligue 1",
}

HISTORY_URL = "https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"
FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"

# How many past seasons (including the current one) to ingest.
N_SEASONS = int(os.environ.get("BO_N_SEASONS", "6"))

# Matches of history used for each team's form window (the Excel model used 11).
FORM_WINDOW = 11
# Head-to-head window.
H2H_WINDOW = 6

# "Top bet of the day" threshold from the MoSCoW spec.
TOP_BET_MIN_PROB = 0.70

# Staking defaults (fractional Kelly with a hard cap per bet).
KELLY_FRACTION = 0.25
MAX_STAKE_PCT = 0.05


def season_code(start_year: int) -> str:
    """2025 -> '2526'."""
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def current_season_start(today: date | None = None) -> int:
    today = today or date.today()
    # European seasons start in August.
    return today.year if today.month >= 7 else today.year - 1


def recent_seasons(n: int = N_SEASONS, today: date | None = None) -> list[str]:
    start = current_season_start(today)
    return [season_code(y) for y in range(start - n + 1, start + 1)]
