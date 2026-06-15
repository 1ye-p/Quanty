import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { riskApi } from '@/lib/api/risk';
import { extendedQueryKeys } from '@/lib/queryKeys';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { cn } from '@/lib/utils';

const getRiskLevel = (value: number, thresholds: [number, number]) => {
  if (value > thresholds[1]) return 'text-red-600';
  if (value > thresholds[0]) return 'text-yellow-600';
  return 'text-green-600';
};

export const PositionRiskDashboard: React.FC = () => {
  const { data: portfolio, isLoading, error } = useQuery({
    queryKey: extendedQueryKeys.risk.positions(),
    queryFn: () => riskApi.getPositions(),
    refetchInterval: 30000,
  });

  if (isLoading) return <div className="text-center py-4 text-gray-500">加载中...</div>;
  if (error) return <div className="text-center py-8 text-red-500">加载失败: {error.message}</div>;
  if (!portfolio?.positions?.length) {
    return <div className="text-center py-8 text-gray-400">暂无持仓</div>;
  }

  const { positions, hhi, max_weight, sector_concentration } = portfolio;

  return (
    <div className="space-y-6">
      {/* Portfolio Risk Summary */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white rounded-xl shadow-sm border p-4 text-center">
          <div className="text-sm text-gray-500">持仓数量</div>
          <div className="text-2xl font-semibold">{positions.length}</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border p-4 text-center">
          <div className="text-sm text-gray-500">集中度 (HHI)</div>
          <div className={cn("text-2xl font-semibold", getRiskLevel(hhi, [0.1, 0.2]))}>
            {(hhi * 10000).toFixed(0)}
          </div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border p-4 text-center">
          <div className="text-sm text-gray-500">最大单只占比</div>
          <div className={cn("text-2xl font-semibold", getRiskLevel(max_weight, [0.1, 0.2]))}>
            {(max_weight * 100).toFixed(1)}%
          </div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border p-4 text-center">
          <div className="text-sm text-gray-500">行业集中度</div>
          <div className={cn("text-2xl font-semibold", getRiskLevel(sector_concentration, [0.3, 0.5]))}>
            {(sector_concentration * 100).toFixed(1)}%
          </div>
        </div>
      </div>

      {/* Position Weight Distribution */}
      <div className="bg-white rounded-xl shadow-sm border p-4">
        <h3 className="font-medium text-gray-800 mb-4">持仓权重分布</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={positions.slice(0, 20)}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="asset_id" tick={{ fontSize: 11 }} angle={-45} textAnchor="end" height={80} />
            <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
            <Tooltip formatter={(v: number) => [`${(v * 100).toFixed(2)}%`, '权重']} />
            <Bar dataKey="weight" fill="#6366f1" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Position Detail Table */}
      <div className="bg-white rounded-xl shadow-sm border p-4">
        <h3 className="font-medium text-gray-800 mb-4">持仓明细</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="p-2 text-left">标的</th>
                <th className="p-2 text-right">权重</th>
                <th className="p-2 text-right">市值</th>
                <th className="p-2 text-right">Beta</th>
                <th className="p-2 text-right">波动率</th>
                <th className="p-2 text-right">VaR (95%)</th>
              </tr>
            </thead>
            <tbody>
              {positions.map(pos => (
                <tr key={pos.asset_id} className="border-t">
                  <td className="p-2 font-medium">{pos.asset_id}</td>
                  <td className="p-2 text-right">{(pos.weight * 100).toFixed(2)}%</td>
                  <td className="p-2 text-right">{pos.market_value?.toFixed(2) ?? '-'}</td>
                  <td className="p-2 text-right">{pos.beta?.toFixed(2) ?? '-'}</td>
                  <td className="p-2 text-right">{pos.volatility != null ? (pos.volatility * 100).toFixed(1) + '%' : '-'}</td>
                  <td className="p-2 text-right">{pos.var_95 != null ? (pos.var_95 * 100).toFixed(2) + '%' : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
