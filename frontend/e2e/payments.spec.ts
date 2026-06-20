import { test, expect, type Route, type Page } from '@playwright/test';
import { loginPartner } from './helpers';

/**
 * Оплата через ЮKassa / ЮMoney.
 *
 * Тесты мокают POST /finance/payments, чтобы не плодить реальные платежи в sandbox
 * и не зависеть от сети до api.yookassa.ru. Проверяем контракт фронта:
 * модалка открывается, 3 способа оплаты задизейблены, ЮMoney отправляет запрос
 * и делает редирект на confirmation_url.
 *
 * Триггер открытия модалки — кнопка "Оплатить" в строке таблицы unpaid fee.
 * У тестового партнёра должен быть хотя бы один неоплаченный клиент.
 */

const FAKE_PAYMENT_URL = 'https://yoomoney.ru/checkout/payments/v2/contract?orderId=e2e-test';

async function mockPaymentsOk(page: Page, amountCents: number) {
  await page.route('**/api/v1/finance/payments', async (route: Route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        payment_id: 'e2e-test-payment',
        confirmation_url: FAKE_PAYMENT_URL,
        amount_cents: amountCents,
      }),
    });
  });
  await page.route(FAKE_PAYMENT_URL, async (route) => {
    await route.fulfill({ status: 200, contentType: 'text/html', body: '<html><body>yoomoney-stub</body></html>' });
  });
}

async function openPaymentModal(page: Page): Promise<boolean> {
  await page.goto('/dashboard/finance/court-fees');
  await page.waitForTimeout(1500);
  const rowPay = page.locator('tbody button', { hasText: /^Оплатить$/ }).first();
  if (!(await rowPay.isVisible().catch(() => false))) return false;
  await rowPay.click();
  await expect(page.getByText('Выберите способ оплаты')).toBeVisible();
  return true;
}

test.describe('PaymentModal — контракт UI', () => {
  test.beforeEach(async ({ page }) => { await loginPartner(page); });

  test('модалка открывается и показывает заголовки', async ({ page }) => {
    const opened = await openPaymentModal(page);
    if (!opened) {
      test.skip(true, 'Нет неоплаченных fee у тестового партнёра');
      return;
    }
    await expect(page.getByText('Оплата судебных расходов', { exact: true })).toBeVisible();
    await expect(page.getByText('Сумма к оплате:')).toBeVisible();
  });

  test('3 кнопки задизейблены, ЮMoney активна', async ({ page }) => {
    const opened = await openPaymentModal(page);
    if (!opened) {
      test.skip(true, 'Нет неоплаченных fee');
      return;
    }
    for (const label of ['Банковская карта', 'СБП', 'Банковский перевод']) {
      const btn = page.getByRole('button', { name: new RegExp(label, 'i') });
      await expect(btn).toBeDisabled();
    }
    await expect(page.getByRole('button', { name: /ЮMoney/i })).toBeEnabled();
  });

  test('клик ЮMoney → POST /finance/payments → редирект на confirmation_url', async ({ page }) => {
    const opened = await openPaymentModal(page);
    if (!opened) {
      test.skip(true, 'Нет fee для оплаты');
      return;
    }
    await mockPaymentsOk(page, 150000);

    const [request, response] = await Promise.all([
      page.waitForRequest((r) => r.url().includes('/api/v1/finance/payments') && r.method() === 'POST'),
      page.waitForResponse((r) => r.url().includes('/api/v1/finance/payments')),
      page.getByRole('button', { name: /ЮMoney/i }).click(),
    ]);

    const payload = request.postDataJSON();
    expect(payload).toHaveProperty('fee_ids');
    expect(Array.isArray(payload.fee_ids)).toBe(true);
    expect(payload.fee_ids).toHaveLength(1);
    expect(response.status()).toBe(201);

    await page.waitForURL(FAKE_PAYMENT_URL, { timeout: 5000 });
    expect(page.url()).toBe(FAKE_PAYMENT_URL);
  });

  test('ошибка backend показывает toast и не редиректит', async ({ page }) => {
    const opened = await openPaymentModal(page);
    if (!opened) {
      test.skip(true, 'Нет fee для оплаты');
      return;
    }

    await page.route('**/api/v1/finance/payments', async (route: Route) => {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Нет неоплаченных судебных расходов', code: 'NO_UNPAID_FEES' }),
      });
    });

    await page.getByRole('button', { name: /ЮMoney/i }).click();
    await expect(page.getByText(/нет неоплаченных|не удалось создать платёж/i)).toBeVisible({ timeout: 3000 });
    expect(page.url()).toContain('/dashboard/finance/court-fees');
  });

  test('500 от backend: кнопка разблокируется, модалка остаётся открытой', async ({ page }) => {
    const opened = await openPaymentModal(page);
    if (!opened) {
      test.skip(true, 'Нет fee для оплаты');
      return;
    }

    await page.route('**/api/v1/finance/payments', async (route: Route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' }),
      });
    });

    await page.getByRole('button', { name: /ЮMoney/i }).click();
    // После ошибки кнопка ЮMoney снова должна быть enabled
    await expect(page.getByRole('button', { name: /ЮMoney/i })).toBeEnabled({ timeout: 5000 });
    // Модалка не должна закрыться
    await expect(page.getByText('Выберите способ оплаты')).toBeVisible();
    // Редиректа не произошло
    expect(page.url()).toContain('/dashboard/finance/court-fees');
  });

  test('сетевой сбой (abort): мягкая обработка, модалка открыта', async ({ page }) => {
    const opened = await openPaymentModal(page);
    if (!opened) {
      test.skip(true, 'Нет fee для оплаты');
      return;
    }

    await page.route('**/api/v1/finance/payments', async (route: Route) => {
      await route.abort('failed');
    });

    await page.getByRole('button', { name: /ЮMoney/i }).click();
    await page.waitForTimeout(1500);
    await expect(page.getByText('Выберите способ оплаты')).toBeVisible();
  });

  test('кнопка ЮMoney показывает спиннер и блокируется во время запроса', async ({ page }) => {
    const opened = await openPaymentModal(page);
    if (!opened) {
      test.skip(true, 'Нет fee для оплаты');
      return;
    }

    // Задержим ответ бэка, чтобы увидеть состояние "создание платежа".
    await page.route('**/api/v1/finance/payments', async (route: Route) => {
      await new Promise((r) => setTimeout(r, 800));
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          payment_id: 'e2e-slow',
          confirmation_url: FAKE_PAYMENT_URL,
          amount_cents: 100000,
        }),
      });
    });
    await page.route(FAKE_PAYMENT_URL, (r) => r.fulfill({ status: 200, contentType: 'text/html', body: 'stub' }));

    const yoomoney = page.getByRole('button', { name: /ЮMoney/i });
    await yoomoney.click();

    // Пока запрос висит — видим надпись "Создание платежа…" и кнопка Отменить задизейблена.
    await expect(page.getByText(/Создание платежа/i)).toBeVisible({ timeout: 1500 });
    const cancelBtn = page.getByRole('button', { name: /^Отменить$/ });
    await expect(cancelBtn).toBeDisabled();

    await page.waitForURL(FAKE_PAYMENT_URL, { timeout: 5000 });
  });
});
