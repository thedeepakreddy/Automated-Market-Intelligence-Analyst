import React from 'react';

interface GaugeProps {
  label: string;
  score: number; // -1 to 1 OR 0 to 100 depending on how we want to visualize
}

function Gauge({ label, score }: GaugeProps) {
  const percentage = ((score + 1) / 2) * 100;

  return (
    <div className="flex flex-col border border-zinc-900 bg-black p-6 rounded-2xl">
      <div className="flex justify-between items-baseline mb-8">
        <h3 className="text-sm font-medium text-zinc-400">{label}</h3>
        <span className="text-lg font-mono text-zinc-100">
          {score > 0 ? '+' : ''}{(score).toFixed(2)}
        </span>
      </div>
      
      <div className="relative w-full h-1 bg-zinc-900 rounded-full overflow-hidden">
        <div 
          className="absolute top-0 bottom-0 left-0 bg-zinc-100 transition-all duration-1000 ease-out"
          style={{ width: `${percentage}%` }}
        />
        <div className="absolute top-0 bottom-0 left-1/2 w-px bg-black z-10" />
      </div>
      
      <div className="flex justify-between mt-3 text-[10px] font-mono text-zinc-600">
        <span>BEARISH</span>
        <span>NEUTRAL</span>
        <span>BULLISH</span>
      </div>
    </div>
  );
}

export function SignalGauges() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <Gauge label="Price Momentum" score={0.65} />
      <Gauge label="Macro Environment" score={-0.3} />
      <Gauge label="Social Sentiment" score={0.15} />
    </div>
  );
}
