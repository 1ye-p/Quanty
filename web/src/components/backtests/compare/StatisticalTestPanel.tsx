import React, { useState } from 'react';
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
            <th className="p-2 text-left">指标</th>
            <th className="p-2 text-right">策略 A</th>
            <th className="p-2 text-right">策略 B</th>
            <th className="p-2 text-right">差值</th>
            <th className="p-2 text-right">p-value</th>
            <th className="p-2 text-center">显著性</th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-t">
            <td className="p-2 text-gray-500">Sharpe</td>
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
                {significant ? '显著' : '不显著'}
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
            <div className="text-xs text-gray-500 mb-1">差值均值 (95% CI)</div>
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
            均值: <span className="font-medium">{r.diff_mean?.toFixed(4)}</span>
          </span>
          <span>
            95% CI: <span className="font-medium">[{r.ci_lower?.toFixed(4)}, {r.ci_upper?.toFixed(4)}]</span>
          </span>
          {r.block_size && (
            <span>
              块大小: <span className="font-medium">{r.block_size}</span>
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
            <th className="p-2 text-left">策略</th>
            <th className="p-2 text-right">Sharpe</th>
            <th className="p-2 text-center">置信集</th>
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
                  {row.in_confidence_set ? '在集中' : '集外'}
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
        return <div className="p-4 text-gray-400">未知测试类型: {data.test_type}</div>;
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4">
      <h3 className="font-medium mb-4">统计检验</h3>

      <div className="flex flex-wrap items-end gap-3 mb-4">
        {/* Test type selector */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">检验类型</label>
          <select
            value={testType}
            onChange={(e) => setTestType(e.target.value)}
            className="border rounded px-2 py-1.5 text-sm"
          >
            <option value="psr_diff">PSR 差异检验</option>
            <option value="bootstrap">Bootstrap</option>
            {backtestIds.length >= 3 && <option value="mcs">MCS 检验</option>}
          </select>
        </div>

        {/* Confidence selector */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">置信水平</label>
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
            <label className="block text-xs text-gray-500 mb-1">块大小 (Block Size)</label>
            <input
              type="number"
              min={1}
              placeholder="自动"
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
          {isLoading ? '运行中...' : '运行检验'}
        </button>
      </div>

      {error && (
        <div className="p-3 text-sm text-red-500 bg-red-50 rounded">
          检验失败: {(error as Error).message}
        </div>
      )}

      {renderResult()}

      {!data && !isLoading && !error && (
        <div className="p-6 text-center text-gray-400 text-sm">
          选择检验类型后点击"运行检验"
        </div>
      )}
    </div>
  );
};
