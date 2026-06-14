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

  const { data: apiData, isLoading, error } = useQuery({
    queryKey: ['backtest-compare', selectedIds],
    queryFn: () => backtestsApi.compare(selectedIds.join(',')),
    enabled: selectedIds.length >= 2,
  });

  // Transform API response to component props
  const metrics = apiData?.runs?.map(run => ({
    backtest_id: run.run_id,
    strategy_name: run.strategy_id,
    total_return: run.metrics?.total_return ?? 0,
    annualized_return: run.metrics?.annualized_return ?? 0,
    sharpe_ratio: run.metrics?.sharpe_ratio ?? 0,
    max_drawdown: run.metrics?.max_drawdown ?? 0,
    win_rate: run.metrics?.win_rate ?? 0,
    calmar_ratio: run.metrics?.calmar_ratio ?? 0,
    sortino_ratio: run.metrics?.sortino_ratio ?? 0,
  }));

  const navCurves = apiData?.runs?.map(run => ({
    backtest_id: run.run_id,
    strategy_name: run.strategy_id,
    data: run.nav_series?.map(p => ({ date: p.date, nav: p.nav })) ?? [],
  }));

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
  if (error) return <div className="card p-8 text-center text-red-500">加载失败: {(error as Error).message}</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="page-title">回测对比</h1>
        <div className="flex gap-2">
          <button onClick={clearSelection} className="btn-secondary">清除选择</button>
          <button onClick={() => navigate('/backtests')} className="btn-secondary">返回列表</button>
        </div>
      </div>
      {metrics && metrics.length > 0 && <CompareMetricsTable metrics={metrics} />}
      {navCurves && navCurves.length > 0 && <CompareNavChart curves={navCurves} />}
    </div>
  );
};
