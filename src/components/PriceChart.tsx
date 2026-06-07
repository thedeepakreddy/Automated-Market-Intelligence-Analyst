import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const mockPriceData = Array.from({ length: 60 }).map((_, i) => {
  const base = 5000 + (Math.sin(i / 5) * 200) + (i * 10);
  const noise = (Math.random() - 0.5) * 50;
  return {
    date: `D${i + 1}`,
    Price: base + noise,
    SMA_7: base + noise - 20,
    SMA_30: base - 50
  };
});

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-zinc-950 border border-zinc-800 p-3 rounded-lg text-xs font-mono">
        <p className="text-zinc-400 mb-2">{payload[0].payload.date}</p>
        {payload.map((entry: any, index: number) => (
          <div key={index} className="flex gap-4 justify-between" style={{ color: entry.stroke }}>
            <span>{entry.name}</span>
            <span className="font-medium">{(entry.value).toFixed(1)}</span>
          </div>
        ))}
      </div>
    );
  }
  return null;
};

export function PriceChart() {
  return (
    <div className="bg-black border border-zinc-900 rounded-2xl p-6">
      <div className="flex justify-between items-baseline mb-6">
        <h3 className="text-sm font-medium text-zinc-100">Price vs Trends (6M)</h3>
        <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">S&P500</span>
      </div>      
      <div className="h-64 sm:h-80 -ml-5">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={mockPriceData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#18181b" vertical={false} />
            <XAxis dataKey="date" stroke="#52525b" tick={{fill: '#52525b', fontSize: 10, fontFamily: 'monospace'}} axisLine={false} tickLine={false} dy={10} />
            <YAxis domain={['auto', 'auto']} stroke="#52525b" tick={{fill: '#52525b', fontSize: 10, fontFamily: 'monospace'}} axisLine={false} tickLine={false} dx={-10} />
            <Tooltip content={<CustomTooltip />} />
            <Line type="monotone" dataKey="Price" stroke="#f4f4f5" strokeWidth={1.5} dot={false} activeDot={{ r: 4, fill: '#f4f4f5' }} />
            <Line type="monotone" dataKey="SMA_30" stroke="#52525b" strokeWidth={1.5} dot={false} strokeDasharray="4 4" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
