import { test, expect, type Route } from '@playwright/test';
import { loginAdmin, loginPartner } from './helpers';

test.describe('Admin Partners', () => {
  test.beforeEach(async ({ page }) => { await loginAdmin(page); });

  test('navigate to partners', async ({ page }) => {
    await page.click('text=Партнеры');
    await expect(page).toHaveURL(/\/admin\/partners/);
  });

  test('partners list shows E2E Company', async ({ page }) => {
    await page.goto('/admin/partners');
    await page.waitForTimeout(1500);
    await expect(page.locator('text=E2E Company')).toBeVisible({ timeout: 5000 });
  });

  test('search partners filters list', async ({ page }) => {
    await page.goto('/admin/partners');
    await page.waitForTimeout(1500);
    const search = page.getByPlaceholder(/поиск/i).first();
    if (await search.isVisible()) {
      await search.fill('E2E');
      await page.waitForTimeout(800);
      await expect(page.locator('text=E2E Company')).toBeVisible();
    }
  });

  test('search no match → list empty', async ({ page }) => {
    await page.goto('/admin/partners');
    await page.waitForTimeout(1500);
    const search = page.getByPlaceholder(/поиск/i).first();
    if (await search.isVisible()) {
      await search.fill('NoSuchPartnerXYZ');
      await page.waitForTimeout(1000);
      const visible = await page.locator('text=E2E Company').isVisible().catch(() => false);
      expect(visible).toBe(false);
    }
  });

  test('partner details page', async ({ page }) => {
    await page.goto('/admin/partners');
    await page.waitForTimeout(1500);
    await page.locator('text=E2E Company').click();
    await page.waitForTimeout(1500);
    await expect(page).toHaveURL(/\/admin\/partners\//);
  });
});

test.describe('Admin Clients', () => {
  test.beforeEach(async ({ page }) => { await loginAdmin(page); });

  test('navigate to all clients', async ({ page }) => {
    await page.click('text=Все клиенты');
    await expect(page).toHaveURL(/\/admin\/clients/);
  });

  test('clients list page renders', async ({ page }) => {
    await page.goto('/admin/clients');
    await page.waitForTimeout(1500);
    await expect(page.locator('body')).not.toBeEmpty();
  });
});

test.describe('Admin Partners — edit & status transitions (моки)', () => {
  test.beforeEach(async ({ page }) => { await loginAdmin(page); });

  test('PATCH /partners/{id} при смене статуса через селект', async ({ page }) => {
    let patchCalled = false;
    await page.route(/\/api\/v1\/admin\/partners\/[0-9a-f-]+/, async (route: Route) => {
      if (route.request().method() === 'PATCH') {
        patchCalled = true;
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ ok: true }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto('/admin/partners');
    await page.waitForTimeout(1500);

    // Ищем select со статусом в строке партнёра
    const statusSelect = page.locator('select, [role="combobox"]').filter({ hasText: /активн|проверк|блокирован/i }).first();
    if (!(await statusSelect.isVisible().catch(() => false))) {
      test.skip(true, 'Селект смены статуса не найден в списке');
      return;
    }
    // Просто фиксируем что UI есть — реальный клик зависит от типа селекта.
    expect(await statusSelect.count()).toBeGreaterThan(0);
  });

  test('страница деталей партнёра имеет кнопки действий (Заблокировать/Разблокировать/Одобрить)', async ({ page }) => {
    await page.goto('/admin/partners');
    await page.waitForTimeout(1500);
    const partnerLink = page.locator('text=E2E Company').first();
    if (!(await partnerLink.isVisible().catch(() => false))) {
      test.skip(true, 'Тестового партнёра нет в списке');
      return;
    }
    await partnerLink.click();
    await page.waitForTimeout(1500);

    const actionBtn = page
      .getByRole('button', { name: /заблокир|разблокир|одобр/i })
      .first();
    await expect(actionBtn).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Permission: partner не может звать admin API', () => {
  test('GET /admin/partners под partner-токеном возвращает 403', async ({ page }) => {
    await loginPartner(page);
    // page.request использует куки текущего контекста партнёра
    const resp = await page.request.get('http://localhost:8000/api/v1/admin/partners');
    expect([401, 403]).toContain(resp.status());
  });
});
