import React from 'react';
import type { Signal } from '../lib/api';

/** The glass panel every section sits in. */
export function Panel({
  title,
  eyebrow,
  aside,
  children,
  className = '',
  bodyClassName = '',
}: {
  title?: string;
  eyebrow?: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={`glass p-5 sm:p-6 ${className}`}>
      {(title || aside) && (
        <header className="flex items-start justify-between gap-4 mb-5">
          <div className="min-w-0">
            {eyebrow && <p className="label-eyebrow mb-1.5">{eyebrow}</p>}
            {title && (
              <h3 className="text-sm font-medium text-zinc-100 leading-tight">{title}</h3>
            )}
          </div>
          {aside && <div className="shrink-0 text-right">{aside}</div>}
        </header>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}

/** Placeholder that keeps a panel's height while its data loads. */
export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2.5 animate-pulse" aria-hidden="true">
      {Array.from({ length: lines }).map((_, index) => (
        <div
          key={index}
          className="h-3 rounded bg-white/5"
          style={{ width: `${90 - index * 12}%` }}
        />
      ))}
    </div>
  );
}

/**
 * One place where "no data" is explained. A warming-up engine, an unreachable
 * one, and an analytic that genuinely has nothing to say are different
 * situations, and flattening them into "no data" would hide a broken deploy.
 */
export function Empty({
  message,
  hint,
  tone = 'muted',
}: {
  message: string;
  hint?: string;
  tone?: 'muted' | 'warning';
}) {
  return (
    <div className="glass-well px-4 py-5 text-center">
      <p
        className="text-xs leading-relaxed"
        style={{ color: tone === 'warning' ? 'var(--status-warning)' : 'var(--text-secondary)' }}
      >
        {message}
      </p>
      {hint && <p className="text-[11px] text-zinc-600 mt-1.5 leading-relaxed">{hint}</p>}
    </div>
  );
}

export const SIGNAL_COLOR: Record<Signal, string> = {
  UP: 'var(--status-good)',
  DOWN: 'var(--status-critical)',
  UNCERTAIN: 'var(--status-warning)',
};

/** Arrow glyph per signal, so direction never rests on colour alone. */
export const SIGNAL_GLYPH: Record<Signal, string> = {
  UP: '↑',
  DOWN: '↓',
  UNCERTAIN: '~',
};

export function SignalPill({ signal, size = 'sm' }: { signal: Signal; size?: 'sm' | 'xs' }) {
  const color = SIGNAL_COLOR[signal];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-medium ${
        size === 'xs' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs'
      }`}
      style={{ color, borderColor: `${color}55`, backgroundColor: `${color}14` }}
    >
      <span aria-hidden="true">{SIGNAL_GLYPH[signal]}</span>
      {signal}
    </span>
  );
}

/** A labelled statistic. `hint` carries the caveat that keeps it honest. */
export function Stat({
  label,
  value,
  hint,
  color,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  color?: string;
}) {
  return (
    <div>
      <p className="label-eyebrow mb-1">{label}</p>
      <p
        className="text-xl font-light tracking-tight"
        style={{ color: color ?? 'var(--text-primary)' }}
      >
        {value}
      </p>
      {hint && <p className="text-[10px] text-zinc-600 mt-1 leading-snug">{hint}</p>}
    </div>
  );
}
