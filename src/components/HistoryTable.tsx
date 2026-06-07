import React from 'react';
import { Check, X } from 'lucide-react';

const history = [
  { date: 'Oct 15', predicted: 'UP', confidence: 62.1, actual: 'UP', correct: true },
  { date: 'Oct 08', predicted: 'DOWN', confidence: 58.4, actual: 'UP', correct: false },
  { date: 'Oct 01', predicted: 'UP', confidence: 71.0, actual: 'UP', correct: true },
  { date: 'Sep 24', predicted: 'DOWN', confidence: 65.2, actual: 'DOWN', correct: true },
  { date: 'Sep 17', predicted: 'UNCERT', confidence: 51.0, actual: 'DOWN', correct: null },
];

export function HistoryTable() {
  return (
    <div className="bg-black border border-zinc-900 rounded-2xl p-6">
      <h3 className="text-sm font-medium text-zinc-100 mb-6">Recent History</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-[10px] text-zinc-500 uppercase tracking-widest border-b border-zinc-900 font-mono">
            <tr>
              <th className="px-2 py-3 font-normal">Date</th>
              <th className="px-2 py-3 font-normal">Predicted</th>
              <th className="px-2 py-3 font-normal text-right">Conf.</th>
              <th className="px-2 py-3 font-normal text-right">Result</th>
            </tr>
          </thead>
          <tbody className="text-zinc-400">
            {history.map((row, i) => (
              <tr key={i} className="border-b border-zinc-900/50 last:border-0 hover:bg-zinc-900/30 transition-colors">
                <td className="px-2 py-4 font-mono text-xs">{row.date}</td>
                <td className="px-2 py-4 flex items-center gap-1.5 font-medium">
                  {row.predicted === 'UP' && <span className="text-zinc-100">↑</span>}
                  {row.predicted === 'DOWN' && <span className="text-zinc-500">↓</span>}
                  {row.predicted === 'UNCERT' && <span className="text-zinc-500">~</span>}
                  <span className={row.predicted === 'UP' ? 'text-zinc-100' : 'text-zinc-500'}>{row.predicted}</span>
                </td>
                <td className="px-2 py-4 font-mono text-xs text-right text-zinc-500">{row.confidence}%</td>
                <td className="px-2 py-4 flex justify-end">
                  {row.correct === true && <div className="w-2 h-2 rounded-full bg-zinc-100" title="Correct"></div>}
                  {row.correct === false && <div className="w-2 h-2 rounded-full bg-zinc-700" title="Incorrect"></div>}
                  {row.correct === null && <div className="w-2 h-2 rounded-full bg-zinc-800" title="Uncertain"></div>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
