import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import type { PricePoint } from "../types";

interface Props {
  data: PricePoint[];
}

export default function PriceChart({ data }: Props) {
  const formatted = data.map((p) => ({
    ...p,
    time: new Date(p.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  }));

  const prices = data.map((p) => p.close);
  const min = Math.floor(Math.min(...prices) - 2);
  const max = Math.ceil(Math.max(...prices) + 2);
  const trend = data.length > 1 && data[data.length - 1].close >= data[0].close;

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={formatted}>
        <XAxis dataKey="time" tick={{ fill: "#78716c", fontSize: 11, fontFamily: "Inter" }} tickLine={false} axisLine={false} />
        <YAxis domain={[min, max]} tick={{ fill: "#78716c", fontSize: 11, fontFamily: "Inter" }} tickLine={false} axisLine={false} width={50} />
        <Tooltip
          contentStyle={{ backgroundColor: "#fafaf9", border: "1px solid #d6d3d1", borderRadius: 4, fontSize: 12, fontFamily: "Inter" }}
          labelStyle={{ color: "#78716c" }}
        />
        <Line type="monotone" dataKey="close" stroke={trend ? "#059669" : "#dc2626"} strokeWidth={1.5} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
