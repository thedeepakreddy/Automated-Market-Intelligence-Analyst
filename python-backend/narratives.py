"""What the crowd is talking about, not just how it feels.

VADER crushes a thread into one scalar and throws away the interesting part:
*what* people are arguing about. This module keeps that part.

  extract_themes   cluster recent posts into named themes and track their share
  answer_question  answer questions about past runs from the stored record

Gemini does the work when a key is configured; both functions fall back to a
deterministic, dependency-free path otherwise, and the ``source`` field always
says which one ran so a keyword count is never mistaken for an LLM reading.
"""

import collections
import json
import logging
import os
import re

LOG = logging.getLogger("market_engine.narratives")

MAX_DOCUMENTS = 220  # keep the prompt bounded; newest first

# Deliberately includes finance filler ("market", "stock") - those words are in
# every post and carry no information about *which* story is running.
STOPWORDS = frozenset(
    """
    a an and are as at be been but by can could did do does for from had has have
    he her his how i if in into is it its me my no not of on or our out she so
    such than that the their them then there these they this those to too us was
    we were what when where which while who why will with would you your about
    just like get got going make really think know see say said want need way
    time day week month year today lot much many more most any some all one two
    market markets stock stocks share shares price prices buy sell hold thoughts
    question discussion advice help anyone everyone guys please thanks edit
    """.split()
)

TICKER_PATTERN = re.compile(r"\$?\b[A-Z]{2,5}\b")
WORD_PATTERN = re.compile(r"[a-z][a-z'\-]{2,}")


def extract_themes(documents, max_themes=6, model_name=None):
    """Name the stories running through recent posts.

    ``documents`` are dicts with at least ``text``; ``score`` and ``date`` are
    used when present. Returns ``{"themes": [...], "source": ...}``.
    """
    documents = [
        document
        for document in (documents or [])
        if (document.get("text") or "").strip()
    ][:MAX_DOCUMENTS]

    if not documents:
        return {"themes": [], "source": "unavailable", "n_documents": 0}

    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        themes = _gemini_themes(documents, max_themes, api_key, model_name)
        if themes is not None:
            return {
                "themes": themes,
                "source": f"gemini:{model_name or os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')}",
                "n_documents": len(documents),
            }

    return {
        "themes": _keyword_themes(documents, max_themes),
        "source": "keyword_frequency (no Gemini key, or the call failed)",
        "n_documents": len(documents),
    }


def _gemini_themes(documents, max_themes, api_key, model_name):
    """Ask Gemini to group posts into themes. None on any failure."""
    try:
        import google.generativeai as genai

        model_name = model_name or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        corpus = "\n".join(
            f"- {(document.get('text') or '')[:220]}" for document in documents
        )
        prompt = (
            "Below are recent retail-investor forum posts. Identify the "
            f"{max_themes} distinct topics being discussed most.\n\n"
            "Return ONLY a JSON array, no prose and no code fence. Each element:\n"
            '{"theme": "<3-5 word topic name>", "mentions": <int, how many posts '
            'touch it>, "stance": "bullish"|"bearish"|"mixed", '
            '"summary": "<one sentence on what is being said>"}\n\n'
            "Name concrete topics (a sector, a policy, a specific worry), never "
            'generic ones like "market discussion".\n\nPOSTS:\n' + corpus
        )

        genai.configure(api_key=api_key)
        response = genai.GenerativeModel(model_name).generate_content(prompt)
        parsed = _parse_json_array(response.text)
        if not parsed:
            return None

        total = len(documents)
        themes = []
        for item in parsed[:max_themes]:
            if not isinstance(item, dict) or not item.get("theme"):
                continue
            mentions = item.get("mentions")
            mentions = int(mentions) if isinstance(mentions, (int, float)) else None
            themes.append(
                {
                    "theme": str(item["theme"])[:60],
                    "mentions": mentions,
                    "share": round(mentions / total, 4) if mentions and total else None,
                    "stance": item.get("stance")
                    if item.get("stance") in ("bullish", "bearish", "mixed")
                    else "mixed",
                    "summary": str(item.get("summary", ""))[:280],
                }
            )
        return themes or None
    except Exception as exc:
        LOG.warning("Gemini theme extraction failed (%s); using keyword counts", exc)
        return None


def _parse_json_array(text):
    """Pull a JSON array out of an LLM reply that may be fenced or chatty."""
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned.strip())
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("["), cleaned.rfind("]")
        if start == -1 or end <= start:
            return None
        try:
            parsed = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, list) else None


def _keyword_themes(documents, max_themes):
    """Deterministic fallback: most distinctive repeated phrases.

    Bigrams first because they carry topics ("credit spreads", "rate cut")
    where single words mostly carry noise.
    """
    bigrams = collections.Counter()
    tickers = collections.Counter()
    stance_by_phrase = collections.defaultdict(list)

    for document in documents:
        text = document.get("text") or ""
        score = document.get("score")

        for ticker in TICKER_PATTERN.findall(text):
            symbol = ticker.lstrip("$")
            if symbol.lower() not in STOPWORDS and not symbol.isdigit():
                tickers[symbol] += 1

        words = [
            word
            for word in WORD_PATTERN.findall(text.lower())
            if word not in STOPWORDS
        ]
        for first, second in zip(words, words[1:]):
            phrase = f"{first} {second}"
            bigrams[phrase] += 1
            if score is not None:
                stance_by_phrase[phrase].append(score)

    total = len(documents)
    themes = []
    for phrase, count in bigrams.most_common(max_themes * 3):
        if count < 2:
            continue
        scores = stance_by_phrase.get(phrase, [])
        mean = sum(scores) / len(scores) if scores else 0.0
        themes.append(
            {
                "theme": phrase,
                "mentions": count,
                "share": round(count / total, 4) if total else None,
                "stance": "bullish" if mean > 0.15 else "bearish" if mean < -0.15 else "mixed",
                "summary": f"Appears in {count} of {total} recent posts.",
            }
        )
        if len(themes) >= max_themes:
            break

    if tickers:
        top = ", ".join(f"{symbol} ({count})" for symbol, count in tickers.most_common(5))
        themes.append(
            {
                "theme": "Most-mentioned tickers",
                "mentions": sum(count for _, count in tickers.most_common(5)),
                "share": None,
                "stance": "mixed",
                "summary": top,
            }
        )
    return themes


def theme_shift(current_themes, previous_themes):
    """Which stories are new, growing, or gone since the last run."""
    current = {theme["theme"].lower(): theme for theme in (current_themes or [])}
    previous = {theme["theme"].lower(): theme for theme in (previous_themes or [])}
    if not current:
        return []

    shifts = []
    for key, theme in current.items():
        before = previous.get(key)
        mentions = theme.get("mentions") or 0
        if before is None:
            shifts.append({"theme": theme["theme"], "status": "new", "change": None})
        else:
            was = before.get("mentions") or 0
            change = (mentions - was) / was if was else None
            shifts.append(
                {
                    "theme": theme["theme"],
                    "status": "growing" if change and change > 0.25 else "fading" if change and change < -0.25 else "steady",
                    "change": round(change, 3) if change is not None else None,
                }
            )
    for key, theme in previous.items():
        if key not in current:
            shifts.append({"theme": theme["theme"], "status": "gone", "change": None})
    return shifts


# ==========================================
# Ask the analyst - Q&A over the stored record
# ==========================================
def answer_question(question, runs, model_name=None):
    """Answer a question about past runs, grounded only in the stored record.

    The runs are the evidence; nothing else is consulted. Without a Gemini key
    this degrades to returning the relevant runs so the caller can still show
    the user something true.
    """
    question = (question or "").strip()
    if not question:
        return {"answer": None, "source": "error", "error": "empty question"}
    if not runs:
        return {
            "answer": "There are no stored prediction runs to answer from yet.",
            "source": "no_data",
            "used_runs": [],
        }

    relevant = _select_runs(question, runs)
    context = "\n".join(_summarise_run(run) for run in relevant)
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        return {
            "answer": (
                "No Gemini key is configured, so here is the raw record for the runs "
                "most relevant to that question:\n\n" + context
            ),
            "source": "record_only (GEMINI_API_KEY not set)",
            "used_runs": [run.get("as_of_date") for run in relevant],
        }

    try:
        import google.generativeai as genai

        model_name = model_name or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        prompt = (
            "You are answering questions about a market model's own prediction "
            "history. Use ONLY the run records below. If they do not contain the "
            "answer, say so plainly - never speculate about markets, and never "
            "give investment advice.\n\n"
            f"RUN RECORDS:\n{context}\n\nQUESTION: {question}\n\n"
            "Answer in under 150 words, citing the relevant dates."
        )
        genai.configure(api_key=api_key)
        response = genai.GenerativeModel(model_name).generate_content(prompt)
        return {
            "answer": response.text,
            "source": f"gemini:{model_name}",
            "used_runs": [run.get("as_of_date") for run in relevant],
        }
    except Exception as exc:
        LOG.warning("Gemini Q&A failed (%s); returning the raw record", exc)
        return {
            "answer": "The language model was unavailable, so here is the raw record:\n\n" + context,
            "source": f"record_only ({exc})",
            "used_runs": [run.get("as_of_date") for run in relevant],
        }


def _select_runs(question, runs, limit=12):
    """Pick runs to ground the answer: anything whose date is named, else recent."""
    mentioned = set(re.findall(r"\d{4}-\d{2}(?:-\d{2})?", question))
    months = {
        name: index
        for index, name in enumerate(
            "january february march april may june july august september october november december".split(),
            start=1,
        )
    }
    lowered = question.lower()
    for name, index in months.items():
        if name in lowered:
            mentioned.add(f"-{index:02d}-")

    if mentioned:
        matched = [
            run
            for run in runs
            if any(token.strip("-") in (run.get("as_of_date") or "") for token in mentioned)
        ]
        if matched:
            return matched[-limit:]
    return runs[-limit:]


def _summarise_run(run):
    drivers = ", ".join(
        f"{item['feature']} {item['value']:+.3f}"
        for item in (run.get("top_features") or [])[:4]
    )
    outcome = run.get("outcome") or {}
    verdict = ""
    if outcome.get("correct") is not None:
        realized = outcome.get("realized_return")
        verdict = (
            f" Outcome: {'correct' if outcome['correct'] else 'wrong'}"
            + (f", realised {realized * 100:+.2f}%." if realized is not None else ".")
        )
    confidence = run.get("confidence")
    confidence_text = f"{confidence * 100:.1f}%" if isinstance(confidence, (int, float)) else "n/a"
    return (
        f"[{run.get('as_of_date')}] {run.get('prediction')} at {confidence_text} confidence. "
        f"Drivers: {drivers or 'n/a'}.{verdict}"
    )
