# 产品经理 Agent 测试用例 1：策略组合功能

> 测试时间：2026-07-13
> 测试目标：验证产品经理提示词对复杂策略需求的理解能力

---

## 输入需求

```
我期望策略配置功能的自由度更好：
1. 自定义一个交易策略后(选股可能包含非常多标的)，结合截面因子、行业因子、时序因子等多个因子打分，选择得分更高的标的进行交易。
2. 支持多个交易策略/策略配置组合使用。先自定义好多个选股/交易策略(包含指标定义，以及建仓、加仓、减仓、平仓、止盈止损等操作)，新策略能够组合多个已有的交易策略。

具体场景：
- 策略 A 负责"建仓"阶段，使用多因子打分选股
- 策略 B 负责"加仓"阶段，在策略 A 建仓后，当出现相对确定性行情时加仓
- 两个策略独立，每一笔买入操作需要根据对应策略的卖出、止盈、止损条件触发执行
- 当配置了全局止盈或止损时，触发条件也需要执行
```

---

## 预期输出（PRD 草稿）

# 策略组合增强 PRD

> 版本：v1.0 · 2026-07-13
> 状态：Draft
> 优先级：P1

---

## 一、背景

当前 cQuant 平台的策略配置存在以下限制：
1. CompositeStrategy 仅支持简单加权组合（equal_weight / custom）
2. 无法定义策略间的执行顺序（建仓 → 加仓）
3. 缺少全局止盈止损机制
4. 每笔交易无法追溯来源策略

### 架构前提

- 复用现有 Strategy ABC 接口
- 扩展 CompositeStrategy 支持阶段式协调
- 复用现有止盈止损逻辑，扩展为全局级别

---

## 二、用户故事

> 作为量化交易员，我希望能够定义多个独立的交易策略，并按阶段组合执行（如建仓策略 + 加仓策略），每个策略有独立的止盈止损，同时支持全局止盈止损，以便实现更灵活的策略组合。

---

## 三、功能规格

| 项目 | 规格 |
|------|------|
| **入口** | StrategiesPage → 新建组合策略 |
| **输入** | 多个已保存的策略 ID + 协调模式 + 全局止盈止损参数 |
| **输出** | 组合策略配置（JSON） |
| **协调模式** | sequential（阶段式）/ parallel（并行式）/ conditional（条件式） |
| **策略角色** | entry（建仓）/ add_position（加仓）/ exit（退出） |
| **全局止盈** | 所有持仓达到 X% 盈利时卖出 |
| **全局止损** | 所有持仓达到 X% 亏损时卖出 |
| **交易归因** | 每笔交易记录来源策略 ID |

---

## 四、API 需求

```python
# 保存组合策略配置
POST /strategies/composite
Body: {
  "strategy_id": "my_composite",
  "coordination_mode": "sequential",
  "strategies": [
    {"strategy_id": "strategy_a", "role": "entry"},
    {"strategy_id": "strategy_b", "role": "add_position"}
  ],
  "global_stop_loss": 0.05,
  "global_take_profit": 0.20
}

# 获取组合策略配置
GET /strategies/composite/{id}

# 运行组合策略回测
POST /backtests/composite
Body: {
  "strategy_id": "my_composite",
  "start_date": "2025-01-01",
  "end_date": "2025-06-30"
}
```

---

## 五、前端组件

```
components/strategies/
├── CompositeStrategyForm.tsx    # 组合策略配置表单
├── StrategyRoleSelector.tsx     # 策略角色选择器
├── CoordinationModeSelector.tsx # 协调模式选择器
└── TradeAttributionTable.tsx    # 交易归因表格
```

---

## 六、后端实现

```
python/cquant/backtest_vector/strategies/
├── combo.py                     # 增强 CompositeStrategy
│   ├── coordination.py          # 协调逻辑
│   └── attribution.py           # 交易归因
└── global_risk.py               # 全局止盈止损
```

---

## 七、验收标准

- [ ] 支持 sequential 协调模式（策略 A → 策略 B）
- [ ] 每个策略独立管理自己的止盈止损
- [ ] 全局止盈止损覆盖所有持仓
- [ ] 每笔交易记录来源策略 ID
- [ ] 前端可配置组合策略
- [ ] 回测结果展示交易归因

---

## 八、非目标（Out of Scope）

| 功能 | 说明 | 优先级 |
|------|------|--------|
| 自动调参 | 策略参数自动优化 | 低 |
| 实时策略切换 | 运行时动态切换策略 | 低 |
| 策略回测对比 | 多策略回测结果对比 | 低 |

---

## 九、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 策略间信号冲突 | 高 | 定义优先级规则，entry 信号优先于 add_position |
| 全局止盈止损与策略级冲突 | 中 | 全局级优先执行，策略级作为补充 |
| 交易归因复杂 | 中 | 每笔交易强制记录来源策略 |

---

## 测试结果

**评估维度**：
- ✅ 需求理解：准确理解了阶段式策略组合需求
- ✅ 功能规格：覆盖了协调模式、策略角色、全局止盈止损
- ✅ API 设计：遵循现有 RESTful 模式
- ✅ 验收标准：可测试、可量化
- ⚠️ 改进建议：可补充更多边界条件（如策略 A 无信号时策略 B 的行为）
