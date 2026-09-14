import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { num, shortDate } from '../lib/format';
import { AXIS_TICK, ChartTooltip, GRID_STROKE } from './ChartBits';
import { Empty, Panel, Skeleton } from './Panel';

interface Point {
  date: string;
  close: number;
}

/** One series, so the title names it and no legend is needed. */
export function PriceChart({
  points,
  loading,
  error,
}: {
  points: Point[] | null;
  loading: boolean;
  error: string | null;
}) {
  const last = points?.[points.length - 1];
  const first = points?.[0];
  const change = first && last && first.close ? last.close / first.close - 1 : null;

  return (
    <Panel
      title="S&P 500 close"
      eyebrow={points?.length ? `${points.length} sessions` : 'Price history'}
      aside={
        last ? (
          <>
            <p className="font-mono text-lg text-zinc-100 tabular-nums">
              {last.close.toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </p>
            <p
              className="font-mono text-[11px]"
              style={{
                color: (change ?? 0) >= 0 ? 'var(--status-good)' : 'var(--status-critical)',
              }}
            >
              {change === null ? '' : `${change >= 0 ? '+' : ''}${(change * 100).toFixed(2)}%`}
            </p>
          </>
        ) : null
      }
    >
      {loading ? (
        <Skeleton lines={6} />
      ) : !points?.length ? (
        <Empty
          message={error ?? 'No price history yet.'}
          hint="Populated once the pipeline completes its first run."
        />
      ) : (
        <div className="h-60 sm:h-72 -ml-2">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={points} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--series-1)" stopOpacity={0.28} />
                  <stop offset="100%" stopColor="var(--series-1)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={GRID_STROKE} vertical={false} />
              <XAxis
                dataKey="date"
                tick={AXIS_TICK}
                tickFormatter={shortDate}
                axisLine={false}
                tickLine={false}
                minTickGap={48}
              />
              <YAxis
                tick={AXIS_TICK}
                axisLine={false}
                tickLine={false}
                width={52}
                domain={['auto', 'auto']}
                tickFormatter={(value: number) => value.toFixed(0)}
              />
              <Tooltip
                cursor={{ stroke: 'var(--axis)', strokeWidth: 1 }}
                content={({ active, payload }: any) =>
                  active && payload?.length ? (
                    <ChartTooltip
                      title={shortDate(payload[0].payload.date)}
                      rows={[
                        {
                          label: 'Close',
                          value: num(payload[0].payload.close, 2),
                          color: 'var(--series-1)',
                        },
                      ]}
                    />
                  ) : null
                }
              />
              <Area
                type="monotone"
                dataKey="close"
                stroke="var(--series-1)"
                strokeWidth={2}
                fill="url(#priceFill)"
                dot={false}
                activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface-1)' }}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}
