import React from 'react';
import { cn } from '@/lib/utils';

interface CompareMetrics {
  backtest_id: string;
  strategy_name: string;
  total_return: number;
  annualized_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  calmar_ratio: number;
  sortino_ratio: number;
}

interface CompareMetricsTableProps {
  metrics: CompareMetrics[];
}

export const CompareMetricsTable: React.FC<CompareMetricsTableProps> = ({ metrics }) => {
  if (metrics.length === 0) return null;

  const rows = [
    { key: 'total_return', label: '总收益', format: (v: number) => `${(v * 100).toFixed(1)}%`, higher: true },
    { key: 'annualized_return', label: '年化收益', format: (v: number) => `${(v * 100).toFixed(1)}%`, higher: true },
    { key: 'sharpe_ratio', label: 'Sharpe', format: (v: number) => v.toFixed(2), higher: true },
    { key: 'max_drawdown', label: '最大回撤', format: (v: number) => `${(v * 100).toFixed(1)}%`, higher: false },
    { key: 'win_rate', label: '胜率', format: (v: number) => `${(v * 100).toFixed(0)}%`, higher: true },
    { key: 'calmar_ratio', label: 'Calmar', format: (v: number) => v.toFixed(2), higher: true },
    { key: 'sortino_ratio', label: 'Sortino', format: (v: number) => v.toFixed(2), higher: true },
  ];

  const getBestIndex = (key: string, higher: boolean) => {
    const values = metrics.map(m => m[key as keyof CompareMetrics] as number);
    const best = higher ? Math.max(...values) : Math.min(...values);
    return values.indexOf(best);
  };

  return (
    <div className="card overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="bg-gray-50">
            <th className="p-3 text-left font-medium">指标</th>
            {metrics.map(m => (
              <th key={m.backtest_id} className="p-3 text-right font-medium">{m.strategy_name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(row => {
            const bestIdx = getBestIndex(row.key, row.higher);
            return (
              <tr key={row.key} className="border-t">
                <td className="p-3 text-gray-500">{row.label}</td>
                {metrics.map((m, idx) => (
                  <td key={m.backtest_id} className={cn(
                    "p-3 text-right font-medium",
                    idx === bestIdx && "text-brand-600 font-semibold"
                  )}>
                    {row.format(m[row.key as keyof CompareMetrics] as number)}
                    {idx === bestIdx && <span className="ml-1">🏆</span>}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
