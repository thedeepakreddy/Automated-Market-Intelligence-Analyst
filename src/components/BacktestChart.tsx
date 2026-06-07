import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const backtestData = Array.from({ length: 80 }).map((_, i) => {
  const t = i / 10;
  const buyHold = 10000 * Math.exp(t * 0.04) + Math.sin(t) * 300;
  const aiStrategy = 10000 * Math.exp(t * 0.07) + Math.sin(t * 0.8) * 150; 
  return {
    date: `Wk ${i + 1}`,
    'Buy & Hold': buyHold,
    'AI Strategy': aiStrategy
  };
});

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-zinc-950 border border-zinc-800 p-3 rounded-lg text-xs font-mono">
        <p className="text-zinc-500 mb-2">{payload[0].payload.date}</p>
        {payload.map((entry: any, index: number) => (
          <div key={index} className="flex gap-4 justify-between" style={{ color: entry.stroke }}>
            <span>{entry.name}</span>
            <span className="font-medium">${(entry.value).toLocaleString(undefined, {maximumFractionDigits: 0})}</span>
          </div>
        ))}
      </div>
    );
  }
  return null;
};

export function BacktestChart() {
  return (
    <div className="bg-black border border-zinc-900 rounded-2xl p-6 h-full">
      <div className="flex justify-between items-baseline mb-6">
        <h3 className="text-sm font-medium text-zinc-100">Backtest Performance</h3>
        <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">20% Test Set</span>
      </div>      
      <div className="h-64 sm:h-80 -ml-4">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={backtestData}>
            <defs>
              <linearGradient id="colorAI" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f4f4f5" stopOpacity={0.08}/>
                <stop offset="95%" stopColor="#f4f4f5" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#18181b" vertical={false} />
            <XAxis dataKey="date" stroke="#52525b" tick={{fill: '#52525b', fontSize: 10, fontFamily: 'monospace'}} axisLine={false} tickLine={false} dy={10} />
            <YAxis domain={['auto', 'auto']} stroke="#52525b" tick={{fill: '#52525b', fontSize: 10, fontFamily: 'monospace'}} axisLine={false} tickLine={false} dx={-10} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
            <Tooltip content={<CustomTooltip />} />
            <Area type="monotone" dataKey="AI Strategy" stroke="#f4f4f5" fillOpacity={1} fill="url(#colorAI)" strokeWidth={1.5} />
            <Area type="monotone" dataKey="Buy & Hold" stroke="#3f3f46" fillOpacity={0} strokeWidth={1.5} strokeDasharray="4 4" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
