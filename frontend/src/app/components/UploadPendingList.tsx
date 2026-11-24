import { AlertCircle, Check, FileText, Loader2 } from 'lucide-react';

import type { UploadItemStatus } from '@/app/hooks/useBulkUpload';

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const index = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  return `${Math.round((bytes / 1024 ** index) * 100) / 100} ${units[index]}`;
}

function StatusIcon({ status }: { status: UploadItemStatus }) {
  if (status === 'done') return <Check className="h-4 w-4 text-emerald-600" />;
  if (status === 'uploading') return <Loader2 className="h-4 w-4 animate-spin text-blue-600" />;
  if (status === 'failed') return <AlertCircle className="h-4 w-4 text-amber-600" />;
  return <span className="block h-2 w-2 rounded-full bg-gray-300" />;
}

interface UploadPendingListProps {
  files: File[];
  statuses: UploadItemStatus[];
  percents: number[];
}

/** Список файлов, которые прямо сейчас уходят на сервер. */
export default function UploadPendingList({ files, statuses, percents }: UploadPendingListProps) {
  return (
    <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
      {files.map((file, index) => {
        const status = statuses[index] ?? 'queued';
        const percent = percents[index] ?? 0;
        return (
          <div
            key={`${file.name}-${file.size}-${index}`}
            className={`flex items-center gap-3 rounded-lg p-3 transition-colors ${
              status === 'queued' ? 'bg-gray-50/70 opacity-60' : 'bg-gray-50'
            }`}
          >
            <span className="flex w-4 shrink-0 items-center justify-center">
              <StatusIcon status={status} />
            </span>
            <FileText className="h-5 w-5 shrink-0 text-gray-400" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-gray-900">{file.name}</p>
              <p className="text-xs text-gray-500">
                {status === 'queued' ? 'в очереди · ' : status === 'uploading' ? 'загружается · ' : ''}
                {formatFileSize(file.size)}
              </p>
              {status === 'uploading' ? (
                <div className="mt-2 h-1 max-w-[320px] overflow-hidden rounded-full bg-blue-600/15">
                  <div
                    className="h-full rounded-full bg-blue-600 transition-[width] duration-200"
                    style={{ width: `${Math.max(3, percent)}%` }}
                  />
                </div>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
