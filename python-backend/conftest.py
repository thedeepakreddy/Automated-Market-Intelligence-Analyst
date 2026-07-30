"""Test-suite bootstrap.

These have to be set before ``engine`` is imported: the module starts
APScheduler and opens SQLite at import time, and neither belongs in a test run.
Living in ``python-backend/`` also puts that directory on ``sys.path``, so the
tests can ``import engine`` directly.
"""

import os
import tempfile

os.environ.setdefault("DISABLE_SCHEDULER", "1")
os.environ.setdefault(
    "MARKET_DB_PATH",
    os.path.join(tempfile.mkdtemp(prefix="market-engine-tests-"), "predictions.db"),
)
