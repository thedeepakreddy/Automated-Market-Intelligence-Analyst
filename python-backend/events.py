"""Macro event awareness: does this call span an event that moves markets?

Two sources, deliberately different in kind:

  * FOMC meeting dates come from a published schedule. They are hardcoded here
    because the Fed publishes them years ahead and there is no free API worth a
    dependency - but a hardcoded calendar rots, so it is overridable via
    MACRO_CALENDAR_PATH and every consumer is told how stale it is.

  * Macro release windows are derived from the data itself: a forward-filled
    FRED series only steps when a new figure lands, so the step dates are the
    releases. No hardcoding, and it stays correct as the data grows.

Caveat worth carrying: a series forward-filled from its *reference* date steps
on the reference date, not the publication date (January CPI steps on Jan 1,
though it is published mid-February). Until the pipeline moves to point-in-time
vintages, treat these windows as approximate.
"""

import datetime
import json
import logging
import os

import pandas as pd

LOG = logging.getLogger("market_engine.events")

# Published FOMC meeting dates (decision day). VERIFY ANNUALLY against
# federalreserve.gov/monetarypolicy/fomccalendars.htm - dates beyond the
# current year are the Fed's advance schedule and do occasionally move.
FOMC_DATES = (
    # 2024
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12",
    "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    # 2025
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
    # 2026 (advance schedule - confirm before relying on it)
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16",
)

CALENDAR_SOURCE = "built-in FOMC schedule (verify annually)"


def fomc_dates():
    """FOMC decision days as a sorted DatetimeIndex.

    MACRO_CALENDAR_PATH may point at a JSON file - either a bare list of
    ISO dates or ``{"fomc": [...]}`` - to override the built-in schedule
    without a code change.
    """
    global CALENDAR_SOURCE
    path = os.environ.get("MACRO_CALENDAR_PATH")
    dates = FOMC_DATES
    CALENDAR_SOURCE = "built-in FOMC schedule (verify annually)"

    if path:
        try:
            with open(path) as handle:
                payload = json.load(handle)
            loaded = payload.get("fomc", []) if isinstance(payload, dict) else payload
            if loaded:
                dates = tuple(loaded)
                CALENDAR_SOURCE = f"override file {path}"
        except Exception as exc:
            LOG.warning("Could not read MACRO_CALENDAR_PATH=%s (%s); using built-in", path, exc)

    return pd.DatetimeIndex(sorted(pd.to_datetime(list(dates)))).normalize()


def calendar_health(today=None):
    """How stale the calendar is - surfaced so nobody trusts it blindly."""
    dates = fomc_dates()
    today = pd.Timestamp(today or datetime.date.today()).normalize()
    future = dates[dates >= today]
    return {
        "source": CALENDAR_SOURCE,
        "last_known_date": dates[-1].date().isoformat() if len(dates) else None,
        "future_events_known": int(len(future)),
        "stale": bool(len(future) < 2),
        "note": "Fewer than two future FOMC dates known; refresh the calendar."
        if len(future) < 2
        else None,
    }


def events_in_window(start, end):
    """FOMC decision days falling inside [start, end]."""
    start = pd.Timestamp(start).normalize()
    end = pd.Timestamp(end).normalize()
    if end < start:
        start, end = end, start
    dates = fomc_dates()
    hits = dates[(dates >= start) & (dates <= end)]
    return [
        {"type": "FOMC", "date": stamp.date().isoformat()} for stamp in hits
    ]


def forward_window_events(as_of, sessions=7, session_index=None):
    """Events the *next* `sessions` trading days will run through.

    With a session index the window is exact; without one it falls back to a
    calendar-day approximation, which is flagged in the payload.
    """
    as_of = pd.Timestamp(as_of).normalize()

    approximate = True
    end = as_of + pd.Timedelta(days=round(sessions * 7 / 5))
    if session_index is not None and len(session_index):
        index = pd.DatetimeIndex(session_index).normalize()
        future = index[index > as_of]
        if len(future) >= sessions:
            end, approximate = future[sessions - 1], False
        elif len(future):
            end, approximate = future[-1], True

    events = events_in_window(as_of, end)
    return {
        "from": as_of.date().isoformat(),
        "to": end.date().isoformat(),
        "sessions": sessions,
        "approximate_window": approximate,
        "events": events,
        "has_event": bool(events),
        "note": (
            f"This call spans {', '.join(event['type'] + ' ' + event['date'] for event in events)}."
            if events
            else "No scheduled FOMC decision inside this call's window."
        ),
    }


def macro_release_dates(macro_df, columns=None):
    """Dates a forward-filled macro series stepped, i.e. when new data landed."""
    if macro_df is None or macro_df.empty:
        return {}

    columns = columns or [
        column for column in macro_df.columns if not column.endswith("_MoM_Change")
    ]
    releases = {}
    for column in columns:
        if column not in macro_df.columns:
            continue
        series = macro_df[column].astype(float).dropna()
        stepped = series[series.diff().fillna(0) != 0]
        if len(stepped):
            releases[column] = pd.DatetimeIndex(stepped.index).normalize()
    return releases


def conditional_accuracy(resolved, sessions=7, session_index=None):
    """Split the realised hit rate by whether the call spanned an FOMC meeting.

    This is the honest version of "our model is 57% accurate": it asks whether
    that number survives the weeks when policy actually moved.
    """
    scored = [
        row
        for row in (resolved or [])
        if row.get("correct") is not None and row.get("prediction") in ("UP", "DOWN")
    ]
    if not scored:
        return None

    with_event, without_event = [], []
    for row in scored:
        as_of = row.get("as_of_date")
        if not as_of:
            continue
        window = forward_window_events(as_of, sessions=sessions, session_index=session_index)
        (with_event if window["has_event"] else without_event).append(bool(row["correct"]))

    def summarise(bucket):
        if not bucket:
            return None
        return {"n": len(bucket), "hit_rate": sum(bucket) / len(bucket)}

    event_stats = summarise(with_event)
    quiet_stats = summarise(without_event)

    return {
        "fomc_weeks": event_stats,
        "quiet_weeks": quiet_stats,
        "gap": (
            event_stats["hit_rate"] - quiet_stats["hit_rate"]
            if event_stats and quiet_stats
            else None
        ),
        "note": _conditional_note(event_stats, quiet_stats),
    }


def _conditional_note(event_stats, quiet_stats):
    if not event_stats or not quiet_stats:
        return "Not enough resolved calls in both buckets to compare yet."
    if min(event_stats["n"], quiet_stats["n"]) < 10:
        return (
            f"{event_stats['n']} FOMC-week calls versus {quiet_stats['n']} quiet-week calls - "
            "too few to read anything into the gap."
        )
    gap = event_stats["hit_rate"] - quiet_stats["hit_rate"]
    if abs(gap) < 0.05:
        return "Accuracy holds up about the same through FOMC weeks."
    worse = "worse" if gap < 0 else "better"
    return (
        f"Accuracy is {abs(gap) * 100:.1f}pp {worse} on calls spanning an FOMC decision "
        f"({event_stats['hit_rate'] * 100:.0f}% versus {quiet_stats['hit_rate'] * 100:.0f}%)."
    )
