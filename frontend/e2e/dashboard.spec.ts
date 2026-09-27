import { test, expect } from '@playwright/test';
import { loginPartner, loginAdmin } from './helpers';

test.describe('Partner Dashboard', () => {
  test.beforeEach(async ({ page }) => { await loginPartner(page); });

  test('shows stats cards', async ({ page }) => {
    await expect(page.locator('text=Всего клиентов')).toBeVisible();
    await expect(page.locator('text=ДО подачи в суд')).toBeVisible();
  });

  test('shows partner sidebar', async ({ page }) => {
    await expect(page.locator('text=Дашборд').first()).toBeVisible();
    await expect(page.locator('text=Клиенты').first()).toBeVisible();
    await expect(page.locator('text=Чат').first()).toBeVisible();
    await expect(page.locator('text=Финансы').first()).toBeVisible();
  });

  test('cross-tab navigation works', async ({ page }) => {
    await page.click('text=Клиенты');
    await expect(page).toHaveURL(/\/dashboard\/clients/);
    await page.click('text=Дашборд');
    await expect(page).toHaveURL(/\/dashboard$/);
  });

  test('partner sidebar has no admin items', async ({ page }) => {
    await expect(page.locator('text=Партнеры')).not.toBeVisible();
    await expect(page.locator('text=Все клиенты')).not.toBeVisible();
  });
});

test.describe('Admin Dashboard', () => {
  test.beforeEach(async ({ page }) => { await loginAdmin(page); });

  test('shows analytics sections', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Управленческие показатели' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Клиентский поток' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Финансовые показатели' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Риски и внимание' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Рейтинг партнёров' })).toBeVisible();
  });

  test('shows admin sidebar', async ({ page }) => {
    await expect(page.locator('text=Партнеры').first()).toBeVisible();
    await expect(page.locator('text=Все клиенты').first()).toBeVisible();
    await expect(page.locator('text=Чат').first()).toBeVisible();
  });

  test('cross-tab navigation', async ({ page }) => {
    await page.click('text=Партнеры');
    await expect(page).toHaveURL(/\/admin\/partners/);
    await page.click('text=Дашборд');
    await expect(page).toHaveURL(/\/admin$/);
  });

  test('admin sidebar has no partner-only items', async ({ page }) => {
    await expect(page.locator('text=Финансы')).not.toBeVisible();
    await expect(page.locator('text=Обучение')).not.toBeVisible();
  });
});
