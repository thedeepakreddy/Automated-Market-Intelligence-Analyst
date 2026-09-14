import { useEffect, useMemo, useRef, useState } from 'react';
import { api, type FlipPoint, type LiveFeature, type Signal, type WhatIfResult } from '../lib/api';
import { featureLabel, num, pct } from '../lib/format';
import { Empty, Panel, SIGNAL_COLOR, SignalPill, Skeleton } from './Panel';

/**
 * The counterfactual explorer: move a driver, watch the call move.
 *
 * Its real job is the inverse question — what would have to be true for this
 * call to be wrong. The flip-point list answers that directly, and a call that
 * flips inside half a standard deviation is fragile however confident it reads.
 */
export function WhatIfPanel({
  features,
  flipPoints,
  loading,
  error,
}: {
  features: LiveFeature[] | null;
  flipPoints: FlipPoint[] | null;
  loading: boolean;
  error: string | null;
}) {
  const sliders = useMemo(() => (features ?? []).slice(0, 4), [features]);
  const [overrides, setOverrides] = useState<Record<string, number>>({});
  const [result, setResult] = useState<WhatIfResult | null>(null);
  const [scoring, setScoring] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  // Debounced so dragging a slider does not fire a request per pixel.
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  useEffect(() => {
    if (!Object.keys(overrides).length) {
      setResult(null);
      return;
    }
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      setScoring(true);
      try {
        const scored = await api.whatIf(overrides);
        if (alive.current) {
          setResult(scored);
          setFailure(null);
        }
      } catch (caught) {
        if (alive.current) setFailure(caught instanceof Error ? caught.message : 'Scoring failed');
      } finally {
        if (alive.current) setScoring(false);
      }
    }, 220);
  }, [overrides]);

  const reset = () => {
    setOverrides({});
    setResult(null);
    setFailure(null);
  };

  const baselineSignal = (result?.baseline_signal ?? flipPoints?.[0]?.baseline_signal) as
    | Signal
    | undefined;

  return (
    <Panel
      title="What would change this call?"
      eyebrow="Counterfactual"
      aside={
        Object.keys(overrides).length ? (
          <button
            type="button"
            onClick={reset}
            className="text-[11px] text-zinc-400 hover:text-zinc-100 border border-white/10 hover:border-white/20 rounded-full px-3 py-1.5 transition-colors"
          >
            Reset
          </button>
        ) : null
      }
    >
      {loading ? (
        <Skeleton lines={6} />
      ) : !sliders.length ? (
        <Empty
          message={error ?? 'No live feature row yet.'}
          hint="Available once the pipeline has trained a model in this process."
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="space-y-5">
            {sliders.map((feature) => {
              const min = feature.min ?? feature.current - 1;
              const max = feature.max ?? feature.current + 1;
              const value = overrides[feature.feature] ?? feature.current;
              const step = (max - min) / 200 || 0.001;
              return (
                <div key={feature.feature}>
                  <div className="flex justify-between items-baseline mb-2.5">
                    <label
                      htmlFor={`slider-${feature.feature}`}
                      className="text-[11.5px] text-zinc-400"
                    >
                      {featureLabel(feature.feature)}
                    </label>
                    <span className="font-mono text-[11px] text-zinc-100 tabular-nums">
                      {num(value, Math.abs(value) < 1 ? 4 : 2)}
                    </span>
                  </div>
                  <input
                    id={`slider-${feature.feature}`}
                    type="range"
                    min={min}
                    max={max}
                    step={step}
                    value={value}
                    onChange={(event) =>
                      setOverrides((current) => ({
                        ...current,
                        [feature.feature]: Number(event.target.value),
                      }))
                    }
                    className="w-full accent-[var(--series-1)] cursor-pointer"
                  />
                  <div className="flex justify-between font-mono text-[10px] text-zinc-600 mt-1.5">
                    <span>{num(min, Math.abs(min) < 1 ? 4 : 2)}</span>
                    <span>{num(max, Math.abs(max) < 1 ? 4 : 2)}</span>
                  </div>
                </div>
              );
            })}

            <div className="glass-well px-4 py-3.5 flex items-center justify-between gap-4">
              <div>
                <p className="label-eyebrow mb-1.5">Baseline</p>
                {baselineSignal ? (
                  <SignalPill signal={baselineSignal} size="xs" />
                ) : (
                  <span className="text-xs text-zinc-500">—</span>
                )}
              </div>
              <span className="text-zinc-600" aria-hidden="true">
                →
              </span>
              <div className="text-right">
                <p className="label-eyebrow mb-1.5">Adjusted</p>
                {result?.signal ? (
                  <span className="flex items-center gap-2 justify-end">
                    <SignalPill signal={result.signal} size="xs" />
                    <span
                      className="font-mono text-[11px]"
                      style={{ color: SIGNAL_COLOR[result.signal] }}
                    >
                      {pct(result.probability)}
                    </span>
                  </span>
                ) : (
                  <span className="text-[11px] text-zinc-500">
                    {scoring ? 'scoring…' : 'move a slider'}
                  </span>
                )}
              </div>
            </div>

            {failure && (
              <p className="text-[11px]" style={{ color: 'var(--status-warning)' }}>
                {failure}
              </p>
            )}
          </div>

          <div>
            <p className="label-eyebrow mb-3.5">Flip points · smallest move that changes the call</p>
            {!flipPoints?.length ? (
              <Empty message="No flip points computed for this run." />
            ) : (
              <ul className="space-y-2.5">
                {flipPoints.slice(0, 5).map((point) => (
                  <li
                    key={point.feature}
                    className="glass-well px-4 py-3 flex items-center justify-between gap-3"
                  >
                    <span className="text-[11.5px] text-zinc-300 truncate">
                      {featureLabel(point.feature)}
                    </span>
                    <span className="flex items-center gap-2.5 shrink-0">
                      <span className="font-mono text-[11px] text-zinc-500">
                        {point.move_in_std === null
                          ? 'no flip'
                          : `${point.move_in_std >= 0 ? '+' : ''}${point.move_in_std.toFixed(2)}σ`}
                      </span>
                      {point.flips_to ? (
                        <span
                          className="font-mono text-[10px] rounded-full px-2 py-0.5 border"
                          style={{
                            color: SIGNAL_COLOR[point.flips_to],
                            borderColor: `${SIGNAL_COLOR[point.flips_to]}55`,
                            backgroundColor: `${SIGNAL_COLOR[point.flips_to]}14`,
                          }}
                        >
                          → {point.flips_to}
                        </span>
                      ) : (
                        <span className="font-mono text-[10px] rounded-full px-2 py-0.5 border border-white/10 text-zinc-500">
                          stable
                        </span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-[10px] text-zinc-600 mt-4 leading-relaxed">
              Scanned ±3 historical standard deviations per driver. A call that flips inside half a
              σ is fragile, however confident it reads.
            </p>
          </div>
        </div>
      )}
    </Panel>
  );
}
