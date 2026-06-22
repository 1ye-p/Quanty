import React from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

interface DrawdownPoint {
  date: string;
  drawdown: number;
}

interface DrawdownSeries {
  backtest_id: string;
  name: string;
  data: DrawdownPoint[];
}

interface CompareDrawdownChartProps {
  drawdowns: DrawdownSeries[];
}

const COLORS = ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6'];

export const CompareDrawdownChart: React.FC<CompareDrawdownChartProps> = ({
  drawdowns,
}) => {
  if (drawdowns.length === 0) return null;

  // Merge all drawdown data onto same timeline
  const allDates = new Set<string>();
  drawdowns.forEach((s) => s.data.forEach((d) => allDates.add(d.date)));
  const sortedDates = Array.from(allDates).sort();

  const mergedData = sortedDates.map((date) => {
    const point: Record<string, unknown> = { date };
    drawdowns.forEach((s) => {
      const d = s.data.find((p) => p.date === date);
      point[s.name] = d?.drawdown;
    });
    return point;
  });

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4">
      <h3 className="font-medium mb-4">回撤对比</h3>
      <ResponsiveContainer width="100%" height={350}>
        <AreaChart data={mergedData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 12 }}
            tickFormatter={(value: string) => value.slice(5)}
          />
          <YAxis
            tick={{ fontSize: 12 }}
            tickFormatter={(value: number) => `${(value * 100).toFixed(0)}%`}
          />
          <Tooltip
            labelFormatter={(value: string) => value}
            formatter={(value: number, name: string) => [
              `${(value * 100).toFixed(2)}%`,
              name,
            ]}
          />
          <Legend />
          {drawdowns.map((s, idx) => (
            <Area
              key={s.backtest_id}
              type="monotone"
              dataKey={s.name}
              stroke={COLORS[idx % COLORS.length]}
              fill={COLORS[idx % COLORS.length]}
              fillOpacity={0.1}
              strokeWidth={2}
              dot={false}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};
