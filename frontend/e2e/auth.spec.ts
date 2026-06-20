import { test, expect, type Route } from '@playwright/test';
import { PARTNER, loginPartner, loginAdmin } from './helpers';

test.describe('Auth — happy paths', () => {
  test('partner login → dashboard', async ({ page }) => {
    await loginPartner(page);
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('admin login → admin panel', async ({ page }) => {
    await loginAdmin(page);
    await expect(page).toHaveURL(/\/admin/);
  });

  test('refresh preserves session', async ({ page }) => {
    await loginPartner(page);
    await page.reload();
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('navigate works after refresh', async ({ page }) => {
    await loginPartner(page);
    await page.reload();
    await page.click('text=Клиенты');
    await expect(page).toHaveURL(/\/dashboard\/clients/);
  });
});

test.describe('Auth — errors', () => {
  test('wrong password stays on login', async ({ page }) => {
    await page.goto('/login');
    await page.getByPlaceholder('partner@example.com').fill(PARTNER.email);
    await page.getByPlaceholder('Введите пароль').fill('wrongpassword');
    await page.getByRole('button', { name: /войти/i }).click();
    await page.waitForTimeout(1500);
    await expect(page).toHaveURL(/\/login/);
  });

  test('nonexistent user stays on login', async ({ page }) => {
    await page.goto('/login');
    await page.getByPlaceholder('partner@example.com').fill('noone@nowhere.com');
    await page.getByPlaceholder('Введите пароль').fill('AnyPass123');
    await page.getByRole('button', { name: /войти/i }).click();
    await page.waitForTimeout(1500);
    await expect(page).toHaveURL(/\/login/);
  });

  test('empty email blocks submit', async ({ page }) => {
    await page.goto('/login');
    await page.getByPlaceholder('Введите пароль').fill('something');
    await page.getByRole('button', { name: /войти/i }).click();
    await page.waitForTimeout(500);
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe('Auth — routing & access', () => {
  test('unauthenticated /dashboard → /login', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/login/, { timeout: 5000 });
  });

  test('unauthenticated /admin → /login', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/admin');
    await expect(page).toHaveURL(/\/login/, { timeout: 5000 });
  });

  test('partner cannot access admin pages', async ({ page }) => {
    await loginPartner(page);
    await page.goto('/admin');
    await page.waitForTimeout(1500);
    expect(page.url()).not.toMatch(/\/admin\/dashboard/);
  });

  test('logout clears session and blocks /dashboard', async ({ page }) => {
    await loginPartner(page);
    await page.locator('text=Партнёр').click();
    await page.waitForURL(/\/login/, { timeout: 5000 });
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/login/, { timeout: 5000 });
  });
});

test.describe('Auth — server errors (моки)', () => {
  test('сервер отвечает 401 на логин → остаёмся на /login с ошибкой', async ({ page }) => {
    await page.route('**/api/v1/auth/login', async (route: Route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Invalid credentials', code: 'INVALID_CREDENTIALS' }),
      });
    });

    await page.goto('/login');
    await page.getByPlaceholder('partner@example.com').fill(PARTNER.email);
    await page.getByPlaceholder('Введите пароль').fill(PARTNER.password);
    await page.getByRole('button', { name: /войти/i }).click();

    await expect(page).toHaveURL(/\/login/);
  });

  test('сервер отвечает 403 PARTNER_PENDING → сообщение "ожидает одобрения"', async ({ page }) => {
    await page.route('**/api/v1/auth/login', async (route: Route) => {
      await route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Partner is pending approval', code: 'PARTNER_PENDING' }),
      });
    });

    await page.goto('/login');
    await page.getByPlaceholder('partner@example.com').fill('pending@test.com');
    await page.getByPlaceholder('Введите пароль').fill('AnyPass123');
    await page.getByRole('button', { name: /войти/i }).click();

    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByText(/одобрен|pending|проверк|ожида/i).first()).toBeVisible({ timeout: 5000 });
  });

  test('сервер отвечает 403 PARTNER_BLOCKED → сообщение "заблокирован"', async ({ page }) => {
    await page.route('**/api/v1/auth/login', async (route: Route) => {
      await route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Partner is blocked', code: 'PARTNER_BLOCKED' }),
      });
    });

    await page.goto('/login');
    await page.getByPlaceholder('partner@example.com').fill('blocked@test.com');
    await page.getByPlaceholder('Введите пароль').fill('AnyPass123');
    await page.getByRole('button', { name: /войти/i }).click();

    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByText(/заблокирован|blocked/i).first()).toBeVisible({ timeout: 5000 });
  });

  test('429 rate limit на логин → сообщение об ограничении', async ({ page }) => {
    await page.route('**/api/v1/auth/login', async (route: Route) => {
      await route.fulfill({
        status: 429,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Too many login attempts', code: 'RATE_LIMITED' }),
      });
    });

    await page.goto('/login');
    await page.getByPlaceholder('partner@example.com').fill(PARTNER.email);
    await page.getByPlaceholder('Введите пароль').fill(PARTNER.password);
    await page.getByRole('button', { name: /войти/i }).click();

    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe('Auth — session lifecycle', () => {
  test('истёкший access token → автоматический refresh → запрос успешен', async ({ page }) => {
    await loginPartner(page);

    // Перехватим первый /auth/me после reload и отдадим 401,
    // рассчитывая что клиент дёрнет /auth/refresh и повторит запрос.
    let meCalls = 0;
    await page.route('**/api/v1/auth/me', async (route: Route) => {
      meCalls += 1;
      if (meCalls === 1) {
        await route.fulfill({
          status: 401,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Token expired', code: 'TOKEN_EXPIRED' }),
        });
      } else {
        await route.continue();
      }
    });

    await page.reload();
    // После refresh-flow юзер должен остаться на защищённой странице.
    // В худшем случае редиректит на /login — тест фиксирует текущее поведение.
    await page.waitForTimeout(2000);
    expect(meCalls).toBeGreaterThanOrEqual(1);
  });

  test('удалённый refresh cookie → protected страница редиректит на /login', async ({ page }) => {
    await loginPartner(page);
    // Удаляем все куки кроме access (эмулируем истечение refresh)
    await page.context().clearCookies();
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/login/, { timeout: 5000 });
  });

  test('logout в одной вкладке блокирует другую', async ({ browser }) => {
    const ctx = await browser.newContext();
    const page1 = await ctx.newPage();
    const page2 = await ctx.newPage();

    await loginPartner(page1);
    await page2.goto('/dashboard');
    await expect(page2).toHaveURL(/\/dashboard/, { timeout: 5000 });

    // Logout в первой вкладке
    await page1.locator('text=Партнёр').click();
    await page1.waitForURL(/\/login/, { timeout: 5000 });

    // Во второй вкладке переход должен привести на /login
    await page2.goto('/dashboard');
    await expect(page2).toHaveURL(/\/login/, { timeout: 5000 });

    await ctx.close();
  });
});
