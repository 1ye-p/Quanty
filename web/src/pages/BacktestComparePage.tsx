import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { backtestsApi } from '@/lib/api/backtests';
import { useBacktestCompareStore } from '@/stores/backtestCompareStore';
import { CompareMetricsTable } from '@/components/backtests/compare/CompareMetricsTable';
import { CompareNavChart } from '@/components/backtests/compare/CompareNavChart';

export const BacktestComparePage: React.FC = () => {
  const navigate = useNavigate();
  const { selectedIds, clearSelection } = useBacktestCompareStore();

  const { data: compareData, isLoading } = useQuery({
    queryKey: ['backtest-compare', selectedIds],
    queryFn: () => backtestsApi.getCompare(selectedIds),
    enabled: selectedIds.length >= 2,
  });

  if (selectedIds.length < 2) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <h1 className="page-title">回测对比</h1>
          <button onClick={() => navigate('/backtests')} className="btn-secondary">返回列表</button>
        </div>
        <div className="card p-8 text-center text-gray-400">
          请先在回测列表中选择至少 2 个回测进行对比
        </div>
      </div>
    );
  }

  if (isLoading) return <div>加载中...</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="page-title">回测对比</h1>
        <div className="flex gap-2">
          <button onClick={clearSelection} className="btn-secondary">清除选择</button>
          <button onClick={() => navigate('/backtests')} className="btn-secondary">返回列表</button>
        </div>
      </div>
      {compareData?.metrics && <CompareMetricsTable metrics={compareData.metrics} />}
      {compareData?.navCurves && <CompareNavChart curves={compareData.navCurves} />}
    </div>
  );
};
