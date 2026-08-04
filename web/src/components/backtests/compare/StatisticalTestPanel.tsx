import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { backtestsApi } from '@/lib/api/backtests';
import { cn } from '@/lib/utils';

interface StatisticalTestPanelProps {
  backtestIds: string[];
  backtestNames: Record<string, string>;
}

/** PSR-difference result row */
interface PsrRow {
  sharpe_a: number;
  sharpe_b: number;
  diff: number;
  p_value: number;
}

/** Bootstrap result */
interface BootstrapResult {
  diff_mean: number;
  ci_lower: number;
  ci_upper: number;
  block_size?: number;
}

/** MCS result row */
interface McsRow {
  run_id: string;
  sharpe: number;
  in_confidence_set: boolean;
}

export const StatisticalTestPanel: React.FC<StatisticalTestPanelProps> = ({
  backtestIds,
  backtestNames,
}) => {
  const { t } = useTranslation();
  const isTwoStrategies = backtestIds.length === 2;
  const defaultTestType = isTwoStrategies ? 'psr' : 'mcs';
  const [testType, setTestType] = useState<string>(defaultTestType);
  const [confidence, setConfidence] = useState(0.95);
  const [blockSize, setBlockSize] = useState<string>('');

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['statistical-test', backtestIds, testType, confidence, blockSize],
    queryFn: () =>
      backtestsApi.statisticalTest({
        backtest_ids: backtestIds,
        test_type: testType,
        confidence,
        ...(testType === 'bootstrap' && blockSize ? { block_size: Number(blockSize) } : {}),
      }),
    enabled: false,
  });

  const handleRun = () => refetch();

  const renderPsrResult = () => {
    if (!data?.results) return null;
    const r = data.results as unknown as PsrRow;
    const significant = r.p_value < 0.05;

    return (
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50">
            <th className="p-2 text-left">{t('component.compare.stat_test.psr.col.metric')}</th>
            <th className="p-2 text-right">{t('component.compare.stat_test.psr.col.strategy_a')}</th>
            <th className="p-2 text-right">{t('component.compare.stat_test.psr.col.strategy_b')}</th>
            <th className="p-2 text-right">{t('component.compare.stat_test.psr.col.diff')}</th>
            <th className="p-2 text-right">{t('component.compare.stat_test.psr.col.p_value')}</th>
            <th className="p-2 text-center">{t('component.compare.stat_test.psr.col.significance')}</th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-t">
            <td className="p-2 text-gray-500">{t('component.compare.stat_test.psr.row.sharpe')}</td>
            <td className="p-2 text-right font-medium">{r.sharpe_a?.toFixed(3)}</td>
            <td className="p-2 text-right font-medium">{r.sharpe_b?.toFixed(3)}</td>
            <td className="p-2 text-right font-medium">{r.diff?.toFixed(3)}</td>
            <td className="p-2 text-right font-medium">{r.p_value?.toFixed(4)}</td>
            <td className="p-2 text-center">
              <span
                className={cn(
                  'inline-block px-2 py-0.5 rounded-full text-xs font-medium',
                  significant
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-500',
                )}
              >
                {significant
                  ? t('component.compare.stat_test.psr.significant')
                  : t('component.compare.stat_test.psr.not_significant')}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    );
  };

  const renderBootstrapResult = () => {
    if (!data?.results) return null;
    const r = data.results as unknown as BootstrapResult;

    const barMax = Math.max(Math.abs(r.ci_lower), Math.abs(r.ci_upper), Math.abs(r.diff_mean));
    const scale = barMax > 0 ? 140 / barMax : 1;

    return (
      <div className="space-y-3 p-3">
        <div className="flex items-end gap-4 h-40 justify-center">
          {/* CI error bar */}
          <div className="flex flex-col items-center">
            <div className="text-xs text-gray-500 mb-1">{t('component.compare.stat_test.bootstrap.diff_mean_label')}</div>
            <div className="relative flex items-end h-32">
              {/* CI line */}
              <div
                className="absolute h-0.5 bg-gray-300"
                style={{
                  bottom: `${(r.ci_lower + barMax) * scale}px`,
                  width: `${(r.ci_upper - r.ci_lower) * scale}px`,
                  left: '0',
                }}
              />
              {/* CI caps */}
              <div
                className="absolute w-0.5 h-3 bg-gray-400"
                style={{ bottom: `${(r.ci_lower + barMax) * scale - 4}px`, left: '0' }}
              />
              <div
                className="absolute w-0.5 h-3 bg-gray-400"
                style={{
                  bottom: `${(r.ci_upper + barMax) * scale - 4}px`,
                  left: `${(r.ci_upper - r.ci_lower) * scale}px`,
                }}
              />
              {/* Mean bar */}
              <div
                className="w-8 rounded-t"
                style={{
                  height: `${Math.abs(r.diff_mean) * scale}px`,
                  backgroundColor: r.diff_mean >= 0 ? '#22c55e' : '#ef4444',
                  marginLeft: `${(r.diff_mean - r.ci_lower) * scale - 16}px`,
                }}
              />
            </div>
          </div>
        </div>
        <div className="flex justify-center gap-6 text-sm">
          <span>
            {t('component.compare.stat_test.bootstrap.mean')}: <span className="font-medium">{r.diff_mean?.toFixed(4)}</span>
          </span>
          <span>
            {t('component.compare.stat_test.bootstrap.ci')}: <span className="font-medium">[{r.ci_lower?.toFixed(4)}, {r.ci_upper?.toFixed(4)}]</span>
          </span>
          {r.block_size && (
            <span>
              {t('component.compare.stat_test.bootstrap.block_size')}: <span className="font-medium">{r.block_size}</span>
            </span>
          )}
        </div>
      </div>
    );
  };

  const renderMcsResult = () => {
    if (!data?.results) return null;
    const rows = data.results as unknown as McsRow[];

    return (
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50">
            <th className="p-2 text-left">{t('component.compare.stat_test.mcs.col.strategy')}</th>
            <th className="p-2 text-right">{t('component.compare.stat_test.mcs.col.sharpe')}</th>
            <th className="p-2 text-center">{t('component.compare.stat_test.mcs.col.confidence_set')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.run_id} className="border-t">
              <td className="p-2 font-medium">
                {backtestNames[row.run_id] ?? row.run_id}
              </td>
              <td className="p-2 text-right font-medium">{row.sharpe?.toFixed(3)}</td>
              <td className="p-2 text-center">
                <span
                  className={cn(
                    'inline-block px-2 py-0.5 rounded-full text-xs font-medium',
                    row.in_confidence_set
                      ? 'bg-green-100 text-green-700'
                      : 'bg-gray-100 text-gray-500',
                  )}
                >
                  {row.in_confidence_set
                    ? t('component.compare.stat_test.mcs.in_set')
                    : t('component.compare.stat_test.mcs.out_set')}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  };

  const renderResult = () => {
    if (!data) return null;
    switch (data.test_type) {
      case 'psr_diff':
        return renderPsrResult();
      case 'bootstrap':
        return renderBootstrapResult();
      case 'mcs':
        return renderMcsResult();
      default:
        return <div className="p-4 text-gray-400">{t('component.compare.stat_test.error.unknown_type', { type: data.test_type })}</div>;
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4">
      <h3 className="font-medium mb-4">{t('component.compare.stat_test.title')}</h3>

      <div className="flex flex-wrap items-end gap-3 mb-4">
        {/* Test type selector */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t('component.compare.stat_test.label.test_type')}</label>
          <select
            value={testType}
            onChange={(e) => setTestType(e.target.value)}
            className="border rounded px-2 py-1.5 text-sm"
          >
            <option value="psr_diff">{t('component.compare.stat_test.option.psr_diff')}</option>
            <option value="bootstrap">Bootstrap</option>
            {backtestIds.length >= 3 && <option value="mcs">{t('component.compare.stat_test.option.mcs')}</option>}
          </select>
        </div>

        {/* Confidence selector */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t('component.compare.stat_test.label.confidence')}</label>
          <select
            value={confidence}
            onChange={(e) => setConfidence(Number(e.target.value))}
            className="border rounded px-2 py-1.5 text-sm"
          >
            <option value={0.9}>90%</option>
            <option value={0.95}>95%</option>
            <option value={0.99}>99%</option>
          </select>
        </div>

        {/* Block size input (bootstrap only) */}
        {testType === 'bootstrap' && (
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t('component.compare.stat_test.label.block_size')}</label>
            <input
              type="number"
              min={1}
              placeholder={t('component.compare.stat_test.placeholder.block_size')}
              value={blockSize}
              onChange={(e) => setBlockSize(e.target.value)}
              className="border rounded px-2 py-1.5 text-sm w-24"
            />
          </div>
        )}

        <button
          onClick={handleRun}
          disabled={isLoading}
          className="px-4 py-1.5 text-sm font-medium bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
        >
          {isLoading ? t('common.running') : t('component.compare.stat_test.btn.run')}
        </button>
      </div>

      {error && (
        <div className="p-3 text-sm text-red-500 bg-red-50 rounded">
          {t('component.compare.stat_test.error.failed', { error: (error as Error).message })}
        </div>
      )}

      {renderResult()}

      {!data && !isLoading && !error && (
        <div className="p-6 text-center text-gray-400 text-sm">
          {t('component.compare.stat_test.hint.empty')}
        </div>
      )}
    </div>
  );
};
