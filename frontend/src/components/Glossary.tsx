import { useState } from "react";
import { HiOutlineBookOpen, HiOutlineXMark } from "react-icons/hi2";

interface Term {
  term: string;
  definition: string;
}

const TERMS: Term[] = [
  { term: "MACD", definition: "Moving Average Convergence Divergence. Compares a fast (12-day) and slow (26-day) exponential moving average. When the MACD line crosses above the signal line, it suggests bullish momentum; below, bearish. It's a trend-following indicator, not a crystal ball -- it works best in trending markets and lags in choppy ones." },
  { term: "RSI", definition: "Relative Strength Index. Measures how fast and how much a stock's price has moved recently on a scale of 0-100. Below 30 means it's been beaten down and may bounce (oversold). Above 70 means it's been running hot and may pull back (overbought). Uses a 14-period lookback by default." },
  { term: "Bollinger Bands", definition: "A volatility envelope around a 20-day moving average, set 2 standard deviations above and below. When price touches the lower band, the stock is at a statistical extreme (cheap relative to recent history). Upper band means statistically expensive. It's about reversion to the mean, not a guarantee." },
  { term: "Volume", definition: "The number of shares traded in a given period. High volume confirms conviction behind a move -- a rally on heavy volume is more trustworthy than one on thin volume. Volume spikes often precede breakouts or breakdowns." },
  { term: "Volume Divergence", definition: "When price and volume move in opposite directions. Bullish divergence: price rises and volume rises too (strong confirmation). Bearish divergence: price rises but volume fades, warning the rally may be running on fumes." },
  { term: "52-Week High/Low", definition: "The highest and lowest prices a stock has traded at in the past year. Near a 52-week high often signals strong momentum -- breakouts above tend to run. Near a 52-week low can signal capitulation or a potential bottom, but catching falling knives is risky." },
  { term: "Insider Trading (Legal)", definition: "When corporate officers, directors, or large shareholders buy or sell their own company's stock and report it to the SEC. Cluster buying -- multiple insiders buying around the same time -- is historically one of the strongest bullish signals because these people know the business intimately." },
  { term: "Sentiment Score", definition: "A numerical score derived from NLP analysis of news article text. Positive scores mean coverage is predominantly optimistic; negative means pessimistic. TickerLinks weights primary mentions (where the company is the subject) more heavily than passing references." },
  { term: "Primacy Weighting", definition: "Articles where a company is the primary subject count more toward its sentiment score than articles where it's just mentioned in passing. An article titled 'Apple Reports Record Earnings' matters more to AAPL's score than 'Tech Sector Rallies' where Apple gets one sentence." },
  { term: "Signal Confidence", definition: "A 0-100% score representing how strong a particular signal detection is. Higher confidence means the pattern is clearer and more pronounced. Multiple high-confidence signals pointing the same direction create a stronger prediction." },
  { term: "Operative Accuracy", definition: "A signal's historical win rate, weighted so recent performance matters more than old results. Uses exponential decay -- a signal that was right 8 of the last 10 times scores higher than one that was right 80 of 100 times three years ago." },
  { term: "Ticker Digest", definition: "An AI-generated summary that takes all the raw signal matches for a single stock and synthesizes them into a net assessment -- weighing bullish vs bearish signals, noting which are strongest, and producing a 1-2 sentence outlook." },
  { term: "Source Breadth", definition: "How many unique news outlets are covering a story. A story picked up by Reuters, Bloomberg, CNBC, and MarketWatch has broader reach (and likely more market impact) than one only on a single blog." },
  { term: "Mention Velocity", definition: "The acceleration of news mentions over time. If a stock went from 2 mentions yesterday to 10 today, that 5x spike in attention often precedes a significant price move." },
];

export default function Glossary() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 text-xs font-sans text-stone-400 hover:text-stone-700 transition-colors"
      >
        <HiOutlineBookOpen className="w-4 h-4" />
        <span>Glossary</span>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40 bg-stone-900/20 backdrop-blur-sm" onClick={() => setOpen(false)} />
          <div className="fixed top-0 right-0 z-50 h-screen w-full max-w-lg bg-stone-50 border-l border-stone-300 shadow-2xl overflow-y-auto">
            <div className="flex items-center justify-between px-6 h-14 border-b border-stone-200 sticky top-0 bg-stone-50">
              <h2 className="font-serif font-bold text-lg text-stone-900">Glossary</h2>
              <button onClick={() => setOpen(false)} className="text-stone-400 hover:text-stone-700">
                <HiOutlineXMark className="w-5 h-5" />
              </button>
            </div>
            <div className="px-6 py-6 space-y-6">
              {TERMS.map((t) => (
                <div key={t.term} className="border-b border-stone-200 pb-4">
                  <dt className="font-serif font-bold text-stone-900 mb-1">{t.term}</dt>
                  <dd className="font-body text-sm text-stone-600 leading-relaxed">{t.definition}</dd>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </>
  );
}
