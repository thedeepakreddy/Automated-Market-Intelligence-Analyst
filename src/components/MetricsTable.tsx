import type { Backtest } from '../lib/api';
import { num, pct, signedPct } from '../lib/format';
import { Empty, Panel, Skeleton, Stat } from './Panel';

/**
 * The four numbers a strategy is judged on, each against its benchmark.
 * Return without drawdown and Sharpe beside it is how a backtest flatters
 * itself, so they move together or not at all.
 */
export function MetricsTable({
  backtest,
  loading,
  error,
}: {
  backtest: Backtest | null;
  loading: boolean;
  error: string | null;
}) {
  const strategy = backtest?.strategy;
  const benchmark = backtest?.buy_and_hold;

  return (
    <Panel title="Metrics" eyebrow="Strategy vs benchmark" className="h-full">
      {loading ? (
        <Skeleton lines={5} />
      ) : !backtest?.n_periods || !strategy ? (
        <Empty message={error ?? backtest?.note ?? 'No backtest available yet.'} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-x-5 gap-y-6">
            <Stat
              label="Accuracy"
              value={pct(backtest.directional_accuracy)}
              hint={`of ${backtest.n_directional_calls ?? 0} directional calls`}
            />
            <Stat
              label="Sharpe"
              value={num(strategy.sharpe)}
              hint={`vs ${num(benchmark?.sharpe)} benchmark`}
            />
            <Stat
              label="Max drawdown"
              value={pct(strategy.max_drawdown)}
              hint={`vs ${pct(benchmark?.max_drawdown)}`}
              color="var(--status-critical)"
            />
            <Stat
              label="Cumulative"
              value={signedPct(strategy.cumulative_return)}
              hint={`vs ${signedPct(benchmark?.cumulative_return)}`}
              color={
                (strategy.cumulative_return ?? 0) >= (benchmark?.cumulative_return ?? 0)
                  ? 'var(--status-good)'
                  : undefined
              }
            />
          </div>

          <div className="glass-well px-4 py-3 mt-6">
            <p className="text-[11px] leading-relaxed text-zinc-400">
              {backtest.n_periods} periods is a small sample. Read these as indicative, and check
              the realised record below before trusting any of them.
            </p>
          </div>

          {backtest.coverage !== undefined && (
            <p className="text-[10px] text-zinc-600 mt-3 leading-relaxed">
              Invested in {backtest.n_long_periods ?? 0} of {backtest.n_periods} periods; a
              directional view was taken in {pct(backtest.coverage, 0)}.
            </p>
          )}
        </>
      )}
    </Panel>
  );
}
