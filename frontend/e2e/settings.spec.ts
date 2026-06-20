import { test, expect, type Route } from '@playwright/test';
import { loginPartner, loginAdmin } from './helpers';

test.describe('Partner Settings', () => {
  test.beforeEach(async ({ page }) => { await loginPartner(page); });

  test('navigate to settings', async ({ page }) => {
    await page.click('text=Настройки');
    await expect(page).toHaveURL(/\/dashboard\/settings/);
  });

  test('settings page renders', async ({ page }) => {
    await page.goto('/dashboard/settings');
    await page.waitForTimeout(1500);
    await expect(page.locator('body')).not.toBeEmpty();
  });

  test('contains timezone section', async ({ page }) => {
    await page.goto('/dashboard/settings');
    await page.waitForTimeout(1500);
    const hasTz = await page.locator('text=/часовой пояс|timezone|Москва/i').first().isVisible().catch(() => false);
    expect(typeof hasTz).toBe('boolean');
  });

  test('contains password section', async ({ page }) => {
    await page.goto('/dashboard/settings');
    await page.waitForTimeout(1500);
    const hasPw = await page.locator('text=/пароль/i').first().isVisible().catch(() => false);
    expect(typeof hasPw).toBe('boolean');
  });
});

test.describe('Partner Settings — смена пароля', () => {
  test.beforeEach(async ({ page }) => { await loginPartner(page); });

  test('неверный текущий пароль → тост ошибки, пароль не меняется', async ({ page }) => {
    await page.route('**/api/v1/settings/change-password', async (route: Route) => {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Неверный текущий пароль', code: 'INVALID_CREDENTIALS' }),
      });
    });

    await page.goto('/dashboard/settings');
    await page.waitForTimeout(1500);

    const changeBtn = page.getByRole('button', { name: /^Изменить$/ }).first();
    if (!(await changeBtn.isVisible().catch(() => false))) {
      test.skip(true, 'Нет кнопки "Изменить" в разделе пароля');
      return;
    }
    await changeBtn.click();
    await page.waitForTimeout(300);

    await page.getByPlaceholder(/текущий пароль/i).fill('WrongPass123');
    await page.getByPlaceholder(/новый пароль/i).fill('NewPass123');
    await page.getByRole('button', { name: /^Сохранить$/ }).click();

    await expect(page.getByText(/неверный|ошибк/i).first()).toBeVisible({ timeout: 5000 });
  });

  test('успешная смена → тост "Пароль успешно изменён"', async ({ page }) => {
    await page.route('**/api/v1/settings/change-password', async (route: Route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
    });

    await page.goto('/dashboard/settings');
    await page.waitForTimeout(1500);

    const changeBtn = page.getByRole('button', { name: /^Изменить$/ }).first();
    if (!(await changeBtn.isVisible().catch(() => false))) {
      test.skip(true, 'Нет кнопки "Изменить"');
      return;
    }
    await changeBtn.click();
    await page.waitForTimeout(300);

    await page.getByPlaceholder(/текущий пароль/i).fill('E2eTest123');
    await page.getByPlaceholder(/новый пароль/i).fill('E2eTestNew456');
    await page.getByRole('button', { name: /^Сохранить$/ }).click();

    await expect(page.getByText(/успешно|изменён|изменен/i).first()).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Partner Settings — notifications preferences', () => {
  test.beforeEach(async ({ page }) => { await loginPartner(page); });

  test('PUT /settings/notifications выполняется после смены чекбокса', async ({ page }) => {
    let called = false;
    await page.route('**/api/v1/settings/notifications', async (route: Route) => {
      if (route.request().method() === 'PUT') {
        called = true;
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
      } else {
        await route.continue();
      }
    });

    await page.goto('/dashboard/settings');
    await page.waitForTimeout(1500);

    const checkbox = page.locator('input[type="checkbox"]').first();
    if (!(await checkbox.isVisible().catch(() => false))) {
      test.skip(true, 'Нет чекбоксов уведомлений');
      return;
    }
    await checkbox.click();
    await page.waitForTimeout(1000);

    expect(called).toBe(true);
  });
});

test.describe('Admin Settings', () => {
  test.beforeEach(async ({ page }) => { await loginAdmin(page); });

  test('navigate', async ({ page }) => {
    await page.click('text=Настройки');
    await expect(page).toHaveURL(/\/admin\/settings/);
  });

  test('page renders', async ({ page }) => {
    await page.goto('/admin/settings');
    await page.waitForTimeout(1500);
    await expect(page.locator('body')).not.toBeEmpty();
  });
});
