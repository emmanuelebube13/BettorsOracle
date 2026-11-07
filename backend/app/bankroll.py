"""Bet log + bankroll growth (MoSCoW: money management, account growth analysis)."""
from __future__ import annotations

from datetime import datetime, timezone

from . import data

DEFAULT_BANKROLL = 1000.0
STATUSES = {"pending", "won", "lost", "void"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_starting_bankroll() -> float:
    v = data.get_meta("starting_bankroll")
    return float(v) if v else DEFAULT_BANKROLL


def set_starting_bankroll(amount: float) -> None:
    with data.connect() as conn:
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('starting_bankroll', ?)",
                     (str(amount),))


def list_bets() -> list[dict]:
    with data.connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM bets ORDER BY placed_at DESC, id DESC")]


def add_bet(match: str, market: str, odds: float, stake: float) -> dict:
    with data.connect() as conn:
        cur = conn.execute(
            "INSERT INTO bets (placed_at, match, market, odds, stake) VALUES (?, ?, ?, ?, ?)",
            (_now(), match, market, odds, stake),
        )
        return dict(conn.execute("SELECT * FROM bets WHERE id = ?", (cur.lastrowid,)).fetchone())


def settle(bet_id: int, status: str) -> dict | None:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {sorted(STATUSES)}")
    with data.connect() as conn:
        conn.execute("UPDATE bets SET status = ?, settled_at = ? WHERE id = ?",
                     (status, None if status == "pending" else _now(), bet_id))
        row = conn.execute("SELECT * FROM bets WHERE id = ?", (bet_id,)).fetchone()
        return dict(row) if row else None


def delete(bet_id: int) -> bool:
    with data.connect() as conn:
        return conn.execute("DELETE FROM bets WHERE id = ?", (bet_id,)).rowcount > 0


def _pnl(bet: dict) -> float:
    if bet["status"] == "won":
        return bet["stake"] * (bet["odds"] - 1)
    if bet["status"] == "lost":
        return -bet["stake"]
    return 0.0


def summary() -> dict:
    start = get_starting_bankroll()
    bets = list_bets()
    settled = sorted((b for b in bets if b["status"] in ("won", "lost", "void")),
                     key=lambda b: (b["settled_at"] or b["placed_at"], b["id"]))
    balance = start
    series = [{"t": None, "bankroll": round(start, 2)}]
    for b in settled:
        balance += _pnl(b)
        series.append({"t": b["settled_at"], "bankroll": round(balance, 2)})
    pending = [b for b in bets if b["status"] == "pending"]
    staked = sum(b["stake"] for b in settled if b["status"] != "void")
    won = sum(1 for b in settled if b["status"] == "won")
    decided = sum(1 for b in settled if b["status"] in ("won", "lost"))
    peak, max_dd = start, 0.0
    for p in series:
        peak = max(peak, p["bankroll"])
        max_dd = max(max_dd, (peak - p["bankroll"]) / peak if peak else 0)
    return {
        "starting_bankroll": start,
        "bankroll": round(balance, 2),
        "available": round(balance - sum(b["stake"] for b in pending), 2),
        "profit": round(balance - start, 2),
        "roi": round((balance - start) / staked, 4) if staked else None,
        "hit_rate": round(won / decided, 4) if decided else None,
        "max_drawdown": round(max_dd, 4),
        "pending": len(pending),
        "settled": len(settled),
        "series": series,
    }
