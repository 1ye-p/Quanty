import { test, expect } from '@playwright/test'
import { mockAllApis, gotoPage } from './fixtures'

test.describe('Alerts Management Flow', () => {
  test.beforeEach(async ({ page }) => {
    await mockAllApis(page)
  })

  test('alerts page loads with rules and history', async ({ page }) => {
    await gotoPage(page, '/alerts')

    await expect(page.locator('h1')).toContainText('告警中心')
    await expect(page.locator('text=/1 条未读告警/')).toBeVisible()
    await expect(page.locator('text=数据过期')).toBeVisible()
  })

  test('create new alert rule', async ({ page }) => {
    await gotoPage(page, '/alerts')

    await page.click('text=+ 新增规则')
    await expect(page.locator('text=新增告警规则')).toBeVisible()
    await expect(page.locator('text=保存规则')).toBeVisible()

    // Submit
    await page.click('text=保存规则')
    await expect(page.locator('text=新增告警规则')).not.toBeVisible({ timeout: 10000 })
  })

  test('switch rule type to factor_ic_low', async ({ page }) => {
    await gotoPage(page, '/alerts')

    await page.click('text=+ 新增规则')

    const select = page.locator('select, [role="combobox"]').first()
    await select.selectOption('factor_ic_low')

    // Factor IC fields appear
    await expect(page.locator('input[placeholder="ret_20d"]')).toBeVisible()
    await expect(page.locator('input[placeholder="0.02"]')).toBeVisible()
    await expect(page.locator('input[placeholder="20"]')).toBeVisible()
  })

  test('alert history shows triggered alerts', async ({ page }) => {
    await gotoPage(page, '/alerts')

    await expect(page.locator('text=数据已过期 3 天')).toBeVisible()
  })

  test('mark all as read button exists and clickable', async ({ page }) => {
    await gotoPage(page, '/alerts')

    await page.waitForSelector('text=全部标为已读')
    const btn = page.locator('text=全部标为已读')
    await expect(btn).toBeVisible()
    await btn.click()

    // Button click triggers API call (verified by no crash)
    await page.waitForTimeout(500)
  })

  test('immediate check button', async ({ page }) => {
    await gotoPage(page, '/alerts')

    await page.click('text=立即检查')

    // Should show result
    await expect(page.locator('text=/触发.*告警|检查完成/')).toBeVisible({ timeout: 10000 })
  })

  test('delete rule confirmation dialog', async ({ page }) => {
    await gotoPage(page, '/alerts')

    await page.waitForSelector('text=删除')
    await page.click('text=删除')

    // Confirm dialog appears
    await expect(page.locator('text=确认删除规则')).toBeVisible()
    await expect(page.locator('text=确定删除此告警规则')).toBeVisible()

    // Cancel
    await page.click('text=取消')
    await expect(page.locator('text=确认删除规则')).not.toBeVisible()
  })

  test('cancel create form', async ({ page }) => {
    await gotoPage(page, '/alerts')

    await page.click('text=+ 新增规则')
    await expect(page.locator('text=新增告警规则')).toBeVisible()

    await page.click('text=取消')
    await expect(page.locator('text=新增告警规则')).not.toBeVisible()
  })
})
