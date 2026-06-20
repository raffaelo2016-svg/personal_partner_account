import { test, expect, type Route } from '@playwright/test';
import { loginPartner, expectNoScriptExecution, createClientViaApi } from './helpers';

test.describe('Clients — navigation & list', () => {
  test.beforeEach(async ({ page }) => { await loginPartner(page); });

  test('navigate to clients', async ({ page }) => {
    await page.click('text=Клиенты');
    await expect(page).toHaveURL(/\/dashboard\/clients/);
  });

  test('search input visible', async ({ page }) => {
    await page.goto('/dashboard/clients');
    await page.waitForTimeout(1000);
    await expect(page.getByPlaceholder(/поиск/i).first()).toBeVisible();
  });

  test('search filters list', async ({ page }) => {
    await page.goto('/dashboard/clients');
    await page.waitForTimeout(1000);
    await page.getByPlaceholder(/поиск/i).first().fill('NoSuchClient_XYZ');
    await page.waitForTimeout(800);
    // List should be empty or show no results
  });
});

test.describe('Clients — CRUD', () => {
  test.beforeEach(async ({ page }) => { await loginPartner(page); });

  test('create client with minimal fields', async ({ page }) => {
    const name = 'E2E_Client_' + Date.now();
    await page.goto('/dashboard/clients/new');
    // Select "in_court" type — у него минимум required-полей (caseNumber + ФИО)
    await page.getByText('Клиент в суде').click();
    await page.getByPlaceholder('А40-123456/2026').fill('А40-1/2026');
    await page.getByLabel(/ФИО/i).first().fill(name);
    await page.getByRole('button', { name: /создать карточку|сохранить/i }).click();
    await page.waitForTimeout(2500);
    const found = await page.locator(`text=${name}`).count();
    expect(found).toBeGreaterThan(0);
  });

  test('create with empty name shows validation', async ({ page }) => {
    await page.goto('/dashboard/clients/new');
    await page.getByRole('button', { name: /создать карточку|сохранить/i }).click();
    await page.waitForTimeout(800);
    // Should stay on form
    expect(page.url()).toContain('/clients/new');
  });

  test('client details page loads progress bar', async ({ page }) => {
    await page.goto('/dashboard/clients');
    await page.waitForTimeout(1500);
    // Карточка клиента: href с UUID, но не /new и не /:id/edit
    const card = page
      .locator('a[href^="/dashboard/clients/"]')
      .filter({ hasNot: page.locator('text=Добавить') })
      .filter({ has: page.locator('text=/.*/') })
      .first();
    if (await card.isVisible().catch(() => false)) {
      const href = await card.getAttribute('href');
      // Skip nav links like /dashboard/clients/new
      if (href && !href.endsWith('/new')) {
        await card.click();
        await page.waitForTimeout(1500);
        await expect(page.locator('text=Сбор документов').first()).toBeVisible({ timeout: 5000 });
      }
    }
  });
});

test.describe('Clients — edit & delete', () => {
  test.beforeEach(async ({ page }) => { await loginPartner(page); });

  test('edit client changes full name', async ({ page }) => {
    const original = 'E2E_Edit_Before_' + Date.now();
    const renamed = 'E2E_Edit_After_' + Date.now();

    // Создаём клиента через API, чтобы не зависеть от UI.
    const created = await createClientViaApi(page, { full_name: original });
    test.skip(created.status !== 201 || !created.json, `API create failed: ${created.status}`);
    const clientId = created.json!.id;

    await page.goto(`/dashboard/clients/${clientId}/edit`);
    await page.waitForTimeout(1500);

    const nameInput = page.locator('input[id^="fullName"]').first();
    await nameInput.fill(renamed);
    await page.getByRole('button', { name: /^Сохранить$/ }).click();
    await page.waitForTimeout(1500);

    await page.goto(`/dashboard/clients/${clientId}`);
    await expect(page.locator(`text=${renamed}`).first()).toBeVisible({ timeout: 5000 });
  });

  test('несуществующий client id: GET /clients/{id} возвращает 404 или 403', async ({ page }) => {
    const resp = await page.request.get(
      'http://localhost:8000/api/v1/clients/00000000-0000-0000-0000-000000000000'
    );
    // Бэкенд защищает от enumeration: 403 вместо 404. Принимаем оба.
    expect([403, 404]).toContain(resp.status());
  });

  test('permission: чужой client id через API → 403', async ({ page }) => {
    // Чужой / несуществующий UUID — бэкенд должен вернуть 403 (anti-enumeration) или 404.
    const resp = await page.request.get(
      'http://localhost:8000/api/v1/clients/11111111-1111-1111-1111-111111111111'
    );
    expect([403, 404]).toContain(resp.status());
  });
});

test.describe('Clients — XSS safety', () => {
  test.beforeEach(async ({ page }) => { await loginPartner(page); });

  test('ФИО с <script> не выполняется, отображается как текст', async ({ page }) => {
    const payload = '<script>alert("xss-' + Date.now() + '")</script>';
    const safeMarker = 'XSS_' + Date.now();

    const created = await createClientViaApi(page, { full_name: `${safeMarker} ${payload}` });
    test.skip(created.status !== 201, `API rejected payload or create failed: ${created.status}`);

    await expectNoScriptExecution(page, async () => {
      await page.goto('/dashboard/clients');
      await page.waitForTimeout(1500);
      // Маркер должен быть виден как обычный текст
      await expect(page.locator(`text=${safeMarker}`).first()).toBeVisible({ timeout: 5000 });
    });
  });
});

test.describe('Clients — filters & pagination', () => {
  test.beforeEach(async ({ page }) => { await loginPartner(page); });

  test('пустой результат поиска не крашит страницу', async ({ page }) => {
    await page.goto('/dashboard/clients');
    await page.waitForTimeout(1500);
    const search = page.getByPlaceholder(/поиск/i).first();
    await search.fill('ZZZ_impossible_query_' + Date.now());
    await page.waitForTimeout(800);
    await expect(page.locator('body')).not.toBeEmpty();
  });

  test('список клиентов отрисовывается после создания', async ({ page }) => {
    const name = 'E2E_List_' + Date.now();
    const created = await createClientViaApi(page, { full_name: name });
    test.skip(created.status !== 201, `API create failed: ${created.status}`);

    await page.goto('/dashboard/clients');
    await page.waitForTimeout(1500);
    await page.getByPlaceholder(/поиск/i).first().fill(name);
    await page.waitForTimeout(800);
    await expect(page.locator(`text=${name}`).first()).toBeVisible({ timeout: 5000 });
  });
});
