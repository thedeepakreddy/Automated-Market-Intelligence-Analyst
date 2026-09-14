/** Formatting helpers. Every one renders a dash for missing data rather than
 *  "NaN" or "0" - an absent number and a zero mean different things here. */

export const DASH = '—';

export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  return `${(value * 100).toFixed(digits)}%`;
}

export function signedPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(digits)}%`;
}

export function num(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  return value.toFixed(digits);
}

export function signed(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  return `${value >= 0 ? '+' : ''}${value.toFixed(digits)}`;
}

/** Percentage points, for differences between two percentages. */
export function pp(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(digits)}pp`;
}

export function shortDate(value: string | null | undefined): string {
  if (!value) return DASH;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  }).format(parsed);
}

export function fullDate(value: string | null | undefined): string {
  if (!value) return DASH;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(parsed);
}

export function relativeTime(value: string | null | undefined): string {
  if (!value) return DASH;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  const seconds = Math.round((Date.now() - parsed.getTime()) / 1000);
  if (seconds < 90) return 'just now';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

/** Turn `^GSPC_BB_Upper` into `S&P 500 · Bollinger upper`. */
const TICKER_NAMES: Record<string, string> = {
  '^GSPC': 'S&P 500',
  '^IXIC': 'Nasdaq',
  'GC=F': 'Gold',
  'CL=F': 'Crude',
};

const FEATURE_NAMES: Record<string, string> = {
  SMA_7: '7d average',
  SMA_14: '14d average',
  SMA_30: '30d average',
  Daily_Return: 'daily return',
  Volatility_7: '7d volatility',
  RSI: 'RSI',
  BB_Mid: 'Bollinger mid',
  BB_Upper: 'Bollinger upper',
  BB_Lower: 'Bollinger lower',
  Close: 'close',
  Open: 'open',
  High: 'high',
  Low: 'low',
  Volume: 'volume',
  Sentiment_Avg: 'Reddit sentiment',
  Sentiment_Momentum: 'sentiment momentum',
  Sentiment_Volume: 'post volume',
  CPI: 'CPI',
  Unemployment: 'unemployment',
  FedFunds: 'fed funds',
  GDP: 'GDP',
  ConsumerSentiment: 'consumer sentiment',
};

export function featureLabel(raw: string): string {
  for (const [ticker, name] of Object.entries(TICKER_NAMES)) {
    if (raw.startsWith(`${ticker}_`)) {
      const rest = raw.slice(ticker.length + 1);
      return `${name} · ${FEATURE_NAMES[rest] ?? rest.replace(/_/g, ' ').toLowerCase()}`;
    }
  }
  if (raw.startsWith('SP500_Lag_')) return `S&P 500 · lag ${raw.replace('SP500_Lag_', '')}d`;
  if (raw.endsWith('_MoM_Change')) {
    const base = raw.replace('_MoM_Change', '');
    return `${FEATURE_NAMES[base] ?? base} · MoM change`;
  }
  return FEATURE_NAMES[raw] ?? raw.replace(/_/g, ' ');
}

/** Compact label for axes, where the full name will not fit. */
export function shortFeatureLabel(raw: string, max = 22): string {
  const label = featureLabel(raw);
  return label.length > max ? `${label.slice(0, max - 1)}…` : label;
}
