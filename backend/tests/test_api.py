"""End-to-end API test on a temporary database with synthetic data (no network)."""
import importlib

import pytest
from fastapi.testclient import TestClient

from tests.test_core import synthetic_matches


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("bo")
    mp = pytest.MonkeyPatch()
    from app import config
    mp.setattr(config, "DB_PATH", tmp / "test.db")
    mp.setattr(config, "MODEL_PATH", tmp / "model.pkl")
    mp.setattr(config, "DATA_DIR", tmp)
    from app import data, service
    mp.setattr(service, "BACKTEST_PATH", tmp / "backtest.json")
    service._state.update(feats=None, model=None)

    m = synthetic_matches(n_rounds=40)
    cols = list(m.columns)
    with data.connect() as conn:
        conn.executemany(f"INSERT INTO matches ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                         m.values.tolist())
        conn.execute("INSERT INTO fixtures (league, date, time, home, away, odds_h, odds_d, odds_a, "
                     "odds_o25, odds_u25) VALUES ('E0','2030-01-01','15:00','T7','T0',1.3,5.0,9.0,1.6,2.3)")
    service.refresh(fetch=False, run_backtest=False)

    from app import main
    importlib.reload(main)
    yield TestClient(main.app)
    service._state.update(feats=None, model=None)
    mp.undo()


def test_health(client):
    r = client.get("/api/health").json()
    assert r["status"] == "ok" and r["ready"] is True


def test_fixtures_and_top_bets(client):
    fx = client.get("/api/fixtures").json()
    assert len(fx) == 1
    f = fx[0]
    assert abs(f["probs"]["home"] + f["probs"]["draw"] + f["probs"]["away"] - 1) < 1e-3
    assert f["probs"]["home"] > f["probs"]["away"]   # strongest vs weakest
    assert {m["market"] for m in f["markets"]} >= {"Home win", "Over 2.5 goals"}
    tb = client.get("/api/top-bets", params={"min_prob": 0.6}).json()
    assert all(b["prob"] >= 0.6 for b in tb)


def test_predict(client):
    r = client.get("/api/predict", params={"home": "T7", "away": "T0"})
    assert r.status_code == 200
    assert client.get("/api/predict", params={"home": "X", "away": "T0"}).status_code == 404


def test_bankroll_flow(client):
    client.put("/api/bankroll", json={"amount": 500})
    b = client.post("/api/bets", json={"match": "T7 v T0", "market": "Home win", "odds": 2.0, "stake": 50})
    assert b.status_code == 201
    bid = b.json()["id"]
    assert client.get("/api/bankroll").json()["available"] == 450
    client.patch(f"/api/bets/{bid}", json={"status": "won"})
    s = client.get("/api/bankroll").json()
    assert s["bankroll"] == 550 and s["profit"] == 50 and s["hit_rate"] == 1
    assert client.patch(f"/api/bets/{bid}", json={"status": "nope"}).status_code == 400
    assert client.delete(f"/api/bets/{bid}").status_code == 204


def test_stake(client):
    r = client.get("/api/stake", params={"prob": 0.6, "odds": 2.0, "bankroll_amount": 1000}).json()
    assert r["stake"] == 50.0  # 0.25 Kelly of 20% = 5%, at the 5% cap
