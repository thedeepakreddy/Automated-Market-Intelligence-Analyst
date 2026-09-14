import type { Analogue, Regime } from '../lib/api';
import { fullDate, pct, signedPct } from '../lib/format';
import { Empty, Panel, Skeleton } from './Panel';

/**
 * Nearest historical sessions by standardised state vector, with what happened
 * next. Deliberately not a forecast — it shows the spread of outcomes and lets
 * the reader draw the inference, which is how analogue reasoning actually works.
 */
export function AnaloguePanel({
  analogues,
  regime,
  loading,
  error,
}: {
  analogues: Analogue[] | null;
  regime: Regime | null;
  loading: boolean;
  error: string | null;
}) {
  const currentRegime = regime?.regimes.find((entry) => entry.id === regime.current);

  return (
    <Panel
      title="This looks like…"
      eyebrow="Nearest historical sessions"
      aside={
        currentRegime ? (
          <span className="text-[10px] font-mono text-zinc-400 border border-white/10 bg-white/[0.03] rounded-full px-3 py-1.5">
            Regime {currentRegime.id} · {currentRegime.label}
          </span>
        ) : null
      }
    >
      {loading ? (
        <Skeleton lines={5} />
      ) : !analogues?.length ? (
        <Empty
          message={error ?? 'Not enough history to find analogues yet.'}
          hint="Needs roughly a quarter of sessions beyond the exclusion window."
        />
      ) : (
        <>
          <ul className="space-y-2.5">
            {analogues.map((analogue) => (
              <li
                key={analogue.date}
                className="glass-well px-4 py-3.5 flex items-center gap-4"
              >
                <span className="font-mono text-[11.5px] text-zinc-200 w-20 shrink-0">
                  {fullDate(analogue.date)}
                </span>
                <span className="relative flex-1 h-1 rounded-full bg-white/5">
                  <span
                    className="absolute inset-y-0 left-0 rounded-full"
                    style={{
                      width: `${Math.max(4, (analogue.similarity ?? 0) * 100)}%`,
                      backgroundColor: 'var(--series-3)',
                    }}
                  />
                </span>
                <span className="font-mono text-[11px] text-zinc-500 w-10 text-right shrink-0">
                  {pct(analogue.similarity, 0)}
                </span>
                <span
                  className="font-mono text-[11.5px] w-16 text-right shrink-0 tabular-nums"
                  style={{
                    color:
                      analogue.forward_return === null
                        ? 'var(--text-muted)'
                        : analogue.forward_return >= 0
                          ? 'var(--status-good)'
                          : 'var(--status-critical)',
                  }}
                >
                  {signedPct(analogue.forward_return, 2)}
                </span>
              </li>
            ))}
          </ul>

          {currentRegime && (
            <div className="grid grid-cols-3 gap-3 mt-5">
              <div className="glass-well px-3 py-2.5">
                <p className="label-eyebrow mb-1">In regime</p>
                <p className="font-mono text-xs text-zinc-200">{currentRegime.sessions} sessions</p>
              </div>
              <div className="glass-well px-3 py-2.5">
                <p className="label-eyebrow mb-1">Up rate</p>
                <p className="font-mono text-xs text-zinc-200">{pct(currentRegime.up_rate, 0)}</p>
              </div>
              <div className="glass-well px-3 py-2.5">
                <p className="label-eyebrow mb-1">Since</p>
                <p className="font-mono text-xs text-zinc-200">{fullDate(regime?.current_since)}</p>
              </div>
            </div>
          )}

          <p className="text-[10px] text-zinc-600 mt-5 leading-relaxed">
            Forward 7-session return after each analogue. {analogues.length} samples is an anecdote,
            not a base rate — read the spread, not the average.
          </p>
        </>
      )}
    </Panel>
  );
}
