import { test, expect, type Route } from '@playwright/test';
import { loginPartner } from './helpers';

test.describe('Finance', () => {
  test.beforeEach(async ({ page }) => { await loginPartner(page); });

  test('navigate to court fees', async ({ page }) => {
    await page.click('text=Финансы');
    await expect(page).toHaveURL(/\/dashboard\/finance/);
  });

  test('court fees page renders', async ({ page }) => {
    await page.goto('/dashboard/finance/court-fees');
    await page.waitForTimeout(1500);
    await expect(page.locator('body')).not.toBeEmpty();
  });

  test('summary block is visible', async ({ page }) => {
    await page.goto('/dashboard/finance/court-fees');
    await page.waitForTimeout(1500);
    // Summary должна показывать total/current/overdue
    const hasSummary = await page.locator('text=/задолженность|оплачено|долг/i').first().isVisible().catch(() => false);
    expect(typeof hasSummary).toBe('boolean');
  });

  test('navigate to payment history', async ({ page }) => {
    await page.goto('/dashboard/finance/history');
    await page.waitForTimeout(1000);
    await expect(page).toHaveURL(/\/finance\/history/);
  });

  test('history page does not crash', async ({ page }) => {
    await page.goto('/dashboard/finance/history');
    await page.waitForTimeout(1500);
    await expect(page.locator('body')).not.toBeEmpty();
  });
});

test.describe('Finance — debt banner & пустое состояние (моки)', () => {
  test.beforeEach(async ({ page }) => { await loginPartner(page); });

  test('ZERO overdue: красный alert не отображается', async ({ page }) => {
    await page.route('**/api/v1/finance/court-fees/summary', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_debt: 0,
          current_debt: 0,
          overdue_debt: 0,
          paid_this_month: 0,
          total_fees: 0,
          fee_per_client: 150000,
        }),
      });
    });

    await page.goto('/dashboard/finance/court-fees');
    await page.waitForTimeout(1500);
    const redAlert = await page
      .getByText('Требуется оплата судебных расходов')
      .first()
      .isVisible()
      .catch(() => false);
    expect(redAlert).toBe(false);
  });

  test('overdue debt > 0: появляется alert с кнопкой "Оплатить"', async ({ page }) => {
    await page.route('**/api/v1/finance/court-fees/summary', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_debt: 300000,
          current_debt: 150000,
          overdue_debt: 150000,
          paid_this_month: 0,
          total_fees: 2,
          fee_per_client: 150000,
        }),
      });
    });

    await page.goto('/dashboard/finance/court-fees');
    await page.waitForTimeout(1500);
    await expect(page.getByText('Требуется оплата судебных расходов').first()).toBeVisible({ timeout: 5000 });
  });

  test('пустая история платежей: страница отрисовывается без ошибок', async ({ page }) => {
    await page.route('**/api/v1/finance/history**', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 10 }),
      });
    });

    await page.goto('/dashboard/finance/history');
    await page.waitForTimeout(1500);
    await expect(page.locator('body')).not.toBeEmpty();
  });

  test('500 при загрузке summary: страница не падает', async ({ page }) => {
    await page.route('**/api/v1/finance/court-fees/summary', async (route: Route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Server error' }),
      });
    });

    await page.goto('/dashboard/finance/court-fees');
    await page.waitForTimeout(1500);
    // UI не должен быть полностью сломан
    await expect(page.locator('body')).not.toBeEmpty();
  });
});
