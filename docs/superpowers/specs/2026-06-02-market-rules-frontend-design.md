# PRD v3.0 Phase 1: 市场规则前端集成 设计文档

> **目标：** 为已完成的市场规则后端模块提供前端集成，包括策略配置页的市场规则表单和回测结果页的展示增强。
>
> **范围：** 策略配置页新增市场规则区块、回测结果页参数摘要、交易明细退市事件标记。
>
> **技术栈：** React 18 + TypeScript + Vite + TanStack Query

---

## 1. 背景与动机

PRD v3.0 Phase 1 后端已实现 7 项 A 股市场规则（复权因子、涨跌停含一字板、停牌、ST 状态、退市日期、退市持仓处理、YAML 配置）。前端需要提供配置入口和结果展示，使用户能够：

- 在策略配置时选择市场和复权方式
- 在回测结果中看到复权方式和退市强制平仓事件

---

## 2. 策略配置页改动

### 2.1 市场规则区块

**位置：** `StrategyBuilder` 组件中，「风控限制」区块下方、「快速风控」上方。

**文件：** `web/src/pages/StrategiesPage.tsx`

**UI 结构：**

```tsx
<div className="border rounded-lg p-3">
  <div className="text-xs font-medium text-gray-600 mb-2">市场规则</div>
  <div className="grid grid-cols-2 gap-3">
    <div>
      <label className="text-xs text-gray-500">市场</label>
      <select className="input w-full" value={market} onChange={e => setMarket(e.target.value)}>
        <option value="CN">A 股</option>
        <option value="US">美股</option>
        <option value="HK">港股</option>
      </select>
    </div>
    <div>
      <label className="text-xs text-gray-500">复权方式</label>
      <select className="input w-full" value={adjType} onChange={e => setAdjType(e.target.value)}>
        <option value="forward">前复权</option>
        <option value="backward">后复权</option>
        <option value="none">不复权</option>
      </select>
    </div>
  </div>
</div>
```

**State 管理：**

```tsx
const [market, setMarket] = useState(parsed.market_rule?.market ?? 'CN')
const [adjType, setAdjType] = useState(parsed.market_rule?.adj_type ?? 'forward')
```

**Config 输出：**

在 `useEffect` 中添加：

```tsx
config.market_rule = { market, adj_type: adjType }
```

**DEFAULT_CONFIG 更新：**

```tsx
const DEFAULT_CONFIG = JSON.stringify({
  // ... existing fields ...
  market_rule: { market: "CN", adj_type: "forward" },
}, null, 2)
```

**useEffect 依赖：** 将 `market` 和 `adjType` 加入依赖数组。

---

## 3. 回测结果页改动

### 3.1 Overview — 参数摘要

**位置：** Overview tab 的指标卡片上方。

**文件：** `web/src/pages/BacktestsPage.tsx`

**UI 结构：**

```tsx
{detail?.strategy_config && (
  <div className="text-xs text-gray-400 flex flex-wrap gap-x-3 gap-y-1">
    <span>市场: {marketLabel(detail.strategy_config.market_rule?.market)}</span>
    <span>复权: {adjLabel(detail.strategy_config.market_rule?.adj_type)}</span>
    <span>调仓: {rebalanceLabel(detail.strategy_config.rebalance_frequency)}</span>
    <span>Sizer: {detail.strategy_config.sizer ?? 'equal_weight'}</span>
  </div>
)}
```

**辅助函数：**

```tsx
function marketLabel(m?: string) {
  return { CN: 'A股', US: '美股', HK: '港股' }[m ?? 'CN'] ?? 'A股'
}
function adjLabel(a?: string) {
  return { forward: '前复权', backward: '后复权', none: '不复权' }[a ?? 'forward'] ?? '前复权'
}
function rebalanceLabel(r?: string) {
  return { '1d': '每日', '5d': '每周', '20d': '每月' }[r ?? '1d'] ?? r ?? '每日'
}
```

**数据来源：** `detail.strategy_config` — 需要后端在 `GET /backtests/{id}` 返回中包含 `strategy_config` 字段。若后端已存储则直接使用；若未存储，需在回测创建时传入并持久化。

### 3.2 Fills — 退市事件标记

**位置：** Fills tab 的 DataTable。

**文件：** `web/src/pages/BacktestsPage.tsx`

**Column 定义：**

在现有 columns 数组中新增：

```tsx
{
  key: 'reason',
  label: '原因',
  render: (value: unknown) => {
    if (value === 'delist_forced_liquidation') return '退市强制平仓'
    return '—'
  },
}
```

**行高亮：**

在 DataTable 组件中，通过 `rowClassName` 回调实现：

```tsx
<DataTable
  // ... existing props ...
  rowClassName={(row) =>
    row.reason === 'delist_forced_liquidation' ? 'bg-orange-50' : ''
  }
/>
```

**DataTable 组件改动：** `web/src/components/ui/DataTable.tsx` 需新增 `rowClassName` prop：

```tsx
interface DataTableProps<T> {
  // ... existing props ...
  rowClassName?: (row: T) => string
}
```

在 `<tr>` 元素上应用：

```tsx
<tr className={rowClassName?.(row) ?? ''}>
```

---

## 4. API 层改动

### 4.1 策略 API

无需改动。`strategiesApi.create/update` 已接受任意 JSON config，`market_rule` 字段会随 config 一起存储。

### 4.2 回测 API

需确认 `backtestsApi.get()` 返回的 detail 对象包含 `strategy_config` 字段。若后端未返回，需在后端 `GET /backtests/{id}` 响应中添加。

需确认 `backtestsApi.getFills()` 返回的 fill 记录包含 `reason` 字段。后端 fill_simulator 已在 `ForcedLiquidationTrade` 中设置 `reason="delist_forced_liquidation"`。

---

## 5. 测试策略

| 层级 | 框架 | 内容 |
|------|------|------|
| 组件测试 | Vitest | StrategyBuilder 市场规则区块渲染、state 变化、config 输出 |
| 组件测试 | Vitest | BacktestsPage 参数摘要显示、退市行高亮 |
| E2E | Playwright | 策略配置选择市场+复权 → 保存 → 回测 → 验证参数摘要和退市标记 |

---

## 6. 验收标准

- [ ] 策略配置页「风控限制」下方显示「市场规则」区块
- [ ] 市场下拉框：A股/美股/港股，默认 A股
- [ ] 复权方式下拉框：前复权/后复权/不复权，默认前复权
- [ ] JSON config 中包含 `market_rule: { market, adj_type }`
- [ ] 回测结果 Overview 显示参数摘要行（市场、复权、调仓、Sizer）
- [ ] 交易明细新增「原因」列
- [ ] 退市强制平仓行显示「退市强制平仓」+ 橙色高亮背景
- [ ] 现有功能无回归
