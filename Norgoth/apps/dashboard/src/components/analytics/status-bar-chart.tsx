"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type StatusBarChartRow = {
  label: string;
  count: number;
  color?: string;
};

type StatusBarChartProps = {
  data: StatusBarChartRow[];
  height?: number;
  emptyMessage?: string;
  isAnimationActive?: boolean;
  ariaLabel?: string;
};

export function StatusBarChart({
  data,
  height = 240,
  emptyMessage = "No data yet.",
  isAnimationActive = true,
  ariaLabel,
}: StatusBarChartProps) {
  if (!data.length) {
    return (
      <div
        className="d-flex align-items-center justify-content-center small text-body-secondary border rounded"
        style={{ height }}
      >
        {emptyMessage}
      </div>
    );
  }

  return (
    <div style={{ width: "100%", height }} aria-label={ariaLabel}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="rgba(241,244,250,0.08)" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: "rgba(241,244,250,0.55)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "rgba(241,244,250,0.55)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={36}
            allowDecimals={false}
          />
          <Tooltip
            contentStyle={{
              background: "#1a2230",
              border: "1px solid rgba(241,244,250,0.2)",
              borderRadius: 8,
            }}
          />
          <Bar
            dataKey="count"
            radius={[4, 4, 0, 0]}
            isAnimationActive={isAnimationActive}
          >
            {data.map((row) => (
              <Cell key={row.label} fill={row.color ?? "#60A5FA"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
