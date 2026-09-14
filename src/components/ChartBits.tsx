/**
 * Shared chart chrome, so every chart reads as one system.
 *
 * Axes and gridlines are deliberately recessive; the marks carry the meaning.
 * Text stays in ink tokens rather than the series colour - a coloured swatch
 * beside a label carries identity, the label itself does not.
 */

export const AXIS_TICK = {
  fill: 'var(--text-muted)',
  fontSize: 10,
  fontFamily: 'var(--font-mono)',
} as const;

export const GRID_STROKE = 'var(--gridline)';

export interface TooltipRow {
  label: string;
  value: string;
  color?: string;
}

export function ChartTooltip({
  title,
  rows,
  footer,
}: {
  title?: string;
  rows: TooltipRow[];
  footer?: string;
}) {
  return (
    <div className="glass px-3 py-2.5 text-[11px] min-w-[9rem]" style={{ borderRadius: '0.625rem' }}>
      {title && <p className="label-eyebrow mb-1.5">{title}</p>}
      <div className="space-y-1">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-zinc-400">
              {row.color && (
                <span
                  className="h-2 w-2 rounded-sm shrink-0"
                  style={{ backgroundColor: row.color }}
                />
              )}
              {row.label}
            </span>
            <span className="font-mono text-zinc-100 tabular-nums">{row.value}</span>
          </div>
        ))}
      </div>
      {footer && <p className="text-[10px] text-zinc-500 mt-1.5">{footer}</p>}
    </div>
  );
}

/** Legend shown whenever a chart carries two or more series. */
export function Legend({ items }: { items: Array<{ label: string; color: string }> }) {
  return (
    <div className="flex flex-wrap items-center gap-4">
      {items.map((item) => (
        <span key={item.label} className="flex items-center gap-1.5 text-[11px] text-zinc-400">
          <span className="h-2 w-2 rounded-sm" style={{ backgroundColor: item.color }} />
          {item.label}
        </span>
      ))}
    </div>
  );
}
