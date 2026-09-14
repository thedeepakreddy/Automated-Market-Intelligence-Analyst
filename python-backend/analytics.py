"""Analytics layer: the things that make a prediction useful even when it is wrong.

Everything here is a pure function over data the pipeline already produces - no
network, no model training, no database. That keeps it cheap to test and safe to
call from a request handler.

  compute_delta        what changed since the previous run, and why
  find_analogues       which historical sessions look like today
  label_regimes        coarse regime clustering over the state vector
  counterfactual       re-score the model on a perturbed feature row
  find_flip_points     how far each driver must move to change the call
  sentiment_divergence retail mood versus what price is actually doing
  build_scorecard      realised hit rate and empirical calibration
  surprise_index       macro releases versus a naive forecast
"""

import logging
import math

import numpy as np
import pandas as pd

LOG = logging.getLogger("market_engine.analytics")

# Columns describing "what kind of market is this" - used for analogues and
# regimes. Resolved leniently: a panel missing one of these still works.
STATE_FEATURES = (
    "^GSPC_Volatility_7",
    "^GSPC_RSI",
    "^GSPC_Daily_Return",
    "CL=F_Daily_Return",
    "GC=F_Daily_Return",
    "Sentiment_Avg",
)


def _present(frame, columns):
    return [column for column in columns if column in frame.columns]


def _safe_float(value):
    """None for anything JSON cannot represent (NaN, inf, non-numeric)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


# ==========================================
# 1. Delta - what changed since last run
# ==========================================
def compute_delta(current, previous, top_n=6):
    """Diff two prediction records into a human-readable "what changed".

    ``current``/``previous`` are the dicts ``load_latest_prediction`` returns.
    Returns None when there is no previous run to compare against - the first
    run of a fresh deployment has nothing to say here, and inventing a delta
    would be worse than omitting one.
    """
    if not previous or not current:
        return None

    current_prob = _safe_float(current.get("probability"))
    previous_prob = _safe_float(previous.get("probability"))
    signal_changed = current.get("prediction") != previous.get("prediction")

    current_features = {
        item["feature"]: _safe_float(item.get("value"))
        for item in current.get("top_features") or []
    }
    previous_features = {
        item["feature"]: _safe_float(item.get("value"))
        for item in previous.get("top_features") or []
    }

    movements = []
    for name in set(current_features) | set(previous_features):
        now = current_features.get(name)
        before = previous_features.get(name)
        if now is None and before is None:
            continue
        change = (now or 0.0) - (before or 0.0)
        movements.append(
            {
                "feature": name,
                "current": now,
                "previous": before,
                "change": change,
                "status": "entered"
                if before is None
                else "exited"
                if now is None
                else "held",
            }
        )

    movements.sort(key=lambda item: abs(item["change"]), reverse=True)
    movements = movements[:top_n]

    return {
        "compared_with": previous.get("generated_at"),
        "compared_with_as_of": previous.get("as_of_date"),
        "signal_changed": signal_changed,
        "previous_signal": previous.get("prediction"),
        "current_signal": current.get("prediction"),
        "probability_change": None
        if current_prob is None or previous_prob is None
        else current_prob - previous_prob,
        "confidence_change": _delta_of(current, previous, "confidence"),
        "movements": movements,
        "headline": _delta_headline(current, previous, signal_changed, movements),
    }


def _delta_of(current, previous, key):
    now = _safe_float(current.get(key))
    before = _safe_float(previous.get(key))
    return None if now is None or before is None else now - before


def _delta_headline(current, previous, signal_changed, movements):
    """One sentence a human can read without decoding the numbers."""
    if signal_changed:
        opening = (
            f"Signal flipped {previous.get('prediction')} to {current.get('prediction')}"
        )
    else:
        opening = f"Signal held at {current.get('prediction')}"

    probability_change = _delta_of(current, previous, "probability")
    if probability_change is not None and abs(probability_change) >= 0.005:
        direction = "rose" if probability_change > 0 else "fell"
        opening += f"; P(up) {direction} {abs(probability_change) * 100:.1f}pp"

    if not movements:
        return opening + "."

    driver = movements[0]
    verb = {
        "entered": "entered the drivers at",
        "exited": "dropped out of the drivers from",
        "held": "moved to",
    }[driver["status"]]
    value = driver["current"] if driver["status"] != "exited" else driver["previous"]
    return f"{opening}. Biggest mover: {driver['feature']} {verb} {value:+.3f}."


# ==========================================
# 2. Historical analogues and regimes
# ==========================================
def find_analogues(panel, as_of=None, k=3, exclusion_days=45, horizon=7, price_col="^GSPC_Close"):
    """Nearest historical sessions to `as_of`, by standardised state vector.

    Deliberately not a prediction: it reports what the market looked like then
    and what happened next, and lets the reader draw the inference. Recent
    sessions are excluded because yesterday always resembles today.
    """
    columns = _present(panel, STATE_FEATURES)
    if not columns or len(panel) < exclusion_days + k + horizon + 5:
        return []

    state = panel[columns].astype(float)
    standardised = (state - state.mean()) / state.std(ddof=0).replace(0, np.nan)
    standardised = standardised.dropna(how="any")
    if standardised.empty:
        return []

    target_label = as_of if as_of is not None else standardised.index[-1]
    if target_label not in standardised.index:
        target_label = standardised.index[-1]
    target = standardised.loc[target_label]

    candidates = standardised[standardised.index < target_label]
    if exclusion_days:
        cutoff = target_label - pd.Timedelta(days=exclusion_days)
        candidates = candidates[candidates.index < cutoff]
    if candidates.empty:
        return []

    distances = np.sqrt(((candidates - target) ** 2).sum(axis=1))
    scale = math.sqrt(len(columns))  # ~1 std per dimension, so similarity is comparable

    results = []
    for label in distances.nsmallest(k).index:
        results.append(
            {
                "date": _label(label),
                "distance": _safe_float(distances[label]),
                "similarity": _safe_float(max(0.0, 1.0 - distances[label] / (3 * scale))),
                "forward_return": _forward_return(panel, label, horizon, price_col),
                "state": {
                    column: _safe_float(panel.at[label, column]) for column in columns
                },
            }
        )
    return results


def _forward_return(panel, label, horizon, price_col):
    if price_col not in panel.columns:
        return None
    position = panel.index.get_loc(label)
    if not isinstance(position, int) or position + horizon >= len(panel):
        return None
    start = _safe_float(panel[price_col].iloc[position])
    end = _safe_float(panel[price_col].iloc[position + horizon])
    if not start or end is None:
        return None
    return end / start - 1


def label_regimes(panel, n_regimes=4, horizon=7, price_col="^GSPC_Close"):
    """Cluster sessions into coarse regimes and describe each one.

    Returns ``{"current": <id>, "regimes": [...]}``; the per-regime forward
    return is descriptive history, not a forecast for the current regime.
    """
    columns = _present(panel, STATE_FEATURES)
    if not columns or len(panel) < n_regimes * 10:
        return None

    try:
        from sklearn.cluster import KMeans
    except ImportError:  # pragma: no cover - sklearn is a hard dependency
        return None

    state = panel[columns].astype(float)
    standardised = ((state - state.mean()) / state.std(ddof=0).replace(0, np.nan)).dropna()
    if len(standardised) < n_regimes * 10:
        return None

    labels = KMeans(n_clusters=n_regimes, n_init=10, random_state=7).fit_predict(
        standardised.to_numpy()
    )
    assignments = pd.Series(labels, index=standardised.index)

    forward = None
    if price_col in panel.columns:
        prices = panel[price_col].astype(float)
        forward = (prices.shift(-horizon) / prices - 1).reindex(assignments.index)

    regimes = []
    for regime_id in range(n_regimes):
        members = assignments[assignments == regime_id]
        window = forward.loc[members.index].dropna() if forward is not None else pd.Series(dtype=float)
        centre = standardised.loc[members.index].mean()
        regimes.append(
            {
                "id": int(regime_id),
                "sessions": int(len(members)),
                "share": _safe_float(len(members) / len(assignments)),
                "label": _describe_regime(centre),
                "mean_forward_return": _safe_float(window.mean()) if len(window) else None,
                "up_rate": _safe_float((window > 0).mean()) if len(window) else None,
                "last_seen": _label(members.index.max()) if len(members) else None,
            }
        )

    return {
        "current": int(assignments.iloc[-1]),
        "current_since": _label(_regime_run_start(assignments)),
        "n_regimes": n_regimes,
        "regimes": regimes,
    }


def _regime_run_start(assignments):
    """First session of the current unbroken regime run."""
    current = assignments.iloc[-1]
    start = assignments.index[-1]
    for label, value in zip(reversed(assignments.index), reversed(assignments.tolist())):
        if value != current:
            break
        start = label
    return start


def _describe_regime(centre):
    """Name a cluster from its centroid, in the terms a reader thinks in."""
    volatility = centre.get("^GSPC_Volatility_7", 0.0)
    momentum = centre.get("^GSPC_Daily_Return", 0.0)
    mood = centre.get("Sentiment_Avg", 0.0)

    stress = "high-volatility" if volatility > 0.5 else "calm" if volatility < -0.3 else "average-volatility"
    drift = "rising" if momentum > 0.15 else "falling" if momentum < -0.15 else "rangebound"
    tone = " and bullish chatter" if mood > 0.5 else " and bearish chatter" if mood < -0.5 else ""
    return f"{stress}, {drift}{tone}"


# ==========================================
# 3. Counterfactuals - what would change the call
# ==========================================
def counterfactual(predict_proba, base_row, overrides, classify=None):
    """Re-score the model with some features overridden.

    ``predict_proba`` takes a one-row DataFrame and returns P(up).
    Unknown feature names are reported back rather than silently ignored, so a
    typo in the UI cannot look like "the model didn't care".
    """
    if base_row is None or base_row.empty:
        raise ValueError("no live feature row is available to perturb")

    known = set(base_row.columns)
    applied, rejected = {}, []
    perturbed = base_row.copy()

    for name, value in (overrides or {}).items():
        if name not in known:
            rejected.append(name)
            continue
        numeric = _safe_float(value)
        if numeric is None:
            rejected.append(name)
            continue
        perturbed.iloc[0, perturbed.columns.get_loc(name)] = numeric
        applied[name] = numeric

    baseline_probability = _safe_float(predict_proba(base_row))
    probability = _safe_float(predict_proba(perturbed))

    result = {
        "baseline_probability": baseline_probability,
        "probability": probability,
        "probability_change": None
        if probability is None or baseline_probability is None
        else probability - baseline_probability,
        "applied": applied,
        "rejected": rejected,
    }
    if classify is not None and probability is not None:
        result["baseline_signal"] = classify(baseline_probability)
        result["signal"] = classify(probability)
        result["signal_changed"] = result["signal"] != result["baseline_signal"]
    return result


def find_flip_points(predict_proba, base_row, features, history, classify, steps=41, span=3.0):
    """For each feature, the value at which the call changes - or None.

    Scans a span of +/- `span` historical standard deviations. A linear scan
    rather than a bisection because the response is not monotonic: a tree
    ensemble can flip back and forth, and we want the *nearest* flip.
    """
    if base_row is None or base_row.empty:
        return []

    baseline_probability = _safe_float(predict_proba(base_row))
    if baseline_probability is None:
        return []
    baseline_signal = classify(baseline_probability)

    results = []
    for name in features:
        if name not in base_row.columns or name not in history.columns:
            continue

        series = history[name].astype(float)
        deviation = _safe_float(series.std(ddof=0))
        current = _safe_float(base_row.iloc[0][name])
        if current is None or not deviation:
            continue

        nearest = None
        for candidate in np.linspace(current - span * deviation, current + span * deviation, steps):
            probe = base_row.copy()
            probe.iloc[0, probe.columns.get_loc(name)] = float(candidate)
            signal = classify(_safe_float(predict_proba(probe)))
            if signal != baseline_signal:
                distance = abs(candidate - current)
                if nearest is None or distance < nearest["distance"]:
                    nearest = {
                        "value": float(candidate),
                        "distance": distance,
                        "signal": signal,
                    }

        results.append(
            {
                "feature": name,
                "current": current,
                "baseline_signal": baseline_signal,
                "flips_to": nearest["signal"] if nearest else None,
                "flips_at": nearest["value"] if nearest else None,
                "move_required": nearest["distance"] if nearest else None,
                "move_in_std": _safe_float(nearest["distance"] / deviation) if nearest else None,
            }
        )

    # Most fragile drivers first: the smallest move that changes the answer.
    results.sort(key=lambda item: (item["move_in_std"] is None, item["move_in_std"]))
    return results


# ==========================================
# 4. Sentiment divergence
# ==========================================
def sentiment_divergence(panel, window=20, sentiment_col="Sentiment_Avg", price_col="^GSPC_Close"):
    """Flag retail mood pulling away from what price is doing.

    Crowd euphoria while price deteriorates (and the reverse) is the
    configuration worth surfacing; agreement is not news.
    """
    if sentiment_col not in panel.columns or price_col not in panel.columns:
        return None
    if len(panel) < window * 2:
        return None

    sentiment = panel[sentiment_col].astype(float)
    momentum = panel[price_col].astype(float).pct_change(window)

    sentiment_z = _zscore(sentiment, window * 3)
    momentum_z = _zscore(momentum, window * 3)
    if sentiment_z is None or momentum_z is None:
        return None

    gap = sentiment_z - momentum_z
    if abs(gap) < 1.0:
        state, note = "aligned", "Sentiment and price momentum agree; nothing to flag."
    elif gap > 0:
        state, note = (
            "crowd_ahead_of_price",
            "Retail mood is running hotter than price action - historically a fade setup, not a confirmation.",
        )
    else:
        state, note = (
            "price_ahead_of_crowd",
            "Price is climbing while the crowd stays sour - the wall-of-worry configuration.",
        )

    return {
        "state": state,
        "divergence": _safe_float(gap),
        "sentiment_z": _safe_float(sentiment_z),
        "momentum_z": _safe_float(momentum_z),
        "window": window,
        "note": note,
    }


def _zscore(series, lookback):
    series = series.dropna()
    if len(series) < 5:
        return None
    window = series.iloc[-lookback:]
    deviation = window.std(ddof=0)
    if not deviation or not math.isfinite(deviation):
        return None
    return float((series.iloc[-1] - window.mean()) / deviation)


# ==========================================
# 5. Scorecard - the realised record
# ==========================================
def build_scorecard(resolved, bins=(0.5, 0.55, 0.6, 0.65, 0.7, 1.01)):
    """Aggregate resolved predictions into a hit rate and a calibration curve.

    Calibration is measured, not modelled: each bucket reports how often calls
    at that stated confidence actually came true. `n` travels with every number
    because a 100% hit rate on 2 calls is not a hit rate.
    """
    rows = [row for row in (resolved or []) if row.get("correct") is not None]
    directional = [row for row in rows if row.get("prediction") in ("UP", "DOWN")]

    scorecard = {
        "n_resolved": len(rows),
        "n_directional": len(directional),
        "hit_rate": _mean([row["correct"] for row in directional]),
        "coverage": _mean([row.get("prediction") in ("UP", "DOWN") for row in rows]),
        "by_confidence": [],
        "by_signal": {},
        "recent": rows[-20:],
    }

    for lower, upper in zip(bins, bins[1:]):
        bucket = [
            row
            for row in directional
            if lower <= (row.get("confidence") or 0) < upper
        ]
        if not bucket:
            continue
        scorecard["by_confidence"].append(
            {
                "bucket": f"{lower * 100:.0f}-{min(upper, 1.0) * 100:.0f}%",
                "stated": _mean([row["confidence"] for row in bucket]),
                "realised": _mean([row["correct"] for row in bucket]),
                "n": len(bucket),
            }
        )

    for signal in ("UP", "DOWN", "UNCERTAIN"):
        bucket = [row for row in rows if row.get("prediction") == signal]
        if bucket:
            scorecard["by_signal"][signal] = {
                "n": len(bucket),
                "hit_rate": _mean([row["correct"] for row in bucket]),
                "mean_forward_return": _mean(
                    [row.get("realized_return") for row in bucket if row.get("realized_return") is not None]
                ),
            }

    # Calibration error: mean gap between stated confidence and realised rate.
    gaps = [
        abs(entry["stated"] - entry["realised"]) * entry["n"]
        for entry in scorecard["by_confidence"]
        if entry["stated"] is not None and entry["realised"] is not None
    ]
    counted = sum(entry["n"] for entry in scorecard["by_confidence"])
    scorecard["calibration_error"] = _safe_float(sum(gaps) / counted) if counted else None
    scorecard["verdict"] = _scorecard_verdict(scorecard)
    return scorecard


def _scorecard_verdict(scorecard):
    """Say plainly whether the record means anything yet. It usually does not."""
    n = scorecard["n_directional"]
    hit_rate = scorecard["hit_rate"]
    if not n or hit_rate is None:
        return "No resolved directional calls yet. Nothing to judge."
    if n < 20:
        return (
            f"{n} resolved directional calls is too few to distinguish skill from luck. "
            "Treat the hit rate as provisional."
        )
    # Two-sided binomial sanity check against a coin flip.
    spread = 1.96 * math.sqrt(0.25 / n)
    if abs(hit_rate - 0.5) < spread:
        return (
            f"Hit rate {hit_rate * 100:.1f}% over {n} calls is inside the range a coin "
            "flip would produce. No demonstrated edge."
        )
    direction = "above" if hit_rate > 0.5 else "below"
    return (
        f"Hit rate {hit_rate * 100:.1f}% over {n} calls sits {direction} the coin-flip "
        "band, which is suggestive but still a small sample."
    )


def _mean(values):
    numbers = [float(value) for value in values if value is not None]
    return _safe_float(sum(numbers) / len(numbers)) if numbers else None


# ==========================================
# 6. Macro surprise index
# ==========================================
def surprise_index(macro_df, series_names, lookback=365):
    """Surprise of each macro release against a naive random-walk forecast.

    A real surprise index scores releases against published consensus, which is
    not freely available. This scores them against "the last value", which is a
    documented proxy - and it is labelled as such everywhere it surfaces so it
    is never mistaken for the real thing.
    """
    if macro_df is None or macro_df.empty:
        return None

    entries = []
    for name in series_names:
        if name not in macro_df.columns:
            continue
        series = macro_df[name].astype(float).dropna()
        # Daily frame is forward-filled from a monthly release: changes only at
        # a release, so the distinct steps are the releases.
        releases = series[series.diff() != 0]
        if len(releases) < 6:
            continue

        changes = releases.diff().dropna()
        recent = changes.iloc[-int(max(3, lookback / 30)) :]
        deviation = _safe_float(changes.std(ddof=0))
        latest = _safe_float(changes.iloc[-1])
        if latest is None or deviation is None:
            continue

        # A series whose releases barely vary (a policy rate held flat for
        # months, or a synthetic straight line) has a denominator near zero,
        # and dividing by it produces a "surprise" in the trillions. There is
        # no dispersion to score against, so there is no surprise to report.
        typical = _safe_float(changes.abs().median()) or 0.0
        if deviation < max(1e-12, typical * 1e-6):
            LOG.debug("Skipping %s in the surprise index: releases show no dispersion", name)
            continue

        entries.append(
            {
                "series": name,
                "latest_change": latest,
                "surprise_z": _safe_float(latest / deviation),
                "released_on": _label(changes.index[-1]),
                "recent_mean_change": _safe_float(recent.mean()),
            }
        )

    if not entries:
        return None

    scores = [entry["surprise_z"] for entry in entries if entry["surprise_z"] is not None]
    return {
        "index": _safe_float(sum(scores) / len(scores)) if scores else None,
        "method": "naive_random_walk_forecast",
        "caveat": "Scored against the previous release, not against published consensus.",
        "components": sorted(
            entries, key=lambda entry: abs(entry["surprise_z"] or 0), reverse=True
        ),
    }


def _label(value):
    if value is None:
        return None
    return value.date().isoformat() if hasattr(value, "date") else str(value)
