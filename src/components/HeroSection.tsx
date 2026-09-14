import type { Delta, EventWindow, Signal } from '../lib/api';
import { pct, pp, fullDate } from '../lib/format';
import { SIGNAL_COLOR, SIGNAL_GLYPH } from './Panel';

/**
 * The call, above the fold. Confidence is stated as conviction in whichever
 * side was called, and the band note explains what UNCERTAIN means so a
 * neutral reading is not mistaken for a weak bullish one.
 */
export function HeroSection({
  prediction,
  confidence,
  asOf,
  delta,
  events,
}: {
  prediction: Signal;
  confidence: number;
  asOf: string;
  delta: Delta | null;
  events: EventWindow | null;
}) {
  const color = SIGNAL_COLOR[prediction];

  return (
    <div className="text-center py-10 md:py-14 flex flex-col items-center">
      <span className="label-eyebrow mb-6">7-session horizon · as of {fullDate(asOf)}</span>

      <h1
        className="text-6xl sm:text-8xl font-semibold tracking-tighter mb-5 flex items-center gap-4"
        style={{ color }}
      >
        <span aria-hidden="true" className="opacity-40">
          {SIGNAL_GLYPH[prediction]}
        </span>
        {prediction}
      </h1>

      <div className="flex items-center gap-5">
        <span className="label-eyebrow">Confidence</span>
        <span className="h-px w-10 sm:w-16 bg-white/10" />
        <span className="text-2xl font-mono tracking-tight text-zinc-100">{pct(confidence)}</span>
      </div>

      {prediction === 'UNCERTAIN' && (
        <p className="text-[11px] text-zinc-500 mt-4 max-w-md leading-relaxed">
          The blended probability sits inside the neutral band. The model is declining to take a
          view this week, which is a position in itself — not a weak bullish call.
        </p>
      )}

      {delta && (
        <div className="mt-8 max-w-2xl">
          <div
            className="glass-well px-4 py-3 flex items-start gap-3 text-left"
            style={
              delta.signal_changed
                ? { borderColor: 'rgba(250, 178, 25, 0.35)' }
                : undefined
            }
          >
            <span
              className="label-eyebrow mt-0.5 shrink-0"
              style={delta.signal_changed ? { color: 'var(--status-warning)' } : undefined}
            >
              {delta.signal_changed ? 'Changed' : 'Held'}
            </span>
            <p className="text-xs text-zinc-300 leading-relaxed">
              {delta.headline}
              {delta.probability_change !== null && (
                <span className="text-zinc-500 font-mono ml-1">({pp(delta.probability_change)})</span>
              )}
            </p>
          </div>
        </div>
      )}

      {events?.has_event && (
        <p
          className="text-[11px] mt-3 max-w-xl leading-relaxed"
          style={{ color: 'var(--status-warning)' }}
        >
          ⚠ {events.note} Accuracy through policy weeks is reported separately in the scorecard.
        </p>
      )}
    </div>
  );
}
