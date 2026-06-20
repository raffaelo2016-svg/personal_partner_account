import { AxiosError } from 'axios';

export interface ExtractedError {
  message: string;
  status: number | null;
}

export function extractErrorMessage(error: unknown): ExtractedError {
  if (error instanceof AxiosError) {
    const status = error.response?.status ?? null;
    const data = error.response?.data as { message?: string; detail?: unknown } | undefined;
    const detail = data?.detail;
    const detailMessage =
      typeof detail === 'string'
        ? detail
        : detail && typeof detail === 'object' && 'message' in detail
          ? String((detail as { message?: unknown }).message ?? '')
          : '';
    const message = data?.message || detailMessage || error.message || 'Неизвестная ошибка';
    return { message, status };
  }
  if (error instanceof Error) return { message: error.message, status: null };
  return { message: 'Неизвестная ошибка', status: null };
}
