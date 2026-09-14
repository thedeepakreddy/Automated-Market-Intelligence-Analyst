import React from 'react';
import type { Delta } from '../lib/api';
import { featureLabel, pp, shortDate, signed } from '../lib/format';
import { Empty, Panel } from './Panel';

/**
 * What moved since the previous run. The static attribution chart says which
 * features matter; this says which ones *changed their mind*, which is the
 * part that is actually news.
 */
export function DeltaPanel({ delta }: { delta: Delta | null }) {
  if (!delta) {
    return (
      <Panel title="What changed" eyebrow="Since the previous run">
        <Empty
          message="No previous run to compare against yet."
          hint="The delta appears once the pipeline has completed twice."
        />
      </Panel>
    );
  }

  const movements = delta.movements.filter((movement) => Number.isFinite(movement.change));

  return (
    <Panel
      title="What changed"
      eyebrow={`vs ${shortDate(delta.compared_with_as_of)}`}
      aside={
        delta.probability_change !== null ? (
          <span
            className="font-mono text-sm"
            style={{
              color:
                delta.probability_change >= 0 ? 'var(--status-good)' : 'var(--status-critical)',
            }}
          >
            {pp(delta.probability_change)}
          </span>
        ) : null
      }
    >
      <p className="text-xs text-zinc-300 leading-relaxed mb-5">{delta.headline}</p>

      {movements.length === 0 ? (
        <Empty message="No driver moved enough to report." />
      ) : (
        <ul className="space-y-2.5">
          {movements.map((movement) => {
            const rising = movement.change >= 0;
            const magnitude = Math.abs(movement.change);
            const widest = Math.max(...movements.map((item) => Math.abs(item.change)), 1e-9);
            return (
              <li key={movement.feature} className="flex items-center gap-3">
                <span className="w-40 sm:w-52 shrink-0 text-[11px] text-zinc-400 truncate">
                  {featureLabel(movement.feature)}
                </span>

                {/* Bar reads from a centre baseline: left is a fall, right a rise. */}
                <span className="relative flex-1 h-1.5 rounded-full bg-white/5 overflow-hidden">
                  <span className="absolute inset-y-0 left-1/2 w-px bg-white/15" />
                  <span
                    className="absolute inset-y-0 rounded-full"
                    style={{
                      width: `${(magnitude / widest) * 50}%`,
                      [rising ? 'left' : 'right']: '50%',
                      backgroundColor: rising ? 'var(--series-1)' : 'var(--series-2)',
                    }}
                  />
                </span>

                <span className="w-16 shrink-0 text-right font-mono text-[11px] text-zinc-300">
                  {signed(movement.change)}
                </span>
                {movement.status !== 'held' && (
                  <span className="label-eyebrow w-12 shrink-0 text-right">{movement.status}</span>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <p className="text-[10px] text-zinc-600 mt-5 leading-relaxed">
        Change in each driver's SHAP contribution to P(up) between the two runs. Rightward is a
        push toward UP, leftward toward DOWN.
      </p>
    </Panel>
  );
}
