/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { api, ok, type Analytics } from './lib/api';
import { useApi } from './hooks/useApi';
import { relativeTime } from './lib/format';
import { AnaloguePanel } from './components/AnaloguePanel';
import { AskPanel } from './components/AskPanel';
import { BacktestChart } from './components/BacktestChart';
import { DeltaPanel } from './components/DeltaPanel';
import { HeroSection } from './components/HeroSection';
import { HistoryTable } from './components/HistoryTable';
import { Logo } from './components/Logo';
import { MetricsTable } from './components/MetricsTable';
import { Panel } from './components/Panel';
import { PriceChart } from './components/PriceChart';
import { ScorecardPanel } from './components/ScorecardPanel';
import { ShapChart } from './components/ShapChart';
import { SignalGauges } from './components/SignalGauges';
import { ThemesPanel } from './components/ThemesPanel';
import { WeeklyReport } from './components/WeeklyReport';
import { WhatIfPanel } from './components/WhatIfPanel';

/** Poll a little faster than the 30-minute pipeline so a new run shows up. */
const REFRESH_MS = 5 * 60 * 1000;

export default function App() {
  const latest = useApi(() => api.latest(), REFRESH_MS);
  const scorecard = useApi(() => api.scorecard(), REFRESH_MS);
  const history = useApi(() => api.history(100), REFRESH_MS);
  const features = useApi(() => api.features());

  const record = latest.data;
  const analytics: Analytics = record?.analytics ?? {};

  return (
    <div className="min-h-screen text-zinc-100 p-4 md:p-8 md:py-10 font-sans selection:bg-white/10">
      <div className="max-w-[1440px] mx-auto space-y-5">
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-5 pb-7 border-b border-white/[0.07]">
          <div className="flex items-center gap-4">
            <Logo className="w-8 h-8 md:w-9 md:h-9 shrink-0" />
            <div>
              <h1 className="text-[17px] font-medium tracking-tight">Market Intelligence</h1>
              <p className="label-eyebrow mt-1">Ensemble · XGBoost + LSTM</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <span className="flex items-center gap-2 label-eyebrow">
              <span className="relative flex h-1.5 w-1.5">
                {!latest.error && (
                  <span
                    className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
                    style={{ backgroundColor: 'var(--status-good)' }}
                  />
                )}
                <span
                  className="relative inline-flex rounded-full h-1.5 w-1.5"
                  style={{
                    backgroundColor: latest.error ? 'var(--status-warning)' : 'var(--status-good)',
                  }}
                />
              </span>
              {latest.error
                ? latest.pending
                  ? 'Warming up'
                  : 'Engine unreachable'
                : `Updated ${relativeTime(record?.generated_at)}`}
            </span>
            <span className="text-[11px] text-zinc-400 border border-white/10 bg-white/[0.03] rounded-full px-3 py-1.5">
              S&P 500
            </span>
            <span className="text-[11px] text-zinc-400 border border-white/10 bg-white/[0.03] rounded-full px-3 py-1.5">
              7 sessions
            </span>
          </div>
        </header>

        <main className="space-y-5">
          {/* Hero: live, warming up, or unreachable — never a fabricated call. */}
          {record ? (
            <HeroSection
              prediction={record.prediction}
              confidence={record.confidence}
              asOf={record.as_of_date}
              delta={ok(analytics.delta)}
              events={ok(analytics.events)}
            />
          ) : (
            <Panel className="py-16">
              <div className="max-w-md mx-auto text-center space-y-3">
                <p className="text-sm text-zinc-300">
                  {latest.loading
                    ? 'Connecting to the engine…'
                    : latest.pending
                      ? 'The engine is warming up.'
                      : 'Cannot reach the engine.'}
                </p>
                <p className="text-[11px] text-zinc-500 leading-relaxed">
                  {latest.pending
                    ? 'The pipeline runs on startup and then every 30 minutes. The first call appears once it completes.'
                    : latest.loading
                      ? 'Fetching the most recent run.'
                      : `${latest.error} Set VITE_API_URL to point the dashboard at your API.`}
                </p>
                {!latest.loading && (
                  <button
                    type="button"
                    onClick={latest.reload}
                    className="text-[11px] text-zinc-300 hover:text-white border border-white/10 hover:border-white/25 rounded-full px-4 py-2 transition-colors"
                  >
                    Retry
                  </button>
                )}
              </div>
            </Panel>
          )}

          <SignalGauges
            disagreement={ok(analytics.disagreement)}
            divergence={ok(analytics.divergence)}
            surprise={ok(analytics.surprise)}
          />

          <section className="grid grid-cols-1 lg:grid-cols-[1.35fr_1fr] gap-5">
            <PriceChart
              points={ok(analytics.price_series)}
              loading={latest.loading}
              error={latest.error}
            />
            <ShapChart
              features={record?.top_features ?? null}
              source={record?.attribution_source}
              loading={latest.loading}
              error={latest.error}
            />
          </section>

          <WhatIfPanel
            features={features.data?.features ?? null}
            flipPoints={ok(analytics.flip_points)}
            loading={features.loading}
            error={features.error}
          />

          <section className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <AnaloguePanel
              analogues={ok(analytics.analogues)}
              regime={ok(analytics.regime)}
              loading={latest.loading}
              error={latest.error}
            />
            <ThemesPanel
              themes={ok(analytics.themes)?.themes ?? null}
              source={ok(analytics.themes)?.source}
              documentCount={ok(analytics.themes)?.n_documents}
              shift={ok(analytics.theme_shift)}
              loading={latest.loading}
              error={latest.error}
            />
          </section>

          <section className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-5">
            <BacktestChart
              backtest={record?.backtest ?? null}
              loading={latest.loading}
              error={latest.error}
            />
            <MetricsTable
              backtest={record?.backtest ?? null}
              loading={latest.loading}
              error={latest.error}
            />
          </section>

          <section className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <ScorecardPanel
              scorecard={scorecard.data}
              loading={scorecard.loading}
              error={scorecard.error}
            />
            <DeltaPanel delta={ok(analytics.delta)} />
          </section>

          <section className="grid grid-cols-1 lg:grid-cols-[1.35fr_1fr] gap-5">
            <WeeklyReport
              report={record?.report ?? null}
              loading={latest.loading}
              error={latest.error}
            />
            <AskPanel />
          </section>

          <HistoryTable
            rows={history.data?.predictions ?? null}
            loading={history.loading}
            error={history.error}
          />

          <footer className="flex flex-col sm:flex-row justify-between gap-3 pt-10 pb-4 border-t border-white/[0.06]">
            <p className="label-eyebrow">Educational research · not investment advice</p>
            <p className="label-eyebrow">yfinance · FRED · Reddit</p>
          </footer>
        </main>
      </div>
    </div>
  );
}
