import { AlertCircle, Check, Loader2 } from 'lucide-react';

import { filesCountLabel, pluralFiles } from '@/app/utils/plural';

interface UploadProgressBannerProps {
  phase: 'idle' | 'uploading' | 'done' | 'partial';
  total: number;
  done: number;
  percent: number;
  failedCount: number;
  etaSeconds?: number | null;
  onRetry?: () => void;
  onDismiss?: () => void;
}

function successTitle(total: number): string {
  return total === 1 ? 'Файл загружен' : `Все ${filesCountLabel(total)} загружены`;
}

function failureNote(count: number): string {
  if (count === 1) return '1 файл не загрузился. Нажмите «Повторить» — загрузим только его.';
  return `${count} ${pluralFiles(count)} не удалось загрузить. Нажмите «Повторить» — загрузим только их.`;
}

function etaLabel(seconds: number | null | undefined): string | null {
  if (!seconds || seconds < 3) return null;
  if (seconds < 60) return `осталось около ${seconds} сек.`;
  const minutes = Math.round(seconds / 60);
  return `осталось около ${minutes} мин.`;
}

export default function UploadProgressBanner({
  phase,
  total,
  done,
  percent,
  failedCount,
  etaSeconds,
  onRetry,
  onDismiss,
}: UploadProgressBannerProps) {
  if (phase === 'idle') return null;

  if (phase === 'uploading') {
    const eta = etaLabel(etaSeconds);
    return (
      <div className="mb-4 rounded-[10px] bg-blue-50 px-4 py-3.5" aria-live="polite">
        <div className="mb-2.5 flex items-baseline gap-3">
          <span className="flex items-center gap-2 text-sm font-semibold text-gray-900">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-600" />
            Загружено {done} из {total}
          </span>
          {eta ? <span className="ml-auto text-xs text-gray-500">{eta}</span> : null}
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-blue-600/15">
          <div
            className="h-full rounded-full bg-blue-600 transition-[width] duration-300"
            style={{ width: `${Math.max(2, percent)}%` }}
          />
        </div>
      </div>
    );
  }

  if (phase === 'done') {
    return (
      <div className="mb-4 flex items-start gap-2.5 rounded-[10px] border border-emerald-200 bg-emerald-50 px-4 py-3.5" aria-live="polite">
        <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-emerald-800">{successTitle(total)}</p>
          <p className="mt-0.5 text-[13px] text-emerald-700">Можно переходить к следующему клиенту.</p>
        </div>
        {onDismiss ? (
          <button type="button" onClick={onDismiss} className="text-xs text-emerald-700 hover:text-emerald-900">
            Скрыть
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="mb-4 flex items-start gap-2.5 rounded-[10px] border border-amber-200 bg-amber-50 px-4 py-3.5" aria-live="polite">
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-amber-800">
          Загружено {done} из {total}
        </p>
        <p className="mt-0.5 text-[13px] text-amber-700">{failureNote(failedCount)}</p>
        <div className="mt-3 flex items-center gap-2">
          <button
            type="button"
            onClick={onRetry}
            className="rounded-lg bg-blue-600 px-3.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-700"
          >
            Повторить
          </button>
          {onDismiss ? (
            <button type="button" onClick={onDismiss} className="px-1.5 py-1.5 text-xs text-gray-500 hover:text-gray-900">
              Скрыть
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
