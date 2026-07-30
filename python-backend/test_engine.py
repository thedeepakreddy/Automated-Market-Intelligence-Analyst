"""Tests for the market intelligence engine.

Everything here runs on synthetic data - no network, no API keys, no
credentials. The point is to pin the contracts the Flask API and the dashboard
depend on: the shape of the feature panel, the shape of a prediction, and the
arithmetic behind the backtest metrics.
"""

import datetime

import numpy as np
import pandas as pd
import pytest

import engine


# ------------------------------------------------------------------
# Synthetic fixtures shaped like what the real fetchers return
# ------------------------------------------------------------------
def market_frame(n_sessions=300, start="2023-01-02"):
    """One frame per ticker, prefixed and concatenated, on a session index."""
    index = pd.bdate_range(start=start, periods=n_sessions)
    rng = np.random.default_rng(7)

    frames = []
    for offset, ticker in enumerate(engine.TICKERS):
        close = pd.Series(
            100 + offset + np.cumsum(rng.normal(0.05, 1.0, n_sessions)), index=index
        )
        df = pd.DataFrame(
            {
                "Open": close.shift(1).bfill(),
                "High": close * 1.01,
                "Low": close * 0.99,
                "Close": close,
                "Volume": 1_000_000.0,
            },
            index=index,
        )
        frames.append(engine._add_technical_features(df).add_prefix(f"{ticker}_"))

    return pd.concat(frames, axis=1)


def macro_frame(session_index):
    """Monthly FRED series already resampled to a daily calendar index."""
    days = pd.date_range(
        session_index[0] - pd.Timedelta(days=60),
        session_index[-1] + pd.Timedelta(days=5),
        freq="D",
    )
    df = pd.DataFrame(index=days)
    for offset, name in enumerate(engine.MACRO_SERIES):
        df[name] = np.linspace(100 + offset, 110 + offset, len(days))
        df[f"{name}_MoM_Change"] = df[name].pct_change(periods=30)
    return df


def sentiment_frame(session_index):
    """Daily aggregated sentiment, as fetch_social_sentiment returns it."""
    days = pd.date_range(
        session_index[0] - pd.Timedelta(days=30),
        session_index[-1] + pd.Timedelta(days=1),
        freq="D",
    )
    rng = np.random.default_rng(11)
    df = pd.DataFrame(index=days)
    df["Sentiment_Avg"] = rng.uniform(-0.4, 0.4, len(days))
    df["Sentiment_Volume"] = rng.integers(0, 60, len(days))
    df["Sentiment_Momentum"] = df["Sentiment_Avg"].diff(periods=7)
    return df


def price_frame(closes, start="2024-01-01"):
    """Minimal test_df for the backtest: just the S&P close on a session index."""
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame(
        {engine.PRICE_COL: closes},
        index=pd.bdate_range(start=start, periods=len(closes)),
    )


def tabular_dataset(n_rows=200, n_features=6, seed=3):
    """A learnable binary problem for the model tests."""
    rng = np.random.default_rng(seed)
    X = pd.DataFrame(
        rng.normal(size=(n_rows, n_features)),
        columns=[f"feature_{i}" for i in range(n_features)],
        index=pd.bdate_range("2023-01-02", periods=n_rows),
    )
    y = (X["feature_0"] + 0.5 * X["feature_1"] > 0).astype(int)
    return X, y


class StubLSTM:
    """Stands in for the Keras model: predict() returns a column vector."""

    def __init__(self, value):
        self.value = value

    def predict(self, X, verbose=0):
        return np.full((X.shape[0], 1), self.value, dtype=float)


@pytest.fixture(scope="module")
def panel_split():
    market = market_frame()
    return engine.feature_engineering(
        market, macro_frame(market.index), sentiment_frame(market.index)
    )


# ------------------------------------------------------------------
# Feature engineering
# ------------------------------------------------------------------
def test_feature_engineering_splits_chronologically(panel_split):
    train_df, test_df, live_df = panel_split

    assert len(train_df) and len(test_df) and len(live_df)
    assert train_df.index.max() < test_df.index.min() < live_df.index.min()

    # 80/20 of the labelled rows, no shuffling, no overlap.
    labelled = len(train_df) + len(test_df)
    assert len(train_df) == int(labelled * 0.8)
    assert not train_df.index.intersection(test_df.index).size
    assert not test_df.index.intersection(live_df.index).size

    # The unlabelled tail is exactly the rows whose forward close is unknown.
    assert len(live_df) == engine.HORIZON


def test_feature_engineering_columns(panel_split):
    train_df, test_df, live_df = panel_split

    assert engine.TARGET_COL in train_df.columns
    assert engine.TARGET_COL in test_df.columns
    assert engine.TARGET_COL not in live_df.columns
    assert list(live_df.columns) == [
        column for column in train_df.columns if column != engine.TARGET_COL
    ]
    assert list(test_df.columns) == list(train_df.columns)

    for ticker in engine.TICKERS:
        for feature in (
            "Close",
            "SMA_7",
            "SMA_14",
            "SMA_30",
            "Daily_Return",
            "Volatility_7",
            "RSI",
            "BB_Mid",
            "BB_Upper",
            "BB_Lower",
        ):
            assert f"{ticker}_{feature}" in train_df.columns

    for name in engine.MACRO_SERIES:
        assert name in train_df.columns
        assert f"{name}_MoM_Change" in train_df.columns

    for column in ("Sentiment_Avg", "Sentiment_Momentum", "Sentiment_Volume"):
        assert column in train_df.columns

    for lag in (1, 3, 7, 14):
        assert f"SP500_Lag_{lag}" in train_df.columns


def test_feature_engineering_has_no_gaps_and_binary_target(panel_split):
    train_df, test_df, live_df = panel_split

    for frame in (train_df, test_df, live_df):
        assert not frame.isna().to_numpy().any()

    for frame in (train_df, test_df):
        assert set(frame[engine.TARGET_COL].unique()) <= {0, 1}
        assert frame[engine.TARGET_COL].dtype.kind in "iu"


def test_target_is_the_forward_session_move():
    market = market_frame()
    panel = engine.build_feature_panel(
        market, macro_frame(market.index), sentiment_frame(market.index)
    )

    # Rows are trading sessions only, so the horizon is 7 sessions ahead.
    assert panel.index.isin(market.index).all()

    closes = panel[engine.PRICE_COL].to_numpy()
    targets = panel[engine.TARGET_COL].to_numpy()
    for position in (0, 17, len(panel) - engine.HORIZON - 1):
        expected = float(closes[position + engine.HORIZON] > closes[position])
        assert targets[position] == expected

    # The final `horizon` sessions cannot be labelled yet.
    assert np.isnan(targets[-engine.HORIZON :]).all()
    assert not np.isnan(targets[: -engine.HORIZON]).any()


def test_split_features_target(panel_split):
    train_df, _, _ = panel_split
    X, y = engine.split_features_target(train_df)

    assert engine.TARGET_COL not in X.columns
    assert X.shape == (len(train_df), train_df.shape[1] - 1)
    assert y.name == engine.TARGET_COL
    assert len(y) == len(train_df)


# ------------------------------------------------------------------
# Ensemble
# ------------------------------------------------------------------
def test_classify_probability_thresholds():
    assert engine.classify_probability(0.90) == "UP"
    assert engine.classify_probability(0.10) == "DOWN"
    # The band edges are inside the neutral zone: no view is taken there.
    assert engine.classify_probability(0.55) == "UNCERTAIN"
    assert engine.classify_probability(0.45) == "UNCERTAIN"
    assert engine.classify_probability(0.50) == "UNCERTAIN"


def test_confidence_is_conviction_in_the_called_side():
    assert engine.confidence_from_probability(0.68) == pytest.approx(0.68)
    assert engine.confidence_from_probability(0.32) == pytest.approx(0.68)
    assert engine.confidence_from_probability(0.50) == pytest.approx(0.50)


def test_predict_returns_direction_probability_pairs():
    X, y = tabular_dataset()
    model = engine.EnsembleModel()
    model.train_xgboost(X, y, n_splits=3)
    model.lstm_model = StubLSTM(0.5)

    predictions = model.predict(X)

    assert len(predictions) == len(X)
    for prediction in predictions:
        assert isinstance(prediction, tuple) and len(prediction) == 2
        direction, probability = prediction
        assert direction in {"UP", "DOWN", "UNCERTAIN"}
        assert isinstance(probability, float)
        assert 0.0 <= probability <= 1.0
        assert direction == engine.classify_probability(probability)

    # The ensemble probability is the mean of its two members.
    xgb_probs = model.xgb_model.predict_proba(X)[:, 1]
    np.testing.assert_allclose(
        [probability for _, probability in predictions],
        (xgb_probs + 0.5) / 2,
        rtol=1e-6,
    )


def test_predict_falls_back_to_xgboost_when_lstm_is_missing():
    X, y = tabular_dataset(n_rows=120)
    model = engine.EnsembleModel()
    model.train_xgboost(X, y, n_splits=3)

    assert model.lstm_model is None
    np.testing.assert_allclose(
        model.predict_proba(X), model.xgb_model.predict_proba(X)[:, 1]
    )


def test_train_xgboost_reports_cross_validated_accuracy():
    X, y = tabular_dataset()
    model = engine.EnsembleModel()

    cv_results = model.train_xgboost(X, y, n_splits=5)

    assert cv_results["n_splits"] == 5
    assert len(cv_results["fold_accuracies"]) == 5
    assert all(0.0 <= accuracy <= 1.0 for accuracy in cv_results["fold_accuracies"])
    assert cv_results["mean_accuracy"] == pytest.approx(
        float(np.mean(cv_results["fold_accuracies"]))
    )
    assert cv_results["std_accuracy"] is not None
    assert model.feature_names == list(X.columns)
    # A learnable signal should beat a coin flip out of sample.
    assert cv_results["mean_accuracy"] > 0.6


def test_train_xgboost_skips_cv_when_there_are_too_few_rows():
    X, y = tabular_dataset(n_rows=4)
    model = engine.EnsembleModel()

    cv_results = model.train_xgboost(X, y, n_splits=5)

    assert cv_results["fold_accuracies"] == []
    assert cv_results["mean_accuracy"] is None
    # The model is still fitted on everything available.
    assert len(model.predict(X)) == len(X)


def test_lstm_path_produces_ensemble_probabilities():
    pytest.importorskip("tensorflow")
    X, y = tabular_dataset(n_rows=120, n_features=4)

    model = engine.EnsembleModel()
    model.train_xgboost(X, y, n_splits=3)
    model.build_and_train_lstm(X, y, epochs=1, batch_size=32)

    assert model.lstm_model is not None
    probabilities = model.predict_proba(X)
    assert probabilities.shape == (len(X),)
    assert ((probabilities >= 0.0) & (probabilities <= 1.0)).all()


def test_reshape_adds_a_single_time_step():
    X, _ = tabular_dataset(n_rows=10, n_features=4)
    reshaped = engine.EnsembleModel._reshape(X)
    assert reshaped.shape == (10, 1, 4)
    assert reshaped.dtype == np.float32


# ------------------------------------------------------------------
# Backtest
# ------------------------------------------------------------------
def test_backtest_on_a_monotonic_riser():
    # 1% per session for 29 sessions: every 7-session period returns 1.01**7 - 1.
    closes = 100 * 1.01 ** np.arange(29)
    test_df = price_frame(closes)
    predictions = [("UP", 0.8)] * len(test_df)

    result = engine.run_backtest(test_df, predictions)

    # Sampled at rows 0, 7, 14, 21; row 28 has no forward close so it is dropped.
    assert result["n_periods"] == 4
    assert result["horizon_sessions"] == engine.HORIZON
    assert result["directional_accuracy"] == pytest.approx(1.0)
    assert result["coverage"] == pytest.approx(1.0)
    assert result["n_directional_calls"] == 4
    assert result["n_long_periods"] == 4
    assert result["long_hit_rate"] == pytest.approx(1.0)

    expected = 1.01 ** 28 - 1
    assert result["strategy"]["cumulative_return"] == pytest.approx(expected)
    assert result["buy_and_hold"]["cumulative_return"] == pytest.approx(expected)
    assert result["strategy"]["max_drawdown"] == pytest.approx(0.0)
    # Identical returns every period: dispersion is zero, so Sharpe is undefined
    # rather than infinite.
    assert result["strategy"]["sharpe"] is None

    assert len(result["equity_curve"]) == 4
    assert result["equity_curve"][0]["date"] == "2024-01-01"
    assert result["equity_curve"][-1]["strategy"] == pytest.approx(1.01 ** 28)


def test_backtest_rewards_sitting_out_a_drawdown():
    # Rises, then a 16% fall, then two rises. The model calls the fall.
    closes = np.concatenate(
        [
            np.linspace(100, 107, 8)[:-1],  # sessions 0-6
            np.linspace(107, 90, 8)[:-1],  # sessions 7-13
            np.linspace(90, 99, 8)[:-1],  # sessions 14-20
            np.linspace(99, 105, 8),  # sessions 21-28
        ]
    )
    test_df = price_frame(closes)

    # Only rows 0, 7, 14 and 21 are sampled; the rest must not affect anything.
    predictions = ["UNCERTAIN"] * len(test_df)
    predictions[0] = "UP"
    predictions[7] = "DOWN"
    predictions[14] = "UP"
    predictions[21] = "UP"

    result = engine.run_backtest(test_df, predictions)

    assert result["n_periods"] == 4
    assert result["directional_accuracy"] == pytest.approx(1.0)
    assert result["n_long_periods"] == 3  # flat through the fall

    strategy_expected = (107 / 100) * (99 / 90) * (105 / 99) - 1
    benchmark_expected = (107 / 100) * (90 / 107) * (99 / 90) * (105 / 99) - 1
    assert result["strategy"]["cumulative_return"] == pytest.approx(strategy_expected)
    assert result["buy_and_hold"]["cumulative_return"] == pytest.approx(benchmark_expected)
    assert result["strategy"]["cumulative_return"] > result["buy_and_hold"]["cumulative_return"]

    # Buy-and-hold wears the fall; the long/flat strategy does not.
    assert result["buy_and_hold"]["max_drawdown"] < -0.15
    assert result["strategy"]["max_drawdown"] == pytest.approx(0.0)
    assert result["strategy"]["sharpe"] > result["buy_and_hold"]["sharpe"]


def test_backtest_scores_only_directional_calls():
    closes = 100 * 1.01 ** np.arange(29)
    test_df = price_frame(closes)
    predictions = ["UNCERTAIN"] * len(test_df)
    predictions[0] = "UP"
    predictions[7] = "DOWN"  # wrong: the market rose

    result = engine.run_backtest(test_df, predictions)

    assert result["n_periods"] == 4
    assert result["n_directional_calls"] == 2
    assert result["coverage"] == pytest.approx(0.5)
    assert result["directional_accuracy"] == pytest.approx(0.5)
    # UNCERTAIN is flat, so only the one UP call is ever invested.
    assert result["n_long_periods"] == 1


def test_backtest_reports_no_edge_when_there_is_none():
    closes = 100 * 1.01 ** np.arange(29)
    test_df = price_frame(closes)
    predictions = ["DOWN"] * len(test_df)

    result = engine.run_backtest(test_df, predictions)

    assert result["directional_accuracy"] == pytest.approx(0.0)
    assert result["n_long_periods"] == 0
    assert result["strategy"]["cumulative_return"] == pytest.approx(0.0)
    assert result["buy_and_hold"]["cumulative_return"] > 0


def test_backtest_charges_transaction_costs():
    closes = 100 * 1.01 ** np.arange(29)
    test_df = price_frame(closes)
    predictions = [("UP", 0.9)] * len(test_df)

    free = engine.run_backtest(test_df, predictions)
    costed = engine.run_backtest(test_df, predictions, cost_bps=10)

    assert costed["cost_bps"] == 10.0
    assert costed["strategy"]["cumulative_return"] < free["strategy"]["cumulative_return"]

    # One entry, then held: 10bp is charged once, on the first period only.
    period_return = 1.01 ** 7 - 1
    expected = (1 + period_return - 0.001) * (1 + period_return) ** 3 - 1
    assert costed["strategy"]["cumulative_return"] == pytest.approx(expected)


def test_backtest_handles_a_window_too_short_to_realise_a_period():
    test_df = price_frame(100 * 1.01 ** np.arange(5))

    result = engine.run_backtest(test_df, ["UP"] * 5)

    assert result["n_periods"] == 0
    assert "note" in result


def test_backtest_rejects_misaligned_predictions():
    test_df = price_frame(100 * 1.01 ** np.arange(29))

    with pytest.raises(ValueError, match="same length"):
        engine.run_backtest(test_df, ["UP"] * 5)


def test_backtest_accepts_predict_output_directly():
    X, y = tabular_dataset(n_rows=60)
    model = engine.EnsembleModel()
    model.train_xgboost(X, y, n_splits=3)
    model.lstm_model = StubLSTM(0.6)

    test_df = price_frame(100 * 1.005 ** np.arange(len(X)))
    result = engine.run_backtest(test_df, model.predict(X))

    assert result["n_periods"] == (len(X) - 1) // engine.HORIZON
    assert 0.0 <= result["coverage"] <= 1.0


def test_performance_helpers():
    assert engine._max_drawdown([1.0, 1.2, 0.9, 1.1]) == pytest.approx(0.9 / 1.2 - 1)
    assert engine._max_drawdown([1.0, 1.1, 1.2]) == pytest.approx(0.0)
    assert engine._sharpe([0.01]) is None
    assert engine._sharpe([0.01, 0.01, 0.01]) is None
    # Doubling over exactly one year of holding periods annualises to +100%.
    assert engine._annualized_return(2.0, int(engine.PERIODS_PER_YEAR)) == pytest.approx(1.0)
    assert engine._annualized_return(1.0, 0) is None


# ------------------------------------------------------------------
# Persistence and the API contract the dashboard reads
# ------------------------------------------------------------------
def sample_record(direction="UP", generated_at="2026-07-29T14:00:00+00:00"):
    return {
        "generated_at": generated_at,
        "as_of_date": "2026-07-29",
        "prediction": direction,
        "probability": 0.684,
        "confidence": 0.684,
        "top_features": [
            {"feature": "^GSPC_RSI", "value": 0.12},
            {"feature": "CPI_MoM_Change", "value": -0.05},
        ],
        "attribution_source": "shap",
        "model": {"cv_accuracy": 0.57, "test_accuracy": 0.61, "lstm_trained": True},
        "backtest": {"n_periods": 4, "directional_accuracy": 0.75},
        "data_sources": {"sentiment": "reddit:investing,stocks"},
        "report": {
            "text": "Outlook body.",
            "source": "gemini:gemini-2.5-flash",
            "pdf_path": "/tmp/weekly_report.pdf",
        },
    }


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_DB_PATH", str(tmp_path / "predictions.db"))
    engine.init_db()
    return engine.app.test_client()


def test_health_check(api_client):
    response = api_client.get("/")
    assert response.status_code == 200
    assert response.get_json()["status"] == "healthy"


def test_latest_is_pending_before_the_first_run(api_client):
    response = api_client.get("/api/latest")

    assert response.status_code == 503
    assert response.get_json()["status"] == "pending"
    assert engine.load_latest_prediction() is None


def test_latest_serves_the_most_recent_run(api_client):
    engine.save_prediction(sample_record("DOWN", "2026-07-22T14:00:00+00:00"))
    engine.save_prediction(sample_record("UP", "2026-07-29T14:00:00+00:00"))

    response = api_client.get("/api/latest")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["prediction"] == "UP"
    assert payload["confidence"] == pytest.approx(0.684)
    assert payload["probability"] == pytest.approx(0.684)
    assert payload["as_of_date"] == "2026-07-29"
    assert payload["attribution_source"] == "shap"
    assert payload["top_features"][0] == {"feature": "^GSPC_RSI", "value": 0.12}
    assert payload["model"]["cv_accuracy"] == pytest.approx(0.57)
    assert payload["backtest"]["n_periods"] == 4
    assert payload["data_sources"]["sentiment"] == "reddit:investing,stocks"
    assert payload["report"]["source"] == "gemini:gemini-2.5-flash"
    # The dashboard is served from another origin.
    assert response.headers["Access-Control-Allow-Origin"] == "*"


# ------------------------------------------------------------------
# Social sentiment
# ------------------------------------------------------------------
def _ago(days, hours=12):
    """A UTC timestamp `days` ago, as praw reports created_utc."""
    moment = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=days, hours=hours
    )
    return moment.timestamp()


class StubComment:
    def __init__(self, body, created_utc):
        self.body = body
        self.created_utc = created_utc


class StubCommentForest:
    """praw's CommentForest: iterable, and needs replace_more() called first."""

    def __init__(self, comments):
        self._comments = comments
        self.replaced = False

    def replace_more(self, limit=0):
        self.replaced = True

    def __iter__(self):
        if not self.replaced:
            raise AssertionError("replace_more() must be called before iterating")
        return iter(self._comments)


class StubPost:
    def __init__(self, ident, title, selftext, created_utc, comments=()):
        self.id = ident
        self.title = title
        self.selftext = selftext
        self.created_utc = created_utc
        self.comments = StubCommentForest(list(comments))
        self.comment_sort = "best"


class StubSubreddit:
    def __init__(self, posts):
        self._posts = posts

    def new(self, limit=None):
        return iter(self._posts[:limit])


class StubReddit:
    def __init__(self, posts_by_subreddit):
        self._posts = posts_by_subreddit
        self.requested = []

    def subreddit(self, name):
        self.requested.append(name)
        return StubSubreddit(self._posts.get(name, []))


@pytest.fixture
def reddit_pipeline():
    """A pipeline whose Reddit client is a stub, with VADER scoring for real."""
    pytest.importorskip("nltk")
    posts = {
        "investing": [
            StubPost(
                "a",
                "Huge rally, best gains in months, incredibly bullish",
                "Everything is up and the outlook is excellent.",
                _ago(0),
                comments=[
                    StubComment("Fantastic news, wonderful quarter!", _ago(0)),
                    StubComment("   ", _ago(0)),  # blank: must be skipped
                ],
            ),
            StubPost(
                "b",
                "Terrible crash, catastrophic losses, panic everywhere",
                "This is a disaster and I am terrified.",
                _ago(1),
            ),
        ],
        "stocks": [
            StubPost(
                "c",
                "Awful selloff, horrible sentiment, dreadful week",
                "Losses keep piling up.",
                _ago(1),
            ),
            StubPost(
                "d",
                "This post is far too old to count",
                "Stale.",
                _ago(400),  # outside the lookback window
            ),
        ],
    }
    pipeline = engine.DataPipeline(reddit_client_id="id", reddit_secret="secret")
    pipeline.reddit = StubReddit(posts)
    pipeline.subreddits = ("investing", "stocks")
    return pipeline


def test_fetch_social_sentiment_aggregates_reddit_to_a_daily_mean(reddit_pipeline):
    df = reddit_pipeline.fetch_social_sentiment(lookback_days=30)

    assert list(df.columns) == [
        "Sentiment_Avg",
        "Sentiment_Volume",
        "Sentiment_Momentum",
    ]
    assert len(df) == 30
    assert df.index.max().date() == datetime.date.today()
    assert reddit_pipeline.reddit.requested == ["investing", "stocks"]

    today = pd.Timestamp(datetime.date.today())
    yesterday = today - pd.Timedelta(days=1)

    # Today: one bullish post plus its one non-blank comment.
    assert df.loc[today, "Sentiment_Volume"] == 2
    assert df.loc[today, "Sentiment_Avg"] > 0.3

    # Yesterday: two bearish posts from two subreddits.
    assert df.loc[yesterday, "Sentiment_Volume"] == 2
    assert df.loc[yesterday, "Sentiment_Avg"] < -0.3

    # Momentum is the 7-day change in the daily average.
    assert df["Sentiment_Momentum"].iloc[-1] == pytest.approx(
        df["Sentiment_Avg"].iloc[-1] - df["Sentiment_Avg"].iloc[-8]
    )


def test_fetch_social_sentiment_marks_unobserved_days(reddit_pipeline):
    df = reddit_pipeline.fetch_social_sentiment(lookback_days=30)

    # Reddit only exposes recent listings, so most of the window is unobserved.
    # Those days must read as neutral-with-no-data, not as invented sentiment.
    unobserved = df[df["Sentiment_Volume"] == 0]
    assert len(unobserved) == 28
    assert (unobserved["Sentiment_Avg"] == 0.0).all()

    # The stale post is outside the lookback window and is never scored.
    assert df["Sentiment_Volume"].sum() == 4


def test_fetch_social_sentiment_expands_comments_only_for_recent_posts(reddit_pipeline):
    df = reddit_pipeline.fetch_social_sentiment(lookback_days=30, comment_post_limit=0)

    # With no comment expansion, only the three in-window posts are scored.
    assert df["Sentiment_Volume"].sum() == 3


def test_fetch_social_sentiment_raises_when_nothing_is_scoreable():
    pipeline = engine.DataPipeline(reddit_client_id="id", reddit_secret="secret")
    pipeline.reddit = StubReddit({})
    pipeline.subreddits = ("investing",)

    with pytest.raises(RuntimeError, match="no scoreable posts"):
        pipeline.fetch_social_sentiment(lookback_days=30)


def test_fetch_social_sentiment_survives_one_broken_subreddit(reddit_pipeline):
    class HalfBrokenReddit(StubReddit):
        def subreddit(self, name):
            if name == "stocks":
                raise RuntimeError("403 Forbidden")
            return super().subreddit(name)

    broken = HalfBrokenReddit(reddit_pipeline.reddit._posts)
    reddit_pipeline.reddit = broken

    df = reddit_pipeline.fetch_social_sentiment(lookback_days=30)

    # r/investing still lands: two posts plus one non-blank comment.
    assert df["Sentiment_Volume"].sum() == 3


# ------------------------------------------------------------------
# Sentiment fallback
# ------------------------------------------------------------------
def test_neutral_sentiment_frame_is_flat_not_random():
    df = engine.neutral_sentiment_frame(lookback_days=30)

    assert list(df.columns) == ["Sentiment_Avg", "Sentiment_Volume", "Sentiment_Momentum"]
    assert len(df) == 30
    assert (df["Sentiment_Avg"] == 0.0).all()
    assert (df["Sentiment_Volume"] == 0).all()


def test_social_sentiment_requires_credentials():
    pipeline = engine.DataPipeline(
        fred_api_key=None, reddit_client_id=None, reddit_secret=None
    )

    assert pipeline.reddit is None
    with pytest.raises(RuntimeError, match="REDDIT_CLIENT_ID"):
        pipeline.fetch_social_sentiment()
    with pytest.raises(RuntimeError, match="FRED_API_KEY"):
        pipeline.fetch_macro_data()
