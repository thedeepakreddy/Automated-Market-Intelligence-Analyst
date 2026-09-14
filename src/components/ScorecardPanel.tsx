import type { Scorecard } from '../lib/api';
import { pct, pp } from '../lib/format';
import { Empty, Panel, Skeleton } from './Panel';

/**
 * The realised record, and the calibration curve that says whether the stated
 * confidence means anything. `n` travels with every number, because a 100% hit
 * rate on two calls is not a hit rate.
 */
export function ScorecardPanel({
  scorecard,
  loading,
  error,
}: {
  scorecard: Scorecard | null;
  loading: boolean;
  error: string | null;
}) {
  const buckets = scorecard?.by_confidence ?? [];

  return (
    <Panel
      title="Are we as right as we sound?"
      eyebrow="Realised record · calibration"
      aside={
        scorecard?.n_directional ? (
          <span className="font-mono text-sm text-zinc-100">{pct(scorecard.hit_rate)}</span>
        ) : null
      }
    >
      {loading ? (
        <Skeleton lines={5} />
      ) : !scorecard || !scorecard.n_resolved ? (
        <Empty
          message={error ?? 'No calls have resolved yet.'}
          hint="A call resolves once seven further sessions have printed."
        />
      ) : (
        <>
          {buckets.length > 0 && (
            <>
              <ul className="space-y-3.5">
                {buckets.map((bucket) => (
                  <li key={bucket.bucket} className="flex items-center gap-3">
                    <span className="w-16 shrink-0 font-mono text-[11px] text-zinc-400">
                      {bucket.bucket}
                    </span>
                    <span className="flex-1 relative h-[22px]">
                      <span
                        className="absolute left-0 top-0.5 h-2 rounded"
                        style={{
                          width: `${Math.min(100, (bucket.stated ?? 0) * 100)}%`,
                          backgroundColor: 'var(--series-1)',
                        }}
                      />
                      <span
                        className="absolute left-0 top-3 h-2 rounded"
                        style={{
                          width: `${Math.min(100, (bucket.realised ?? 0) * 100)}%`,
                          backgroundColor: 'var(--text-muted)',
                        }}
                      />
                    </span>
                    <span className="w-9 shrink-0 text-right font-mono text-[10px] text-zinc-600">
                      n={bucket.n}
                    </span>
                  </li>
                ))}
              </ul>

              <div className="flex flex-wrap gap-4 mt-4 pt-3.5 border-t border-white/5">
                <span className="flex items-center gap-2 text-[11px] text-zinc-400">
                  <span
                    className="h-2 w-2 rounded-sm"
                    style={{ backgroundColor: 'var(--series-1)' }}
                  />
                  Stated confidence
                </span>
                <span className="flex items-center gap-2 text-[11px] text-zinc-400">
                  <span
                    className="h-2 w-2 rounded-sm"
                    style={{ backgroundColor: 'var(--text-muted)' }}
                  />
                  Actually right
                </span>
              </div>
            </>
          )}

          <div
            className="glass-well px-4 py-3.5 mt-5"
            style={{ borderColor: 'rgba(250, 178, 25, 0.22)' }}
          >
            <p className="text-[11px] leading-relaxed text-zinc-300">{scorecard.verdict}</p>
          </div>

          <div className="grid grid-cols-3 gap-3 mt-4">
            <div className="glass-well px-3 py-2.5">
              <p className="label-eyebrow mb-1">Resolved</p>
              <p className="font-mono text-xs text-zinc-200">{scorecard.n_resolved}</p>
            </div>
            <div className="glass-well px-3 py-2.5">
              <p className="label-eyebrow mb-1">Pending</p>
              <p className="font-mono text-xs text-zinc-200">{scorecard.n_unresolved}</p>
            </div>
            <div className="glass-well px-3 py-2.5">
              <p className="label-eyebrow mb-1">Calib. error</p>
              <p className="font-mono text-xs text-zinc-200">{pct(scorecard.calibration_error)}</p>
            </div>
          </div>

          {scorecard.by_event?.note && (
            <p className="text-[10px] text-zinc-600 mt-4 leading-relaxed">
              {scorecard.by_event.note}
              {scorecard.by_event.gap !== null && ` (${pp(scorecard.by_event.gap)})`}
            </p>
          )}
        </>
      )}
    </Panel>
  );
}
