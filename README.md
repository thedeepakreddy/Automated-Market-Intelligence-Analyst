# Automated Market Intelligence Analyst

An end-to-end quantitative research system that forecasts the 7-day directional move of the S&P 500 by fusing price action, macroeconomic releases, and social sentiment into an explainable ensemble model, then publishes the output through a production-deployed research dashboard.

Repository: https://github.com/thedeepakreddy/Automated-Market-Intelligence-Analyst

---
[dashboard](/Dashboard.png)

## Overview

Most retail-facing market models stop at a prediction. A research desk needs three things a prediction alone cannot provide: a defensible data lineage, a validation scheme that respects time, and an explanation of *why* the model is positioned the way it is.

This project is built around those three requirements. It ingests four asset series and five macro indicators, engineers a momentum and volatility feature set, trains a gradient-boosted tree and a recurrent neural network on a strictly chronological split, blends their probabilities into a single directional call with an explicit uncertainty band, and attributes that call back to individual features using SHAP. A scheduler re-runs the pipeline autonomously, and a language model drafts the weekly outlook note in the format of a desk research memo.

The result is a working analogue of the workflow an analyst runs manually every week, compressed into a repeatable, auditable pipeline.

---

## System Architecture

```text
  Data Layer                Feature Layer            Model Layer              Delivery Layer
+--------------+        +-------------------+    +-----------------+    +--------------------+
| yfinance     |        | Momentum: SMA     |    | XGBoost         |    | Flask REST API     |
| ^GSPC ^IXIC  |        | 7 / 14 / 30       |    | (tabular signal)|    |                    |
| GC=F  CL=F   | -----> |                   | -->|                 | -->| React dashboard    |
|              |        | Volatility, RSI   |    | LSTM 64 -> 32   |    | (Vite, Recharts)   |
| FRED macro   |        | Bollinger Bands   |    | (sequential)    |    |                    |
| CPI UNRATE   | -----> | Macro MoM deltas  | -->|                 | -->| Weekly PDF memo    |
| FEDFUNDS GDP |        | Sentiment moment. |    | Probability     |    | (Gemini +          |
| UMCSENT      |        | Lags 1/3/7/14     |    | ensemble        |    |  ReportLab)        |
|              |        |                   |    |        |        |    |                    |
| Reddit (praw)| -----> | Target: 7d fwd    | -->|      SHAP       | -->| APScheduler        |
| sentiment    |        | direction, binary |    | attribution     |    | (30-min refresh)   |
+--------------+        +-------------------+    +-----------------+    +--------------------+
```

---

## Data Sources

| Source | Series | Purpose |
| --- | --- | --- |
| yfinance | `^GSPC`, `^IXIC`, `GC=F`, `CL=F` | Equity benchmark, tech beta, and the gold/oil cross-asset risk signal |
| FRED (`fredapi`) | CPIAUCSL, UNRATE, FEDFUNDS, A191RL1Q225SBEA, UMCSENT | Inflation, labour, policy rate, growth, and consumer confidence regime context |
| Reddit (`praw`) | Retail finance discussion | Crowd positioning and sentiment momentum |

Macro series publish at monthly or quarterly frequency, so they are resampled to a daily index and forward-filled. This deliberately avoids look-ahead: a value is only carried forward from its release date, never interpolated backward from a future print.

---

## Feature Engineering

For each of the four instruments:

- **Trend**: 7, 14, and 30-day simple moving averages
- **Return and risk**: daily returns and 7-day rolling realised volatility
- **Mean reversion**: 14-period RSI and 20-period Bollinger Bands at two standard deviations
- **Memory**: S&P 500 close lagged 1, 3, 7, and 14 sessions

For each macro series:

- Level plus 30-day month-over-month percentage change, so the model reads the *direction of the surprise* rather than only the absolute level

**Target definition**: a binary label, one if the S&P 500 close seven sessions forward exceeds today's close, zero otherwise. Framing the problem as directional classification rather than point-estimate regression matches how a positioning decision is actually made, and avoids optimising a loss function nobody trades on.

---

## Modelling Approach

Two learners with complementary inductive biases:

- **XGBoost** captures non-linear interactions across the wide cross-sectional feature panel, which is where macro-versus-momentum conflicts show up.
- **LSTM** (64 units returning sequences into 32 units, sigmoid output, Adam, binary cross-entropy) captures temporal structure the tree model discards.

The two probabilities are averaged, and the blend is mapped to a three-state signal rather than a forced binary:

| Ensemble probability | Signal |
| --- | --- |
| Above 0.55 | UP |
| 0.45 to 0.55 | UNCERTAIN |
| Below 0.45 | DOWN |

The neutral band is the point of the design. A model forced to be long or short every week generates turnover with no edge; declining to take a view when the signal sits inside the noise band is a risk-management decision, not a modelling failure.

---

## Validation Methodology

Financial time series break the assumptions behind standard cross-validation, so the pipeline enforces:

- **Chronological 80/20 split.** The test set is strictly the most recent window. No shuffling.
- **`TimeSeriesSplit` with 5 folds** for in-sample tuning, so every fold trains only on data preceding its validation window.
- **No backward filling** of macro data across the release boundary.

These constraints lower headline accuracy relative to a randomly shuffled split. That is the intended trade-off: the number is lower because it is honest.

---

## Explainability

SHAP `TreeExplainer` runs against the gradient-boosted model to produce per-prediction feature attribution, surfaced in the dashboard as a ranked contribution chart.

This is the component that turns a score into research. It answers the question a portfolio manager asks first: is this call being driven by price momentum, by a shift in the rates and inflation complex, or by retail sentiment? A model that cannot answer that will not survive an investment committee.

---

## Evaluation Framework

The backtest layer is designed to report the metrics a strategy is actually judged on, benchmarked against buy-and-hold over the same window:

- Directional accuracy
- Sharpe ratio, that is risk-adjusted return rather than raw return
- Maximum drawdown
- Annualised return versus benchmark

Reporting return without drawdown and Sharpe alongside it is the most common way a backtest flatters itself, so all four move together throughout the interface.

---

## Research Dashboard

A dark-themed React interface built for scanning, in the layout convention of a terminal research page:

- **Directional call** with confidence, above the fold
- **Signal gauges** for the underlying component scores
- **Price chart** with the model's regime overlay
- **SHAP attribution chart** for the current prediction
- **Equity curve** comparing the strategy against buy-and-hold
- **Strategy metrics** panel covering accuracy, Sharpe, max drawdown, and annualised return
- **Weekly generated outlook** in desk-memo format
- **Prediction history table** for tracking calls against outcomes

---

## Automation

- **APScheduler** re-runs the pipeline on a 30-minute interval inside the Flask process, so the dashboard reflects the current session rather than a stale batch job.
- **Gemini** drafts the weekly outlook from the live prediction, confidence level, and top SHAP drivers, structured as current assessment, key risks, and supporting signals.
- **ReportLab** renders that outlook to a distributable PDF.
- **Flask** exposes a health endpoint for uptime monitoring on the deployment target.

---

## Tech Stack

| Layer | Technologies |
| --- | --- |
| Modelling | XGBoost, TensorFlow / Keras (LSTM), scikit-learn, SHAP |
| Data | pandas, NumPy, yfinance, fredapi, praw |
| Backend | Python 3.11, Flask, Gunicorn, APScheduler |
| Reporting | Google Gemini, ReportLab, Matplotlib |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, Recharts, Lucide |
| Deployment | Render Blueprint (`render.yaml`), pinned runtimes |

---

## Repository Structure

```text
.
├── src/                        React dashboard
│   ├── App.tsx                 Layout and composition
│   └── components/
│       ├── HeroSection.tsx     Directional call and confidence
│       ├── SignalGauges.tsx    Component signal scores
│       ├── PriceChart.tsx      Price series with model overlay
│       ├── ShapChart.tsx       Feature attribution
│       ├── BacktestChart.tsx   Strategy versus buy-and-hold
│       ├── MetricsTable.tsx    Accuracy, Sharpe, drawdown, return
│       ├── WeeklyReport.tsx    Generated market outlook
│       └── HistoryTable.tsx    Prediction log
├── python-backend/
│   ├── engine.py               Pipeline, features, ensemble, SHAP, API, scheduler
│   └── requirements.txt
├── render.yaml                 Blueprint for API and static frontend
├── python-version.txt          Pinned runtime, 3.11.9
├── vite.config.ts
└── package.json
```

---

## Running Locally

### Prerequisites

Python 3.11, Node 20, and API keys for FRED, Reddit, and Google Gemini. All three have free tiers.

### Backend

```bash
cd python-backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python engine.py
```

Serves on `http://localhost:5000`, or `$PORT` if set.

Credentials are read from the environment:

```bash
FRED_API_KEY=your_key
REDDIT_CLIENT_ID=your_id
REDDIT_CLIENT_SECRET=your_secret
REDDIT_USER_AGENT=market-intelligence-analyst/1.0
GEMINI_API_KEY=your_key
```

### Frontend

```bash
npm install
npm run dev
```

Serves on `http://localhost:3000`.

---

## Deployment

`render.yaml` defines both services as a single Render Blueprint:

- **`market-intelligence-api`** — Python web service on Gunicorn, with Python pinned to 3.11.9 for TensorFlow and Keras compatibility
- **`market-intelligence-frontend`** — static site built with Vite, Node pinned to 20.11.0

Connect the repository under Blueprints in Render and both services provision from the manifest, with continuous deployment on push to `main`.

---

## Project Status

The data pipeline, feature engineering, ensemble architecture, SHAP explainability, API, scheduler, and full dashboard are implemented. The following are scoped and in progress, and the interface currently renders representative values for them:

- **Backtest engine** — `run_backtest` is stubbed; the equity curve and strategy metrics panel are placeholders pending live wiring
- **Sentiment ingestion** — the Reddit and VADER path is scaffolded; the pipeline currently synthesises the sentiment series while ingestion is completed
- **Persistence** — SQLAlchemy and Postgres are in the dependency set for prediction history; the history table does not yet read from a live store

These are called out deliberately. The metrics shown in the dashboard are interface placeholders, not validated performance claims, and should be read as such until the backtest engine is connected.

### Roadmap

- Complete the trade simulator with transaction cost and slippage assumptions
- Walk-forward analysis with periodic retraining, in place of a single split
- Persist predictions to Postgres for live hit-rate tracking against realised outcomes
- Probability calibration, Platt or isotonic, so confidence is interpretable as a frequency
- Regime-conditional evaluation, reporting performance separately across volatility states

---

## What This Project Demonstrates

- **Quantitative research process**: hypothesis-driven feature construction, time-aware validation, and benchmark-relative evaluation
- **Financial domain knowledge**: cross-asset signal construction, macro regime context, technical indicator design, and the risk metrics that gate a strategy
- **Machine learning engineering**: ensemble design across complementary model classes, with explainability as a first-class requirement rather than an afterthought
- **Data engineering**: multi-source ingestion across mismatched frequencies, with explicit handling of release timing and look-ahead risk
- **Full-stack and deployment**: a Python service and TypeScript research interface, deployed through infrastructure-as-code with pinned runtimes
- **Research communication**: findings rendered as a dashboard and a written outlook memo, in the format a decision-maker actually consumes

---

## Disclaimer

This project is for educational and research purposes only. It is not investment advice, and nothing here is a recommendation to buy or sell any security. Model outputs are experimental and have not been validated for live trading.

---

## Author

**Deepak Reddy**

Working at the intersection of quantitative research, machine learning, and financial markets. Open to analyst and quantitative research roles.

GitHub: [@thedeepakreddy](https://github.com/thedeepakreddy)
