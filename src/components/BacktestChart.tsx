import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { Backtest } from '../lib/api';
import { num, shortDate } from '../lib/format';
import { AXIS_TICK, ChartTooltip, GRID_STROKE, Legend } from './ChartBits';
import { Empty, Panel, Skeleton } from './Panel';

const SERIES = [
  { key: 'strategy', label: 'Strategy', color: 'var(--series-1)' },
  { key: 'buy_and_hold', label: 'Buy & hold', color: 'var(--series-2)' },
];

/**
 * Growth of 1 for the long/flat strategy against buy-and-hold over the same
 * window. Both on one axis — two scales would let the strategy look like
 * whatever the axis wanted it to.
 */
export function BacktestChart({
  backtest,
  loading,
  error,
}: {
  backtest: Backtest | null;
  loading: boolean;
  error: string | null;
}) {
  const curve = backtest?.equity_curve ?? [];

  return (
    <Panel
      title="Long/flat strategy vs buy-and-hold"
      eyebrow={
        backtest?.n_periods
          ? `Out of sample · ${backtest.n_periods} non-overlapping periods`
          : 'Out of sample'
      }
      aside={<Legend items={SERIES.map(({ label, color }) => ({ label, color }))} />}
    >
      {loading ? (
        <Skeleton lines={7} />
      ) : !curve.length ? (
        <Empty
          message={error ?? backtest?.note ?? 'No backtest available yet.'}
          hint="Needs enough held-out sessions to realise a full holding period."
        />
      ) : (
        <>
          <div className="h-60 sm:h-72 -ml-2">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={curve} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid stroke={GRID_STROKE} vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={AXIS_TICK}
                  tickFormatter={shortDate}
                  axisLine={false}
                  tickLine={false}
                  minTickGap={44}
                />
                <YAxis
                  tick={AXIS_TICK}
                  axisLine={false}
                  tickLine={false}
                  width={46}
                  domain={['auto', 'auto']}
                  tickFormatter={(value: number) => value.toFixed(2)}
                />
                <Tooltip
                  cursor={{ stroke: 'var(--axis)', strokeWidth: 1 }}
                  content={({ active, payload }: any) =>
                    active && payload?.length ? (
                      <ChartTooltip
                        title={shortDate(payload[0].payload.date)}
                        rows={SERIES.map((series) => ({
                          label: series.label,
                          value: num(payload[0].payload[series.key], 3),
                          color: series.color,
                        }))}
                        footer="Growth of 1"
                      />
                    ) : null
                  }
                />
                {SERIES.map((series) => (
                  <Line
                    key={series.key}
                    type="monotone"
                    dataKey={series.key}
                    stroke={series.color}
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface-1)' }}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[10px] text-zinc-600 mt-4 leading-relaxed">
            Positions are sampled every {backtest?.horizon_sessions ?? 7} sessions so holding
            periods never overlap. UNCERTAIN is flat, not a coin flip.
          </p>
        </>
      )}
    </Panel>
  );
}
