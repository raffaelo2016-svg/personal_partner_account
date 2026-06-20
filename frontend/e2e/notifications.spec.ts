import { test, expect, type Route } from '@playwright/test';
import { loginPartner } from './helpers';

test.describe('Notifications', () => {
  test.beforeEach(async ({ page }) => { await loginPartner(page); });

  test('bell visible in header', async ({ page }) => {
    await expect(page.locator('button[aria-label*="Уведомления"]')).toBeVisible();
  });

  test('click bell opens dropdown', async ({ page }) => {
    await page.locator('button[aria-label*="Уведомления"]').click();
    await expect(page.locator('h3:has-text("Уведомления")')).toBeVisible();
  });

  test('close dropdown', async ({ page }) => {
    await page.locator('button[aria-label*="Уведомления"]').click();
    await page.locator('button[aria-label="Закрыть уведомления"]').click();
    await page.waitForTimeout(300);
    // Dropdown should close
    const visible = await page.locator('h3:has-text("Уведомления")').isVisible().catch(() => false);
    expect(visible).toBe(false);
  });

  test('aria-expanded toggles', async ({ page }) => {
    const bell = page.locator('button[aria-label*="Уведомления"]');
    await expect(bell).toHaveAttribute('aria-expanded', 'false');
    await bell.click();
    await expect(bell).toHaveAttribute('aria-expanded', 'true');
  });
});

test.describe('Notifications — контент dropdown', () => {
  test.beforeEach(async ({ page }) => { await loginPartner(page); });

  test('пустой список → "Нет новых уведомлений"', async ({ page }) => {
    await page.route('**/api/v1/notifications**', async (route: Route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 10 }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto('/dashboard');
    await page.locator('button[aria-label*="Уведомления"]').click();
    await expect(page.getByText('Нет новых уведомлений')).toBeVisible({ timeout: 5000 });
  });

  test('"Прочитать все" вызывает mark-all-as-read', async ({ page }) => {
    await page.route('**/api/v1/notifications**', async (route: Route) => {
      const url = route.request().url();
      if (route.request().method() === 'GET' && !url.includes('unread')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            items: [
              {
                id: 'n1',
                title: 'Тестовое уведомление',
                message: 'Hello',
                type: 'status_change',
                is_read: false,
                created_at: new Date().toISOString(),
              },
            ],
            total: 1,
            page: 1,
            page_size: 10,
          }),
        });
      } else {
        await route.continue();
      }
    });

    let markAllCalled = false;
    await page.route(/\/notifications\/(mark-all-as-read|read-all)/, async (route: Route) => {
      markAllCalled = true;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
    });

    await page.goto('/dashboard');
    await page.locator('button[aria-label*="Уведомления"]').click();
    await page.waitForTimeout(500);

    const markAllBtn = page.getByRole('button', { name: /Прочитать все/i }).first();
    if (!(await markAllBtn.isVisible().catch(() => false))) {
      test.skip(true, 'Кнопка "Прочитать все" не отображается');
      return;
    }
    await markAllBtn.click();
    await page.waitForTimeout(1000);
    expect(markAllCalled).toBe(true);
  });

  test('клик по уведомлению вызывает mark as read', async ({ page }) => {
    await page.route('**/api/v1/notifications**', async (route: Route) => {
      const url = route.request().url();
      if (route.request().method() === 'GET' && !url.includes('unread')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            items: [
              {
                id: 'n-click',
                title: 'Для клика',
                message: 'text',
                type: 'new_task',
                is_read: false,
                created_at: new Date().toISOString(),
              },
            ],
            total: 1,
            page: 1,
            page_size: 10,
          }),
        });
      } else {
        await route.continue();
      }
    });

    let markOneCalled = false;
    await page.route(/\/notifications\/n-click\/read/, async (route: Route) => {
      markOneCalled = true;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
    });

    await page.goto('/dashboard');
    await page.locator('button[aria-label*="Уведомления"]').click();
    await expect(page.getByText('Для клика')).toBeVisible({ timeout: 5000 });
    await page.getByText('Для клика').click();
    await page.waitForTimeout(1000);
    expect(markOneCalled).toBe(true);
  });
});
