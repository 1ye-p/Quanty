import { test, expect } from '@playwright/test'
import { mockAllApis, gotoPage } from './fixtures'

test.describe('Portfolio Optimization Flow', () => {
  test.beforeEach(async ({ page }) => {
    await mockAllApis(page)
  })

  test('optimize page loads with sections', async ({ page }) => {
    await gotoPage(page, '/optimize')

    await expect(page.locator('h1')).toContainText('组合优化')
    await expect(page.locator('text=协方差计算')).toBeVisible()
    await expect(page.locator('text=优化器配置')).toBeVisible()
  })

  test('full optimization flow: covariance then optimize', async ({ page }) => {
    await gotoPage(page, '/optimize')

    // Enter assets
    const assetInput = page.locator('input[placeholder*="600519"]').first()
    await assetInput.fill('SSE:600000, SZSE:000001')

    // Compute covariance
    await page.click('text=计算协方差')
    await expect(page.locator('text=/协方差矩阵已计算/')).toBeVisible({ timeout: 10000 })

    // Run optimization
    await page.click('text=运行优化')

    // Results appear
    await expect(page.locator('text=优化结果')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('text=/12\\.00%/')).toBeVisible()
    await expect(page.locator('text=/0\\.667/')).toBeVisible()
  })

  test('advanced constraints section toggles', async ({ page }) => {
    await gotoPage(page, '/optimize')

    // Hidden by default
    await expect(page.locator('text=最大换手率 (%)')).not.toBeVisible()

    // Toggle open
    await page.click('text=/高级约束配置/')
    await expect(page.locator('text=最大换手率 (%)')).toBeVisible()
    await expect(page.locator('text=换手率惩罚系数')).toBeVisible()
  })

  test('optimizer type selector visible', async ({ page }) => {
    await gotoPage(page, '/optimize')

    // The select has mean_variance as default
    await expect(page.locator('text=优化器配置')).toBeVisible()
    const selects = page.locator('select')
    await expect(selects.first()).toBeVisible()
  })

  test('cost_aware optimizer shows extra fields', async ({ page }) => {
    await gotoPage(page, '/optimize')

    // Find the optimizer select by looking for the one near "优化器配置"
    const optimizerSelect = page.locator('select').last()
    await optimizerSelect.selectOption('cost_aware')

    await expect(page.locator('text=交易成本率')).toBeVisible()
    await expect(page.locator('text=换手惩罚')).toBeVisible()
  })

  test('optimization result shows weight distribution chart', async ({ page }) => {
    await gotoPage(page, '/optimize')

    const assetInput = page.locator('input[placeholder*="600519"]').first()
    await assetInput.fill('SSE:600000, SZSE:000001')
    await page.click('text=计算协方差')
    await expect(page.locator('text=/协方差矩阵已计算/')).toBeVisible({ timeout: 10000 })
    await page.click('text=运行优化')

    await expect(page.locator('text=权重分布')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('text=权重分配')).toBeVisible()
  })

  test('backtest navigation button in results', async ({ page }) => {
    await gotoPage(page, '/optimize')

    const assetInput = page.locator('input[placeholder*="600519"]').first()
    await assetInput.fill('SSE:600000, SZSE:000001')
    await page.click('text=计算协方差')
    await expect(page.locator('text=/协方差矩阵已计算/')).toBeVisible({ timeout: 10000 })
    await page.click('text=运行优化')

    await expect(page.locator('text=/用这组权重运行回测/')).toBeVisible({ timeout: 10000 })
  })
})
