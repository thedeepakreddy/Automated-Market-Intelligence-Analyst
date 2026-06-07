import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const shapData = [
  { feature: 'Price Momentum', value: 0.12 },
  { feature: 'Sentiment', value: 0.08 },
  { feature: 'CPI MoM', value: -0.05 },
  { feature: 'S&P500 RSI', value: 0.04 },
  { feature: 'Fed Funds', value: -0.03 }
].sort((a, b) => Math.abs(b.value) - Math.abs(a.value));

export function ShapChart() {
  return (
    <div className="bg-black border border-zinc-900 rounded-2xl p-6">
      <div className="flex justify-between items-baseline mb-6">
        <h3 className="text-sm font-medium text-zinc-100">SHAP Attributions</h3>
        <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Impact</span>
      </div>      
      <div className="h-64 sm:h-80 -ml-8">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={shapData} layout="vertical" margin={{ left: 50, right: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#18181b" horizontal={true} vertical={false} />
            <XAxis type="number" stroke="#52525b" tick={{fill: '#52525b', fontSize: 10, fontFamily: 'monospace'}} axisLine={false} tickLine={false} />
            <YAxis dataKey="feature" type="category" stroke="#a1a1aa" tick={{fill: '#a1a1aa', fontSize: 11}} axisLine={false} tickLine={false} width={100} />
            <Tooltip 
              cursor={{fill: '#09090b'}}
              contentStyle={{ backgroundColor: '#09090b', border: '1px solid #27272a', borderRadius: '0.5rem', color: '#f4f4f5', fontSize: '12px', fontFamily: 'monospace' }}
            />
            <Bar dataKey="value" barSize={24} radius={[0, 4, 4, 0]}>
              {shapData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.value > 0 ? '#f4f4f5' : '#3f3f46'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
