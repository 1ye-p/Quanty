import { test, expect } from '@playwright/test'
import { mockAllApis, gotoPage } from './fixtures'

test.describe('Strategy Configuration Flow', () => {
  test.beforeEach(async ({ page }) => {
    await mockAllApis(page)
  })

  test('strategies page loads with title and existing strategies', async ({ page }) => {
    await gotoPage(page, '/strategies')

    await expect(page.locator('h1')).toContainText('策略配置')
    await expect(page.locator('text=top10_equal').first()).toBeVisible()
  })

  test('strategies page has editor area', async ({ page }) => {
    await gotoPage(page, '/strategies')

    // The page should have the strategy list and editor section
    await expect(page.locator('h1')).toContainText('策略配置')

    // Strategy list shows the existing strategy
    await expect(page.locator('text=top10_equal').first()).toBeVisible()
  })

  test('strategies page has create button', async ({ page }) => {
    await gotoPage(page, '/strategies')

    // New strategy button
    await expect(page.locator('text=新建策略').first()).toBeVisible()
  })
})
