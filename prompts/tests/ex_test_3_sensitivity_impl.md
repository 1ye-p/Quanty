# 执行 Agent 测试用例 3：参数敏感性实现

> 测试时间：2026-07-13
> 测试目标：验证执行提示词对参数敏感性 Plan 的实现能力

---

## 输入 Plan

[er_test_3_sensitivity_review.md 的输出]

---

## 预期输出（实现报告）

# 实现报告：参数敏感性分析

## 变更摘要

实现参数扫描 API 和前端组件，支持 1D 曲线图和 2D 热力图。

## 代码变更

### 文件 1：`python/cquant/api_server/routes/backtests.py`

**变更类型**：修改

**变更内容**：
```python
@router.post("/backtests/{backtest_id}/sensitivity")
async def run_sensitivity(
    backtest_id: str,
    request: SensitivityRequest,
    background_tasks: BackgroundTasks,
    catalog=Depends(get_catalog),
):
    """启动参数扫描。"""
    # 验证参数组合数
    param_count = len(
        range(request.range.start, request.range.end + 1, request.range.step)
    )
    if param_count > 100:
        raise HTTPException(
            status_code=400,
            detail="参数组合数不能超过 100 个",
        )

    # 创建 job
    job_id = str(uuid.uuid4())
    _save_job(catalog, job_id, "sensitivity", "running")

    # 异步执行
    background_tasks.add_task(
        _run_sensitivity,
        catalog,
        backtest_id,
        job_id,
        request.param,
        request.range,
        request.metrics,
    )

    return {"job_id": job_id, "status": "running"}


@router.get("/backtests/{backtest_id}/sensitivity/{job_id}")
async def get_sensitivity_result(
    backtest_id: str,
    job_id: str,
    catalog=Depends(get_catalog),
):
    """获取参数扫描结果。"""
    job = _get_job(catalog, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "status": job["status"],
        "results": job.get("results", []),
        "error": job.get("error"),
    }


@router.get("/backtests/{backtest_id}/sensitivity/history")
async def get_sensitivity_history(
    backtest_id: str,
    catalog=Depends(get_catalog),
):
    """获取参数扫描历史。"""
    history = _get_sensitivity_history(catalog, backtest_id)
    return {"history": history}
```

**变更原因**：实现参数扫描 API。

---

### 文件 2：`python/cquant/api_server/routes/backtests_sensitivity.py`

**变更类型**：新增

**变更内容**：
```python
"""参数扫描后端实现。"""
from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from typing import Any

import polars as pl

from cquant.backtest_vector.run import VectorBacktestRunner

logger = logging.getLogger(__name__)


@dataclass
class ParamRange:
    """参数范围。"""
    start: int | float
    end: int | float
    step: int | float


def _run_sensitivity(
    catalog,
    backtest_id: str,
    job_id: str,
    param: str,
    param_range: ParamRange,
    metrics: list[str],
    timeout_seconds: int = 1800,
):
    """运行参数扫描。"""
    start_time = time.time()
    results = []

    try:
        # 生成参数值列表
        values = list(
            range(param_range.start, param_range.end + 1, param_range.step)
        )

        for value in values:
            # 检查超时
            if time.time() - start_time > timeout_seconds:
                _save_job(
                    catalog,
                    job_id,
                    "sensitivity",
                    "failed",
                    error="Timeout",
                )
                return

            # 运行回测
            runner = VectorBacktestRunner(catalog)
            result = runner.run_with_params(
                backtest_id=backtest_id,
                param_overrides={param: value},
            )

            # 提取指标
            metric_values = {}
            for metric in metrics:
                metric_values[metric] = result.get(metric, 0.0)

            results.append({
                "param_value": value,
                "metrics": metric_values,
            })

            # 更新进度
            _update_job_progress(
                catalog,
                job_id,
                len(results),
                len(values),
            )

        # 保存结果
        _save_job(
            catalog,
            job_id,
            "sensitivity",
            "completed",
            results=results,
        )

    except Exception as e:
        logger.exception("Sensitivity scan failed")
        _save_job(
            catalog,
            job_id,
            "sensitivity",
            "failed",
            error=str(e),
        )
```

**变更原因**：实现参数扫描后端逻辑。

---

### 文件 3：`web/src/components/backtests/SensitivityPanel.tsx`

**变更类型**：新增

**变更内容**：
```tsx
import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { backtestsApi } from '@/lib/api'
import { SensitivityChart } from './SensitivityChart'
import { SensitivityHeatmap } from './SensitivityHeatmap'

interface SensitivityPanelProps {
  backtestId: string
}

export function SensitivityPanel({ backtestId }: SensitivityPanelProps) {
  const [param, setParam] = useState('top_n')
  const [range, setRange] = useState({ start: 5, end: 20, step: 5 })
  const [jobId, setJobId] = useState<string | null>(null)

  // 启动参数扫描
  const mutation = useMutation({
    mutationFn: () =>
      backtestsApi.runSensitivity(backtestId, {
        param,
        range,
        metrics: ['total_return', 'sharpe_ratio', 'max_drawdown'],
      }),
    onSuccess: (data) => {
      setJobId(data.job_id)
    },
  })

  // 查询结果
  const { data: result } = useQuery({
    queryKey: ['sensitivity', jobId],
    queryFn: () => backtestsApi.getSensitivityResult(backtestId, jobId!),
    enabled: !!jobId,
    refetchInterval: (query) =>
      query.state.data?.status === 'completed' ? false : 2000,
  })

  // 查询历史
  const { data: history } = useQuery({
    queryKey: ['sensitivity', 'history', backtestId],
    queryFn: () => backtestsApi.getSensitivityHistory(backtestId),
  })

  return (
    <div>
      <h3>参数敏感性分析</h3>

      {/* 配置面板 */}
      <div className="flex gap-4 mb-4">
        <select value={param} onChange={(e) => setParam(e.target.value)}>
          <option value="top_n">Top N</option>
          <option value="rebalance_frequency">调仓频率</option>
          <option value="stop_loss">止损比例</option>
        </select>

        <input
          type="number"
          value={range.start}
          onChange={(e) => setRange({ ...range, start: +e.target.value })}
          placeholder="起始值"
        />
        <input
          type="number"
          value={range.end}
          onChange={(e) => setRange({ ...range, end: +e.target.value })}
          placeholder="终止值"
        />
        <input
          type="number"
          value={range.step}
          onChange={(e) => setRange({ ...range, step: +e.target.value })}
          placeholder="步长"
        />

        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
        >
          {mutation.isPending ? '扫描中...' : '开始扫描'}
        </button>
      </div>

      {/* 结果展示 */}
      {result?.status === 'completed' && (
        <div>
          <SensitivityChart data={result.results} />
          <SensitivityHeatmap data={result.results} />
        </div>
      )}

      {/* 历史列表 */}
      {history?.history && (
        <div>
          <h4>历史扫描</h4>
          <ul>
            {history.history.map((h) => (
              <li key={h.job_id}>
                {h.param} - {h.values.join(', ')} - {h.status}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
```

**变更原因**：实现参数扫描前端组件。

---

## 测试用例

### 测试 1：`test_run_sensitivity`

```python
def test_run_sensitivity(client, sample_backtest):
    """测试参数扫描 API。"""
    response = client.post(
        f"/backtests/{sample_backtest}/sensitivity",
        json={
            "param": "top_n",
            "range": {"start": 5, "end": 20, "step": 5},
            "metrics": ["total_return", "sharpe_ratio"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "running"
```

### 测试 2：`test_sensitivity_timeout`

```python
def test_sensitivity_timeout(client, sample_backtest):
    """测试参数扫描超时。"""
    # Mock 超时场景
    with patch('time.time', side_effect=[0, 0, 2000]):
        response = client.post(
            f"/backtests/{sample_backtest}/sensitivity",
            json={
                "param": "top_n",
                "range": {"start": 1, "end": 100, "step": 1},
                "metrics": ["total_return"],
            },
        )
        # 等待 job 完成
        job_id = response.json()["job_id"]
        result = client.get(f"/backtests/{sample_backtest}/sensitivity/{job_id}")
        assert result.json()["status"] == "failed"
        assert "Timeout" in result.json()["error"]
```

---

## 文档更新

### 更新 1：`docs/PRD_KLINE_SENSITIVITY_DATABROWSE.md`

**更新内容**：标记参数敏感性分析功能为已实现。

---

## 未实现项

| 序号 | 项目 | 原因 | 后续计划 |
|------|------|------|----------|
| 1 | 参数扫描队列机制 | 时间限制 | 后续迭代 |
| 2 | 参数扫描结果对比 | 时间限制 | 后续迭代 |

---

## 质量检查结果

- [x] Lint 通过（ruff check / eslint）
- [x] Type Check 通过（mypy / tsc）
- [x] Test 通过（pytest / vitest）
- [x] Build 通过

---

## 测试结果

**评估维度**：
- ✅ 代码质量：遵循编码规范
- ✅ 测试覆盖：核心功能有测试用例
- ✅ 文档更新：相关文档已更新
- ⚠️ 改进建议：可补充更多边界条件测试
