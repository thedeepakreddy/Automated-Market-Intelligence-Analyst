import React from 'react';

export function MetricsTable() {
  const metrics = [
    { label: "Accuracy", value: "68.4%", desc: "Correct calls" },
    { label: "Sharpe", value: "1.82", desc: "Risk-adjusted" },
    { label: "Max Drawdown", value: "-12.5%", desc: "Worst loss" },
    { label: "Ann. Return", value: "24.1%", desc: "vs 8.4% bench" },
  ];

  return (
    <div className="bg-black border border-zinc-900 rounded-2xl p-6 h-full flex flex-col">
      <h3 className="text-sm font-medium text-zinc-100 mb-6">Strategy Metrics</h3>
      <div className="grid grid-cols-2 gap-x-6 gap-y-8 flex-1 content-center">
        {metrics.map((m, i) => (
          <div key={i} className="">
            <p className="text-[11px] font-mono text-zinc-500 tracking-wider uppercase mb-1">{m.label}</p>
            <p className="text-2xl font-light tracking-tight text-zinc-100">{m.value}</p>
            <p className="text-[10px] text-zinc-600 mt-1">{m.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
