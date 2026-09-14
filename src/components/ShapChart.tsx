import type { FeatureAttribution } from '../lib/api';
import { featureLabel, signed } from '../lib/format';
import { Empty, Panel, Skeleton } from './Panel';

/**
 * Diverging attribution: which drivers push the probability up, which pull it
 * down. Diverging data gets two hues and a neutral centre, never a single ramp
 * — the sign is the whole point.
 *
 * Hand-drawn rather than charted so each row can carry its full feature name
 * at a readable size; a plotted category axis truncates them to noise.
 */
export function ShapChart({
  features,
  source,
  loading,
  error,
  topN = 6,
}: {
  features: FeatureAttribution[] | null;
  source?: string;
  loading: boolean;
  error: string | null;
  topN?: number;
}) {
  const shown = (features ?? []).slice(0, topN);
  const widest = Math.max(...shown.map((item) => Math.abs(item.value)), 1e-9);

  return (
    <Panel
      title="What is driving it"
      eyebrow={source === 'shap' ? 'SHAP · this call' : source ? `${source} · this call` : 'Attribution'}
    >
      {loading ? (
        <Skeleton lines={6} />
      ) : !shown.length ? (
        <Empty message={error ?? 'No attribution available for this run.'} />
      ) : (
        <>
          <ul className="space-y-3.5">
            {shown.map((item) => {
              const positive = item.value >= 0;
              return (
                <li key={item.feature} className="flex items-center gap-3" title={item.feature}>
                  <span className="w-32 sm:w-40 shrink-0 text-[11px] text-zinc-400 text-right truncate">
                    {featureLabel(item.feature)}
                  </span>
                  <span className="relative flex-1 h-4">
                    <span className="absolute inset-y-0 left-1/2 w-px bg-white/15" />
                    <span
                      className="absolute top-0.5 bottom-0.5"
                      style={{
                        width: `${(Math.abs(item.value) / widest) * 48}%`,
                        [positive ? 'left' : 'right']: '50%',
                        backgroundColor: positive ? 'var(--series-1)' : 'var(--status-critical)',
                        borderRadius: positive ? '0 4px 4px 0' : '4px 0 0 4px',
                      }}
                    />
                  </span>
                  <span className="w-14 shrink-0 text-right font-mono text-[11px] text-zinc-200 tabular-nums">
                    {signed(item.value)}
                  </span>
                </li>
              );
            })}
          </ul>

          <div className="flex flex-wrap gap-4 mt-6 pt-4 border-t border-white/5">
            <span className="flex items-center gap-2 text-[11px] text-zinc-400">
              <span className="h-2 w-2 rounded-sm" style={{ backgroundColor: 'var(--series-1)' }} />
              Pushes toward UP
            </span>
            <span className="flex items-center gap-2 text-[11px] text-zinc-400">
              <span
                className="h-2 w-2 rounded-sm"
                style={{ backgroundColor: 'var(--status-critical)' }}
              />
              Pushes toward DOWN
            </span>
          </div>

          {source && source !== 'shap' && (
            <p className="text-[10px] text-zinc-600 mt-3 leading-relaxed">
              SHAP was unavailable for this run, so these are the model's gain importances — a
              ranking of features overall, not an explanation of this particular call.
            </p>
          )}
        </>
      )}
    </Panel>
  );
}
