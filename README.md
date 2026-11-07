# BettorsOracle

**Live app:** https://emmanuelebube13.github.io/BettorsOracle/ (predictions refresh every 6 hours)

## Overview

BettorsOracle is a machine learning–driven web application for predicting football match outcomes using statistical modeling and historical performance data.

The project aims to research, design, and deploy predictive systems capable of estimating match probabilities (win/draw/loss and other betting markets) through data-driven methodologies.

This repository represents an active research and development effort. The system is currently under continuous improvement and structural refinement.

---

## Project Status

Development Status: **MVP running** (November 2026)

What works today:

* Automated data ingestion from football-data.co.uk (results + bookmaker odds for 6 leagues over the last 6 seasons, plus upcoming fixtures), stored in SQLite
* The original Excel model ported to Python ("Oracle rules": metric votes + Double Chance confidence tiers)
* A logistic-regression model (1X2, Over 2.5, BTTS) trained on the same features
* Walk-forward backtest against bookmaker odds
* FastAPI backend + React frontend: Top bets (≥70%), Fixtures, Head-to-head predictor, Model performance, Bankroll tracker with quarter-Kelly staking and account-growth chart

### Honest backtest results

Each season is predicted by a model trained only on earlier seasons:

| Season | Model accuracy | Market accuracy | Excel rules | ≥70% picks hit rate | ≥70% picks ROI |
|---|---|---|---|---|---|
| 2023/24 | 50.4% | 53.3% | 49.6% | 77.0% | −3.8% |
| 2024/25 | 50.8% | 52.4% | 48.6% | 76.5% | −4.7% |
| 2025/26 | 48.9% | 51.7% | 46.6% | 76.4% | −5.2% |

The model is well calibrated but does **not** beat the bookmakers yet. Next steps to close that gap: richer data (xG, lineups, injuries), Poisson/Dixon-Coles goal models, and a league-strength adjustment for promoted teams.

---

## Objectives

1. Build reliable predictive models for football outcomes
2. Implement automated data ingestion pipelines
3. Evaluate model performance using statistical validation metrics
4. Create a scalable backend for model inference
5. Develop a web-based interface for prediction visualization
6. Continuously improve prediction accuracy through research and iteration

---

## System Architecture (Planned)

Data Layer

* Historical match datasets
* League performance metrics
* Team statistics
* External contextual features

Processing Layer

* Data cleaning and normalization
* Feature engineering
* Model training and evaluation

Modeling Layer

* Classification models (e.g., Logistic Regression, Random Forest, Gradient Boosting, Neural Networks)
* Ensemble methods
* Cross-validation strategies
* Performance tracking

Application Layer

* Backend API (planned)
* Model inference engine
* Web application frontend

Deployment Layer (Planned)

* Containerization (Docker)
* Cloud hosting
* CI/CD pipeline

---

## Repository Structure

```
backend/              FastAPI app (Python 3.12)
  app/config.py       leagues, seasons, thresholds
  app/data.py         download + SQLite storage
  app/features.py     pre-match team metrics (ported from the Excel sheets)
  app/rules.py        original Excel decision rules
  app/model.py        logistic-regression model
  app/markets.py      markets, edge, Kelly staking
  app/backtest.py     walk-forward evaluation
  app/bankroll.py     bet log + bankroll growth
  app/main.py         REST API (also serves the built frontend)
  tests/              pytest suite (offline, synthetic data)
frontend/             React + TypeScript (Vite) UI
Dockerfile            single-container build (API + UI)
New betting model (AutoRecovered).xlsm   original Excel model (reference)
MoSCoW.xlsx           feature prioritisation
workplan.docx         project plan
```

---

## Running Locally

Prerequisites: Python 3.12, Node 20+.

```bash
git clone https://github.com/emmanuelebube13/BettorsOracle.git
cd BettorsOracle/backend
python -m venv .venv
.venv\Scripts\activate              # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m app.cli refresh           # download data, train, backtest (~1 min)
uvicorn app.main:app --reload --port 8000

# second terminal
cd frontend
npm install
npm run dev                         # http://localhost:5173 (proxies /api to :8000)
```

* Tests: `cd backend && pytest`
* Single process: `cd frontend && npm run build`, then start uvicorn. The UI is served at http://localhost:8000
* Docker: `docker build -t bettorsoracle . && docker run -p 8000:8000 -v bo-data:/data bettorsoracle`
* Environment variables: `BO_ADMIN_TOKEN` (protects `POST /api/admin/refresh`), `BO_DATA_DIR`, `BO_CORS_ORIGINS`, `BO_N_SEASONS`

---

## Live Deployment

**https://emmanuelebube13.github.io/BettorsOracle/**

The live site runs entirely on GitHub, with no server to maintain:

* `.github/workflows/deploy.yml` runs on every push to `main`, every 6 hours, and on demand (Actions tab → *Run workflow*)
* Each run tests the backend, downloads the latest results and fixtures, retrains the model, re-runs the backtest, exports predictions as JSON (`python -m app.cli export`), builds the React app in static mode (`npm run build:static`) and publishes it to GitHub Pages
* In the hosted version the bankroll tracker is stored in each visitor's browser (localStorage). Run the FastAPI app locally or in Docker for a server-side bet log

Note: GitHub pauses scheduled workflows after 60 days without repository activity; re-enable it from the Actions tab if that happens.

---

## Model Development Philosophy

This project follows:

* Empirical validation over assumptions
* Backtesting before deployment
* Strict separation of training and evaluation datasets
* Continuous performance monitoring
* Conservative interpretation of predictive probabilities

No model is considered valid without statistical validation.

---

## Roadmap

Phase 1 – Data Structuring

* Clean historical datasets
* Normalize team performance metrics
* Build reusable data ingestion pipeline

Phase 2 – Model Optimization

* Hyperparameter tuning
* Cross-league generalization testing
* Reduce overfitting

Phase 3 – Backend API

* RESTful prediction endpoints
* Authentication system
* Usage logging

Phase 4 – Frontend Application

* User interface for match selection
* Prediction visualization
* Probability breakdown

Phase 5 – Deployment

* Docker containerization
* Cloud infrastructure
* Domain and production rollout

---

## Contribution Policy

This is currently a private research-driven project.

External contributions are not automatically accepted.

If collaboration is desired:

* Submit a detailed proposal via email or issue request
* Clearly define the technical value you intend to add
* Do not submit pull requests without prior discussion

Unauthorized forks or derivative commercial implementations may violate licensing terms.

---

## Disclaimer

BettorsOracle is a research and analytical project.

The predictions generated by this system are probabilistic estimates based on historical data and statistical modeling. They do not guarantee outcomes.

Users assume full responsibility for any financial decisions made based on model outputs.

The authors are not liable for financial losses or betting outcomes.

---

## Intellectual Property Notice

All code, models, data structures, methodologies, documentation, and associated materials in this repository are the intellectual property of the project owner unless otherwise stated.

Reverse engineering, replication of modeling strategies, redistribution, or commercial use without explicit written authorization is strictly prohibited.

---

## License

Proprietary License – All Rights Reserved

Copyright © 2026 Emmanuel Mbachu. All Rights Reserved.

This software and associated documentation files are proprietary and confidential.

Permission is NOT granted to:

* Distribute
* Sublicense
* Sell
* Create derivative works

Without prior written consent from the copyright holder.

Unauthorized use, reproduction, or distribution may result in legal action.


