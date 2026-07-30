"""Automated Market Intelligence Analyst - prediction engine.

A single Flask process that, on an APScheduler interval:

  1. ingests market (yfinance), macro (FRED) and social (Reddit) data,
  2. engineers a momentum / volatility / macro / sentiment feature panel,
  3. trains an XGBoost + LSTM ensemble with time-aware cross-validation,
  4. backtests the resulting signal against buy-and-hold,
  5. drafts a PDF memo with Gemini + ReportLab, and
  6. persists the run to SQLite so ``GET /api/latest`` can serve it.

Every stage that depends on a third-party credential degrades explicitly: the
run still completes, and the record it writes says which source was actually
used. Nothing is synthesised and presented as observed data.
"""

import datetime
import json
import logging
import os
import sqlite3
import tempfile

import matplotlib

matplotlib.use("Agg")  # no display on the deployment target

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import praw
import xgboost as xgb
import yfinance as yf
import google.generativeai as genai
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify
from fredapi import Fred
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sklearn.metrics import accuracy_score
from sklearn.model_selection import TimeSeriesSplit

# tensorflow, shap and nltk are imported inside the functions that need them.
# They are heavy (or need a corpus download), and the rest of the module -
# features, backtest, persistence, API - has to stay importable without them.

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
LOG = logging.getLogger("market_engine")

app = Flask(__name__)

# ==========================================
# Configuration
# ==========================================
TICKERS = ("^GSPC", "^IXIC", "GC=F", "CL=F")
MACRO_SERIES = {
    "CPI": "CPIAUCSL",
    "Unemployment": "UNRATE",
    "FedFunds": "FEDFUNDS",
    "GDP": "A191RL1Q225SBEA",
    "ConsumerSentiment": "UMCSENT",
}

PRICE_COL = "^GSPC_Close"
TARGET_COL = "Target"
HORIZON = 7  # sessions ahead the model calls
LOOKBACK_DAYS = 730  # ~2 years of history
UP_THRESHOLD = 0.55
DOWN_THRESHOLD = 0.45
SESSIONS_PER_YEAR = 252
PERIODS_PER_YEAR = SESSIONS_PER_YEAR / HORIZON  # non-overlapping 7-session holds

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(_HERE, "market_intelligence.db")
DEFAULT_REPORT_PATH = os.path.join(_HERE, "weekly_report.pdf")


def db_path():
    """SQLite location. Note that on ephemeral hosts (Render free tier) this
    disk does not survive a redeploy - point MARKET_DB_PATH at a mounted volume
    to keep prediction history."""
    return os.environ.get("MARKET_DB_PATH", DEFAULT_DB_PATH)


def report_path():
    return os.environ.get("MARKET_REPORT_PATH", DEFAULT_REPORT_PATH)


def _default_if_none(value, env_var, fallback):
    """Explicit argument, else environment, else the built-in default."""
    if value is not None:
        return int(value)
    return int(os.environ.get(env_var, fallback))


def sentiment_subreddits():
    raw = os.environ.get("REDDIT_SUBREDDITS", "investing,stocks")
    return tuple(name.strip() for name in raw.split(",") if name.strip())


# ==========================================
# STEP 0: Persistence (SQLite)
# ==========================================
SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at        TEXT NOT NULL,
    as_of_date          TEXT NOT NULL,
    direction           TEXT NOT NULL,
    probability         REAL NOT NULL,
    confidence          REAL NOT NULL,
    cv_accuracy         REAL,
    test_accuracy       REAL,
    top_features        TEXT,
    attribution_source  TEXT,
    model               TEXT,
    backtest            TEXT,
    data_sources        TEXT,
    report_text         TEXT,
    report_source       TEXT,
    report_path         TEXT
);
CREATE INDEX IF NOT EXISTS idx_predictions_generated_at
    ON predictions (generated_at DESC);
"""


def _connect():
    conn = sqlite3.connect(db_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.executescript(SCHEMA)


def save_prediction(record):
    """Persist one pipeline run. Returns the new row id."""
    row = {
        "generated_at": record["generated_at"],
        "as_of_date": record["as_of_date"],
        "direction": record["prediction"],
        "probability": float(record["probability"]),
        "confidence": float(record["confidence"]),
        "cv_accuracy": record.get("model", {}).get("cv_accuracy"),
        "test_accuracy": record.get("model", {}).get("test_accuracy"),
        "top_features": json.dumps(record.get("top_features", [])),
        "attribution_source": record.get("attribution_source"),
        "model": json.dumps(record.get("model", {})),
        "backtest": json.dumps(record.get("backtest")),
        "data_sources": json.dumps(record.get("data_sources", {})),
        "report_text": record.get("report", {}).get("text"),
        "report_source": record.get("report", {}).get("source"),
        "report_path": record.get("report", {}).get("pdf_path"),
    }
    columns = ", ".join(row)
    placeholders = ", ".join(f":{name}" for name in row)
    with _connect() as conn:
        cursor = conn.execute(
            f"INSERT INTO predictions ({columns}) VALUES ({placeholders})", row
        )
        return cursor.lastrowid


def load_latest_prediction():
    """Most recent run as the dict shape the API serves, or None if empty."""
    with _connect() as conn:
        conn.executescript(SCHEMA)  # first request can precede the first write
        row = conn.execute(
            "SELECT * FROM predictions ORDER BY generated_at DESC, id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "generated_at": row["generated_at"],
        "as_of_date": row["as_of_date"],
        "prediction": row["direction"],
        "probability": row["probability"],
        "confidence": row["confidence"],
        "top_features": json.loads(row["top_features"] or "[]"),
        "attribution_source": row["attribution_source"],
        "model": json.loads(row["model"] or "{}"),
        "backtest": json.loads(row["backtest"] or "null"),
        "data_sources": json.loads(row["data_sources"] or "{}"),
        "report": {
            "text": row["report_text"],
            "source": row["report_source"],
            "pdf_path": row["report_path"],
        },
    }


# ==========================================
# STEP 1: Multi-Source Data Pipeline
# ==========================================
def _flatten_columns(df):
    """Recent yfinance versions return (field, ticker) MultiIndex columns."""
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [level[0] for level in df.columns]
    return df


def _normalize_daily_index(df):
    """Coerce onto a tz-naive, midnight-normalised DatetimeIndex so that the
    market, macro and sentiment frames can be joined."""
    index = pd.DatetimeIndex(pd.to_datetime(df.index))
    if index.tz is not None:
        index = index.tz_convert("UTC").tz_localize(None)
    df = df.copy()
    df.index = index.normalize()
    return df


def _add_technical_features(df):
    df = df.copy()
    close = df["Close"]

    df["SMA_7"] = close.rolling(window=7).mean()
    df["SMA_14"] = close.rolling(window=14).mean()
    df["SMA_30"] = close.rolling(window=30).mean()
    df["Daily_Return"] = close.pct_change()
    df["Volatility_7"] = df["Daily_Return"].rolling(window=7).std()

    # Simple RSI approximation
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # Bollinger Bands
    df["BB_Mid"] = close.rolling(window=20).mean()
    df["BB_Upper"] = df["BB_Mid"] + 2 * close.rolling(window=20).std()
    df["BB_Lower"] = df["BB_Mid"] - 2 * close.rolling(window=20).std()

    return df


class DataPipeline:
    def __init__(
        self,
        fred_api_key=None,
        reddit_client_id=None,
        reddit_secret=None,
        reddit_user_agent=None,
        subreddits=None,
    ):
        fred_api_key = fred_api_key or os.environ.get("FRED_API_KEY")
        reddit_client_id = reddit_client_id or os.environ.get("REDDIT_CLIENT_ID")
        reddit_secret = reddit_secret or os.environ.get("REDDIT_CLIENT_SECRET")
        reddit_user_agent = (
            reddit_user_agent
            or os.environ.get("REDDIT_USER_AGENT")
            or "market-intelligence-analyst/1.0"
        )

        # Both clients are optional at construction time so the pipeline can run
        # in a degraded-but-labelled mode when a credential is missing.
        self.fred = Fred(api_key=fred_api_key) if fred_api_key else None
        self.reddit = None
        if reddit_client_id and reddit_secret:
            self.reddit = praw.Reddit(
                client_id=reddit_client_id,
                client_secret=reddit_secret,
                user_agent=reddit_user_agent,
                check_for_async=False,
            )
        self.subreddits = tuple(subreddits) if subreddits else sentiment_subreddits()

    def fetch_market_data(self, lookback_days=LOOKBACK_DAYS):
        end_date = datetime.date.today() + datetime.timedelta(days=1)  # end is exclusive
        start_date = end_date - datetime.timedelta(days=lookback_days)

        data_frames = []
        for ticker in TICKERS:
            df = yf.download(
                ticker,
                start=start_date,
                end=end_date,
                auto_adjust=True,
                progress=False,
            )
            if df is None or df.empty:
                raise RuntimeError(f"yfinance returned no rows for {ticker}")

            df = _add_technical_features(_flatten_columns(df))
            data_frames.append(df.add_prefix(f"{ticker}_"))

        return _normalize_daily_index(pd.concat(data_frames, axis=1))

    def fetch_macro_data(self):
        if self.fred is None:
            raise RuntimeError("FRED_API_KEY is not set; cannot fetch macro data")

        dfs = []
        for name, series_id in MACRO_SERIES.items():
            series = self.fred.get_series(series_id)
            df = _normalize_daily_index(series.rename(name).to_frame())
            df = df.resample("D").ffill()  # monthly/quarterly -> daily
            df[f"{name}_MoM_Change"] = df[name].pct_change(periods=30)
            dfs.append(df)

        return pd.concat(dfs, axis=1)

    def fetch_social_sentiment(
        self,
        lookback_days=LOOKBACK_DAYS,
        post_limit=None,
        comment_post_limit=None,
        comments_per_post=None,
    ):
        """Score recent Reddit discussion with VADER, aggregated to a daily mean.

        Reddit's API only exposes recent listings, so the *observed* window is
        days-to-weeks rather than the full ``lookback_days`` the model trains
        over. Unobserved days are filled with a neutral 0.0 and carry a
        ``Sentiment_Volume`` of 0, which keeps an imputed day distinguishable
        from a genuinely flat one instead of inventing a history for it.
        """
        if self.reddit is None:
            raise RuntimeError(
                "REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET are not set; "
                "cannot fetch social sentiment"
            )

        # `or` would swallow an explicit 0, which has to mean "none of these".
        post_limit = _default_if_none(post_limit, "REDDIT_POST_LIMIT", 200)
        # Comments are a separate API round-trip per post, so only the newest
        # handful of threads are expanded - enough to catch the discussion
        # around a post without blowing the rate limit on every run.
        comment_post_limit = _default_if_none(
            comment_post_limit, "REDDIT_COMMENT_POST_LIMIT", 25
        )
        comments_per_post = _default_if_none(
            comments_per_post, "REDDIT_COMMENTS_PER_POST", 5
        )

        analyzer = _vader_analyzer()
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            days=lookback_days
        )
        scored = []

        for name in self.subreddits:
            try:
                posts = list(self.reddit.subreddit(name).new(limit=post_limit))
            except Exception as exc:  # one dead subreddit shouldn't kill the run
                LOG.warning("Reddit fetch failed for r/%s: %s", name, exc)
                continue

            LOG.info("r/%s: scoring %d posts", name, len(posts))
            for position, post in enumerate(posts):
                created = datetime.datetime.fromtimestamp(
                    post.created_utc, tz=datetime.timezone.utc
                )
                if created < cutoff:
                    continue

                text = f"{post.title or ''}\n{getattr(post, 'selftext', '') or ''}"
                scored.append(
                    {
                        "date": created.date(),
                        "score": analyzer.polarity_scores(text)["compound"],
                    }
                )

                if position < comment_post_limit and comments_per_post:
                    for comment in _top_comments(post, comments_per_post):
                        body = getattr(comment, "body", "") or ""
                        if not body.strip():
                            continue
                        comment_date = datetime.datetime.fromtimestamp(
                            comment.created_utc, tz=datetime.timezone.utc
                        ).date()
                        scored.append(
                            {
                                "date": comment_date,
                                "score": analyzer.polarity_scores(body)["compound"],
                            }
                        )

        if not scored:
            raise RuntimeError("Reddit returned no scoreable posts or comments")

        raw = pd.DataFrame(scored)
        daily = raw.groupby("date")["score"].agg(["mean", "count"])
        daily.index = pd.to_datetime(daily.index)

        index = pd.date_range(
            end=pd.Timestamp(datetime.date.today()), periods=lookback_days, freq="D"
        )
        df = pd.DataFrame(index=index)
        df["Sentiment_Avg"] = daily["mean"].reindex(index).fillna(0.0)
        df["Sentiment_Volume"] = daily["count"].reindex(index).fillna(0).astype(int)
        df["Sentiment_Momentum"] = df["Sentiment_Avg"].diff(periods=7)

        observed = int((df["Sentiment_Volume"] > 0).sum())
        LOG.info(
            "Reddit sentiment: %d documents scored across %d days (%d of %d days observed)",
            len(scored),
            daily.shape[0],
            observed,
            lookback_days,
        )
        return df


_VADER = None


def _vader_analyzer():
    """Lazily build the VADER analyzer, downloading the lexicon on first use."""
    global _VADER
    if _VADER is None:
        import nltk
        from nltk.sentiment.vader import SentimentIntensityAnalyzer

        try:
            _VADER = SentimentIntensityAnalyzer()
        except LookupError:
            nltk.download("vader_lexicon", quiet=True)
            _VADER = SentimentIntensityAnalyzer()
    return _VADER


def _top_comments(post, limit):
    try:
        post.comment_sort = "top"
        post.comments.replace_more(limit=0)
        return list(post.comments)[:limit]
    except Exception as exc:
        LOG.warning("Could not expand comments for %s: %s", getattr(post, "id", "?"), exc)
        return []


def neutral_sentiment_frame(lookback_days=LOOKBACK_DAYS):
    """Flat, all-zero sentiment for when Reddit is unavailable.

    Deliberately neutral rather than random: a synthetic series that *looks*
    like data would let the model - and the dashboard reading its output -
    present noise as signal. Runs using this are tagged in ``data_sources``.
    """
    index = pd.date_range(
        end=pd.Timestamp(datetime.date.today()), periods=lookback_days, freq="D"
    )
    df = pd.DataFrame(index=index)
    df["Sentiment_Avg"] = 0.0
    df["Sentiment_Volume"] = 0
    df["Sentiment_Momentum"] = 0.0
    return df


# ==========================================
# STEP 2: Feature Engineering
# ==========================================
def build_feature_panel(market_df, macro_df, sentiment_df, horizon=HORIZON):
    """Join the three sources into one panel and attach lags plus the target.

    Rows are restricted to trading sessions after the forward-fill, so macro and
    sentiment values are carried *into* a session but calendar days without a
    session never become rows of their own. The horizon is therefore 7 sessions,
    not 7 calendar days.

    ``Target`` is NaN on the most recent ``horizon`` sessions, whose forward
    close has not happened yet - those are the rows a live prediction runs on.
    """
    master_df = market_df.join(macro_df, how="outer").join(sentiment_df, how="outer")
    master_df = master_df.ffill()
    master_df = master_df[master_df.index.isin(market_df.index)]

    for lag in (1, 3, 7, 14):
        master_df[f"SP500_Lag_{lag}"] = master_df[PRICE_COL].shift(lag)

    forward_close = master_df[PRICE_COL].shift(-horizon)
    master_df[TARGET_COL] = (forward_close > master_df[PRICE_COL]).astype(float)
    master_df.loc[forward_close.isna(), TARGET_COL] = np.nan

    feature_cols = [c for c in master_df.columns if c != TARGET_COL]
    return master_df.dropna(subset=feature_cols)


def feature_engineering(
    market_df, macro_df, sentiment_df, horizon=HORIZON, train_fraction=0.8
):
    """Return ``(train_df, test_df, live_df)``.

    ``train_df``/``test_df`` are a chronological (never shuffled) split of every
    labelled row; ``live_df`` holds the unlabelled tail - features only - that
    the current-week prediction is made from.
    """
    panel = build_feature_panel(market_df, macro_df, sentiment_df, horizon=horizon)

    labelled = panel[panel[TARGET_COL].notna()].copy()
    labelled[TARGET_COL] = labelled[TARGET_COL].astype(int)
    live_df = panel[panel[TARGET_COL].isna()].drop(columns=[TARGET_COL])

    train_size = int(len(labelled) * train_fraction)
    return labelled.iloc[:train_size], labelled.iloc[train_size:], live_df


def split_features_target(df):
    """Split a labelled panel into ``(X, y)``."""
    return df.drop(columns=[TARGET_COL]), df[TARGET_COL]


# ==========================================
# STEP 3: Model Training
# ==========================================
def classify_probability(probability, up_threshold=UP_THRESHOLD, down_threshold=DOWN_THRESHOLD):
    """Map an ensemble probability onto the three-state signal."""
    if probability > up_threshold:
        return "UP"
    if probability < down_threshold:
        return "DOWN"
    return "UNCERTAIN"


def confidence_from_probability(probability):
    """Conviction in whichever side was called: 0.5 is a coin flip, 1.0 certain."""
    return float(max(probability, 1 - probability))


class EnsembleModel:
    def __init__(self, up_threshold=UP_THRESHOLD, down_threshold=DOWN_THRESHOLD):
        self.xgb_model = xgb.XGBClassifier(eval_metric="logloss")
        self.lstm_model = None
        self.up_threshold = up_threshold
        self.down_threshold = down_threshold
        self.feature_names = None
        self.cv_results = None

    def train_xgboost(self, X_train, y_train, n_splits=5):
        """Walk-forward CV with TimeSeriesSplit, then refit on the full window.

        Each fold trains only on rows preceding its validation window, so the
        reported accuracy is out-of-sample in time. The final ``fit`` uses every
        training row - scoring happens first so it stays honest.
        """
        self.feature_names = list(X_train.columns)

        fold_accuracies = []
        if n_splits and len(X_train) > n_splits:
            tscv = TimeSeriesSplit(n_splits=n_splits)
            for fold, (train_idx, val_idx) in enumerate(tscv.split(X_train), start=1):
                fold_model = xgb.XGBClassifier(**self.xgb_model.get_params())
                fold_model.fit(X_train.iloc[train_idx], y_train.iloc[train_idx])
                accuracy = accuracy_score(
                    y_train.iloc[val_idx], fold_model.predict(X_train.iloc[val_idx])
                )
                fold_accuracies.append(float(accuracy))
                LOG.info(
                    "XGBoost CV fold %d/%d: %d train / %d val rows, accuracy=%.4f",
                    fold,
                    n_splits,
                    len(train_idx),
                    len(val_idx),
                    accuracy,
                )
        else:
            LOG.warning(
                "Skipping TimeSeriesSplit CV: %d rows is too few for %s splits",
                len(X_train),
                n_splits,
            )

        self.xgb_model.fit(X_train, y_train)

        self.cv_results = {
            "n_splits": n_splits,
            "fold_accuracies": fold_accuracies,
            "mean_accuracy": float(np.mean(fold_accuracies)) if fold_accuracies else None,
            "std_accuracy": float(np.std(fold_accuracies)) if fold_accuracies else None,
        }
        return self.cv_results

    def build_and_train_lstm(self, X_train, y_train, epochs=5, batch_size=32):
        from tensorflow.keras.layers import LSTM, Dense, Input
        from tensorflow.keras.models import Sequential

        X_train_lstm = self._reshape(X_train)

        self.lstm_model = Sequential(
            [
                Input(shape=(1, X_train.shape[1])),
                LSTM(64, return_sequences=True),
                LSTM(32),
                Dense(1, activation="sigmoid"),
            ]
        )
        self.lstm_model.compile(
            optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"]
        )
        self.lstm_model.fit(
            X_train_lstm,
            np.asarray(y_train, dtype="float32"),
            epochs=epochs,
            batch_size=batch_size,
            verbose=0,
        )
        return self.lstm_model

    @staticmethod
    def _reshape(X):
        """(samples, features) -> (samples, time steps, features)."""
        values = np.asarray(X, dtype="float32")
        return values.reshape((values.shape[0], 1, values.shape[1]))

    def predict_proba(self, X):
        """Averaged P(up) for each row of X."""
        xgb_probs = np.asarray(self.xgb_model.predict_proba(X))[:, 1]
        if self.lstm_model is None:
            LOG.warning("LSTM unavailable; probabilities are XGBoost-only")
            return xgb_probs

        lstm_probs = np.asarray(
            self.lstm_model.predict(self._reshape(X), verbose=0)
        ).flatten()
        return (xgb_probs + lstm_probs) / 2

    def predict(self, X):
        """``[(direction, probability), ...]``, one tuple per row of X."""
        return [
            (classify_probability(p, self.up_threshold, self.down_threshold), float(p))
            for p in self.predict_proba(X)
        ]


# ==========================================
# STEP 4: SHAP Explainability
# ==========================================
def get_shap_explanation(model, X_instance):
    import shap

    explainer = shap.TreeExplainer(model)
    return explainer.shap_values(X_instance)


def top_features(model, X_instance, top_n=5):
    """Ranked attribution for the last row of ``X_instance``.

    Returns ``(features, source)``. SHAP is the intended path; if it fails the
    fallback is the model's own gain importances, and ``source`` says so rather
    than passing one off as the other.
    """
    names = list(X_instance.columns)

    try:
        values = np.asarray(get_shap_explanation(model, X_instance))
        if values.ndim == 3:  # (samples, features, classes) on some versions
            values = values[..., -1]
        row = values[-1] if values.ndim == 2 else values
        return _rank_features(names, row, top_n), "shap"
    except Exception as exc:
        LOG.warning("SHAP failed (%s); falling back to XGBoost gain importances", exc)

    importances = getattr(model, "feature_importances_", None)
    if importances is None:
        return [], "unavailable"
    return _rank_features(names, importances, top_n), "xgboost_gain"


def _rank_features(names, values, top_n):
    ranked = sorted(zip(names, values), key=lambda pair: abs(pair[1]), reverse=True)
    return [{"feature": name, "value": float(value)} for name, value in ranked[:top_n]]


# ==========================================
# STEP 5: Backtesting Engine
# ==========================================
def run_backtest(test_df, predictions, price_col=PRICE_COL, horizon=HORIZON, cost_bps=0.0):
    """Score the signal as a long/flat strategy against buy-and-hold.

    ``predictions`` aligns positionally with ``test_df`` - one entry per row,
    either ``('UP', prob)`` tuples from ``EnsembleModel.predict`` or bare
    direction strings.

    Holding periods are sampled every ``horizon`` rows so they do not overlap.
    Compounding a 7-session forward return once per session would count each
    move roughly seven times and inflate the equity curve accordingly. The
    strategy is long when the call is UP and flat otherwise: UNCERTAIN declines
    to take a view, and the model does not short.
    """
    if len(predictions) != len(test_df):
        raise ValueError(
            f"predictions ({len(predictions)}) and test_df ({len(test_df)}) "
            "must be the same length"
        )

    directions = [p[0] if isinstance(p, (tuple, list)) else p for p in predictions]
    frame = pd.DataFrame({"direction": directions}, index=test_df.index)
    frame["close"] = np.asarray(test_df[price_col], dtype=float)

    # Forward return over the horizon, computed before subsampling so it spans
    # `horizon` sessions rather than `horizon` holding periods.
    frame["forward_return"] = frame["close"].shift(-horizon) / frame["close"] - 1
    frame = frame.iloc[::horizon].dropna(subset=["forward_return"])

    if frame.empty:
        return {
            "n_periods": 0,
            "horizon_sessions": horizon,
            "note": "not enough test rows to realise a single holding period",
        }

    frame["position"] = (frame["direction"] == "UP").astype(float)
    entry_exit = frame["position"].diff()
    entry_exit.iloc[0] = frame["position"].iloc[0]
    costs = entry_exit.abs() * (cost_bps / 10_000.0)

    frame["strategy_return"] = frame["position"] * frame["forward_return"] - costs
    frame["strategy_equity"] = (1 + frame["strategy_return"]).cumprod()
    frame["benchmark_equity"] = (1 + frame["forward_return"]).cumprod()

    actual_up = frame["forward_return"] > 0
    called = frame["direction"].isin(("UP", "DOWN"))
    correct = ((frame["direction"] == "UP") & actual_up) | (
        (frame["direction"] == "DOWN") & ~actual_up
    )
    longs = frame["position"] > 0

    return {
        "n_periods": int(len(frame)),
        "horizon_sessions": horizon,
        "start": _index_label(frame.index[0]),
        "end": _index_label(frame.index[-1]),
        "cost_bps": float(cost_bps),
        "directional_accuracy": float(correct[called].mean()) if called.any() else None,
        "n_directional_calls": int(called.sum()),
        "coverage": float(called.mean()),
        "n_long_periods": int(longs.sum()),
        "long_hit_rate": float(actual_up[longs].mean()) if longs.any() else None,
        "strategy": _performance(frame["strategy_return"], frame["strategy_equity"]),
        "buy_and_hold": _performance(frame["forward_return"], frame["benchmark_equity"]),
        "equity_curve": [
            {
                "date": _index_label(timestamp),
                "strategy": float(strategy),
                "buy_and_hold": float(benchmark),
            }
            for timestamp, strategy, benchmark in zip(
                frame.index, frame["strategy_equity"], frame["benchmark_equity"]
            )
        ],
    }


def _performance(returns, equity):
    """Growth-of-1 performance summary for one return stream."""
    final = float(equity.iloc[-1])
    return {
        "cumulative_return": final - 1,
        "annualized_return": _annualized_return(final, len(returns)),
        "sharpe": _sharpe(returns),
        "max_drawdown": _max_drawdown(equity),
        "final_equity": final,
    }


def _annualized_return(final_equity, n_periods, periods_per_year=PERIODS_PER_YEAR):
    if n_periods <= 0 or final_equity <= 0:
        return None
    return float(final_equity ** (periods_per_year / n_periods) - 1)


def _sharpe(returns, periods_per_year=PERIODS_PER_YEAR):
    """Annualised Sharpe at a zero risk-free rate, over holding periods.

    Undefined rather than astronomical when the return stream has no dispersion
    - a flat strategy, or a synthetic series whose only variation is float
    noise, would otherwise report a Sharpe in the thousands.
    """
    values = np.asarray(returns, dtype=float)
    if len(values) < 2:
        return None
    deviation = values.std(ddof=1)
    if not np.isfinite(deviation) or deviation < 1e-12:
        return None
    return float(values.mean() / deviation * np.sqrt(periods_per_year))


def _max_drawdown(equity):
    values = np.asarray(equity, dtype=float)
    if not len(values):
        return None
    peak = np.maximum.accumulate(values)
    return float((values / peak - 1).min())


def _index_label(value):
    return value.date().isoformat() if hasattr(value, "date") else str(value)


# ==========================================
# STEP 6: Weekly AI Report (Gemini + ReportLab)
# ==========================================
def generate_weekly_report(
    prediction_direction,
    confidence,
    top_features,
    backtest=None,
    as_of=None,
    output_path=None,
):
    """Draft the outlook and render it to PDF.

    Returns ``{"text", "source", "pdf_path"}``. ``source`` names the Gemini
    model that wrote it, or the deterministic fallback used when no key is
    configured, so a template summary is never mistaken for a generated one.
    """
    output_path = output_path or report_path()
    text, source = _draft_report_text(
        prediction_direction, confidence, top_features, backtest, as_of
    )
    pdf_path = _render_report_pdf(
        text, prediction_direction, confidence, top_features, backtest, as_of, output_path
    )
    return {"text": text, "source": source, "pdf_path": pdf_path}


def _draft_report_text(prediction_direction, confidence, top_features, backtest, as_of):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        LOG.warning("GEMINI_API_KEY is not set; writing the fallback outlook")
        return (
            _fallback_report_text(
                prediction_direction, confidence, top_features, backtest, as_of
            ),
            "template_fallback (GEMINI_API_KEY not set)",
        )

    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    feature_list = ", ".join(
        f"{item['feature']} ({item['value']:+.4f})" for item in top_features
    ) or "not available"

    prompt = f"""
    Write a professional weekly market outlook for the S&P 500, as of {as_of or datetime.date.today()}.
    Current model prediction: {prediction_direction} over the next 7 trading sessions,
    with {confidence * 100:.2f}% confidence.
    Top driving features by SHAP attribution: {feature_list}.
    {_backtest_prompt_context(backtest)}

    Sections:
    - Current market assessment
    - Key risk factors this week
    - Data signals supporting the prediction
    - Disclaimer: This is for educational purposes only.

    Keep it under 500 words. Use plain prose, no markdown tables. Do not
    overstate confidence: describe the backtested edge as it is reported above.
    """

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text, f"gemini:{model_name}"
    except Exception as exc:
        LOG.warning("Gemini call failed (%s); writing the fallback outlook", exc)
        return (
            _fallback_report_text(
                prediction_direction, confidence, top_features, backtest, as_of
            ),
            f"template_fallback ({exc})",
        )


def _backtest_prompt_context(backtest):
    if not backtest or not backtest.get("n_periods"):
        return "No backtest is available for this run."
    strategy = backtest.get("strategy", {})
    benchmark = backtest.get("buy_and_hold", {})
    return (
        "Out-of-sample backtest over {n} non-overlapping 7-session periods "
        "({start} to {end}): directional accuracy {acc}, strategy cumulative "
        "return {sret}, buy-and-hold {bret}, strategy Sharpe {sharpe}, "
        "strategy max drawdown {dd}.".format(
            n=backtest["n_periods"],
            start=backtest.get("start"),
            end=backtest.get("end"),
            acc=_pct(backtest.get("directional_accuracy")),
            sret=_pct(strategy.get("cumulative_return")),
            bret=_pct(benchmark.get("cumulative_return")),
            sharpe=_num(strategy.get("sharpe")),
            dd=_pct(strategy.get("max_drawdown")),
        )
    )


def _fallback_report_text(prediction_direction, confidence, top_features, backtest, as_of):
    """Deterministic summary of the run, used when Gemini is unavailable."""
    lines = [
        f"Weekly outlook as of {as_of or datetime.date.today()}.",
        "",
        f"Current market assessment: the ensemble calls {prediction_direction} for the "
        f"S&P 500 over the next {HORIZON} trading sessions, with "
        f"{confidence * 100:.2f}% confidence. An UNCERTAIN call means the blended "
        "probability sits inside the neutral band and no directional view is taken.",
        "",
        "Data signals supporting the prediction:",
    ]
    lines += [
        f"  - {item['feature']}: {item['value']:+.4f}" for item in top_features
    ] or ["  - attribution unavailable for this run"]

    if backtest and backtest.get("n_periods"):
        strategy = backtest.get("strategy", {})
        benchmark = backtest.get("buy_and_hold", {})
        lines += [
            "",
            "Key risk factors: the out-of-sample record is the only guide to how much "
            "weight this call deserves. Over "
            f"{backtest['n_periods']} non-overlapping {HORIZON}-session periods "
            f"({backtest.get('start')} to {backtest.get('end')}), directional accuracy "
            f"was {_pct(backtest.get('directional_accuracy'))} and the long/flat "
            f"strategy returned {_pct(strategy.get('cumulative_return'))} against "
            f"{_pct(benchmark.get('cumulative_return'))} for buy-and-hold, at a Sharpe "
            f"of {_num(strategy.get('sharpe'))} and a maximum drawdown of "
            f"{_pct(strategy.get('max_drawdown'))}.",
        ]
    else:
        lines += ["", "Key risk factors: no backtest was available for this run."]

    lines += [
        "",
        "Disclaimer: This is for educational purposes only. It is not investment "
        "advice and is not a recommendation to buy or sell any security.",
        "",
        "(Generated without the language model: no Gemini API key was configured, "
        "so this is a deterministic summary of the run's own numbers.)",
    ]
    return "\n".join(lines)


def _pct(value):
    return "n/a" if value is None else f"{value * 100:.2f}%"


def _num(value):
    return "n/a" if value is None else f"{value:.2f}"


def _render_report_pdf(
    text, prediction_direction, confidence, top_features, backtest, as_of, output_path
):
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "MemoBody",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        spaceAfter=8,
    )
    meta = ParagraphStyle(
        "MemoMeta", parent=styles["BodyText"], fontSize=8, textColor=colors.grey
    )

    story = [
        Paragraph("Weekly AI Market Report", styles["Title"]),
        Paragraph(
            "S&amp;P 500 directional outlook &middot; as of "
            f"{as_of or datetime.date.today()} &middot; generated "
            f"{datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d %H:%M UTC}",
            meta,
        ),
        Spacer(1, 0.25 * inch),
        _summary_table(prediction_direction, confidence, backtest),
        Spacer(1, 0.25 * inch),
    ]

    if backtest and backtest.get("n_periods"):
        story += [
            Paragraph("Out-of-sample backtest", styles["Heading3"]),
            _backtest_table(backtest),
            Spacer(1, 0.25 * inch),
        ]

    chart_path = None
    if top_features:
        story.append(Paragraph("Top feature attribution", styles["Heading3"]))
        chart_path = _feature_chart_png(top_features)
        if chart_path:
            story.append(Image(chart_path, width=6.0 * inch, height=2.6 * inch))
        story += [_feature_table(top_features), Spacer(1, 0.25 * inch)]

    paragraphs = [Paragraph(block, body) for block in _text_to_paragraphs(text)]
    heading = Paragraph("Outlook", styles["Heading3"])
    # Keep the heading with its first paragraph so it never orphans on a break.
    story.append(KeepTogether([heading, *paragraphs[:1]]))
    story += paragraphs[1:]

    try:
        SimpleDocTemplate(
            output_path,
            pagesize=LETTER,
            title="Weekly AI Market Report",
            author="Automated Market Intelligence Analyst",
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        ).build(story)
    finally:
        if chart_path and os.path.exists(chart_path):
            os.unlink(chart_path)

    LOG.info("Wrote weekly report to %s", output_path)
    return output_path


_TABLE_STYLE = TableStyle(
    [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2933")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f4f6")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd2d9")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
)


def _summary_table(prediction_direction, confidence, backtest):
    rows = [
        ["Signal", "Confidence", "Horizon", "Out-of-sample accuracy"],
        [
            prediction_direction,
            f"{confidence * 100:.2f}%",
            f"{HORIZON} sessions",
            _pct((backtest or {}).get("directional_accuracy")),
        ],
    ]
    table = Table(rows, colWidths=[1.6 * inch] * 4)
    table.setStyle(_TABLE_STYLE)
    return table


def _backtest_table(backtest):
    strategy = backtest.get("strategy", {})
    benchmark = backtest.get("buy_and_hold", {})
    rows = [
        ["Metric", "Long/flat strategy", "Buy & hold"],
        [
            "Cumulative return",
            _pct(strategy.get("cumulative_return")),
            _pct(benchmark.get("cumulative_return")),
        ],
        [
            "Annualised return",
            _pct(strategy.get("annualized_return")),
            _pct(benchmark.get("annualized_return")),
        ],
        ["Sharpe", _num(strategy.get("sharpe")), _num(benchmark.get("sharpe"))],
        [
            "Max drawdown",
            _pct(strategy.get("max_drawdown")),
            _pct(benchmark.get("max_drawdown")),
        ],
        [
            f"Periods ({backtest.get('start')} to {backtest.get('end')})",
            str(backtest.get("n_periods")),
            str(backtest.get("n_periods")),
        ],
    ]
    table = Table(rows, colWidths=[2.6 * inch, 2.0 * inch, 1.8 * inch])
    table.setStyle(_TABLE_STYLE)
    return table


def _feature_table(top_features):
    rows = [["Feature", "Attribution"]] + [
        [item["feature"], f"{item['value']:+.4f}"] for item in top_features
    ]
    table = Table(rows, colWidths=[4.6 * inch, 1.8 * inch])
    table.setStyle(_TABLE_STYLE)
    return table


def _feature_chart_png(top_features):
    """Horizontal bar chart of the attributions, as a temp PNG for the PDF."""
    try:
        ordered = sorted(top_features, key=lambda item: abs(item["value"]))
        labels = [item["feature"] for item in ordered]
        values = [item["value"] for item in ordered]

        figure, axis = plt.subplots(figsize=(7.5, 3.2))
        axis.barh(
            labels,
            values,
            color=["#1f2933" if value >= 0 else "#9aa5b1" for value in values],
        )
        axis.axvline(0, color="#616e7c", linewidth=0.8)
        axis.set_xlabel("Contribution to P(up)")
        axis.tick_params(labelsize=8)
        for spine in ("top", "right"):
            axis.spines[spine].set_visible(False)
        figure.tight_layout()

        handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        handle.close()
        figure.savefig(handle.name, dpi=150)
        plt.close(figure)
        return handle.name
    except Exception as exc:
        LOG.warning("Could not render the attribution chart: %s", exc)
        return None


def _text_to_paragraphs(text):
    """Split generated text into ReportLab-safe paragraph markup."""
    paragraphs = []
    for block in (text or "").split("\n\n"):
        block = block.strip()
        if not block:
            continue
        escaped = (
            block.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        # Gemini answers in markdown; carry bold across and drop heading hashes.
        while "**" in escaped:
            escaped = escaped.replace("**", "<b>", 1).replace("**", "</b>", 1)
        lines = [line.lstrip("#").strip() for line in escaped.split("\n")]
        paragraphs.append("<br/>".join(line for line in lines if line))
    return paragraphs


# ==========================================
# STEP 7: Pipeline orchestration
# ==========================================
def run_pipeline(persist=True):
    """Ingest, train, predict, backtest, report and persist one full run."""
    started = datetime.datetime.now(datetime.timezone.utc)
    pipeline = DataPipeline()
    sources = {}

    # Prices are the one hard requirement: no prices, no model.
    market_df = pipeline.fetch_market_data()
    sources["market"] = f"yfinance:{','.join(TICKERS)}"

    try:
        macro_df = pipeline.fetch_macro_data()
        sources["macro"] = f"fred:{','.join(MACRO_SERIES.values())}"
    except Exception as exc:
        LOG.warning("Macro data unavailable (%s); continuing without it", exc)
        macro_df = pd.DataFrame(index=market_df.index)
        sources["macro"] = f"unavailable ({exc})"

    try:
        sentiment_df = pipeline.fetch_social_sentiment()
        sources["sentiment"] = f"reddit:{','.join(pipeline.subreddits)}"
    except Exception as exc:
        LOG.warning("Reddit sentiment unavailable (%s); using a neutral series", exc)
        sentiment_df = neutral_sentiment_frame()
        sources["sentiment"] = f"neutral_fallback ({exc})"

    train_df, test_df, live_df = feature_engineering(market_df, macro_df, sentiment_df)
    X_train, y_train = split_features_target(train_df)
    X_test, y_test = split_features_target(test_df)
    LOG.info(
        "Panel: %d train / %d test rows, %d features, %d unlabelled live rows",
        len(X_train),
        len(X_test),
        X_train.shape[1],
        len(live_df),
    )

    model = EnsembleModel()
    cv_results = model.train_xgboost(X_train, y_train)
    try:
        model.build_and_train_lstm(X_train, y_train)
    except Exception as exc:
        LOG.warning("LSTM training failed (%s); ensemble degrades to XGBoost", exc)

    test_predictions = model.predict(X_test)
    test_probabilities = np.array([probability for _, probability in test_predictions])
    test_accuracy = float(accuracy_score(y_test, (test_probabilities > 0.5).astype(int)))
    backtest = run_backtest(test_df, test_predictions)

    # The live call comes off the newest row whose forward close is still
    # unknown; if the tail is empty (short history) fall back to the last
    # labelled row so a run always produces a signal.
    latest_X = (live_df if not live_df.empty else X_test).iloc[[-1]]
    latest_X = latest_X[model.feature_names]
    direction, probability = model.predict(latest_X)[0]
    features, attribution_source = top_features(model.xgb_model, latest_X)
    as_of = _index_label(latest_X.index[-1])

    LOG.info(
        "Prediction as of %s: %s (p=%.4f, CV accuracy=%s, test accuracy=%.4f)",
        as_of,
        direction,
        probability,
        _num(cv_results.get("mean_accuracy")),
        test_accuracy,
    )

    confidence = confidence_from_probability(probability)
    try:
        report = generate_weekly_report(
            direction, confidence, features, backtest=backtest, as_of=as_of
        )
    except Exception as exc:
        LOG.exception("Weekly report generation failed")
        report = {"text": None, "source": f"failed ({exc})", "pdf_path": None}

    record = {
        "generated_at": started.isoformat(timespec="seconds"),
        "as_of_date": as_of,
        "prediction": direction,
        "probability": float(probability),
        "confidence": confidence,
        "top_features": features,
        "attribution_source": attribution_source,
        "model": {
            "cv_accuracy": cv_results.get("mean_accuracy"),
            "cv_accuracy_std": cv_results.get("std_accuracy"),
            "cv_fold_accuracies": cv_results.get("fold_accuracies"),
            "test_accuracy": test_accuracy,
            "lstm_trained": model.lstm_model is not None,
            "train_rows": len(X_train),
            "test_rows": len(X_test),
            "n_features": int(X_train.shape[1]),
            "up_threshold": model.up_threshold,
            "down_threshold": model.down_threshold,
        },
        "backtest": backtest,
        "data_sources": sources,
        "report": report,
        "runtime_seconds": round(
            (datetime.datetime.now(datetime.timezone.utc) - started).total_seconds(), 1
        ),
    }

    if persist:
        record["id"] = save_prediction(record)
    return record


def scheduled_job():
    """APScheduler entry point. Never raises: a failed run must not kill the job."""
    LOG.info("Running prediction pipeline...")
    try:
        record = run_pipeline()
        LOG.info(
            "Pipeline complete in %ss: %s at %.2f%% confidence (as of %s)",
            record["runtime_seconds"],
            record["prediction"],
            record["confidence"] * 100,
            record["as_of_date"],
        )
        return record
    except Exception:
        LOG.exception("Prediction pipeline failed")
        return None


# ==========================================
# Flask API
# ==========================================
@app.after_request
def add_cors_headers(response):
    # The dashboard is a static site on a different origin.
    response.headers.setdefault("Access-Control-Allow-Origin", os.environ.get("CORS_ORIGIN", "*"))
    response.headers.setdefault("Access-Control-Allow-Methods", "GET, OPTIONS")
    return response


@app.route("/")
def health_check():
    return jsonify({"status": "healthy", "message": "Market Engine is running."})


@app.route("/api/latest")
def latest_prediction():
    """Most recent persisted run: signal, confidence, attribution, backtest."""
    record = load_latest_prediction()
    if record is None:
        return (
            jsonify(
                {
                    "status": "pending",
                    "message": "No prediction has been generated yet. The pipeline "
                    "runs on startup and then on its refresh interval.",
                }
            ),
            503,
        )
    return jsonify(record)


# ==========================================
# Scheduler
# ==========================================
def start_scheduler(interval_minutes=None, run_immediately=True):
    interval = _default_if_none(interval_minutes, "PIPELINE_INTERVAL_MINUTES", 30)
    scheduler = BackgroundScheduler(daemon=True)
    job_kwargs = {}
    if run_immediately:
        # Otherwise /api/latest has nothing to serve for the first interval.
        job_kwargs["next_run_time"] = datetime.datetime.now()
    scheduler.add_job(
        scheduled_job,
        "interval",
        minutes=interval,
        id="prediction_pipeline",
        max_instances=1,  # a run can outlast a short interval
        coalesce=True,
        misfire_grace_time=300,
        **job_kwargs,
    )
    scheduler.start()
    LOG.info("Scheduler started: pipeline every %d minutes", interval)
    return scheduler


def _scheduler_disabled():
    return os.environ.get("DISABLE_SCHEDULER", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


init_db()

# Started at import so it also runs under Gunicorn, which never executes
# __main__. Keep the service at one worker, or each worker runs its own copy.
scheduler = None if _scheduler_disabled() else start_scheduler()

if __name__ == "__main__":
    print("Market Engine Initiated.")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
