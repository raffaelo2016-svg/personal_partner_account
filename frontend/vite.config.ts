/// <reference types="vitest" />
import { defineConfig, loadEnv, type PluginOption } from 'vite'
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

function cspMetaPlugin(apiUrl: string): PluginOption {
  let httpOrigin = ''
  let wsOrigin = ''
  try {
    const u = new URL(apiUrl)
    httpOrigin = `${u.protocol}//${u.host}`
    wsOrigin = `${u.protocol === 'https:' ? 'wss:' : 'ws:'}//${u.host}`
  } catch {
    // ignore — fall back to 'self'
  }
  // Yandex SmartCaptcha: скрипт grabs из smartcaptcha.yandexcloud.net/captcha.js,
  // кидает iframe с челленджем на *.captcha.yandex.ru, POST /validate идёт
  // c клиента на smartcaptcha.yandexcloud.net. Без разрешения домена в CSP
  // браузер блокирует всё это.
  const captcha = 'https://smartcaptcha.yandexcloud.net https://*.captcha.yandex.ru'
  const connectSrc = ["'self'", httpOrigin, wsOrigin, captcha].filter(Boolean).join(' ')
  const csp = [
    "default-src 'self'",
    `script-src 'self' ${captcha}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    `connect-src ${connectSrc}`,
    `frame-src ${captcha}`,
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
  ].join('; ')

  return {
    name: 'csp-meta',
    apply: 'build',
    transformIndexHtml(html) {
      return html.replace(
        '<head>',
        `<head>\n    <meta http-equiv="Content-Security-Policy" content="${csp}" />`,
      )
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiUrl = env.VITE_API_URL || 'http://localhost:8000/api/v1'

  return {
    plugins: [
      // The React and Tailwind plugins are both required for Make, even if
      // Tailwind is not being actively used – do not remove them
      react(),
      tailwindcss(),
      cspMetaPlugin(apiUrl),
    ],
    resolve: {
      alias: {
        // Alias @ to the src directory
        '@': path.resolve(__dirname, './src'),
      },
    },

    // File types to support raw imports. Never add .css, .tsx, or .ts files to this.
    assetsInclude: ['**/*.svg', '**/*.csv'],

    build: {
      // Не публикуем source maps в prod — исходный код не должен утекать клиенту.
      // Для Sentry собирайте симвлинк через CI и загружайте отдельно, не раздавая из dist.
      sourcemap: false,
      // Не удаляем ассеты предыдущих сборок. Открытая до деплоя вкладка может
      // запросить старый lazy-chunk уже после публикации новой версии; хэш в
      // имени делает такие файлы безопасными для совместного хранения.
      emptyOutDir: false,
    },

    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
      css: false,
      include: ['src/**/*.{test,spec}.{ts,tsx}'],
      exclude: ['node_modules', 'dist', 'e2e/**'],
    },
  }
})
