"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type TrendSeries = {
  key: string;
  label: string;
  color: string;
};

type TrendChartProps = {
  data: Record<string, string | number>[];
  xKey: string;
  series: TrendSeries[];
  height?: number;
  variant?: "area" | "line";
  emptyMessage?: string;
  isAnimationActive?: boolean;
};

export function TrendChart({
  data,
  xKey,
  series,
  height = 240,
  variant = "area",
  emptyMessage = "No data in this range.",
  isAnimationActive = true,
}: TrendChartProps) {
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

  const Chart = variant === "line" ? LineChart : AreaChart;

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <Chart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="rgba(241,244,250,0.08)" vertical={false} />
          <XAxis
            dataKey={xKey}
            tick={{ fill: "rgba(241,244,250,0.55)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "rgba(241,244,250,0.55)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={36}
          />
          <Tooltip
            contentStyle={{
              background: "#1a2230",
              border: "1px solid rgba(241,244,250,0.2)",
              borderRadius: 8,
            }}
          />
          <Legend />
          {series.map((s) =>
            variant === "line" ? (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={s.color}
                strokeWidth={2}
                dot={false}
                isAnimationActive={isAnimationActive}
              />
            ) : (
              <Area
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={s.color}
                fill={s.color}
                fillOpacity={0.15}
                strokeWidth={2}
                isAnimationActive={isAnimationActive}
              />
            )
          )}
        </Chart>
      </ResponsiveContainer>
    </div>
  );
}
