import * as Sentry from '@sentry/react';

export function initSentry() {
  const dsn = import.meta.env.VITE_SENTRY_DSN;
  if (!dsn) return;

  Sentry.init({
    dsn,
    environment: import.meta.env.MODE,
    tracesSampleRate: 0.1,
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 1.0,
    // Не передаём cookies/query/ip по умолчанию.
    sendDefaultPii: false,
    integrations: [
      Sentry.browserTracingIntegration(),
      // PII: формы содержат паспорт/СНИЛС/ИНН — маскируем весь текст и инпуты,
      // медиа блокируем. Это дефолт в Sentry 7+, но фиксируем явно, чтобы
      // не зависеть от возможных изменений в апстриме.
      Sentry.replayIntegration({
        maskAllText: true,
        maskAllInputs: true,
        blockAllMedia: true,
      }),
    ],
  });
}

export function captureError(error: unknown, context?: Record<string, unknown>) {
  if (!import.meta.env.VITE_SENTRY_DSN) return;
  Sentry.captureException(error, context ? { extra: context } : undefined);
}
