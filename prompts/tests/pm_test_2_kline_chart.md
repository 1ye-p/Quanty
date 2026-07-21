# 产品经理 Agent 测试用例 2：K 线图交易标注

> 测试时间：2026-07-13
> 测试目标：验证产品经理提示词对 UI 功能需求的理解能力

---

## 输入需求

```
在回测结果中，我希望能看到每笔交易在 K 线图上的买入/卖出位置，以便直观判断策略的入场/出场时机是否合理。

要求：
- 支持日 K、周 K、月 K 切换
- 买入点用绿色向上箭头标注
- 卖出点用红色向下箭头标注
- 悬停标注显示价格、数量、盈亏
- 默认展示近 8 个月数据
```

---

## 预期输出（PRD 草稿）

# K 线图交易标注 PRD

> 版本：v1.0 · 2026-07-13
> 状态：Draft
> 优先级：P1

---

## 一、背景

当前回测结果只有表格和散点图，无法在 K 线图上直观看到买卖点。用户需要切换到其他工具查看 K 线，效率低下。

### 架构前提

- 复用 lightweight-charts 图表库
- 复用 `backtestsApi.getFills()` 成交数据
- 复用 `GET /market/prices` 行情数据

---

## 二、用户故事

> 作为量化交易员，我希望在回测结果中看到每笔交易在 K 线图上的买入/卖出位置，以便直观判断策略的入场/出场时机是否合理。

---

## 三、功能规格

| 项目 | 规格 |
|------|------|
| **入口** | BacktestFillsTab → K 线图 tab |
| **图表库** | lightweight-charts |
| **K 线类型** | 日 K、周 K、月 K（后端聚合） |
| **默认时间范围** | 近 8 个月（~167 个交易日） |
| **交易标注** | 买入：绿色向上箭头，卖出：红色向下箭头 |
| **悬停信息** | 价格、数量、盈亏 |
| **交互** | 点击标注高亮成交记录，滚轮缩放，拖拽平移 |
| **资产选择** | 下拉选择器，列出回测涉及的所有资产 |

---

## 四、API 需求

```python
# 复用现有接口
GET /backtests/{id}/fills           # 获取成交记录
GET /market/prices?period=daily     # 获取日 K 数据

# 增强接口
GET /market/prices?period=weekly    # 周 K 聚合
GET /market/prices?period=monthly   # 月 K 聚合
```

---

## 五、前端组件

```
components/charts/
├── KlineChart.tsx           # 通用 K 线图组件
└── TradeAnnotation.tsx      # 交易标注组件

components/backtests/
├── TradeKlineChart.tsx      # K 线图 + 交易标注
└── AssetSelector.tsx        # 资产选择器
```

---

## 六、后端实现

```python
# python/cquant/api_server/routes/market.py
@router.get("/prices")
async def get_prices(asset_id, start, end, period="daily"):
    if period == "weekly":
        sql = """SELECT date_trunc('week', trade_date) AS trade_date,
                 FIRST(open) AS open, MAX(high) AS high,
                 MIN(low) AS low, LAST(close) AS close,
                 SUM(volume) AS volume
                 FROM silver_prices_1d WHERE ...
                 GROUP BY 1"""
    ...
```

---

## 七、验收标准

- [ ] K 线图正确显示选定资产的日 K 线
- [ ] 买入/卖出标注位置与成交记录一致
- [ ] 悬停标注显示价格、数量、盈亏
- [ ] 支持切换资产、切换 K 线周期（日/周/月）
- [ ] 默认展示近 8 个月数据
- [ ] 页面加载时间 < 2 秒（100 笔交易以内）

---

## 八、非目标（Out of Scope）

| 功能 | 说明 | 优先级 |
|------|------|--------|
| 实时 K 线图 | 仅支持历史数据 | — |
| 分钟级 K 线 | 仅支持日/周/月 | — |
| 自定义标注样式 | 固定箭头样式 | 低 |

---

## 九、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 行情数据量大，查询慢 | K 线图加载慢 | 默认限制 8 个月 + 分页 |
| lightweight-charts 标注 API 不够灵活 | 样式受限 | 必要时使用自定义 Canvas 覆盖层 |

---

## 测试结果

**评估维度**：
- ✅ 需求理解：准确理解了 K 线图标注需求
- ✅ 功能规格：覆盖了 K 线类型、标注样式、交互方式
- ✅ API 设计：复用现有接口，增强周期聚合
- ✅ 验收标准：性能指标明确
- ⚠️ 改进建议：可补充多资产对比视图
