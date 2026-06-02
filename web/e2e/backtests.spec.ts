import { test, expect } from '@playwright/test'
import { mockAllApis, gotoPage } from './fixtures'

test.describe('Backtest Evaluation Flow', () => {
  test.beforeEach(async ({ page }) => {
    await mockAllApis(page)
  })

  test('backtests page loads with completed runs', async ({ page }) => {
    await gotoPage(page, '/backtests')

    await expect(page.locator('h1')).toContainText('回测评估')
    await expect(page.locator('text=top10_equal').first()).toBeVisible()
  })

  test('click backtest row to see detail panel', async ({ page }) => {
    await gotoPage(page, '/backtests')

    await page.waitForSelector('text=top10_equal')

    // Click the row containing top10_equal
    const row = page.locator('tr:has-text("top10_equal")')
    await row.click()

    // Detail panel tabs appear
    await expect(page.locator('text=概览').first()).toBeVisible()
    await expect(page.locator('text=Tearsheet').first()).toBeVisible()
  })

  test('backtest detail overview shows metrics', async ({ page }) => {
    await gotoPage(page, '/backtests')

    await page.waitForSelector('text=top10_equal')
    const row = page.locator('tr:has-text("top10_equal")')
    await row.click()

    // Wait for detail to load
    await page.waitForSelector('text=概览')
    await page.click('text=概览')

    // Metrics cards appear
    await expect(page.locator('text=总收益').first()).toBeVisible({ timeout: 10000 })
    await expect(page.locator('text=Sharpe').first()).toBeVisible()
    await expect(page.locator('text=最大回撤').first()).toBeVisible()
  })

  test('backtest detail has export button', async ({ page }) => {
    await gotoPage(page, '/backtests')

    await page.waitForSelector('text=top10_equal')
    const row = page.locator('tr:has-text("top10_equal")')
    await row.click()

    await page.waitForSelector('text=概览')
    await page.click('text=概览')

    // Export button
    await expect(page.locator('text=导出 HTML 报告')).toBeVisible({ timeout: 10000 })
  })

  test('backtest list shows status badges', async ({ page }) => {
    await gotoPage(page, '/backtests')

    await page.waitForSelector('text=top10_equal')

    // Status badge exists in the table
    await expect(page.locator('td .badge, td [class*="badge"]').first()).toBeVisible()
  })

  test('backtest tearsheet tab', async ({ page }) => {
    await gotoPage(page, '/backtests')

    await page.waitForSelector('text=top10_equal')
    const row = page.locator('tr:has-text("top10_equal")')
    await row.click()

    await page.waitForSelector('text=Tearsheet')
    await page.click('text=Tearsheet')

    // Tearsheet content - uses "NAV & 回撤曲线" or "NAV 曲线"
    await expect(page.locator('text=/NAV/')).toBeVisible({ timeout: 10000 })
  })
})
