import { test, expect } from '@playwright/test'
import { mockAllApis, gotoPage } from './fixtures'

test.describe('Navigation & Layout', () => {
  test.beforeEach(async ({ page }) => {
    await mockAllApis(page)
  })

  test('sidebar renders all nav groups and links', async ({ page }) => {
    await gotoPage(page, '/')

    // Nav groups
    await expect(page.locator('text=研究工具')).toBeVisible()
    await expect(page.locator('text=数据 & 监控')).toBeVisible()
    await expect(page.locator('text=知识 & AI')).toBeVisible()
    await expect(page.locator('text=系统')).toBeVisible()

    // Key nav links
    for (const label of ['因子研究', '策略配置', '回测评估', '组合优化', '告警中心', '总览']) {
      await expect(page.locator(`nav >> text="${label}"`)).toBeVisible()
    }
  })

  test('clicking nav links navigates to correct pages', async ({ page }) => {
    await gotoPage(page, '/')

    await page.click('nav >> text="因子研究"')
    await expect(page).toHaveURL(/\/factors/)
    await expect(page.locator('h1')).toContainText('Alpha 因子研究')

    await page.click('nav >> text="策略配置"')
    await expect(page).toHaveURL(/\/strategies/)
    await expect(page.locator('h1')).toContainText('策略配置')

    await page.click('nav >> text="回测评估"')
    await expect(page).toHaveURL(/\/backtests/)
    await expect(page.locator('h1')).toContainText('回测评估')
  })

  test('sidebar collapse and expand', async ({ page }) => {
    await gotoPage(page, '/')

    // Sidebar is expanded by default
    await expect(page.locator('nav >> text="cQuant"')).toBeVisible()

    // Collapse
    await page.click('button[title="折叠侧边栏"]')
    await expect(page.locator('nav >> text="cQuant"')).not.toBeVisible()
    await expect(page.locator('button[title="展开侧边栏"]')).toBeVisible()

    // Expand
    await page.click('button[title="展开侧边栏"]')
    await expect(page.locator('nav >> text="cQuant"')).toBeVisible()
  })

  test('overview page loads with stats and quick links', async ({ page }) => {
    await gotoPage(page, '/')

    await expect(page.locator('h1')).toContainText('cQuant 量化研究平台')
    await expect(page.locator('text=离线研究仪表盘')).toBeVisible()

    // Quick links exist
    await expect(page.locator('text=因子研究').first()).toBeVisible()
    await expect(page.locator('text=策略配置').first()).toBeVisible()
  })

  test('404 page for unknown routes', async ({ page }) => {
    await gotoPage(page, '/nonexistent-page')
    await expect(page.locator('text=404')).toBeVisible()
  })
})
