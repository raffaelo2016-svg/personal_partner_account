import { test, expect, type Route, type Page } from '@playwright/test';
import { uniquePartnerPayload, PARTNER } from './helpers';

/**
 * Регистрация партнёра (/register) — одноэкранная форма с переключателем
 * типа партнёра: Физическое лицо / Юридическое лицо / ИП.
 *
 * В разметке label и input не связаны через `for` (только визуально), поэтому
 * getByLabel не работает — используем XPath following-sibling::input.
 */

function inputByLabel(page: Page, label: string) {
  return page
    .locator(`//label[normalize-space(.)="${label}"]/following-sibling::input`)
    .first();
}

async function fillIndividual(page: Page, p: ReturnType<typeof uniquePartnerPayload>) {
  await page.locator('input[type="email"]').fill(p.email);
  await page.locator('input#register-phone').fill(p.phone);
  await inputByLabel(page, 'Фамилия').fill('Иванов');
  await inputByLabel(page, 'Имя').fill('Иван');
  await inputByLabel(page, 'Отчество').fill('Иванович');
  await page.locator('input[type="password"]').fill(p.password);
  const numbers = page.locator('input[type="number"]');
  await numbers.nth(0).fill('1500');
  await numbers.nth(1).fill('10');
}

async function selectPartnerType(page: Page, type: 'individual' | 'legal' | 'entrepreneur') {
  await page.locator(`input[type="radio"][value="${type}"]`).check();
}

test.describe('Registration — happy path', () => {
  test('отправка формы физлица → экран "Заявка отправлена"', async ({ page }) => {
    const p = uniquePartnerPayload();

    await page.route('**/api/v1/auth/register', async (route: Route) => {
      const payload = route.request().postDataJSON();
      expect(payload).toHaveProperty('email', p.email);
      expect(payload).toHaveProperty('password', p.password);
      expect(payload).toHaveProperty('partner_type', 'individual');
      expect(payload).toHaveProperty('court_fee_per_client', 150000);
      expect(payload).toHaveProperty('payment_term_days', 10);
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'fake-id', email: p.email, status: 'pending' }),
      });
    });

    await page.goto('/register');
    await fillIndividual(page, p);
    await page.getByRole('button', { name: /^Зарегистрироваться$/ }).click();
    await expect(page.getByText('Заявка отправлена!')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Registration — переключение типа партнёра', () => {
  test.beforeEach(async ({ page }) => { await page.goto('/register'); });

  test('переключение на "Юридическое лицо" показывает поля ИНН и КПП', async ({ page }) => {
    await selectPartnerType(page, 'legal');
    await expect(inputByLabel(page, 'Полное наименование')).toBeVisible();
    await expect(page.locator('input[placeholder="7736050003"]')).toBeVisible();
    await expect(page.locator('input[placeholder="770401001"]')).toBeVisible();
  });

  test('переключение на "ИП" показывает ФИО и ИНН на 12 цифр', async ({ page }) => {
    await selectPartnerType(page, 'entrepreneur');
    await expect(inputByLabel(page, 'Фамилия')).toBeVisible();
    await expect(page.locator('input[placeholder="500100732259"]')).toBeVisible();
    await expect(page.locator('input[placeholder="770401001"]')).toHaveCount(0);
  });

  test('возврат на "Физическое лицо" скрывает поля ИНН/КПП', async ({ page }) => {
    await selectPartnerType(page, 'legal');
    await expect(page.locator('input[placeholder="770401001"]')).toBeVisible();
    await selectPartnerType(page, 'individual');
    await expect(page.locator('input[placeholder="770401001"]')).toHaveCount(0);
    await expect(page.locator('input[placeholder="7736050003"]')).toHaveCount(0);
  });
});

test.describe('Registration — валидация', () => {
  test.beforeEach(async ({ page }) => { await page.goto('/register'); });

  test('пустая форма: submit → "Заполните обязательные поля"', async ({ page }) => {
    await page.getByRole('button', { name: /^Зарегистрироваться$/ }).click();
    await expect(
      page.getByText(/Заполните обязательные поля|обязательн/i).first()
    ).toBeVisible({ timeout: 3000 });
    await expect(page.getByText('Заявка отправлена!')).toHaveCount(0);
  });

  test('без courtFee: валидация не даёт отправить', async ({ page }) => {
    const p = uniquePartnerPayload();
    await page.locator('input[type="email"]').fill(p.email);
    await page.locator('input#register-phone').fill(p.phone);
    await inputByLabel(page, 'Фамилия').fill('И');
    await inputByLabel(page, 'Имя').fill('И');
    await page.locator('input[type="password"]').fill(p.password);
    // courtFee пустой, term заполнен
    await page.locator('input[type="number"]').nth(1).fill('10');

    await page.getByRole('button', { name: /^Зарегистрироваться$/ }).click();
    // Экран успеха не появился
    await expect(page.getByText('Заявка отправлена!')).toHaveCount(0);
    // Либо inline-ошибка у суммы, либо баннер "Заполните поля"
    const hasError = await page
      .getByText(/Обязательное поле|обязательн|больше 0/i)
      .first()
      .isVisible()
      .catch(() => false);
    expect(hasError).toBe(true);
  });

  test('для legal пустой ИНН: форма не отправляется', async ({ page }) => {
    const p = uniquePartnerPayload();
    await selectPartnerType(page, 'legal');
    await page.locator('input[type="email"]').fill(p.email);
    await page.locator('input#register-phone').fill(p.phone);
    await inputByLabel(page, 'Полное наименование').fill('ООО Тест');
    await inputByLabel(page, 'Сокращенное наименование').fill('Тест');
    await page.locator('input[type="password"]').fill(p.password);
    await page.locator('input[type="number"]').nth(0).fill('1500');
    await page.locator('input[type="number"]').nth(1).fill('10');

    await page.getByRole('button', { name: /^Зарегистрироваться$/ }).click();
    // Экран успеха не появился (форма не прошла валидацию ИНН/КПП)
    await expect(page.getByText('Заявка отправлена!')).toHaveCount(0);
  });
});

test.describe('Registration — серверные ошибки', () => {
  test('DUPLICATE_EMAIL → сообщение об ошибке в баннере', async ({ page }) => {
    const p = uniquePartnerPayload();
    await page.route('**/api/v1/auth/register', async (route: Route) => {
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({ detail: { code: 'DUPLICATE_EMAIL', msg: 'Email already registered' } }),
      });
    });

    await page.goto('/register');
    await fillIndividual(page, { ...p, email: PARTNER.email });
    await page.getByRole('button', { name: /^Зарегистрироваться$/ }).click();

    await expect(page.getByText(/уже зарегистрирован/i).first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Заявка отправлена!')).toHaveCount(0);
  });

  test('500 → общий текст "Ошибка при регистрации"', async ({ page }) => {
    const p = uniquePartnerPayload();
    await page.route('**/api/v1/auth/register', async (route: Route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' }),
      });
    });

    await page.goto('/register');
    await fillIndividual(page, p);
    await page.getByRole('button', { name: /^Зарегистрироваться$/ }).click();

    await expect(page.getByText(/Ошибка при регистрации/i).first()).toBeVisible({ timeout: 5000 });
  });

  test('429 rate limit → общий текст ошибки', async ({ page }) => {
    const p = uniquePartnerPayload();
    await page.route('**/api/v1/auth/register', async (route: Route) => {
      await route.fulfill({
        status: 429,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Rate limit exceeded' }),
      });
    });

    await page.goto('/register');
    await fillIndividual(page, p);
    await page.getByRole('button', { name: /^Зарегистрироваться$/ }).click();

    await expect(page.getByText(/Ошибка при регистрации/i).first()).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Registration — навигация', () => {
  test('ссылка "Отменить" ведёт на /login', async ({ page }) => {
    await page.goto('/register');
    await page.getByRole('link', { name: /^Отменить$/ }).click();
    await expect(page).toHaveURL(/\/login/);
  });
});
