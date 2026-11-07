"""BettorsOracle API."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import bankroll, config, data, service
from .markets import kelly_fraction

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(title="BettorsOracle API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("BO_CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

ADMIN_TOKEN = os.environ.get("BO_ADMIN_TOKEN")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "ready": service.ready(),
        "history_updated": data.get_meta("history_updated"),
        "fixtures_updated": data.get_meta("fixtures_updated"),
    }


@app.get("/api/leagues")
def leagues():
    return [{"code": k, "name": v} for k, v in config.LEAGUES.items()]


@app.get("/api/teams")
def teams():
    return service.teams()


@app.get("/api/fixtures")
def fixtures(league: str | None = None):
    return service.fixtures(league)


@app.get("/api/top-bets")
def top_bets(min_prob: float = Query(config.TOP_BET_MIN_PROB, ge=0.5, le=0.99), league: str | None = None):
    return service.top_bets(min_prob, league)


@app.get("/api/predict")
def predict(home: str, away: str):
    if home == away:
        raise HTTPException(400, "Pick two different teams.")
    res = service.predict_matchup(home, away)
    if res is None:
        raise HTTPException(404, "Unknown team(s).")
    return res


@app.get("/api/backtest")
def backtest():
    rep = service.backtest_report()
    if rep is None:
        raise HTTPException(404, "No backtest yet - run a data refresh.")
    return rep


@app.post("/api/admin/refresh")
def refresh(x_admin_token: str | None = Header(None)):
    if ADMIN_TOKEN and x_admin_token != ADMIN_TOKEN:
        raise HTTPException(401, "Bad admin token.")
    return service.refresh()


# ---- Money management -------------------------------------------------------

@app.get("/api/stake")
def stake(prob: float = Query(..., gt=0, lt=1), odds: float = Query(..., gt=1),
          bankroll_amount: float | None = None,
          fraction: float = Query(config.KELLY_FRACTION, gt=0, le=1),
          cap: float = Query(config.MAX_STAKE_PCT, gt=0, le=1)):
    pct = kelly_fraction(prob, odds, fraction, cap)
    bank = bankroll_amount if bankroll_amount is not None else bankroll.summary()["available"]
    return {"stake_pct": pct, "stake": round(bank * pct, 2), "bankroll": bank,
            "edge": round(prob * odds - 1, 4)}


class BetIn(BaseModel):
    match: str = Field(min_length=1, max_length=200)
    market: str = Field(min_length=1, max_length=100)
    odds: float = Field(gt=1)
    stake: float = Field(gt=0)


class SettleIn(BaseModel):
    status: str


class BankrollIn(BaseModel):
    amount: float = Field(gt=0)


@app.get("/api/bankroll")
def get_bankroll():
    return {**bankroll.summary(), "bets": bankroll.list_bets()}


@app.put("/api/bankroll")
def put_bankroll(body: BankrollIn):
    bankroll.set_starting_bankroll(body.amount)
    return bankroll.summary()


@app.post("/api/bets", status_code=201)
def add_bet(body: BetIn):
    return bankroll.add_bet(body.match, body.market, body.odds, body.stake)


@app.patch("/api/bets/{bet_id}")
def settle_bet(bet_id: int, body: SettleIn):
    try:
        bet = bankroll.settle(bet_id, body.status)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if bet is None:
        raise HTTPException(404, "Bet not found.")
    return bet


@app.delete("/api/bets/{bet_id}", status_code=204)
def delete_bet(bet_id: int):
    if not bankroll.delete(bet_id):
        raise HTTPException(404, "Bet not found.")


# ---- Serve the built React app (production) ---------------------------------

_DIST = Path(os.environ.get("BO_FRONTEND_DIST", config.BASE_DIR.parent / "frontend" / "dist"))
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = _DIST / path
        return FileResponse(f if path and f.is_file() else _DIST / "index.html")
