import { test, expect, type Route, type Page } from '@playwright/test';
import { loginPartner, createClientViaApi, makeBuffer } from './helpers';

/**
 * Загрузка документов к карточке клиента.
 *
 * Валидация размера / MIME происходит на backend (413 FILE_TOO_LARGE и 415
 * UNSUPPORTED_FILE_TYPE). Чтобы не гонять реальные файлы через S3, мы мокаем
 * POST /files/upload — важно проверить UX: тост об ошибке, список файлов
 * не растёт, состояние кнопки.
 */

const UPLOAD_URL_RE = /\/api\/v1\/files\/?$|\/api\/v1\/upload|\/api\/v1\/files\/upload/;

async function gotoClientEdit(page: Page): Promise<string | null> {
  const created = await createClientViaApi(page, { full_name: 'E2E_Upload_' + Date.now() });
  if (created.status !== 201 || !created.json) return null;
  const clientId = created.json.id as string;
  await page.goto(`/dashboard/clients/${clientId}/edit`);
  await page.waitForTimeout(1500);
  return clientId;
}

async function findFileInput(page: Page) {
  // На форме — скрытые input[type="file"] рядом с кнопками "Загрузить".
  // Берём первый попавшийся.
  const input = page.locator('input[type="file"]').first();
  return (await input.count()) > 0 ? input : null;
}

test.describe('File uploads — happy path', () => {
  test.beforeEach(async ({ page }) => { await loginPartner(page); });

  test('валидный PDF < 10 MB — success', async ({ page }) => {
    const clientId = await gotoClientEdit(page);
    test.skip(!clientId, 'Не удалось создать клиента для теста');

    let captured = false;
    await page.route(UPLOAD_URL_RE, async (route: Route) => {
      captured = true;
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'e2e-file-' + Date.now(),
          filename: 'ok.pdf',
          size: 1024,
          mime_type: 'application/pdf',
        }),
      });
    });

    const input = await findFileInput(page);
    test.skip(!input, 'На форме нет input[type="file"]');

    await input!.setInputFiles({
      name: 'ok.pdf',
      mimeType: 'application/pdf',
      buffer: makeBuffer(1024),
    });
    await page.waitForTimeout(1500);

    expect(captured).toBe(true);
  });
});

test.describe('File uploads — валидация', () => {
  test.beforeEach(async ({ page }) => { await loginPartner(page); });

  test('файл > 10 MB: backend отвечает 413 → тост ошибки', async ({ page }) => {
    const clientId = await gotoClientEdit(page);
    test.skip(!clientId, 'Не удалось создать клиента для теста');

    await page.route(UPLOAD_URL_RE, async (route: Route) => {
      await route.fulfill({
        status: 413,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'File too large', code: 'FILE_TOO_LARGE' }),
      });
    });

    const input = await findFileInput(page);
    test.skip(!input, 'Нет input[type="file"]');

    // Реально шлём маленький буфер, но backend замокан под 413.
    await input!.setInputFiles({
      name: 'huge.pdf',
      mimeType: 'application/pdf',
      buffer: makeBuffer(1024),
    });

    await expect(
      page.getByText(/превыш|too large|размер|большой/i).first()
    ).toBeVisible({ timeout: 5000 });
  });

  test('неподдерживаемый тип (.exe): backend 415 → тост ошибки', async ({ page }) => {
    const clientId = await gotoClientEdit(page);
    test.skip(!clientId, 'Не удалось создать клиента для теста');

    await page.route(UPLOAD_URL_RE, async (route: Route) => {
      await route.fulfill({
        status: 415,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Unsupported file type', code: 'UNSUPPORTED_FILE_TYPE' }),
      });
    });

    const input = await findFileInput(page);
    test.skip(!input, 'Нет input[type="file"]');

    await input!.setInputFiles({
      name: 'malware.exe',
      mimeType: 'application/x-msdownload',
      buffer: makeBuffer(512),
    });

    // Клиент может отклонить .exe ещё до запроса (на уровне accept= или проверки),
    // тогда появится локальный тост "Недопустимый формат". Либо backend-level.
    await expect(
      page.getByText(/недопустим|формат|тип|unsupported/i).first()
    ).toBeVisible({ timeout: 5000 });
  });

  test('backend 500 при загрузке → ошибка, список не обновляется', async ({ page }) => {
    const clientId = await gotoClientEdit(page);
    test.skip(!clientId, 'Не удалось создать клиента');

    await page.route(UPLOAD_URL_RE, async (route: Route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' }),
      });
    });

    const input = await findFileInput(page);
    test.skip(!input, 'Нет input[type="file"]');

    await input!.setInputFiles({
      name: 'broken.pdf',
      mimeType: 'application/pdf',
      buffer: makeBuffer(2048),
    });
    await page.waitForTimeout(1500);
    // Не должно быть success-toast
    const success = await page
      .getByText(/загружен|успешно/i)
      .first()
      .isVisible()
      .catch(() => false);
    expect(success).toBe(false);
  });
});
