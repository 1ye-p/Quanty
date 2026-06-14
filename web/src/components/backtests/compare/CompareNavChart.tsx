import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface NavCurvePoint {
  date: string;
  value: number;
}

interface CompareNavChartProps {
  curves: Array<{
    backtest_id: string;
    strategy_name: string;
    data: NavCurvePoint[];
  }>;
}

const COLORS = ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6'];

export const CompareNavChart: React.FC<CompareNavChartProps> = ({ curves }) => {
  if (curves.length === 0) return null;

  // Merge all curve data onto same timeline
  const allDates = new Set<string>();
  curves.forEach(c => c.data.forEach(d => allDates.add(d.date)));
  const sortedDates = Array.from(allDates).sort();

  const mergedData = sortedDates.map(date => {
    const point: Record<string, any> = { date };
    curves.forEach(c => {
      const d = c.data.find(d => d.date === date);
      point[c.strategy_name] = d?.value;
    });
    return point;
  });

  return (
    <div className="card p-4">
      <h3 className="font-medium mb-4">净值曲线对比</h3>
      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={mergedData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} tickFormatter={(value) => value.slice(5)} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip labelFormatter={(value) => value} formatter={(value: number) => [value.toFixed(4), '']} />
          <Legend />
          {curves.map((c, idx) => (
            <Line
              key={c.backtest_id}
              type="monotone"
              dataKey={c.strategy_name}
              stroke={COLORS[idx % COLORS.length]}
              dot={false}
              strokeWidth={2}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};
