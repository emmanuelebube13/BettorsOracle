"""Statistical model: regularised logistic regressions on the Excel-derived features.

Three independent heads:
  * result  - multinomial H / D / A
  * over25  - total goals > 2.5
  * btts    - both teams to score
Bookmaker odds are deliberately NOT used as inputs, so the model is an independent
opinion that can be compared with (and bet against) the market.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config, features

RESULT_CLASSES = ["H", "D", "A"]


def _pipe() -> object:
    return make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(C=0.05, max_iter=2000),
    )


def targets(df: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        "result": df["result"],
        "over25": ((df["hg"] + df["ag"]) > 2.5).astype(int),
        "btts": ((df["hg"] > 0) & (df["ag"] > 0)).astype(int),
    }


@dataclass
class OracleModel:
    cols: list[str] = field(default_factory=features.feature_columns)
    heads: dict = field(default_factory=dict)
    n_train: int = 0
    trained_through: str | None = None

    def fit(self, df: pd.DataFrame) -> "OracleModel":
        df = df[features.usable(df) & df["result"].isin(RESULT_CLASSES)]
        X = df[self.cols]
        for name, y in targets(df).items():
            self.heads[name] = _pipe().fit(X, y)
        self.n_train = len(df)
        self.trained_through = str(df["date"].max()) if len(df) else None
        return self

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        X = df[self.cols]
        res = self.heads["result"]
        proba = res.predict_proba(X)
        classes = list(res.classes_)
        out = pd.DataFrame(index=df.index)
        for c in RESULT_CLASSES:
            out[f"p_{c}"] = proba[:, classes.index(c)]
        out["p_over25"] = self.heads["over25"].predict_proba(X)[:, 1]
        out["p_btts"] = self.heads["btts"].predict_proba(X)[:, 1]
        return out

    def save(self, path=config.MODEL_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path=config.MODEL_PATH) -> "OracleModel | None":
        if not path.exists():
            return None
        with open(path, "rb") as f:
            return pickle.load(f)


def implied_probs(oh, od, oa) -> tuple[float, float, float] | None:
    """Market probabilities with the bookmaker margin removed."""
    try:
        inv = np.array([1 / oh, 1 / od, 1 / oa], dtype=float)
    except (TypeError, ZeroDivisionError):
        return None
    if not np.all(np.isfinite(inv)) or np.any(inv <= 0):
        return None
    inv /= inv.sum()
    return tuple(float(x) for x in inv)
