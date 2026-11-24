import { AxiosError } from 'axios';

/** Сколько файлов отправляем одновременно. Сервер и S3 не любят шквал запросов. */
export const UPLOAD_CONCURRENCY = 2;

/** Сколько раз пробуем один и тот же файл при временной ошибке. */
export const UPLOAD_ATTEMPTS = 3;

export interface UploadFailure<T> {
  item: T;
  error: unknown;
}

export interface UploadQueueResult<T> {
  succeeded: T[];
  failed: UploadFailure<T>[];
}

export interface UploadQueueProgress {
  /** Сколько файлов уже обработано (успешно или с ошибкой). */
  processed: number;
  /** Сколько из них сохранено на сервере. */
  succeeded: number;
  /** Общий прогресс по переданному списку, 0–100. */
  percent: number;
}

export interface UploadQueueOptions<T> {
  concurrency?: number;
  attempts?: number;
  onProgress?: (progress: UploadQueueProgress) => void;
  /** Файл взяли в работу. */
  onItemStart?: (index: number) => void;
  /** Прогресс одного файла, 0–100. */
  onItemProgress?: (index: number, percent: number) => void;
  /** Файл завершён: ok = false, если так и не удалось. */
  onItemDone?: (index: number, ok: boolean) => void;
  /** Пауза перед повтором; вынесена, чтобы тесты не ждали секундами. */
  retryDelayMs?: (error: unknown, attempt: number) => number;
  nameOf?: (item: T) => string;
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Временная ли ошибка: сеть, таймаут, «слишком часто», ответы 5xx. */
export function isTransientUploadError(error: unknown): boolean {
  const status = (error as AxiosError | undefined)?.response?.status;
  if (!status) return true;
  return status === 408 || status === 425 || status === 429 || status >= 500;
}

/** Ошибка, которую партнёр может исправить сам: размер или формат файла. */
export function isFileValidationError(error: unknown): boolean {
  const status = (error as AxiosError | undefined)?.response?.status;
  return status === 413 || status === 415;
}

function retryDelayMs(error: unknown, attempt: number): number {
  const header = (error as AxiosError | undefined)?.response?.headers?.['retry-after'];
  const seconds = typeof header === 'string' || typeof header === 'number' ? Number(header) : Number.NaN;
  if (Number.isFinite(seconds) && seconds > 0) return Math.min(seconds * 1000, 15_000);
  return Math.min(800 * 2 ** attempt, 8_000);
}

async function withRetries<T>(
  action: () => Promise<T>,
  attempts: number,
  delayFor: (error: unknown, attempt: number) => number,
): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      return await action();
    } catch (error) {
      lastError = error;
      if (!isTransientUploadError(error) || attempt === attempts - 1) throw error;
      await sleep(delayFor(error, attempt));
    }
  }
  throw lastError;
}

/**
 * Отправляет файлы небольшой очередью: не все сразу, с повтором при временных
 * ошибках. Один упавший файл не мешает остальным.
 */
/** onPercent принимает значение 0–100, как у axios onUploadProgress. */
export async function uploadQueue<T>(
  items: T[],
  upload: (item: T, onPercent: (percent: number) => void) => Promise<unknown>,
  options: UploadQueueOptions<T> = {},
): Promise<UploadQueueResult<T>> {
  const concurrency = Math.max(1, options.concurrency ?? UPLOAD_CONCURRENCY);
  const attempts = Math.max(1, options.attempts ?? UPLOAD_ATTEMPTS);
  const delayFor = options.retryDelayMs ?? retryDelayMs;
  const total = items.length;

  const fractions = new Map<number, number>();
  const succeeded: T[] = [];
  const failed: UploadFailure<T>[] = [];
  let nextIndex = 0;
  let processed = 0;

  const report = () => {
    const inFlight = [...fractions.values()].reduce((sum, value) => sum + value, 0);
    const percent = total === 0 ? 0 : Math.min(100, Math.round(((processed + inFlight) / total) * 100));
    options.onProgress?.({ processed, succeeded: succeeded.length, percent });
  };

  const worker = async () => {
    for (;;) {
      const index = nextIndex;
      nextIndex += 1;
      if (index >= total) return;

      const item = items[index];
      fractions.set(index, 0);
      options.onItemStart?.(index);
      report();

      try {
        await withRetries(
          () =>
            upload(item, (percent) => {
              const fraction = Math.max(0, Math.min(1, percent / 100));
              fractions.set(index, fraction);
              options.onItemProgress?.(index, Math.round(fraction * 100));
              report();
            }),
          attempts,
          delayFor,
        );
        succeeded.push(item);
        options.onItemDone?.(index, true);
      } catch (error) {
        failed.push({ item, error });
        options.onItemDone?.(index, false);
      } finally {
        fractions.delete(index);
        processed += 1;
        report();
      }
    }
  };

  await Promise.all(Array.from({ length: Math.min(concurrency, total) }, () => worker()));

  return { succeeded, failed };
}
