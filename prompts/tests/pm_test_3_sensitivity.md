# 产品经理 Agent 测试用例 3：参数敏感性分析

> 测试时间：2026-07-13
> 测试目标：验证产品经理提示词对数据分析功能的理解能力

---

## 输入需求

```
我希望批量扫描策略参数（如 Top N 从 5 到 20），看到每个参数组合的收益/夏普/回撤变化，以便判断策略是否对参数敏感。

要求：
- 支持 1D（单参数曲线）和 2D（双参数热力图）
- 可扫描参数：top_n / rebalance_frequency / sizer / 止损比例 / 回撤熔断比例
- 用户指定起始值、终止值、步长
- 单次最多 100 个参数组合
- 异步执行，前端显示进度
- 结果可导出 CSV
```

---

## 预期输出（PRD 草稿）

# 参数敏感性分析 PRD

> 版本：v1.0 · 2026-07-13
> 状态：Draft
> 优先级：P2

---

## 一、背景

当前只能单次回测，无法批量扫描参数验证鲁棒性。用户需要手动修改参数多次运行，效率低下。

### 架构前提

- 复用现有 `BackgroundTasks` + DuckDB 持久化 + 前端轮询
- 复用 `GridSearchSensitivity` 引擎（已存在）
- 复用现有"软取消"机制

---

## 二、用户故事

> 作为量化交易员，我希望批量扫描策略参数，看到每个参数组合的收益/夏普/回撤变化，以便判断策略是否对参数敏感。

---

## 三、功能规格

| 项目 | 规格 |
|------|------|
| **入口** | BacktestOverviewTab → 参数扫描按钮 |
| **扫描维度** | 1D（单参数曲线）/ 2D（双参数热力图） |
| **可扫描参数** | top_n / rebalance_frequency / sizer / 止损比例 / 回撤熔断比例 |
| **扫描方式** | 用户指定起始值、终止值、步长 |
| **输出** | 1D：参数-收益/夏普/回撤曲线图；2D：参数-收益热力图 |
| **2D 热力图交互** | 点击单元格 → 弹出详情面板 |
| **并发** | 异步执行（复用 job 机制） |
| **任务取消** | 软取消（`POST /jobs/{id}/cancel`） |
| **超时保护** | 30 分钟，循环内检查 |
| **限制** | 单次最多 100 个参数组合 |
| **CSV 导出** | 前端 JSON→CSV 转换 |
| **历史列表** | 最近 10 次扫描 |

---

## 四、API 需求

```python
# 启动参数扫描
POST /backtests/{id}/sensitivity
Body: {
  "param": "top_n",
  "range": {"start": 5, "end": 20, "step": 5},
  "metrics": ["total_return", "sharpe_ratio", "max_drawdown"]
}
Response: { "job_id": "...", "status": "running" }

# 查询扫描结果
GET /backtests/{id}/sensitivity/{job_id}
Response: {
  "status": "completed",
  "results": [...]
}

# 查询扫描历史
GET /backtests/{id}/sensitivity/history
Response: {
  "history": [
    {"job_id": "...", "param": "top_n", "values": [5,10,15,20], "created_at": "..."},
    ...
  ]
}
```

---

## 五、前端组件

```
components/backtests/
├── SensitivityPanel.tsx     # 参数扫描配置面板
├── SensitivityChart.tsx     # 1D 参数曲线图
├── SensitivityHeatmap.tsx   # 2D 参数热力图
└── SensitivityDetail.tsx    # 热力图单元格详情
```

---

## 六、后端实现

```
python/cquant/backtest_vector/
├── sensitivity.py           # GridSearchSensitivity 引擎（已存在）
└── run.py                   # 复用 VectorBacktestEngine.run()
```

---

## 七、验收标准

- [ ] 支持 1D 参数扫描（单参数曲线）
- [ ] 支持 2D 参数扫描（双参数热力图）
- [ ] 热力图点击单元格弹出详情面板
- [ ] 异步执行 + 进度显示
- [ ] 参数组合数限制 100 个
- [ ] 超时保护（30 分钟）
- [ ] 结果可导出 CSV
- [ ] 历史扫描列表可查看

---

## 八、非目标（Out of Scope）

| 功能 | 说明 | 优先级 |
|------|------|--------|
| 参数扫描自动调参 | 仅展示结果，不做优化 | 低 |
| 3D 热力图 | 仅支持 1D/2D | — |
| 实时参数调整 | 扫描期间不可修改参数 | — |

---

## 九、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 参数扫描耗时长 | 用户等待久 | 异步 job + 进度轮询 + 超时 30 分钟 |
| 资源耗尽 | 系统崩溃 | 组合数限制 100 |
| Combo 策略深拷贝失败 | 扫描中断 | 实现时增加 Combo 策略测试用例 |

---

## 测试结果

**评估维度**：
- ✅ 需求理解：准确理解了参数扫描需求
- ✅ 功能规格：覆盖了 1D/2D 扫描、异步执行、超时保护
- ✅ API 设计：复用 job 机制
- ✅ 验收标准：性能指标明确
- ⚠️ 改进建议：可补充参数扫描结果与原回测的对比视图
