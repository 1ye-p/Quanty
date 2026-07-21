# 执行 Agent 测试用例 2：K 线图实现

> 测试时间：2026-07-13
> 测试目标：验证执行提示词对 K 线图 Plan 的实现能力

---

## 输入 Plan

[er_test_2_kline_review.md 的输出]

---

## 预期输出（实现报告）

# 实现报告：K 线图交易标注

## 变更摘要

增强 GET /market/prices 支持周期聚合，实现 KlineChart 通用组件和 TradeKlineChart 交易标注组件。

## 代码变更

### 文件 1：`python/cquant/api_server/routes/market.py`

**变更类型**：修改

**变更内容**：
```python
@router.get("/prices")
async def get_prices(
    asset_id: str,
    start: str,
    end: str,
    period: str = "daily",
    catalog=Depends(get_catalog),
):
    """获取行情数据，支持日 K/周 K/月 K 聚合。"""
    if period == "weekly":
        sql = """
            SELECT
                date_trunc('week', trade_date) AS trade_date,
                FIRST(open) AS open,
                MAX(high) AS high,
                MIN(low) AS low,
                LAST(close) AS close,
                SUM(volume) AS volume
            FROM silver_prices_1d
            WHERE asset_id = ? AND trade_date BETWEEN ? AND ?
            GROUP BY date_trunc('week', trade_date)
            ORDER BY trade_date
        """
    elif period == "monthly":
        sql = """
            SELECT
                date_trunc('month', trade_date) AS trade_date,
                FIRST(open) AS open,
                MAX(high) AS high,
                MIN(low) AS low,
                LAST(close) AS close,
                SUM(volume) AS volume
            FROM silver_prices_1d
            WHERE asset_id = ? AND trade_date BETWEEN ? AND ?
            GROUP BY date_trunc('month', trade_date)
            ORDER BY trade_date
        """
    else:
        sql = """
            SELECT trade_date, open, high, low, close, volume
            FROM silver_prices_1d
            WHERE asset_id = ? AND trade_date BETWEEN ? AND ?
            ORDER BY trade_date
        """

    df = catalog.query(sql, [asset_id, start, end])
    return {"prices": df.to_dicts()}
```

**变更原因**：支持周 K/月 K 聚合。

---

### 文件 2：`web/src/components/charts/KlineChart.tsx`

**变更类型**：新增

**变更内容**：
```tsx
import { useEffect, useRef } from 'react'
import { createChart, IChartApi, ISeriesApi } from 'lightweight-charts'

interface OHLCV {
  trade_date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

interface TradeAnnotation {
  trade_date: string
  price: number
  direction: 'buy' | 'sell'
  quantity: number
  pnl?: number
}

interface KlineChartProps {
  data: OHLCV[]
  annotations?: TradeAnnotation[]
  height?: number
  onAnnotationClick?: (annotation: TradeAnnotation) => void
}

export function KlineChart({
  data,
  annotations = [],
  height = 400,
  onAnnotationClick,
}: KlineChartProps) {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstanceRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)

  useEffect(() => {
    if (!chartRef.current) return

    const chart = createChart(chartRef.current, {
      height,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333333',
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
    })

    const series = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderVisible: false,
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    })

    chartInstanceRef.current = chart
    seriesRef.current = series

    return () => {
      chart.remove()
    }
  }, [height])

  useEffect(() => {
    if (!seriesRef.current || !data.length) return

    const candleData = data.map((d) => ({
      time: d.trade_date,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }))

    seriesRef.current.setData(candleData)

    // 添加交易标注
    if (annotations.length > 0) {
      const markers = annotations.map((a) => ({
        time: a.trade_date,
        position: a.direction === 'buy' ? 'belowBar' : 'aboveBar',
        color: a.direction === 'buy' ? '#26a69a' : '#ef5350',
        shape: a.direction === 'buy' ? 'arrowUp' : 'arrowDown',
        text: `${a.direction === 'buy' ? '买入' : '卖出'} ${a.quantity}股`,
      }))

      seriesRef.current.setMarkers(markers)
    }
  }, [data, annotations])

  return <div ref={chartRef} />
}
```

**变更原因**：实现通用 K 线图组件。

---

### 文件 3：`web/src/components/backtests/TradeKlineChart.tsx`

**变更类型**：新增

**变更内容**：
```tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { KlineChart } from '@/components/charts/KlineChart'
import { marketApi, backtestsApi } from '@/lib/api'

interface TradeKlineChartProps {
  backtestId: string
  assetId: string
}

export function TradeKlineChart({ backtestId, assetId }: TradeKlineChartProps) {
  const [period, setPeriod] = useState<'daily' | 'weekly' | 'monthly'>('daily')

  // 获取行情数据
  const { data: pricesData } = useQuery({
    queryKey: ['market', 'prices', assetId, period],
    queryFn: () => marketApi.getPrices(assetId, period),
  })

  // 获取成交记录
  const { data: fillsData } = useQuery({
    queryKey: ['backtests', backtestId, 'fills'],
    queryFn: () => backtestsApi.getFills(backtestId),
  })

  // 转换成交记录为标注
  const annotations = (fillsData?.fills ?? [])
    .filter((f) => f.asset_id === assetId)
    .map((f) => ({
      trade_date: f.trade_date,
      price: f.price,
      direction: f.direction as 'buy' | 'sell',
      quantity: f.quantity,
      pnl: f.pnl,
    }))

  return (
    <div>
      <div className="flex gap-2 mb-4">
        {(['daily', 'weekly', 'monthly'] as const).map((p) => (
          <button
            key={p}
            className={`px-3 py-1 rounded ${
              period === p ? 'bg-blue-500 text-white' : 'bg-gray-200'
            }`}
            onClick={() => setPeriod(p)}
          >
            {p === 'daily' ? '日 K' : p === 'weekly' ? '周 K' : '月 K'}
          </button>
        ))}
      </div>
      <KlineChart
        data={pricesData?.prices ?? []}
        annotations={annotations}
        onAnnotationClick={(a) => console.log('Clicked:', a)}
      />
    </div>
  )
}
```

**变更原因**：实现 K 线图 + 交易标注组件。

---

## 测试用例

### 测试 1：`test_get_prices_weekly`

```python
def test_get_prices_weekly(client, sample_prices):
    """测试周 K 聚合。"""
    response = client.get("/market/prices?asset_id=SSE:600036&period=weekly")
    assert response.status_code == 200
    data = response.json()
    assert "prices" in data
    assert len(data["prices"]) > 0
    # 验证聚合结果
    first = data["prices"][0]
    assert "trade_date" in first
    assert "open" in first
    assert "high" in first
    assert "low" in first
    assert "close" in first
    assert "volume" in first
```

### 测试 2：`test_kline_chart_render`

```tsx
test('KlineChart renders correctly', () => {
  const data = [
    { trade_date: '2025-01-15', open: 100, high: 110, low: 95, close: 105, volume: 1000 },
    { trade_date: '2025-01-16', open: 105, high: 115, low: 100, close: 110, volume: 1200 },
  ]

  render(<KlineChart data={data} />)

  expect(screen.getByRole('img')).toBeInTheDocument()
})
```

---

## 文档更新

### 更新 1：`docs/PRD_KLINE_SENSITIVITY_DATABROWSE.md`

**更新内容**：标记 K 线图功能为已实现。

---

## 未实现项

| 序号 | 项目 | 原因 | 后续计划 |
|------|------|------|----------|
| 1 | 多资产对比视图 | 时间限制 | 后续迭代 |
| 2 | 自定义时间范围 | 时间限制 | 后续迭代 |

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
