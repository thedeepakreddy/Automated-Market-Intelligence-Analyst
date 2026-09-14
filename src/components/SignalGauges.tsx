import React from 'react';
import type { Disagreement, Divergence, SurpriseIndex } from '../lib/api';
import { num, pct } from '../lib/format';
import { Panel } from './Panel';

/** A probability plotted on a 0–1 track, with the neutral band marked. */
function ProbabilityTrack({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div className="flex justify-between items-baseline mb-2">
        <span className="text-[11px] text-zinc-400 flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-sm shrink-0" style={{ backgroundColor: color }} />
          {label}
        </span>
        <span className="font-mono text-xs text-zinc-200">{pct(value)}</span>
      </div>
      <div className="relative h-1.5 w-full rounded-full bg-white/5">
        {/* The 0.45–0.55 neutral band, drawn so the reader can see whether a
            probability is actually outside it. */}
        <div className="absolute inset-y-0 bg-white/[0.07]" style={{ left: '45%', width: '10%' }} />
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ width: `${Math.min(100, Math.max(0, value * 100))}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

/**
 * Model disagreement, crowd-versus-price divergence, and the macro surprise
 * index — three readings that qualify the headline call rather than repeat it.
 */
export function SignalGauges({
  disagreement,
  divergence,
  surprise,
}: {
  disagreement: Disagreement | null;
  divergence: Divergence | null;
  surprise: SurpriseIndex | null;
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
      <Panel title="Model disagreement" eyebrow="Ensemble split">
        {disagreement?.available ? (
          <div className="space-y-4">
            <ProbabilityTrack
              label="XGBoost"
              value={disagreement.xgboost ?? 0}
              color="var(--series-1)"
            />
            <ProbabilityTrack
              label="LSTM"
              value={disagreement.lstm ?? 0}
              color="var(--series-2)"
            />
            <div className="flex items-baseline justify-between pt-1">
              <span className="label-eyebrow">Spread</span>
              <span className="font-mono text-sm text-zinc-100">
                {pct(disagreement.spread, 1)}
              </span>
            </div>
            <p className="text-[10px] text-zinc-500 leading-relaxed">{disagreement.note}</p>
          </div>
        ) : (
          <p className="text-[11px] text-zinc-500 leading-relaxed">
            {disagreement?.note ?? 'No second opinion available for this run.'}
          </p>
        )}
      </Panel>

      <Panel title="Crowd vs price" eyebrow="Sentiment divergence">
        {divergence ? (
          <div className="space-y-4">
            <div className="flex items-baseline justify-between">
              <span className="label-eyebrow">Divergence</span>
              <span
                className="font-mono text-lg"
                style={{
                  color:
                    divergence.state === 'aligned'
                      ? 'var(--text-primary)'
                      : 'var(--status-warning)',
                }}
              >
                {num(divergence.divergence, 2)}σ
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3 text-[11px]">
              <div className="glass-well px-3 py-2">
                <p className="label-eyebrow mb-1">Sentiment</p>
                <p className="font-mono text-zinc-200">{num(divergence.sentiment_z, 2)}σ</p>
              </div>
              <div className="glass-well px-3 py-2">
                <p className="label-eyebrow mb-1">Momentum</p>
                <p className="font-mono text-zinc-200">{num(divergence.momentum_z, 2)}σ</p>
              </div>
            </div>
            <p className="text-[10px] text-zinc-500 leading-relaxed">{divergence.note}</p>
          </div>
        ) : (
          <p className="text-[11px] text-zinc-500">Not enough history to measure divergence.</p>
        )}
      </Panel>

      <Panel title="Macro surprise" eyebrow="Releases vs naive forecast">
        {surprise && surprise.index !== null ? (
          <div className="space-y-4">
            <div className="flex items-baseline justify-between">
              <span className="label-eyebrow">Index</span>
              <span className="font-mono text-lg text-zinc-100">{num(surprise.index, 2)}σ</span>
            </div>
            <ul className="space-y-1.5">
              {surprise.components.slice(0, 4).map((component) => (
                <li key={component.series} className="flex justify-between text-[11px]">
                  <span className="text-zinc-400 truncate pr-2">{component.series}</span>
                  <span className="font-mono text-zinc-300 shrink-0">
                    {num(component.surprise_z, 2)}σ
                  </span>
                </li>
              ))}
            </ul>
            <p className="text-[10px] text-zinc-500 leading-relaxed">{surprise.caveat}</p>
          </div>
        ) : (
          <p className="text-[11px] text-zinc-500 leading-relaxed">
            No release dispersion to score against yet. Needs several macro releases of history.
          </p>
        )}
      </Panel>
    </div>
  );
}
