import { useEffect, useRef, useState } from 'react';
import { ArrowRight } from 'lucide-react';
import { api } from '../lib/api';
import { Panel } from './Panel';

interface Exchange {
  question: string;
  answer: string | null;
  source: string;
  failed?: boolean;
}

const SUGGESTIONS = [
  'Why were you bearish in March?',
  'What has driven the last five calls?',
  'When were you most wrong?',
];

/**
 * Questions about the model's own history, answered only from the stored run
 * record. It cannot opine on markets — there is nothing in the context to
 * opine from, which is the point.
 */
export function AskPanel() {
  const [question, setQuestion] = useState('');
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [asking, setAsking] = useState(false);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const ask = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || asking) return;

    setAsking(true);
    setQuestion('');
    try {
      const response = await api.ask(trimmed);
      if (alive.current) {
        setExchanges((current) => [
          ...current,
          { question: trimmed, answer: response.answer, source: response.source },
        ]);
      }
    } catch (caught) {
      if (alive.current) {
        setExchanges((current) => [
          ...current,
          {
            question: trimmed,
            answer: caught instanceof Error ? caught.message : 'Request failed',
            source: 'error',
            failed: true,
          },
        ]);
      }
    } finally {
      if (alive.current) setAsking(false);
    }
  };

  return (
    <Panel
      title="Ask the analyst"
      eyebrow="Grounded in the stored record"
      className="flex flex-col"
      bodyClassName="flex flex-col flex-1"
    >
      <div className="flex-1 space-y-3 min-h-[9rem] max-h-80 overflow-y-auto pr-1">
        {exchanges.length === 0 && (
          <div className="space-y-2.5">
            <p className="text-[11.5px] text-zinc-500 leading-relaxed">
              Answers come only from past runs — their signals, drivers and outcomes. It has no
              view on markets beyond what it has already recorded.
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => ask(suggestion)}
                  className="text-[11px] text-zinc-400 hover:text-zinc-100 border border-white/10 hover:border-white/20 rounded-full px-3 py-1.5 transition-colors text-left"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {exchanges.map((exchange, index) => (
          <div key={index} className="space-y-2.5">
            <p
              className="ml-auto max-w-[80%] w-fit rounded-[14px_14px_4px_14px] px-3.5 py-2.5 text-[12px] text-zinc-100"
              style={{
                backgroundColor: 'rgba(57, 135, 229, 0.13)',
                border: '1px solid rgba(57, 135, 229, 0.26)',
              }}
            >
              {exchange.question}
            </p>
            <p
              className="max-w-[90%] w-fit rounded-[14px_14px_14px_4px] px-3.5 py-3 text-[12px] leading-[1.7] whitespace-pre-line"
              style={{
                backgroundColor: 'rgba(0, 0, 0, 0.26)',
                border: '1px solid rgba(255, 255, 255, 0.06)',
                color: exchange.failed ? 'var(--status-warning)' : 'var(--text-secondary)',
              }}
            >
              {exchange.answer}
            </p>
          </div>
        ))}

        {asking && <p className="text-[11px] text-zinc-500">Reading the record…</p>}
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          ask(question);
        }}
        className="flex items-center gap-2.5 glass-well px-3.5 py-2.5 mt-4"
      >
        <input
          type="text"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask about any past call…"
          aria-label="Ask about any past call"
          maxLength={500}
          className="flex-1 bg-transparent text-[12px] text-zinc-100 placeholder:text-zinc-600 outline-none"
        />
        <button
          type="submit"
          disabled={asking || !question.trim()}
          aria-label="Send question"
          className="disabled:opacity-30 transition-opacity"
        >
          <ArrowRight size={16} style={{ color: 'var(--series-1)' }} />
        </button>
      </form>
    </Panel>
  );
}
