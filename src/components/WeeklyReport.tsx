import React from 'react';
import { ArrowRight } from 'lucide-react';

export function WeeklyReport() {
  return (
    <div className="bg-black border border-zinc-900 rounded-2xl p-6 sm:p-8 flex flex-col h-full">
      <div className="flex justify-between items-baseline mb-8">
        <h3 className="text-sm font-medium text-zinc-100">AI Weekly Synthesis</h3>
        <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Gemini Pro</span>
      </div>

      <div className="space-y-6 flex-1 text-[13.5px] leading-relaxed text-zinc-400">
        <div>
          <p className="text-zinc-100 font-medium mb-1">Outlook</p>
          <p>
            The S&P500 presents a positive setup for the 7-day period. Models detect robust momentum decoupled from traditional macro drags, corroborated by a surge in retail sentiment.
          </p>
        </div>

        <div>
          <p className="text-zinc-100 font-medium mb-1">Key Factors</p>
          <ul className="list-disc pl-4 space-y-1 text-zinc-500 marker:text-zinc-700">
            <li>Upcoming CPI data may introduce short-term volatility.</li>
            <li>Federal Funds Rate speculation remains a lingering headwind.</li>
            <li>Sentiment flipping neutral-to-bullish offsets macro pressure.</li>
          </ul>
        </div>
      </div>

      <div className="mt-8 pt-6 border-t border-zinc-900 flex justify-between items-center">
        <p className="text-[9px] uppercase tracking-widest text-zinc-600">For demonstration purposes</p>
        <button className="text-[11px] font-medium text-zinc-100 flex items-center gap-1 hover:text-zinc-400 transition-colors group">
          Export Document
          <ArrowRight className="w-3 h-3 transform group-hover:translate-x-0.5 transition-transform" />
        </button>
      </div>
    </div>
  );
}
