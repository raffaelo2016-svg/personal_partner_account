import { type Page, expect } from '@playwright/test';

export const PARTNER = { email: 'e2e_partner@test.com', password: 'E2eTest123' };
export const ADMIN = { email: 'e2e_admin@test.com', password: 'E2eAdmin123' };

export const API_BASE = 'http://localhost:8000/api/v1';

export async function login(page: Page, user: { email: string; password: string }) {
  await page.goto('/login');
  await page.getByPlaceholder('partner@example.com').fill(user.email);
  await page.getByPlaceholder('Введите пароль').fill(user.password);
  await page.getByRole('button', { name: /войти/i }).click();
  await page.waitForURL(/\/(dashboard|admin)/, { timeout: 10_000 });
}

export async function loginPartner(page: Page) {
  await login(page, PARTNER);
}

export async function loginAdmin(page: Page) {
  await login(page, ADMIN);
}

/**
 * Ждёт появления Sonner-toast с указанным текстом (регуляркой или строкой).
 */
export async function waitForToast(page: Page, text: string | RegExp, timeout = 5000) {
  const matcher = typeof text === 'string' ? new RegExp(text, 'i') : text;
  await expect(page.locator('[data-sonner-toast], [role="status"]').filter({ hasText: matcher }).first()).toBeVisible({
    timeout,
  });
}

/**
 * Создаёт уникальные реквизиты для регистрации партнёра.
 * Используется, чтобы параллельные тесты не конфликтовали по email.
 */
export function uniquePartnerPayload(prefix = 'e2e_reg') {
  const stamp = Date.now() + '_' + Math.floor(Math.random() * 10_000);
  return {
    email: `${prefix}_${stamp}@test.com`,
    password: 'TestPass123',
    companyName: `E2E Co ${stamp}`,
    contactName: 'Иванов Иван Иванович',
    phone: '+79991234567',
    inn: '7701234567',
    ogrn: '1027700123456',
    legalAddress: 'г. Москва, ул. Тестовая, д. 1',
  };
}

/**
 * Ловит любые dialog/alert события на странице и фейлит тест, если срабатывают
 * в контексте выполнения fn. Используется для проверки XSS-экранирования.
 */
export async function expectNoScriptExecution(page: Page, fn: () => Promise<void>) {
  let triggered = false;
  const handler = (dialog: { message: () => string; dismiss: () => Promise<void> }) => {
    triggered = true;
    void dialog.dismiss();
  };
  page.on('dialog', handler);
  try {
    await fn();
  } finally {
    page.off('dialog', handler);
  }
  expect(triggered, 'script/alert should not execute when rendering user input').toBe(false);
}

/**
 * Создаёт клиента через REST API напрямую — быстрее, чем наживать его через UI.
 * Требует, чтобы в куках уже был валидный access_token (выполни login* перед вызовом).
 */
export async function createClientViaApi(
  page: Page,
  data: {
    type?: 'before_court' | 'in_court';
    full_name: string;
    case_number?: string;
    phone?: string;
    email?: string;
  }
) {
  const body = {
    type: data.type ?? 'in_court',
    full_name: data.full_name,
    case_number: data.case_number ?? `A40-${Date.now()}/2026`,
    phone: data.phone ?? '+79990000000',
    email: data.email ?? `e2e_client_${Date.now()}@test.com`,
  };
  const resp = await page.request.post(`${API_BASE}/clients`, { data: body });
  return { status: resp.status(), json: resp.ok() ? await resp.json() : null };
}

/**
 * Создаёт задачу через REST API напрямую.
 */
export async function createTaskViaApi(
  page: Page,
  clientId: string,
  data: {
    title: string;
    description?: string;
    priority?: 'low' | 'medium' | 'high';
    assigned_to?: string;
    due_date: string;
  }
) {
  const resp = await page.request.post(`${API_BASE}/tasks`, {
    data: {
      client_id: clientId,
      title: data.title,
      description: data.description ?? '',
      priority: data.priority ?? 'medium',
      assigned_to: data.assigned_to ?? 'partner',
      due_date: data.due_date,
    },
  });
  return { status: resp.status(), json: resp.ok() ? await resp.json() : null };
}

/**
 * Генерирует Buffer указанного размера в байтах (нуль-заполненный).
 * Для проверки ограничения размера upload.
 */
export function makeBuffer(sizeBytes: number): Buffer {
  return Buffer.alloc(sizeBytes, 0);
}

/**
 * Короткое ISO-дата (YYYY-MM-DD).
 */
export function isoDate(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}
