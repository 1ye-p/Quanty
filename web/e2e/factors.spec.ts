import { test, expect } from '@playwright/test'
import { mockAllApis, gotoPage } from './fixtures'

test.describe('Factors Research Flow', () => {
  test.beforeEach(async ({ page }) => {
    await mockAllApis(page)
  })

  test('factors page loads with factor cards', async ({ page }) => {
    await gotoPage(page, '/factors')

    await expect(page.locator('h1')).toContainText('Alpha 因子研究')

    // Factor cards render
    await expect(page.locator('text=ret_5d').first()).toBeVisible()
    await expect(page.locator('text=vol_20d').first()).toBeVisible()
    await expect(page.locator('text=5日收益率').first()).toBeVisible()
  })

  test('search filters factors', async ({ page }) => {
    await gotoPage(page, '/factors')

    await page.waitForSelector('text=ret_5d')
    const searchInput = page.locator('input[placeholder*="搜索因子"]')
    await searchInput.fill('vol')

    // vol_20d should remain, ret_5d description should be filtered out
    await expect(page.locator('text=vol_20d').first()).toBeVisible()
    await expect(page.locator('text=5日收益率')).not.toBeVisible()
  })

  test('IC alert badge appears on factors with low IC', async ({ page }) => {
    await gotoPage(page, '/factors')

    await page.waitForSelector('text=ret_5d')

    // ret_20d has is_alert=true in mock data
    await expect(page.locator('[aria-label="ret_20d IC 告警"]')).toBeVisible()
  })

  test('IC alert modal opens and creates rule', async ({ page }) => {
    await gotoPage(page, '/factors')

    await page.waitForSelector('[aria-label="ret_20d IC 告警"]')
    await page.click('[aria-label="ret_20d IC 告警"]')

    // Modal content
    await expect(page.locator('text=创建 IC 告警规则')).toBeVisible()
    await expect(page.locator('text=IC 阈值（绝对值低于此值触发）')).toBeVisible()

    // Submit
    await page.click('text=创建告警')
    await expect(page.locator('text=创建 IC 告警规则')).not.toBeVisible()
  })

  test('select factor and see IC analysis section', async ({ page }) => {
    await gotoPage(page, '/factors')

    await page.waitForSelector('text=ret_5d')

    // The IC analysis section title uses "IC 分析：{factor}" format
    // First verify it's not visible before clicking
    await expect(page.locator('text=/IC 分析：ret_5d/')).not.toBeVisible()

    // Click on the ret_5d factor card - click on the description text which is inside the clickable div
    await page.locator('text=5日收益率').first().click()

    // IC analysis section appears with the factor name
    await expect(page.locator('text=/IC 分析：ret_5d/')).toBeVisible({ timeout: 10000 })
    await expect(page.getByRole('button', { name: '计算 IC/IR' })).toBeVisible()
  })

  test('custom factor creation flow', async ({ page }) => {
    await gotoPage(page, '/factors')

    await page.click('text=+ 新建因子')
    await expect(page.locator('text=新建自定义因子')).toBeVisible()

    // Fill form
    await page.fill('input[placeholder*="my_momentum"]', 'my_roc_5d')
    await page.fill('textarea[placeholder*="close - ma"]', "roc('close', 5)")

    // Preview
    await page.click('text=/预览计算结果/')
    await expect(page.locator('text=表达式有效')).toBeVisible({ timeout: 10000 })
  })

  test('IC matrix section with multi-factor selection', async ({ page }) => {
    await gotoPage(page, '/factors')

    await expect(page.locator('text=多因子 IC 矩阵')).toBeVisible()
    await expect(page.locator('text=全选')).toBeVisible()
    await expect(page.locator('text=计算 IC 矩阵')).toBeVisible()
  })
})
