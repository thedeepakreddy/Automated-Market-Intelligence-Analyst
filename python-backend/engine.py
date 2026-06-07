import os
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score
import xgboost as xgb
import shap
import praw
from fredapi import Fred
import google.generativeai as genai
import matplotlib.pyplot as plt
from apscheduler.schedulers.blocking import BlockingScheduler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from reportlab.pdfgen import canvas

# ==========================================
# STEP 1: Multi-Source Data Pipeline
# ==========================================
class DataPipeline:
    def __init__(self, fred_api_key, reddit_client_id, reddit_secret, reddit_user_agent):
        self.fred = Fred(api_key=fred_api_key)
        self.reddit = praw.Reddit(
            client_id=reddit_client_id,
            client_secret=reddit_secret,
            user_agent=reddit_user_agent
        )
        
    def fetch_market_data(self):
        tickers = ["^GSPC", "^IXIC", "GC=F", "CL=F"]
        # Fetch 2 years
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=730)
        
        data_frames = []
        for t in tickers:
            df = yf.download(t, start=start_date, end=end_date)
            # Calculate features
            df['SMA_7'] = df['Close'].rolling(window=7).mean()
            df['SMA_14'] = df['Close'].rolling(window=14).mean()
            df['SMA_30'] = df['Close'].rolling(window=30).mean()
            df['Daily_Return'] = df['Close'].pct_change()
            df['Volatility_7'] = df['Daily_Return'].rolling(window=7).std()
            
            # Simple RSI approximation
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            # Bollinger Bands
            df['BB_Mid'] = df['Close'].rolling(window=20).mean()
            df['BB_Upper'] = df['BB_Mid'] + 2 * df['Close'].rolling(window=20).std()
            df['BB_Lower'] = df['BB_Mid'] - 2 * df['Close'].rolling(window=20).std()
            
            df = df.add_prefix(f'{t}_')
            data_frames.append(df)
            
        return pd.concat(data_frames, axis=1)

    def fetch_macro_data(self):
        series_ids = {
            'CPI': 'CPIAUCSL',
            'Unemployment': 'UNRATE',
            'FedFunds': 'FEDFUNDS',
            'GDP': 'A191RL1Q225SBEA',
            'ConsumerSentiment': 'UMCSENT'
        }
        dfs = []
        for name, sid in series_ids.items():
            s = self.fred.get_series(sid)
            df = pd.DataFrame(s, columns=[name])
            df = df.resample('D').ffill() # Forward-fill to daily
            df[f'{name}_MoM_Change'] = df[name].pct_change(periods=30)
            dfs.append(df)
            
        return pd.concat(dfs, axis=1)

    def fetch_social_sentiment(self):
        # Implementation depends on VADER analysis over reddit posts
        # Simulated dataframe output for brevity
        dates = pd.date_range(end=datetime.date.today(), periods=730)
        df = pd.DataFrame(index=dates)
        df['Sentiment_Avg'] = np.random.uniform(-0.5, 0.5, size=730)
        df['Sentiment_Momentum'] = df['Sentiment_Avg'].diff(periods=7)
        return df

# ==========================================
# STEP 2: Feature Engineering
# ==========================================
def feature_engineering(market_df, macro_df, sentiment_df):
    master_df = market_df.join(macro_df, how='outer').join(sentiment_df, how='outer')
    master_df = master_df.ffill() # handle missing dates
    
    # Lag features for S&P500 Price
    for lag in [1, 3, 7, 14]:
        master_df[f'SP500_Lag_{lag}'] = master_df['^GSPC_Close'].shift(lag)
        
    # Target variable: Did S&P500 go up 7 days from today?
    master_df['Target'] = (master_df['^GSPC_Close'].shift(-7) > master_df['^GSPC_Close']).astype(int)
    
    master_df = master_df.dropna()
    
    # 80/20 chronological split
    train_size = int(len(master_df) * 0.8)
    train_df = master_df.iloc[:train_size]
    test_df = master_df.iloc[train_size:]
    
    return train_df, test_df

# ==========================================
# STEP 3: Model Training
# ==========================================
class EnsembleModel:
    def __init__(self):
        self.xgb_model = xgb.XGBClassifier(eval_metric='logloss')
        self.lstm_model = None

    def train_xgboost(self, X_train, y_train):
        # TimeSeriesSplit CV
        tscv = TimeSeriesSplit(n_splits=5)
        # simplified training...
        self.xgb_model.fit(X_train, y_train)

    def build_and_train_lstm(self, X_train, y_train):
        # Reshape for LSTM (samples, time steps, features)
        X_train_lstm = np.reshape(X_train.values, (X_train.shape[0], 1, X_train.shape[1]))
        
        self.lstm_model = Sequential([
            LSTM(64, return_sequences=True, input_shape=(1, X_train.shape[1])),
            LSTM(32),
            Dense(1, activation='sigmoid')
        ])
        self.lstm_model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
        self.lstm_model.fit(X_train_lstm, y_train, epochs=5, batch_size=32, verbose=0)

    def predict(self, X):
        xgb_probs = self.xgb_model.predict_proba(X)[:, 1]
        
        X_lstm = np.reshape(X.values, (X.shape[0], 1, X.shape[1]))
        lstm_probs = self.lstm_model.predict(X_lstm).flatten()
        
        # Ensemble average
        ensemble_prob = (xgb_probs + lstm_probs) / 2
        
        predictions = []
        for p in ensemble_prob:
            if p > 0.55:
                predictions.append(('UP', p))
            elif p < 0.45:
                predictions.append(('DOWN', p))
            else:
                predictions.append(('UNCERTAIN', p))
        return predictions

# ==========================================
# STEP 4: SHAP Explainability
# ==========================================
def get_shap_explanation(model, X_bg, X_instance):
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_instance)
    return shap_values

# ==========================================
# STEP 5: Backtesting Engine
# ==========================================
def run_backtest(test_df, predictions):
    # Simulate trading mapping predictions to signals
    # logic...
    pass

# ==========================================
# STEP 6: Weekly AI Report (Gemini)
# ==========================================
def generate_weekly_report(prediction_direction, confidence, top_features):
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-pro')
    
    prompt = f"""
    Write a professional weekly market outlook.
    Current prediction: {prediction_direction} with {confidence*100:.2f}% confidence.
    Top 3 driving features: {top_features}.
    
    Sections:
    - Current market assessment
    - Key risk factors this week
    - Data signals supporting prediction
    - Disclaimer: This is for educational purposes only.
    """
    response = model.generate_content(prompt)
    
    # Save PDF
    c = canvas.Canvas("weekly_report.pdf")
    c.drawString(100, 750, "Weekly AI Market Report")
    # Add content logic...
    c.save()
    return response.text

# Scheduler
def scheduled_job():
    print("Running weekly prediction pipeline...")

if __name__ == "__main__":
    print("Market Engine Initiated.")
    # scheduler = BlockingScheduler()
    # scheduler.add_job(scheduled_job, 'cron', day_of_week='mon', hour=8)
    # scheduler.start()
