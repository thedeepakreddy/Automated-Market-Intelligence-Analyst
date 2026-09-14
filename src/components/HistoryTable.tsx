import { Check, Minus, X } from 'lucide-react';
import type { HistoryRow } from '../lib/api';
import { pct, shortDate, signedPct } from '../lib/format';
import { Empty, Panel, SIGNAL_COLOR, SIGNAL_GLYPH, Skeleton } from './Panel';

const COLUMNS = 'grid grid-cols-[72px_1fr_58px_62px_24px] gap-x-3 items-center';

/** Past calls scored against what actually happened. */
export function HistoryTable({
  rows,
  loading,
  error,
}: {
  rows: HistoryRow[] | null;
  loading: boolean;
  error: string | null;
}) {
  // Newest first for reading; the API returns oldest-first for charting.
  const recent = [...(rows ?? [])].reverse().slice(0, 7);

  return (
    <Panel title="Track record" eyebrow="Resolved calls">
      {loading ? (
        <Skeleton lines={6} />
      ) : !recent.length ? (
        <Empty message={error ?? 'No runs recorded yet.'} />
      ) : (
        <>
          <div
            className={`${COLUMNS} label-eyebrow pb-2.5 border-b border-white/[0.07]`}
          >
            <span>Date</span>
            <span>Called</span>
            <span className="text-right">Conf.</span>
            <span className="text-right">Actual</span>
            <span />
          </div>

          {recent.map((row) => {
            const outcome = row.outcome;
            const correct = outcome?.correct;
            return (
              <div
                key={`${row.as_of_date}-${row.generated_at}`}
                className={`${COLUMNS} py-3 border-b border-white/[0.04] last:border-0 text-[11.5px]`}
              >
                <span className="font-mono text-zinc-400">{shortDate(row.as_of_date)}</span>
                <span style={{ color: SIGNAL_COLOR[row.prediction] }}>
                  <span aria-hidden="true">{SIGNAL_GLYPH[row.prediction]}</span> {row.prediction}
                </span>
                <span className="font-mono text-right text-zinc-300 tabular-nums">
                  {pct(row.confidence)}
                </span>
                <span
                  className="font-mono text-right tabular-nums"
                  style={{
                    color:
                      outcome?.realized_return === null || outcome?.realized_return === undefined
                        ? 'var(--text-muted)'
                        : outcome.realized_return >= 0
                          ? 'var(--status-good)'
                          : 'var(--status-critical)',
                  }}
                >
                  {signedPct(outcome?.realized_return, 2)}
                </span>
                <span className="flex justify-end">
                  {correct === true && (
                    <Check size={14} strokeWidth={2.5} style={{ color: 'var(--status-good)' }} />
                  )}
                  {correct === false && (
                    <X size={14} strokeWidth={2.5} style={{ color: 'var(--status-critical)' }} />
                  )}
                  {(correct === null || correct === undefined) && (
                    <Minus size={14} strokeWidth={2.5} className="text-zinc-700" />
                  )}
                </span>
              </div>
            );
          })}

          <p className="text-[10px] text-zinc-600 mt-4 leading-relaxed">
            UNCERTAIN calls record their realised move but are not scored right or wrong —
            declining to take a view is neither.
          </p>
        </>
      )}
    </Panel>
  );
}
