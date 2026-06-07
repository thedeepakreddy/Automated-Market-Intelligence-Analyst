/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { HeroSection } from './components/HeroSection';
import { SignalGauges } from './components/SignalGauges';
import { PriceChart } from './components/PriceChart';
import { ShapChart } from './components/ShapChart';
import { BacktestChart } from './components/BacktestChart';
import { MetricsTable } from './components/MetricsTable';
import { WeeklyReport } from './components/WeeklyReport';
import { HistoryTable } from './components/HistoryTable';
import { Logo } from './components/Logo';

export default function App() {
  const today = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date());

  return (
    <div className="min-h-screen bg-black text-zinc-100 p-4 md:p-8 md:py-12 font-sans selection:bg-zinc-800">
      <div className="max-w-6xl mx-auto space-y-8 md:space-y-12">
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-8 border-b border-zinc-900">
          <div className="flex items-center gap-4">
            <Logo className="w-8 h-8 md:w-10 md:h-10 shrink-0 drop-shadow-sm" />
            <div>
              <h1 className="text-lg font-medium tracking-tight">Market Intelligence</h1>
              <p className="text-[10px] text-zinc-500 font-mono mt-1 uppercase tracking-widest">Ensemble Model: XGBoost + LSTM</p>
            </div>
          </div>
          <div className="md:text-right">
            <p className="text-sm font-medium text-zinc-300">Analyzing: S&P500, Macros & Social</p>
            <div className="flex items-center md:justify-end gap-2 text-[10px] text-zinc-500 font-mono mt-1.5 uppercase tracking-widest">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500"></span>
              </span>
              <span>As of {today}</span>
              <span className="text-zinc-800">|</span>
              <span>Updates 30m</span>
            </div>
          </div>
        </header>

        <main className="space-y-16">
          <section className="space-y-12">
            <HeroSection prediction="UP" confidence={68.4} />
            <SignalGauges />
          </section>

          <section className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <PriceChart />
            <ShapChart />
          </section>

          <section className="space-y-8">
             <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div className="lg:col-span-2">
                   <BacktestChart />
                </div>
                <div>
                   <MetricsTable />
                </div>
             </div>
          </section>

          <section className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <WeeklyReport />
            <HistoryTable />
          </section>
          
          <footer className="pt-12 pb-6 text-center">
            <p className="text-[10px] text-zinc-600 font-mono uppercase tracking-[0.2em]">Confidential & Proprietary</p>
          </footer>
        </main>
      </div>
    </div>
  );
}
