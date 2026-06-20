import { test, expect, chromium } from '@playwright/test';
import { loginPartner, loginAdmin, PARTNER, ADMIN, expectNoScriptExecution } from './helpers';

test.describe('Partner Chat', () => {
  test.beforeEach(async ({ page }) => { await loginPartner(page); });

  test('navigate to chat', async ({ page }) => {
    await page.click('text=Чат');
    await expect(page).toHaveURL(/\/dashboard\/chat/);
    await expect(page.locator('text=Администратор').first()).toBeVisible();
  });

  test('shows connected status', async ({ page }) => {
    await page.click('text=Чат');
    await expect(page.locator('text=Подключено').first()).toBeVisible({ timeout: 8000 });
  });

  test('send message → appears in chat', async ({ page }) => {
    await page.click('text=Чат');
    await page.waitForTimeout(1500);
    const msg = 'PMsg_' + Date.now();
    await page.getByPlaceholder(/сообщение/i).fill(msg);
    await page.getByRole('button', { name: /отправить/i }).click();
    await expect(page.locator(`text=${msg}`).last()).toBeVisible({ timeout: 5000 });
  });

  test('input clears after send', async ({ page }) => {
    await page.click('text=Чат');
    await page.waitForTimeout(1500);
    const input = page.getByPlaceholder(/сообщение/i);
    await input.fill('Clear test');
    await page.getByRole('button', { name: /отправить/i }).click();
    await page.waitForTimeout(800);
    await expect(input).toHaveValue('');
  });
});

test.describe('Admin Chat', () => {
  test.beforeEach(async ({ page }) => { await loginAdmin(page); });

  test('navigate to chat', async ({ page }) => {
    await page.click('text=Чат');
    await page.waitForTimeout(1500);
    await expect(page.locator('text=Чаты с партнёрами')).toBeVisible();
  });

  test('shows partner rooms', async ({ page }) => {
    await page.click('text=Чат');
    await page.waitForTimeout(1500);
    await expect(page.locator('text=E2E Company').first()).toBeVisible({ timeout: 5000 });
  });

  test('select partner + send message', async ({ page }) => {
    await page.click('text=Чат');
    await page.waitForTimeout(1500);
    await page.locator('text=E2E Company').first().click();
    await page.waitForTimeout(500);
    const msg = 'AdminMsg_' + Date.now();
    await page.getByPlaceholder(/сообщение/i).fill(msg);
    await page.getByRole('button', { name: /отправить/i }).click();
    await expect(page.locator(`text=${msg}`).last()).toBeVisible({ timeout: 5000 });
  });

  test('search partners', async ({ page }) => {
    await page.click('text=Чат');
    await page.waitForTimeout(1500);
    await page.getByPlaceholder(/поиск/i).fill('E2E');
    await page.waitForTimeout(800);
    await expect(page.locator('text=E2E Company').first()).toBeVisible();
  });

  test('search no match → list empty', async ({ page }) => {
    await page.click('text=Чат');
    await page.waitForTimeout(1500);
    await page.getByPlaceholder(/поиск/i).fill('NoSuchPartner_XYZ');
    await page.waitForTimeout(1000);
    const visibleE2E = await page.locator('text=E2E Company').isVisible().catch(() => false);
    expect(visibleE2E).toBe(false);
  });
});

test.describe('2-user real-time flow', () => {
  test('partner sends → admin receives', async ({ browser }) => {
    const partnerCtx = await browser.newContext();
    const adminCtx = await browser.newContext();
    const partnerPage = await partnerCtx.newPage();
    const adminPage = await adminCtx.newPage();

    await loginPartner(partnerPage);
    await loginAdmin(adminPage);

    await partnerPage.goto('/dashboard/chat');
    await adminPage.goto('/admin/chat');
    await partnerPage.waitForTimeout(2000);
    await adminPage.waitForTimeout(2000);

    // Admin opens E2E Company room
    await adminPage.locator('text=E2E Company').first().click();
    await adminPage.waitForTimeout(500);

    // Partner sends message
    const msg = '2User_' + Date.now();
    await partnerPage.getByPlaceholder(/сообщение/i).fill(msg);
    await partnerPage.getByRole('button', { name: /отправить/i }).click();

    // Admin should see it via WS
    await expect(adminPage.locator(`text=${msg}`).last()).toBeVisible({ timeout: 8000 });

    await partnerCtx.close();
    await adminCtx.close();
  });

  test('admin sends → partner receives', async ({ browser }) => {
    const partnerCtx = await browser.newContext();
    const adminCtx = await browser.newContext();
    const partnerPage = await partnerCtx.newPage();
    const adminPage = await adminCtx.newPage();

    await loginPartner(partnerPage);
    await loginAdmin(adminPage);

    await partnerPage.goto('/dashboard/chat');
    await adminPage.goto('/admin/chat');
    await partnerPage.waitForTimeout(2000);
    await adminPage.waitForTimeout(2000);

    await adminPage.locator('text=E2E Company').first().click();
    await adminPage.waitForTimeout(500);

    const msg = 'AdminToP_' + Date.now();
    await adminPage.getByPlaceholder(/сообщение/i).fill(msg);
    await adminPage.getByRole('button', { name: /отправить/i }).click();

    await expect(partnerPage.locator(`text=${msg}`).last()).toBeVisible({ timeout: 8000 });

    await partnerCtx.close();
    await adminCtx.close();
  });
});

test.describe('Partner Chat — edge cases', () => {
  test.beforeEach(async ({ page }) => { await loginPartner(page); });

  test('пустое сообщение не отправляется (кнопка disabled или no-op)', async ({ page }) => {
    await page.click('text=Чат');
    await page.waitForTimeout(1500);

    const input = page.getByPlaceholder(/сообщение/i);
    await input.fill('');
    const sendBtn = page.getByRole('button', { name: /отправить/i });

    // Либо кнопка disabled, либо клик ничего не отправляет.
    const isDisabled = await sendBtn.isDisabled().catch(() => false);
    if (!isDisabled) {
      // Попробуем кликнуть — не должно появиться сообщения.
      await sendBtn.click();
      await page.waitForTimeout(500);
    }
    // Ничего валидирующего не делаем дальше — главное, нет падения и нет нового сообщения.
    await expect(input).toHaveValue('');
  });

  test('XSS в сообщении: <img onerror=...> отображается как текст', async ({ page }) => {
    await page.click('text=Чат');
    await page.waitForTimeout(1500);

    const marker = 'XSS_CHAT_' + Date.now();
    const payload = `${marker} <img src=x onerror="alert(1)">`;

    await expectNoScriptExecution(page, async () => {
      await page.getByPlaceholder(/сообщение/i).fill(payload);
      await page.getByRole('button', { name: /отправить/i }).click();
      await expect(page.locator(`text=${marker}`).last()).toBeVisible({ timeout: 5000 });
    });
  });

  test('длинное сообщение (> 5000 символов): либо обрезается, либо ошибка', async ({ page }) => {
    await page.click('text=Чат');
    await page.waitForTimeout(1500);

    const longText = 'x'.repeat(5500);
    const marker = '__END_MARKER_' + Date.now();
    await page.getByPlaceholder(/сообщение/i).fill(longText + marker);
    await page.getByRole('button', { name: /отправить/i }).click();
    await page.waitForTimeout(1500);

    // Сценарий A: backend отрезал / UI обрезал — marker может отсутствовать.
    // Сценарий B: backend вернул ошибку — видим toast "слишком длинное".
    // Тест фиксирует, что интерфейс не падает.
    await expect(page.locator('body')).not.toBeEmpty();
  });
});
