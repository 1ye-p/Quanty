import { test, expect } from '@playwright/test'
import { mockAllApis, gotoPage } from './fixtures'

test.describe('ML Lab Flow', () => {
  test.beforeEach(async ({ page }) => {
    await mockAllApis(page)
  })

  test('ML page loads with experiments', async ({ page }) => {
    await gotoPage(page, '/ml')

    await expect(page.locator('h1')).toContainText('机器学习实验室')
    await expect(page.locator('text=LightGBM').first()).toBeVisible()
  })

  test('experiment detail shows metrics', async ({ page }) => {
    await gotoPage(page, '/ml')

    await page.waitForSelector('text=LightGBM')
    await page.click('text=LightGBM')

    // Metrics visible
    await expect(page.locator('text=/sharpe|Sharpe/').first()).toBeVisible({ timeout: 10000 })
  })

  test('feature importance chart', async ({ page }) => {
    await gotoPage(page, '/ml')

    await page.waitForSelector('text=LightGBM')
    await page.click('text=LightGBM')

    // Feature importance section
    const fiSection = page.locator('text=特征重要性').first()
    if (await fiSection.isVisible()) {
      await expect(page.locator('text=ret_20d')).toBeVisible()
    }
  })

  test('ML predictions accessible', async ({ page }) => {
    await gotoPage(page, '/ml')

    // Predictions section
    const predTab = page.locator('text=预测').first()
    if (await predTab.isVisible()) {
      await predTab.click()
      await expect(page.locator('text=SSE:600000').first()).toBeVisible()
    }
  })
})
