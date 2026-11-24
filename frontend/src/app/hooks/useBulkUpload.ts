import { useCallback, useRef, useState } from 'react';

import { uploadQueue, type UploadFailure, type UploadQueueResult } from '@/app/utils/uploadQueue';

export type BulkUploadPhase = 'idle' | 'uploading' | 'done' | 'partial';
export type UploadItemStatus = 'queued' | 'uploading' | 'done' | 'failed';

export interface BulkUploadState<T> {
  phase: BulkUploadPhase;
  /** Всего файлов в текущем заходе, включая уже загруженные ранее. */
  total: number;
  /** Сколько файлов сохранено на сервере. */
  done: number;
  percent: number;
  etaSeconds: number | null;
  /** Файлы текущей пачки — их показываем списком во время загрузки. */
  items: T[];
  statuses: UploadItemStatus[];
  percents: number[];
  failed: UploadFailure<T>[];
}

const IDLE: BulkUploadState<never> = {
  phase: 'idle',
  total: 0,
  done: 0,
  percent: 0,
  etaSeconds: null,
  items: [],
  statuses: [],
  percents: [],
  failed: [],
};

export interface UseBulkUploadOptions<T> {
  /** Что показать партнёру в заголовке баннера (не используется в счётчиках). */
  nameOf?: (item: T) => string;
  /** Вызывается после каждого захода: можно обновить список документов. */
  onFinished?: (result: UploadQueueResult<T>) => void;
}

/**
 * Загрузка пачки файлов с прогрессом, очередью и повтором временных ошибок.
 * Один упавший файл не мешает остальным; успешные остаются на месте.
 */
export function useBulkUpload<T>(
  upload: (item: T, onPercent: (percent: number) => void) => Promise<unknown>,
  options: UseBulkUploadOptions<T> = {},
) {
  const [state, setState] = useState<BulkUploadState<T>>(IDLE as BulkUploadState<T>);
  const busyRef = useRef(false);
  const uploadRef = useRef(upload);
  uploadRef.current = upload;
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const run = useCallback(
    async (items: T[], doneOffset: number, total: number, startedAt: number): Promise<UploadQueueResult<T>> => {
      const statuses: UploadItemStatus[] = items.map(() => 'queued');
      const percents: number[] = items.map(() => 0);
      let succeededHere = 0;
      let lastFlush = 0;
      let flushTimer: ReturnType<typeof setTimeout> | null = null;

      const flush = (force: boolean) => {
        const now = Date.now();
        const wait = 120 - (now - lastFlush);
        // Не дёргаем React на каждое событие прогресса, но и не теряем
        // последнее: отложенный вызов дорисует полоску через 120 мс.
        if (!force && wait > 0) {
          if (flushTimer === null) {
            flushTimer = setTimeout(() => {
              flushTimer = null;
              flush(true);
            }, wait);
          }
          return;
        }
        lastFlush = now;

        const processed = statuses.filter((status) => status === 'done' || status === 'failed').length;
        const inFlight = percents.reduce(
          (sum, value, index) => (statuses[index] === 'uploading' ? sum + value / 100 : sum),
          0,
        );
        const progressUnits = doneOffset + processed + inFlight;
        const percent = total === 0 ? 0 : Math.min(100, Math.round((progressUnits / total) * 100));
        const elapsed = (Date.now() - startedAt) / 1000;
        const remaining = total - progressUnits;
        const eta = processed > 0 && remaining > 0 ? Math.round((elapsed / processed) * remaining) : null;

        setState({
          phase: 'uploading',
          total,
          done: doneOffset + succeededHere,
          percent,
          etaSeconds: eta !== null && eta > 1 ? eta : null,
          items,
          statuses: [...statuses],
          percents: [...percents],
          failed: [],
        });
      };

      flush(true);

      const result = await uploadQueue(items, (item, onPercent) => uploadRef.current(item, onPercent), {
        onItemStart: (index) => {
          statuses[index] = 'uploading';
          flush(true);
        },
        onItemProgress: (index, percent) => {
          percents[index] = percent;
          flush(false);
        },
        onItemDone: (index, ok) => {
          statuses[index] = ok ? 'done' : 'failed';
          if (ok) {
            succeededHere += 1;
            percents[index] = 100;
          }
          flush(true);
        },
      });

      if (flushTimer !== null) {
        clearTimeout(flushTimer);
        flushTimer = null;
      }

      const nextDone = doneOffset + result.succeeded.length;
      setState({
        phase: result.failed.length === 0 ? 'done' : 'partial',
        total,
        done: nextDone,
        percent: total === 0 ? 0 : Math.round((nextDone / total) * 100),
        etaSeconds: null,
        items,
        statuses: [...statuses],
        percents: [...percents],
        failed: result.failed,
      });
      optionsRef.current.onFinished?.(result);
      return result;
    },
    [],
  );

  const start = useCallback(
    async (items: T[]): Promise<UploadQueueResult<T> | null> => {
      if (busyRef.current || items.length === 0) return null;
      busyRef.current = true;
      try {
        return await run(items, 0, items.length, Date.now());
      } finally {
        busyRef.current = false;
      }
    },
    [run],
  );

  /** Повторяет только те файлы, которые не прошли. */
  const retry = useCallback(async (): Promise<UploadQueueResult<T> | null> => {
    if (busyRef.current || state.phase !== 'partial' || state.failed.length === 0) return null;
    busyRef.current = true;
    try {
      return await run(
        state.failed.map((failure) => failure.item),
        state.done,
        state.total,
        Date.now(),
      );
    } finally {
      busyRef.current = false;
    }
  }, [run, state.done, state.failed, state.phase, state.total]);

  const dismiss = useCallback(() => setState(IDLE as BulkUploadState<T>), []);

  return { state, start, retry, dismiss, isUploading: state.phase === 'uploading' };
}
