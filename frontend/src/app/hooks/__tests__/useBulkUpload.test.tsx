// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { useBulkUpload } from '../useBulkUpload';

const validationError = () => ({ isAxiosError: true, response: { status: 415, headers: {} } });

describe('useBulkUpload', () => {
  it('показывает прогресс и остаётся в состоянии загрузки до конца', async () => {
    let release: (() => void) | null = null;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });

    const upload = vi.fn(async (_file: File, onPercent: (percent: number) => void) => {
      onPercent(40);
      await gate;
      onPercent(100);
    });

    const { result } = renderHook(() => useBulkUpload<File>(upload));

    act(() => {
      void result.current.start([new File(['a'], 'a.pdf')]);
    });

    await waitFor(() => expect(result.current.state.percent).toBeGreaterThan(0));
    expect(result.current.isUploading).toBe(true);

    await act(async () => {
      release?.();
    });

    await waitFor(() => expect(result.current.state.phase).toBe('done'));
    expect(result.current.state).toMatchObject({ total: 1, done: 1, percent: 100 });
  });

  it('после частичного сбоя уходит в partial и повторяет только упавший файл', async () => {
    let failedOnce = false;
    const upload = vi.fn(async (file: File) => {
      if (file.name === 'bad.pdf' && !failedOnce) {
        failedOnce = true;
        throw validationError();
      }
    });

    const { result } = renderHook(() => useBulkUpload<File>(upload));

    await act(async () => {
      await result.current.start([new File(['a'], 'ok.pdf'), new File(['b'], 'bad.pdf')]);
    });

    expect(result.current.state.phase).toBe('partial');
    expect(result.current.state.done).toBe(1);
    expect(result.current.state.failed.map((failure) => failure.item.name)).toEqual(['bad.pdf']);

    upload.mockClear();
    await act(async () => {
      await result.current.retry();
    });

    expect(upload).toHaveBeenCalledTimes(1);
    expect(upload.mock.calls[0][0]).toMatchObject({ name: 'bad.pdf' });
    expect(result.current.state.phase).toBe('done');
    expect(result.current.state.done).toBe(2);
  });

  it('скрывает баннер по кнопке', async () => {
    const { result } = renderHook(() => useBulkUpload<File>(async () => undefined));

    await act(async () => {
      await result.current.start([new File(['a'], 'a.pdf')]);
    });
    expect(result.current.state.phase).toBe('done');

    act(() => result.current.dismiss());
    expect(result.current.state.phase).toBe('idle');
  });

  it('не запускает вторую пачку во время загрузки', async () => {
    let release: (() => void) | null = null;
    const upload = vi.fn(
      async () =>
        new Promise<void>((resolve) => {
          release = resolve;
        }),
    );

    const { result } = renderHook(() => useBulkUpload<File>(upload));

    act(() => {
      void result.current.start([new File(['a'], 'a.pdf')]);
    });
    await waitFor(() => expect(result.current.isUploading).toBe(true));

    let secondResult: unknown;
    await act(async () => {
      secondResult = await result.current.start([new File(['b'], 'b.pdf')]);
    });

    expect(secondResult).toBeNull();
    expect(upload).toHaveBeenCalledTimes(1);

    await act(async () => {
      release?.();
    });
    await waitFor(() => expect(result.current.state.phase).toBe('done'));
  });
});
