import { useState, useMemo } from "react";
import {
  ComposedChart, Line, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  ReferenceLine, Area,
} from "recharts";
import type { PricePoint } from "../types";

interface Props {
  data: PricePoint[];
}

interface Overlay {
  key: string;
  label: string;
  color: string;
  group: string;
}

const OVERLAYS: Overlay[] = [
  { key: "sma20", label: "SMA 20", color: "#6366f1", group: "Moving Averages" },
  { key: "sma50", label: "SMA 50", color: "#f59e0b", group: "Moving Averages" },
  { key: "ema12", label: "EMA 12", color: "#8b5cf6", group: "Moving Averages" },
  { key: "ema26", label: "EMA 26", color: "#ec4899", group: "Moving Averages" },
  { key: "bbands", label: "Bollinger Bands", color: "#94a3b8", group: "Volatility" },
  { key: "volume", label: "Volume", color: "#a8a29e", group: "Volume" },
  { key: "rsi", label: "RSI (14)", color: "#0ea5e9", group: "Oscillators" },
  { key: "macd", label: "MACD", color: "#10b981", group: "Oscillators" },
  { key: "week52", label: "52-Week Hi/Lo", color: "#f97316", group: "Levels" },
];

function sma(values: number[], period: number): (number | null)[] {
  return values.map((_, i) => {
    if (i < period - 1) return null;
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += values[j];
    return sum / period;
  });
}

function ema(values: number[], period: number): (number | null)[] {
  const result: (number | null)[] = [];
  const k = 2 / (period + 1);
  let prev: number | null = null;
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) {
      result.push(null);
      continue;
    }
    if (prev === null) {
      let sum = 0;
      for (let j = i - period + 1; j <= i; j++) sum += values[j];
      prev = sum / period;
    } else {
      prev = values[i] * k + prev * (1 - k);
    }
    result.push(prev);
  }
  return result;
}

function bollingerBands(values: number[], period = 20, mult = 2) {
  const mid = sma(values, period);
  const upper: (number | null)[] = [];
  const lower: (number | null)[] = [];
  for (let i = 0; i < values.length; i++) {
    if (mid[i] === null) { upper.push(null); lower.push(null); continue; }
    let variance = 0;
    for (let j = i - period + 1; j <= i; j++) variance += (values[j] - mid[i]!) ** 2;
    const std = Math.sqrt(variance / period);
    upper.push(mid[i]! + mult * std);
    lower.push(mid[i]! - mult * std);
  }
  return { upper, mid, lower };
}

function computeRSI(values: number[], period = 14): (number | null)[] {
  const result: (number | null)[] = [null];
  let avgGain = 0, avgLoss = 0;
  for (let i = 1; i < values.length; i++) {
    const change = values[i] - values[i - 1];
    const gain = change > 0 ? change : 0;
    const loss = change < 0 ? -change : 0;
    if (i <= period) {
      avgGain += gain / period;
      avgLoss += loss / period;
      result.push(i < period ? null : 100 - 100 / (1 + avgGain / (avgLoss || 0.0001)));
    } else {
      avgGain = (avgGain * (period - 1) + gain) / period;
      avgLoss = (avgLoss * (period - 1) + loss) / period;
      result.push(100 - 100 / (1 + avgGain / (avgLoss || 0.0001)));
    }
  }
  return result;
}

function computeMACD(values: number[]) {
  const e12 = ema(values, 12);
  const e26 = ema(values, 26);
  const macdLine: (number | null)[] = [];
  for (let i = 0; i < values.length; i++) {
    macdLine.push(e12[i] !== null && e26[i] !== null ? e12[i]! - e26[i]! : null);
  }
  const validMacd = macdLine.filter((v) => v !== null) as number[];
  const signalRaw = ema(validMacd, 9);
  const signal: (number | null)[] = [];
  let si = 0;
  for (let i = 0; i < values.length; i++) {
    if (macdLine[i] === null) { signal.push(null); continue; }
    signal.push(signalRaw[si] ?? null);
    si++;
  }
  const histogram: (number | null)[] = macdLine.map((m, i) =>
    m !== null && signal[i] !== null ? m - signal[i]! : null
  );
  return { macdLine, signal, histogram };
}

export default function PriceChart({ data }: Props) {
  const [active, setActive] = useState<Set<string>>(new Set());

  const toggle = (key: string) =>
    setActive((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  const computed = useMemo(() => {
    const closes = data.map((p) => p.close);
    const sma20 = sma(closes, 20);
    const sma50 = sma(closes, 50);
    const ema12 = ema(closes, 12);
    const ema26 = ema(closes, 26);
    const bb = bollingerBands(closes, 20, 2);
    const rsi = computeRSI(closes, 14);
    const macd = computeMACD(closes);

    const high52 = Math.max(...closes);
    const low52 = Math.min(...closes);

    return data.map((p, i) => ({
      time: new Date(p.timestamp).toLocaleDateString([], { month: "short", day: "numeric" })
        + " " + new Date(p.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      close: +p.close.toFixed(2),
      open: +p.open.toFixed(2),
      high: +p.high.toFixed(2),
      low: +p.low.toFixed(2),
      volume: p.volume || 0,
      sma20: sma20[i] !== null ? +sma20[i]!.toFixed(2) : undefined,
      sma50: sma50[i] !== null ? +sma50[i]!.toFixed(2) : undefined,
      ema12: ema12[i] !== null ? +ema12[i]!.toFixed(2) : undefined,
      ema26: ema26[i] !== null ? +ema26[i]!.toFixed(2) : undefined,
      bbUpper: bb.upper[i] !== null ? +bb.upper[i]!.toFixed(2) : undefined,
      bbMid: bb.mid[i] !== null ? +bb.mid[i]!.toFixed(2) : undefined,
      bbLower: bb.lower[i] !== null ? +bb.lower[i]!.toFixed(2) : undefined,
      bbRange: bb.upper[i] !== null && bb.lower[i] !== null
        ? [+bb.lower[i]!.toFixed(2), +bb.upper[i]!.toFixed(2)]
        : undefined,
      rsi: rsi[i] !== null ? +rsi[i]!.toFixed(1) : undefined,
      macdLine: macd.macdLine[i] !== null ? +macd.macdLine[i]!.toFixed(3) : undefined,
      macdSignal: macd.signal[i] !== null ? +macd.signal[i]!.toFixed(3) : undefined,
      macdHist: macd.histogram[i] !== null ? +macd.histogram[i]!.toFixed(3) : undefined,
      high52,
      low52,
    }));
  }, [data]);

  const prices = data.map((p) => p.close);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const padding = (maxPrice - minPrice) * 0.1 || 2;
  const yMin = Math.floor(minPrice - padding);
  const yMax = Math.ceil(maxPrice + padding);
  const trend = data.length > 1 && data[data.length - 1].close >= data[0].close;

  const showRSI = active.has("rsi");
  const showMACD = active.has("macd");
  const mainHeight = 300;
  const subHeight = 120;

  const groups = OVERLAYS.reduce<Record<string, Overlay[]>>((acc, o) => {
    (acc[o.group] ??= []).push(o);
    return acc;
  }, {});

  return (
    <div>
      {/* Overlay toggles */}
      <div className="flex flex-wrap gap-x-6 gap-y-2 mb-4">
        {Object.entries(groups).map(([group, overlays]) => (
          <div key={group} className="flex items-center gap-2">
            <span className="text-[10px] font-sans font-semibold uppercase tracking-wider text-stone-400">{group}</span>
            {overlays.map((o) => (
              <label key={o.key} className="flex items-center gap-1.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={active.has(o.key)}
                  onChange={() => toggle(o.key)}
                  className="w-3 h-3 rounded border-stone-300 accent-stone-700 cursor-pointer"
                />
                <span className="text-xs font-sans text-stone-600 flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full inline-block" style={{ backgroundColor: o.color }} />
                  {o.label}
                </span>
              </label>
            ))}
          </div>
        ))}
      </div>

      {/* Main price chart */}
      <ResponsiveContainer width="100%" height={mainHeight + (active.has("volume") ? 80 : 0)}>
        <ComposedChart data={computed} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
          <XAxis
            dataKey="time"
            tick={{ fill: "#78716c", fontSize: 10, fontFamily: "Inter" }}
            tickLine={false}
            axisLine={false}
            interval={Math.floor(computed.length / 6)}
          />
          <YAxis
            yAxisId="price"
            domain={[yMin, yMax]}
            tick={{ fill: "#78716c", fontSize: 11, fontFamily: "Inter" }}
            tickLine={false}
            axisLine={false}
            width={55}
          />
          {active.has("volume") && (
            <YAxis yAxisId="vol" orientation="right" tick={false} axisLine={false} tickLine={false} width={0} />
          )}
          <Tooltip
            contentStyle={{ backgroundColor: "#fafaf9", border: "1px solid #d6d3d1", borderRadius: 4, fontSize: 11, fontFamily: "Inter" }}
            labelStyle={{ color: "#78716c", fontSize: 10 }}
          />

          {/* Bollinger Band fill */}
          {active.has("bbands") && (
            <Area yAxisId="price" dataKey="bbRange" stroke="none" fill="#94a3b8" fillOpacity={0.1} connectNulls />
          )}
          {active.has("bbands") && (
            <Line yAxisId="price" dataKey="bbUpper" stroke="#94a3b8" strokeWidth={1} strokeDasharray="3 3" dot={false} connectNulls />
          )}
          {active.has("bbands") && (
            <Line yAxisId="price" dataKey="bbMid" stroke="#94a3b8" strokeWidth={1} dot={false} connectNulls />
          )}
          {active.has("bbands") && (
            <Line yAxisId="price" dataKey="bbLower" stroke="#94a3b8" strokeWidth={1} strokeDasharray="3 3" dot={false} connectNulls />
          )}

          {/* 52-week levels */}
          {active.has("week52") && (
            <ReferenceLine yAxisId="price" y={computed[0]?.high52} stroke="#f97316" strokeDasharray="6 3" strokeWidth={1} label={{ value: "52W Hi", fill: "#f97316", fontSize: 10, position: "right" }} />
          )}
          {active.has("week52") && (
            <ReferenceLine yAxisId="price" y={computed[0]?.low52} stroke="#f97316" strokeDasharray="6 3" strokeWidth={1} label={{ value: "52W Lo", fill: "#f97316", fontSize: 10, position: "right" }} />
          )}

          {/* Volume bars */}
          {active.has("volume") && (
            <Bar yAxisId="vol" dataKey="volume" fill="#d6d3d1" fillOpacity={0.5} barSize={2} />
          )}

          {/* Moving averages */}
          {active.has("sma20") && <Line yAxisId="price" dataKey="sma20" stroke="#6366f1" strokeWidth={1.5} dot={false} connectNulls />}
          {active.has("sma50") && <Line yAxisId="price" dataKey="sma50" stroke="#f59e0b" strokeWidth={1.5} dot={false} connectNulls />}
          {active.has("ema12") && <Line yAxisId="price" dataKey="ema12" stroke="#8b5cf6" strokeWidth={1.5} dot={false} connectNulls />}
          {active.has("ema26") && <Line yAxisId="price" dataKey="ema26" stroke="#ec4899" strokeWidth={1.5} dot={false} connectNulls />}

          {/* Price line (always on top) */}
          <Line yAxisId="price" dataKey="close" stroke={trend ? "#059669" : "#dc2626"} strokeWidth={2} dot={false} />
        </ComposedChart>
      </ResponsiveContainer>

      {/* RSI sub-chart */}
      {showRSI && (
        <div className="mt-2">
          <span className="text-[10px] font-sans font-semibold uppercase tracking-wider text-stone-400">RSI (14)</span>
          <ResponsiveContainer width="100%" height={subHeight}>
            <ComposedChart data={computed} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
              <XAxis dataKey="time" tick={false} axisLine={false} tickLine={false} />
              <YAxis domain={[0, 100]} ticks={[30, 50, 70]} tick={{ fill: "#78716c", fontSize: 10, fontFamily: "Inter" }} tickLine={false} axisLine={false} width={55} />
              <ReferenceLine y={70} stroke="#dc2626" strokeDasharray="3 3" strokeOpacity={0.5} />
              <ReferenceLine y={30} stroke="#059669" strokeDasharray="3 3" strokeOpacity={0.5} />
              <Tooltip
                contentStyle={{ backgroundColor: "#fafaf9", border: "1px solid #d6d3d1", borderRadius: 4, fontSize: 11, fontFamily: "Inter" }}
                labelStyle={{ color: "#78716c", fontSize: 10 }}
              />
              <Line dataKey="rsi" stroke="#0ea5e9" strokeWidth={1.5} dot={false} connectNulls />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* MACD sub-chart */}
      {showMACD && (
        <div className="mt-2">
          <span className="text-[10px] font-sans font-semibold uppercase tracking-wider text-stone-400">MACD</span>
          <ResponsiveContainer width="100%" height={subHeight}>
            <ComposedChart data={computed} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
              <XAxis dataKey="time" tick={false} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#78716c", fontSize: 10, fontFamily: "Inter" }} tickLine={false} axisLine={false} width={55} />
              <ReferenceLine y={0} stroke="#d6d3d1" />
              <Tooltip
                contentStyle={{ backgroundColor: "#fafaf9", border: "1px solid #d6d3d1", borderRadius: 4, fontSize: 11, fontFamily: "Inter" }}
                labelStyle={{ color: "#78716c", fontSize: 10 }}
              />
              <Bar dataKey="macdHist" barSize={2}>
                {computed.map((d, i) => (
                  <rect key={i} fill={(d.macdHist ?? 0) >= 0 ? "#059669" : "#dc2626"} fillOpacity={0.4} />
                ))}
              </Bar>
              <Line dataKey="macdLine" stroke="#10b981" strokeWidth={1.5} dot={false} connectNulls />
              <Line dataKey="macdSignal" stroke="#f59e0b" strokeWidth={1} strokeDasharray="3 3" dot={false} connectNulls />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
