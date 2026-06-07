import React from 'react';

interface HeroProps {
  prediction: 'UP' | 'DOWN' | 'UNCERTAIN';
  confidence: number;
}

export function HeroSection({ prediction, confidence }: HeroProps) {
  return (
    <div className="text-center py-12 md:py-20 flex flex-col items-center">
      <span className="text-[10px] sm:text-xs font-mono text-zinc-500 uppercase tracking-[0.2em] mb-8">
        7-Day Horizon Prediction
      </span>
      
      <h1 className="text-7xl sm:text-9xl font-semibold tracking-tighter text-zinc-100 mb-6 flex items-center gap-4">
        {prediction === 'UP' && <span className="transform -rotate-45 text-zinc-700">→</span>}
        {prediction === 'DOWN' && <span className="transform rotate-45 text-zinc-700">→</span>}
        {prediction === 'UNCERTAIN' && <span className="text-zinc-700">~</span>}
        {prediction}
      </h1>
      
      <div className="flex items-center gap-6 mt-4">
        <div className="text-xs text-zinc-500 uppercase tracking-widest">Confidence</div>
        <div className="h-px w-8 sm:w-16 bg-zinc-800"></div>
        <div className="text-2xl font-mono tracking-tight text-zinc-100">{confidence.toFixed(1)}%</div>
      </div>
    </div>
  );
}
