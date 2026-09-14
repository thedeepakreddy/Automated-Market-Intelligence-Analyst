import type { Latest } from '../lib/api';
import { Empty, Panel, Skeleton } from './Panel';

/**
 * The generated outlook. The source is stated plainly, because a deterministic
 * template summary and a language-model draft are different things and should
 * not be presented as the same one.
 */
export function WeeklyReport({
  report,
  loading,
  error,
}: {
  report: Latest['report'] | null;
  loading: boolean;
  error: string | null;
}) {
  const text = report?.text?.trim();
  const source = report?.source ?? '';
  const isGenerated = source.startsWith('gemini');
  const paragraphs = text ? text.split(/\n\s*\n/).filter(Boolean) : [];

  return (
    <Panel
      title="Weekly outlook"
      eyebrow={isGenerated ? `Generated · ${source.replace('gemini:', '')}` : 'Deterministic summary'}
    >
      {loading ? (
        <Skeleton lines={7} />
      ) : !paragraphs.length ? (
        <Empty message={error ?? 'No outlook written for this run.'} />
      ) : (
        <>
          <div className="space-y-3.5 max-h-96 overflow-y-auto pr-1">
            {paragraphs.map((paragraph, index) => (
              <p
                key={index}
                className="text-[12.5px] leading-[1.85] text-zinc-400 whitespace-pre-line"
              >
                {paragraph.replace(/\*\*/g, '').replace(/^#+\s*/gm, '')}
              </p>
            ))}
          </div>

          {!isGenerated && (
            <p className="text-[10px] text-zinc-600 mt-4 leading-relaxed">
              Written without the language model — no Gemini key is configured, so this is a
              deterministic summary of the run's own numbers.
            </p>
          )}
        </>
      )}
    </Panel>
  );
}
