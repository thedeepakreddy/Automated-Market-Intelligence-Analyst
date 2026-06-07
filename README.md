# Automated Market Intelligence Analyst

An AI-powered market intelligence dashboard and ensemble prediction engine. This project combines a modern React frontend dashboard with a robust Python backend that leverages XGBoost and LSTM neural networks to analyze S&P 500 price momentum, macroeconomic factors, and social sentiment.

## Features
- **Ensemble Model**: Combines XGBoost and LSTM neural networks for 7-day horizon market predictions.
- **Data Pipeline**: Aggregates multi-source data including prices (yfinance), macro-economic indicators, and social sentiment.
- **Interactive Dashboard**: Modern, dark-themed React UI built with Tailwind CSS and Recharts.
- **Automated Scheduling**: Backend includes APScheduler to run predictions autonomously every 30 minutes.

## Tech Stack
- **Frontend**: React 18, Vite, Tailwind CSS, Recharts, Lucide React
- **Backend**: Python 3.11, Flask, TensorFlow / Keras, XGBoost, Pandas, yfinance, APScheduler
- **Deployment**: Configured for Render.com via Blueprint

## Directory Structure
```text
/
├── src/                 # React frontend code (UI components, charts, layout)
├── python-backend/      # Python backend (ML models, data fetching, Flask API)
│   ├── engine.py        # Core prediction pipeline & Flask server
│   └── requirements.txt # Python dependencies
├── render.yaml          # Render Blueprint deployment configuration
├── .python-version      # Defines Python runtime version for cloud deployments
└── package.json         # Frontend Node.js dependencies
```

## Running Locally

### 1. Frontend (React UI)
```bash
# Install Node dependencies
npm install

# Start the Vite development server
npm run dev
```
The frontend will typically be available at `http://localhost:3000` or the port assigned by Vite.

### 2. Backend (Python API & Engine)
Ensure you have Python 3.11 installed. Using a virtual environment is recommended.
```bash
cd python-backend

# Install Python dependencies
pip install -r requirements.txt

# Run the Flask server and background scheduler
python engine.py
```
The backend will start a Flask server on `http://localhost:5000` (or your system's `$PORT`).

## Deployment (Render)

This repository is configured to be easily deployed on [Render.com](https://render.com) using the included `render.yaml` Blueprint.

1. Fork or push this repository to your GitHub account.
2. Log in to your Render dashboard.
3. Click on **Blueprints** (or **New** -> **Blueprint**).
4. Connect the GitHub repository you just uploaded. 
5. Render will automatically detect the `render.yaml` file and provision the `market-intelligence-api` Web Service with the correct `PYTHON_VERSION` (3.11.9) resolving any TensorFlow/Keras compatibility issues. It will continuously build and deploy whenever you push to your main branch.
