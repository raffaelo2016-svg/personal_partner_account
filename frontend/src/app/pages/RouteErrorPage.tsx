import { useEffect } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Link, useRouteError } from 'react-router';
import { captureError } from '@/app/sentry';

const CHUNK_ERROR_PATTERN =
  /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module/i;

export default function RouteErrorPage() {
  const error = useRouteError();
  const isChunkError = error instanceof Error && CHUNK_ERROR_PATTERN.test(error.message);
  const cabinetPath = window.location.pathname.startsWith('/admin') ? '/admin/clients' : '/dashboard';

  useEffect(() => {
    captureError(error, { source: 'route-error-boundary' });
  }, [error]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50 p-6">
      <section className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-8 text-center shadow-sm">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-amber-50">
          <AlertTriangle className="h-7 w-7 text-amber-600" aria-hidden="true" />
        </div>
        <h1 className="mb-2 text-xl font-semibold text-gray-900">Не удалось загрузить страницу</h1>
        <p className="mb-6 text-gray-600">
          {isChunkError
            ? 'Версия кабинета обновилась. Обновите страницу, чтобы продолжить работу.'
            : 'Произошла непредвиденная ошибка. Обновите страницу или вернитесь в кабинет.'}
        </p>
        <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-white transition-colors hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Обновить страницу
          </button>
          <Link
            to={cabinetPath}
            className="inline-flex items-center justify-center rounded-lg border border-gray-300 px-4 py-2 text-gray-700 transition-colors hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
          >
            Вернуться в кабинет
          </Link>
        </div>
      </section>
    </main>
  );
}
