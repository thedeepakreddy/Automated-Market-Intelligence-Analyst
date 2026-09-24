/**
 * Typed client for the market engine API.
 *
 * The backend answers 503 with {"status":"pending"} until the first scheduled
 * run completes, which is a normal state on a cold deployment rather than an
 * error - `pending` is modelled explicitly so the UI can say "warming up"
 * instead of "failed".
 */

/**
 * Resolve the configured API origin defensively.
 *
 * Vite bakes VITE_API_URL in at *build* time. Left unset in production it
 * falls back to localhost, which in every visitor's own browser means "their
 * machine" - guaranteed ERR_CONNECTION_REFUSED, on every load, with nothing
 * to see server-side. A platform's service-discovery env var (Render's
 * `fromService`, for one) can also hand back a bare host with no scheme,
 * which would otherwise silently become a same-origin relative path instead
 * of failing loudly - so a missing scheme is added rather than assumed away.
 */
function resolveApiBase(): string {
  const raw = (import.meta.env.VITE_API_URL ?? 'http://localhost:5000').trim();
  const withScheme = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
  return withScheme.replace(/\/$/, '');
}

const BASE = resolveApiBase();

export type Signal = 'UP' | 'DOWN' | 'UNCERTAIN';

export interface FeatureAttribution {
  feature: string;
  value: number;
}

export interface Movement {
  feature: string;
  current: number | null;
  previous: number | null;
  change: number;
  status: 'entered' | 'exited' | 'held';
}

export interface Delta {
  compared_with: string | null;
  compared_with_as_of: string | null;
  signal_changed: boolean;
  previous_signal: Signal | null;
  current_signal: Signal;
  probability_change: number | null;
  confidence_change: number | null;
  movements: Movement[];
  headline: string;
}

export interface Analogue {
  date: string;
  distance: number | null;
  similarity: number | null;
  forward_return: number | null;
  state: Record<string, number | null>;
}

export interface Regime {
  current: number;
  current_since: string | null;
  n_regimes: number;
  regimes: Array<{
    id: number;
    sessions: number;
    share: number | null;
    label: string;
    mean_forward_return: number | null;
    up_rate: number | null;
    last_seen: string | null;
  }>;
}

export interface Divergence {
  state: 'aligned' | 'crowd_ahead_of_price' | 'price_ahead_of_crowd';
  divergence: number | null;
  sentiment_z: number | null;
  momentum_z: number | null;
  window: number;
  note: string;
}

export interface Theme {
  theme: string;
  mentions: number | null;
  share: number | null;
  stance: 'bullish' | 'bearish' | 'mixed';
  summary: string;
}

export interface FlipPoint {
  feature: string;
  current: number;
  baseline_signal: Signal;
  flips_to: Signal | null;
  flips_at: number | null;
  move_required: number | null;
  move_in_std: number | null;
}

export interface Disagreement {
  available: boolean;
  xgboost?: number;
  lstm?: number;
  spread?: number;
  note: string;
}

export interface EventWindow {
  from: string;
  to: string;
  sessions: number;
  approximate_window: boolean;
  events: Array<{ type: string; date: string }>;
  has_event: boolean;
  note: string;
}

export interface SurpriseIndex {
  index: number | null;
  method: string;
  caveat: string;
  components: Array<{
    series: string;
    latest_change: number | null;
    surprise_z: number | null;
    released_on: string | null;
  }>;
}

export interface Performance {
  cumulative_return: number | null;
  annualized_return: number | null;
  sharpe: number | null;
  max_drawdown: number | null;
  final_equity: number;
}

export interface Backtest {
  n_periods: number;
  horizon_sessions?: number;
  start?: string;
  end?: string;
  directional_accuracy?: number | null;
  n_directional_calls?: number;
  coverage?: number;
  n_long_periods?: number;
  long_hit_rate?: number | null;
  strategy?: Performance;
  buy_and_hold?: Performance;
  equity_curve?: Array<{ date: string; strategy: number; buy_and_hold: number }>;
  note?: string;
}

/** Any analytic can fail independently; the backend records why. */
export type MaybeFailed<T> = T | { error: string } | null;

export interface Analytics {
  delta?: MaybeFailed<Delta>;
  analogues?: MaybeFailed<Analogue[]>;
  regime?: MaybeFailed<Regime>;
  divergence?: MaybeFailed<Divergence>;
  surprise?: MaybeFailed<SurpriseIndex>;
  events?: MaybeFailed<EventWindow>;
  calendar?: MaybeFailed<{ source: string; stale: boolean; note: string | null }>;
  disagreement?: MaybeFailed<Disagreement>;
  flip_points?: MaybeFailed<FlipPoint[]>;
  themes?: MaybeFailed<{ themes: Theme[]; source: string; n_documents: number }>;
  theme_shift?: MaybeFailed<Array<{ theme: string; status: string; change: number | null }>>;
  price_series?: MaybeFailed<Array<{ date: string; close: number }>>;
}

export interface Latest {
  id: number;
  generated_at: string;
  as_of_date: string;
  prediction: Signal;
  probability: number;
  confidence: number;
  top_features: FeatureAttribution[];
  attribution_source: string;
  model: {
    cv_accuracy: number | null;
    cv_accuracy_std: number | null;
    cv_fold_accuracies: number[] | null;
    test_accuracy: number | null;
    lstm_trained: boolean;
    train_rows: number;
    test_rows: number;
    n_features: number;
  };
  backtest: Backtest | null;
  data_sources: Record<string, string>;
  report: { text: string | null; source: string | null; pdf_path: string | null };
  analytics: Analytics;
  outcome?: {
    resolved_at: string | null;
    actual_direction: Signal | null;
    correct: boolean | null;
    realized_return: number | null;
  };
}

export interface Scorecard {
  n_resolved: number;
  n_directional: number;
  hit_rate: number | null;
  coverage: number | null;
  calibration_error: number | null;
  verdict: string;
  by_confidence: Array<{ bucket: string; stated: number; realised: number; n: number }>;
  by_signal: Record<string, { n: number; hit_rate: number | null; mean_forward_return: number | null }>;
  by_event: {
    fomc_weeks: { n: number; hit_rate: number } | null;
    quiet_weeks: { n: number; hit_rate: number } | null;
    gap: number | null;
    note: string;
  } | null;
  n_runs_total: number;
  n_unresolved: number;
}

export interface HistoryRow {
  as_of_date: string;
  generated_at: string;
  prediction: Signal;
  probability: number;
  confidence: number;
  outcome?: {
    correct: boolean | null;
    actual_direction: Signal | null;
    realized_return: number | null;
  } | null;
}

export interface LiveFeature {
  feature: string;
  current: number;
  min?: number;
  max?: number;
  mean?: number;
  std?: number;
  percentile?: number;
}

export interface WhatIfResult {
  baseline_probability: number | null;
  probability: number | null;
  probability_change: number | null;
  baseline_signal?: Signal;
  signal?: Signal;
  signal_changed?: boolean;
  applied: Record<string, number>;
  rejected: string[];
  as_of?: string;
  note?: string;
}

/** Thrown for transport/HTTP failures; `pending` marks the warming-up 503. */
export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly pending = false) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    });
  } catch (cause) {
    throw new ApiError(
      `Cannot reach the engine at ${BASE}. Is it running?`,
      0,
    );
  }

  if (response.status === 503) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(body.message ?? 'The engine is still warming up.', 503, true);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(body.error ?? `Request failed (${response.status})`, response.status);
  }
  return response.json() as Promise<T>;
}

export const api = {
  baseUrl: BASE,
  latest: () => request<Latest>('/api/latest'),
  scorecard: () => request<Scorecard>('/api/scorecard'),
  history: (limit = 100) =>
    request<{ count: number; predictions: HistoryRow[] }>(`/api/history?limit=${limit}`),
  series: () => request<{ as_of: string; points: Array<{ date: string; close: number }> }>('/api/series'),
  features: () => request<{ as_of: string; features: LiveFeature[] }>('/api/features'),
  alerts: (limit = 10) =>
    request<{ alerts: Array<{ id: number; created_at: string; kind: string; message: string }> }>(
      `/api/alerts?limit=${limit}`,
    ),
  whatIf: (overrides: Record<string, number>) =>
    request<WhatIfResult>('/api/whatif', {
      method: 'POST',
      body: JSON.stringify({ overrides }),
    }),
  ask: (question: string) =>
    request<{ answer: string | null; source: string; used_runs: string[] }>('/api/ask', {
      method: 'POST',
      body: JSON.stringify({ question }),
    }),
};

/** Narrow a possibly-failed analytic to its value, or null. */
export function ok<T>(value: MaybeFailed<T> | undefined): T | null {
  if (!value) return null;
  if (typeof value === 'object' && 'error' in (value as object)) return null;
  return value as T;
}
