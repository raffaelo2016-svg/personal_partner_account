import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router';
import { Toaster, toast } from 'sonner';
import ErrorBoundary from './components/ErrorBoundary';
import { TimezoneProvider } from './contexts/TimezoneContext';
import { router } from './routes';
import { captureError } from './sentry';
import { extractErrorMessage } from './utils/errors';

function shouldToast(status: number | null): boolean {
  if (status === null) return true; // network error / no response
  if (status === 401 || status === 403 || status === 404 || status === 409 || status === 422) return false;
  return status >= 500 || status === 0;
}

function handleGlobalError(error: unknown, opts: { silent?: boolean } = {}) {
  const { message, status } = extractErrorMessage(error);
  if (status === null || status >= 500) {
    captureError(error, { message, status });
  }
  if (opts.silent) return;
  if (!shouldToast(status)) return;
  toast.error(status === null ? 'Сервер недоступен' : `Ошибка сервера (${status})`, {
    description: message,
  });
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error, query) => {
      handleGlobalError(error, { silent: query.meta?.silent === true });
    },
  }),
  mutationCache: new MutationCache({
    onError: (error, _vars, _ctx, mutation) => {
      if (mutation.options.onError) return;
      handleGlobalError(error, { silent: mutation.meta?.silent === true });
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <TimezoneProvider>
          <RouterProvider router={router} />
          <Toaster position="top-right" richColors closeButton />
        </TimezoneProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
