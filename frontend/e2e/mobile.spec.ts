import { test, expect } from '@playwright/test';
import { loginPartner } from './helpers';

test.use({ viewport: { width: 375, height: 667 } }); // iPhone SE

test.describe('Mobile responsive', () => {
  test('partner login on mobile', async ({ page }) => {
    await loginPartner(page);
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('mobile menu button visible', async ({ page }) => {
    await loginPartner(page);
    const menuBtn = page.locator('button[aria-label="Открыть меню"]');
    await expect(menuBtn).toBeVisible();
  });

  test('open mobile menu shows nav items', async ({ page }) => {
    await loginPartner(page);
    await page.locator('button[aria-label="Открыть меню"]').click();
    await page.waitForTimeout(500);
    await expect(page.locator('text=Клиенты').first()).toBeVisible();
  });

  test('close mobile menu', async ({ page }) => {
    await loginPartner(page);
    await page.locator('button[aria-label="Открыть меню"]').click();
    await page.waitForTimeout(300);
    await page.locator('button[aria-label="Закрыть меню"]').click();
    await page.waitForTimeout(300);
  });

  test('navigate from mobile menu', async ({ page }) => {
    await loginPartner(page);
    await page.locator('button[aria-label="Открыть меню"]').click();
    await page.waitForTimeout(300);
    await page.locator('text=Клиенты').first().click();
    await expect(page).toHaveURL(/\/dashboard\/clients/);
  });
});
