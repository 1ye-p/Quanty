import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { backtestsApi } from '@/lib/api/backtests';
import { useBacktestCompareStore } from '@/stores/backtestCompareStore';
import { CompareMetricsTable } from '@/components/backtests/compare/CompareMetricsTable';
import { CompareNavChart } from '@/components/backtests/compare/CompareNavChart';
import { StatisticalTestPanel } from '@/components/backtests/compare/StatisticalTestPanel';
import { CompareDrawdownChart } from '@/components/backtests/compare/CompareDrawdownChart';

export const BacktestComparePage: React.FC = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
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

  const backtestNames = Object.fromEntries(
    (apiData?.runs ?? []).map(r => [r.run_id, r.strategy_id]),
  );

  // Compute drawdown series from NAV data
  const drawdowns = apiData?.runs?.map(run => {
    const navs = run.nav_series ?? [];
    let peak = -Infinity;
    const data = navs.map(p => {
      if (p.nav > peak) peak = p.nav;
      return {
        date: p.date,
        drawdown: peak > 0 ? (p.nav - peak) / peak : 0,
      };
    });
    return { backtest_id: run.run_id, name: run.strategy_id, data };
  });

  if (selectedIds.length < 2) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <h1 className="page-title">{t('page.backtest_compare.title')}</h1>
          <button onClick={() => navigate('/backtests')} className="btn-secondary">{t('page.backtest_compare.action.back')}</button>
        </div>
        <div className="card p-8 text-center text-gray-400">
          {t('page.backtest_compare.empty.select_hint')}
        </div>
      </div>
    );
  }

  if (isLoading) return <div>{t('common.loading')}</div>;
  if (error) return <div className="card p-8 text-center text-red-500">{t('page.backtest_compare.error.load_failed', { message: (error as Error).message })}</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="page-title">{t('page.backtest_compare.title')}</h1>
        <div className="flex gap-2">
          <button onClick={clearSelection} className="btn-secondary">{t('page.backtest_compare.action.clear')}</button>
          <button onClick={() => navigate('/backtests')} className="btn-secondary">{t('page.backtest_compare.action.back')}</button>
        </div>
      </div>
      {metrics && metrics.length > 0 && <CompareMetricsTable metrics={metrics} />}
      {navCurves && navCurves.length > 0 && <CompareNavChart curves={navCurves} />}
      {drawdowns && drawdowns.length > 0 && <CompareDrawdownChart drawdowns={drawdowns} />}
      <StatisticalTestPanel backtestIds={selectedIds} backtestNames={backtestNames} />
    </div>
  );
};
