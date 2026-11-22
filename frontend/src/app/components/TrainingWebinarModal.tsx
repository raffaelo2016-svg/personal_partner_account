import { useEffect } from 'react';
import { Clock, ExternalLink, X } from 'lucide-react';
import type { TrainingVideoData } from '../api/training';
import { formatLessonDuration } from '../data/trainingCourse';

interface Props {
  video: TrainingVideoData;
  onClose: () => void;
}

/**
 * Просмотр записи вебинара. Ролики лежат на Яндекс Клауде, поэтому играет
 * их родной плеер в iframe. Ссылка «открыть в новой вкладке» — на случай,
 * если браузер блокирует встраивание.
 */
export default function TrainingWebinarModal({ video, onClose }: Props) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-gray-950/70 backdrop-blur-sm sm:items-center sm:p-6"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Вебинар: ${video.title}`}
        className="flex max-h-[100dvh] w-full flex-col overflow-hidden bg-white shadow-2xl sm:max-h-[92vh] sm:max-w-4xl sm:rounded-3xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start gap-4 bg-gradient-to-r from-slate-800 to-slate-900 px-5 py-4 text-white sm:px-7 sm:py-5">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium uppercase tracking-wide text-white/60">
              Запись вебинара
            </p>
            <h2 className="mt-0.5 text-lg font-semibold sm:text-xl">{video.title}</h2>
          </div>
          <div className="flex items-center gap-1">
            {video.duration ? (
              <span className="mr-1 hidden items-center gap-1 rounded-full bg-white/15 px-2.5 py-1 text-xs font-medium sm:flex">
                <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                {formatLessonDuration(video.duration)}
              </span>
            ) : null}
            <button
              type="button"
              onClick={onClose}
              aria-label="Закрыть вебинар"
              className="rounded-lg p-2 text-white/80 transition hover:bg-white/15 hover:text-white"
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="aspect-video w-full bg-black">
            <iframe
              src={video.video_url}
              title={video.title}
              className="h-full w-full border-0"
              allow="autoplay; fullscreen; picture-in-picture; encrypted-media"
              allowFullScreen
              referrerPolicy="strict-origin-when-cross-origin"
            />
          </div>

          {video.description && (
            <p className="px-5 py-5 text-[15px] leading-6 text-gray-700 sm:px-7">
              {video.description}
            </p>
          )}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-gray-200 bg-gray-50 px-5 py-4 sm:px-7">
          <a
            href={video.video_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-gray-900 hover:underline"
          >
            <ExternalLink className="h-4 w-4" aria-hidden="true" />
            Открыть в новой вкладке
          </a>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl bg-gray-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-gray-800"
          >
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
}
