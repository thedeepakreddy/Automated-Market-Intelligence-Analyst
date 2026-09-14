import type { Theme } from '../lib/api';
import { pct } from '../lib/format';
import { Empty, Panel, Skeleton } from './Panel';

const STANCE_COLOR: Record<Theme['stance'], string> = {
  bullish: 'var(--status-good)',
  bearish: 'var(--status-critical)',
  mixed: 'var(--text-muted)',
};

const SHIFT_LABEL: Record<string, string> = {
  new: '▲ new',
  growing: '▲ growing',
  fading: '▼ fading',
  gone: '× gone',
  steady: '',
};

/**
 * What the crowd is arguing about, rather than how it feels. A single
 * polarity score throws away the only genuinely interesting part of a forum —
 * the subject.
 */
export function ThemesPanel({
  themes,
  source,
  documentCount,
  shift,
  loading,
  error,
}: {
  themes: Theme[] | null;
  source?: string;
  documentCount?: number;
  shift: Array<{ theme: string; status: string; change: number | null }> | null;
  loading: boolean;
  error: string | null;
}) {
  const shown = (themes ?? []).slice(0, 5);
  const widest = Math.max(...shown.map((theme) => theme.mentions ?? 0), 1);
  const shiftFor = (name: string) =>
    shift?.find((entry) => entry.theme.toLowerCase() === name.toLowerCase())?.status;

  const isLlm = source?.startsWith('gemini');

  return (
    <Panel
      title="What the crowd is arguing about"
      eyebrow={documentCount ? `Reddit · ${documentCount} posts scored` : 'Reddit narratives'}
    >
      {loading ? (
        <Skeleton lines={5} />
      ) : !shown.length ? (
        <Empty
          message={error ?? 'No themes extracted for this run.'}
          hint="Needs Reddit credentials; without them the pipeline runs on a neutral series."
        />
      ) : (
        <>
          <ul className="space-y-3.5">
            {shown.map((theme) => {
              const status = shiftFor(theme.theme);
              return (
                <li key={theme.theme} className="flex items-start gap-3.5">
                  <span className="w-11 shrink-0 font-mono text-[11px] text-zinc-100 text-right pt-px tabular-nums">
                    {theme.share !== null ? pct(theme.share, 0) : `n=${theme.mentions ?? 0}`}
                  </span>
                  <span className="flex-1 min-w-0">
                    <span className="flex items-center gap-2 mb-1.5 flex-wrap">
                      <span className="text-[12px] text-zinc-100">{theme.theme}</span>
                      <span
                        className="font-mono text-[9px] uppercase tracking-wider rounded-full px-1.5 py-0.5 border"
                        style={{
                          color: STANCE_COLOR[theme.stance],
                          borderColor: `${STANCE_COLOR[theme.stance]}4d`,
                        }}
                      >
                        {theme.stance}
                      </span>
                      {status && SHIFT_LABEL[status] && (
                        <span
                          className="font-mono text-[9px]"
                          style={{
                            color:
                              status === 'fading' || status === 'gone'
                                ? 'var(--text-muted)'
                                : 'var(--status-warning)',
                          }}
                        >
                          {SHIFT_LABEL[status]}
                        </span>
                      )}
                    </span>
                    <span className="block h-[3px] rounded-full bg-white/[0.06] relative">
                      <span
                        className="absolute inset-y-0 left-0 rounded-full"
                        style={{
                          width: `${((theme.mentions ?? 0) / widest) * 100}%`,
                          backgroundColor: 'var(--series-2)',
                        }}
                      />
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>

          <p className="text-[10px] text-zinc-600 mt-5 leading-relaxed">
            {isLlm
              ? 'Themes extracted by Gemini from post text. Share of recent posts touching each topic.'
              : 'No Gemini key configured, so these are the most repeated phrases rather than interpreted topics.'}
          </p>
        </>
      )}
    </Panel>
  );
}
