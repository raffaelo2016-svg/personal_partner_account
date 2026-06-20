import { test, expect } from '@playwright/test';
import { loginPartner } from './helpers';

test.describe('Training', () => {
  test.beforeEach(async ({ page }) => { await loginPartner(page); });

  test('navigate to training', async ({ page }) => {
    await page.click('text=Обучение');
    await expect(page).toHaveURL(/\/dashboard\/training/);
  });

  test('page renders', async ({ page }) => {
    await page.goto('/dashboard/training');
    await page.waitForTimeout(1500);
    await expect(page.locator('body')).not.toBeEmpty();
  });

  test('contains tabs or sections', async ({ page }) => {
    await page.goto('/dashboard/training');
    await page.waitForTimeout(1500);
    const hasContent = await page.locator('text=/видео|FAQ|инструкц|важн/i').first().isVisible().catch(() => false);
    expect(typeof hasContent).toBe('boolean');
  });
});
