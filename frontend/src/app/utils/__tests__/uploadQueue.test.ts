import { describe, it, expect, vi } from 'vitest';

import {
  isFileValidationError,
  isTransientUploadError,
  uploadQueue,
  UPLOAD_CONCURRENCY,
} from '../uploadQueue';

const axiosError = (status?: number, headers: Record<string, string> = {}) => ({
  isAxiosError: true,
  response: status === undefined ? undefined : { status, headers },
});

describe('uploadQueue', () => {
  it('разделяет успешные и упавшие файлы, порядок сохраняется', async () => {
    const items = ['a', 'b', 'c', 'd'];
    const result = await uploadQueue(
      items,
      async (item) => {
        if (item === 'a' || item === 'c') throw new Error('no');
        return item;
      },
      { retryDelayMs: () => 0 },
    );

    expect(result.succeeded).toEqual(['b', 'd']);
    expect(result.failed.map((failure) => failure.item)).toEqual(['a', 'c']);
  });

  it('на пустом списке ничего не делает', async () => {
    const result = await uploadQueue([], async () => undefined);
    expect(result).toEqual({ succeeded: [], failed: [] });
  });

  it('держит не больше двух загрузок одновременно', async () => {
    let active = 0;
    let peak = 0;

    await uploadQueue([1, 2, 3, 4, 5, 6], async (item) => {
      active += 1;
      peak = Math.max(peak, active);
      await new Promise((resolve) => setTimeout(resolve, 5));
      active -= 1;
      return item;
    });

    expect(peak).toBeLessThanOrEqual(UPLOAD_CONCURRENCY);
    expect(peak).toBeGreaterThan(1);
  });

  it('повторяет запрос при ответе 429 и берёт паузу из Retry-After', async () => {
    let attempts = 0;
    const delays: number[] = [];

    const result = await uploadQueue(
      ['file.pdf'],
      async () => {
        attempts += 1;
        if (attempts < 3) throw axiosError(429, { 'retry-after': '2' });
      },
      { retryDelayMs: (error) => {
        const seconds = Number((error as { response?: { headers?: Record<string, string> } }).response?.headers?.['retry-after']);
        delays.push(seconds * 1000);
        return 0;
      } },
    );

    expect(result.failed).toHaveLength(0);
    expect(attempts).toBe(3);
    expect(delays).toEqual([2000, 2000]);
  });

  it('повторяет сетевую ошибку без ответа сервера', async () => {
    let attempts = 0;

    const result = await uploadQueue(
      ['file.pdf'],
      async () => {
        attempts += 1;
        if (attempts === 1) throw axiosError();
      },
      { retryDelayMs: () => 0 },
    );

    expect(result.failed).toHaveLength(0);
    expect(attempts).toBe(2);
  });

  it('не повторяет ошибку формата или размера', async () => {
    let attempts = 0;

    const result = await uploadQueue(
      ['file.exe'],
      async () => {
        attempts += 1;
        throw axiosError(415);
      },
      { retryDelayMs: () => 0 },
    );

    expect(attempts).toBe(1);
    expect(result.failed).toHaveLength(1);
  });

  it('сдаётся после заданного числа попыток', async () => {
    let attempts = 0;

    const result = await uploadQueue(
      ['file.pdf'],
      async () => {
        attempts += 1;
        throw axiosError(503);
      },
      { attempts: 3, retryDelayMs: () => 0 },
    );

    expect(attempts).toBe(3);
    expect(result.failed).toHaveLength(1);
  });

  it('сообщает прогресс по каждому файлу и общий процент', async () => {
    const started: number[] = [];
    const percents: number[] = [];
    const done: Array<{ index: number; ok: boolean }> = [];
    const overall: number[] = [];

    await uploadQueue(
      ['a', 'b'],
      async (_item, onPercent) => {
        onPercent(50);
        onPercent(100);
      },
      {
        onItemStart: (index) => started.push(index),
        onItemProgress: (index, percent) => percents.push(percent),
        onItemDone: (index, ok) => done.push({ index, ok }),
        onProgress: (progress) => overall.push(progress.percent),
      },
    );

    expect(started.sort()).toEqual([0, 1]);
    expect(percents).toContain(100);
    expect(done.sort((a, b) => a.index - b.index)).toEqual([
      { index: 0, ok: true },
      { index: 1, ok: true },
    ]);
    expect(Math.max(...overall)).toBe(100);
  });
});

describe('uploadQueue helpers', () => {
  it('считает временными сеть, 408, 429 и 5xx', () => {
    expect(isTransientUploadError(axiosError())).toBe(true);
    expect(isTransientUploadError(axiosError(408))).toBe(true);
    expect(isTransientUploadError(axiosError(429))).toBe(true);
    expect(isTransientUploadError(axiosError(500))).toBe(true);
    expect(isTransientUploadError(axiosError(504))).toBe(true);
  });

  it('не считает временными отказы по формату и размеру', () => {
    expect(isTransientUploadError(axiosError(413))).toBe(false);
    expect(isTransientUploadError(axiosError(415))).toBe(false);
    expect(isTransientUploadError(axiosError(403))).toBe(false);
  });

  it('отличает ошибку валидации файла', () => {
    expect(isFileValidationError(axiosError(413))).toBe(true);
    expect(isFileValidationError(axiosError(415))).toBe(true);
    expect(isFileValidationError(axiosError(500))).toBe(false);
    expect(isFileValidationError(new Error('network'))).toBe(false);
  });
});

describe('uploadQueue — прогресс не ломается на медленных загрузках', () => {
  it('вызывает onProgress не реже, чем раз в 120 мс, и всегда в конце', async () => {
    const spy = vi.fn();
    await uploadQueue(
      [1, 2, 3],
      async (_item, onPercent) => {
        for (const value of [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]) {
          onPercent(value);
          await new Promise((resolve) => setTimeout(resolve, 1));
        }
      },
      { onProgress: spy },
    );

    expect(spy).toHaveBeenCalled();
    const lastCall = spy.mock.calls[spy.mock.calls.length - 1]?.[0];
    expect(lastCall).toMatchObject({ processed: 3, succeeded: 3, percent: 100 });
  });
});
