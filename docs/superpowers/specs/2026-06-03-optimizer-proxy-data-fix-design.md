# PRD v3.0 Phase 2: 优化器代理数据修复 设计文档

> **目标：** 修复回测引擎中 portfolio optimizer 使用代理数据（proxy data）的问题，接入真实的预期收益和协方差矩阵。
>
> **范围：** `backtest_vector/engine.py` 的优化器区块，新增两个辅助方法。
>
> **技术栈：** Python 3.12 + Polars + NumPy + CovarianceEstimator

---

## 1. 背景与动机

`backtest_vector/engine.py:216-231` 的优化器代码使用代理数据：

```python
# PLACEHOLDER: Uses proxy data (signal-scaled returns, uniform diagonal
# covariance). For real mean-variance optimization, replace with actual
# expected returns from ML predictions and covariance from CovarianceEstimator.
expected_returns = {k: float(v) * 0.10 for k, v in weights_dict.items()}
_cov = (0.20 ** 2) / 252
covariance = {a: {b: _cov if a == b else 0.0 for b in weights_dict} ...}
```

**问题：**
- 预期收益 = 信号强度 × 0.10（任意缩放，无经济含义）
- 协方差 = 所有资产之间零相关（现实中不可能）
- 优化器输入是垃圾数据，输出的权重毫无意义

**影响：** 所有使用 optimizer 参数的回测结果中，组合优化部分不可信。

---

## 2. 设计方案

### 2.1 预期收益（Expected Returns）

**三级数据源（按优先级）：**

1. **ML 模型预测** — 如果 `spec.extra["ml_predictions"]` 存在（`dict[str, float]`，asset_id → 预期收益率），直接使用
2. **历史收益率** — 从 `spec.prices` 计算近 N 天的年化收益率（默认 60 天窗口）
3. **降级** — 如果历史数据不足（< 10 天），使用信号强度映射（strength × 0.05）

**计算逻辑：**

```python
def _compute_expected_returns(self, signals, prices, td, ml_predictions=None, lookback=60):
    asset_ids = signals["asset_id"].to_list()
    
    # 优先使用 ML 预测
    if ml_predictions:
        return {aid: ml_predictions[aid] for aid in asset_ids if aid in ml_predictions}
    
    # 从历史价格计算收益率
    hist = prices.filter(
        (pl.col("asset_id").is_in(asset_ids)) &
        (pl.col("trade_date") <= td)
    ).sort(["asset_id", "trade_date"])
    
    # 取最近 lookback 天
    unique_dates = sorted(hist["trade_date"].unique().to_list())
    if len(unique_dates) >= 10:
        cutoff = unique_dates[-min(lookback, len(unique_dates))]
        hist = hist.filter(pl.col("trade_date") >= cutoff)
    
    # 计算年化收益率
    returns = (
        hist.group_by("asset_id")
        .agg([
            (pl.col("close").last() / pl.col("close").first() - 1).alias("raw_return"),
            pl.col("trade_date").n_unique().alias("days"),
        ])
        .with_columns(
            (pl.col("raw_return") * 252 / pl.col("days")).alias("annualized_return")
        )
    )
    
    result = {row["asset_id"]: float(row["annualized_return"]) for row in returns.iter_rows(named=True)}
    
    # 降级：缺失资产用信号强度映射
    for aid in asset_ids:
        if aid not in result:
            strength = float(signals.filter(pl.col("asset_id") == aid)["strength"].item())
            result[aid] = strength * 0.05
    
    return result
```

### 2.2 协方差矩阵（Covariance Matrix）

**使用已有的 `CovarianceEstimator`：**

```python
def _compute_covariance(self, asset_ids, prices, td):
    from cquant.portfolio_opt.covariance import CovarianceEstimator
    
    estimator = CovarianceEstimator(method="historical", window=252, min_periods=10)
    cov_matrix = estimator.estimate(prices, as_of_date=td)
    
    # 只保留有信号的资产子集
    return {
        a: {b: cov_matrix.get(a, {}).get(b, 0.0) for b in asset_ids}
        for a in asset_ids
    }
```

**降级策略：** `CovarianceEstimator` 内部已处理数据不足的情况（`min_periods` 参数），会自动降级为对角矩阵。

### 2.3 优化器调用替换

**替换 engine.py:215-231 的 PLACEHOLDER 代码：**

```python
# Apply portfolio optimizer if set (overrides sizer weights)
if spec.optimizer is not None and weights_dict:
    try:
        active_assets = list(weights_dict.keys())
        
        # Compute expected returns: ML predictions > historical returns
        ml_preds = spec.extra.get("ml_predictions")
        expected_returns = self._compute_expected_returns(
            signals, prices, td, ml_predictions=ml_preds,
        )
        
        # Compute covariance from historical prices
        covariance = self._compute_covariance(active_assets, prices, td)
        
        # Call optimizer with real data
        opt_result = spec.optimizer.optimize(expected_returns, covariance)
        if opt_result.weights:
            weights_dict = opt_result.weights
    except Exception as _exc:
        logger.debug("Optimizer skipped for %s: %s", td, _exc)
```

---

## 3. 数据流

```
signals (StrategyContext)
    │
    ├── asset_ids ──────────────────────────────┐
    │                                           │
    ├── spec.extra["ml_predictions"] ──→ _compute_expected_returns
    │   (如果有)                                │
    │                                           │
    └── spec.prices ──→ _compute_expected_returns (历史回退)
                        ──→ CovarianceEstimator.estimate()
                                │
                                ▼
                    optimizer.optimize(expected_returns, covariance)
                                │
                                ▼
                        OptimizationResult.weights
```

---

## 4. 边界情况处理

| 场景 | 处理 |
|------|------|
| ML 预测只覆盖部分资产 | 只用 ML 覆盖的资产，其余用历史收益率 |
| 历史数据不足（< 10 天） | 降级为信号强度映射（strength × 0.05） |
| 协方差计算失败 | 降级为对角矩阵（与 CovarianceEstimator 一致） |
| 优化器不收敛 | 保持现有行为：logger.warning + 使用原始 weights_dict |
| 单资产 | 跳过优化（单资产无优化意义） |
| 空信号 | 跳过优化（现有逻辑已处理） |

---

## 5. 测试策略

| 层级 | 内容 |
|------|------|
| 单元测试 | `_compute_expected_returns`：ML 优先、历史回退、降级逻辑 |
| 单元测试 | `_compute_covariance`：正常计算、数据不足降级 |
| 集成测试 | 优化器端到端：传入真实价格数据 + optimizer，验证输出权重合理 |
| 回归测试 | 现有回测测试不回归 |

---

## 6. 验收标准

- [ ] `engine.py` 中不再有 PLACEHOLDER 注释
- [ ] 优化器使用真实的历史协方差矩阵（非对角矩阵）
- [ ] 预期收益优先使用 ML 预测，否则使用历史收益率
- [ ] 数据不足时优雅降级（不崩溃、不返回垃圾数据）
- [ ] 现有回测测试通过
- [ ] 新增单元测试覆盖 `_compute_expected_returns` 和 `_compute_covariance`
