import { useEffect, useRef } from 'react';
import { Link } from 'react-router';
import {
  ArrowRight,
  Check,
  CheckCircle2,
  Circle,
  Clock,
  FileText,
  Home,
  MessageSquare,
  FolderOpen,
  UserPlus,
  Wallet,
  X,
} from 'lucide-react';
import type { LessonIcon, TrainingLesson } from '../data/trainingCourse';
import { formatLessonDuration } from '../data/trainingCourse';

const ICONS: Record<LessonIcon, typeof Home> = {
  intro: Home,
  client: UserPlus,
  documents: FolderOpen,
  tasks: CheckCircle2,
  finance: Wallet,
  chat: MessageSquare,
};

interface Props {
  lesson: TrainingLesson;
  completed: boolean;
  nextLesson: TrainingLesson | null;
  onClose: () => void;
  onComplete: () => void;
  onReset: () => void;
  onNext: () => void;
}

export default function TrainingLessonModal({
  lesson,
  completed,
  nextLesson,
  onClose,
  onComplete,
  onReset,
  onNext,
}: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const Icon = ICONS[lesson.icon];

  // Снятие отметки должно останавливать ролик: иначе видео доиграет до конца
  // и сразу поставит отметку обратно.
  const handleReset = () => {
    const video = videoRef.current;
    if (video) {
      video.pause();
      video.currentTime = 0;
    }
    onReset();
  };

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

  useEffect(() => {
    // Плеер пытается стартовать сразу: звук включён, но браузер может
    // попросить нажать play — тогда просто показываем обычные контролы.
    scrollRef.current?.scrollTo({ top: 0 });
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = 0;
    void video.play().catch(() => undefined);
  }, [lesson.key]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-gray-950/70 backdrop-blur-sm sm:items-center sm:p-6"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Урок ${lesson.number}: ${lesson.title}`}
        className="flex max-h-[100dvh] w-full flex-col overflow-hidden bg-white shadow-2xl sm:max-h-[92vh] sm:max-w-4xl sm:rounded-3xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className={`flex items-start gap-4 bg-gradient-to-r ${lesson.accent.gradient} px-5 py-4 text-white sm:px-7 sm:py-5`}>
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white/15">
            <Icon className="h-5 w-5" aria-hidden="true" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium uppercase tracking-wide text-white/70">
              Урок {lesson.number} из 6
            </p>
            <h2 className="mt-0.5 truncate text-lg font-semibold sm:text-xl">{lesson.title}</h2>
          </div>
          <div className="flex items-center gap-1">
            <span className="mr-1 hidden items-center gap-1 rounded-full bg-white/15 px-2.5 py-1 text-xs font-medium sm:flex">
              <Clock className="h-3.5 w-3.5" aria-hidden="true" />
              {formatLessonDuration(lesson.duration)}
            </span>
            <button
              type="button"
              onClick={onClose}
              aria-label="Закрыть урок"
              className="rounded-lg p-2 text-white/80 transition hover:bg-white/15 hover:text-white"
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>
        </div>

        <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
          <video
            ref={videoRef}
            src={lesson.videoUrl}
            controls
            playsInline
            preload="metadata"
            onEnded={onComplete}
            className="aspect-video w-full bg-black"
          >
            Ваш браузер не поддерживает видео. Откройте урок в современном браузере.
          </video>

          <div className="space-y-7 px-5 py-6 sm:px-7 sm:py-7">
            <section>
              <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
                <FileText className="h-4 w-4" aria-hidden="true" />
                Конспект урока
              </h3>
              <ul className="space-y-2.5">
                {lesson.conspect.map((item) => (
                  <li key={item} className="flex gap-3 text-[15px] leading-6 text-gray-700">
                    <span
                      className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full"
                      style={{ backgroundColor: lesson.accent.hex }}
                    />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </section>

            <section>
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
                Сделайте в кабинете
              </h3>
              <ol className="space-y-3">
                {lesson.steps.map((step, index) => (
                  <li key={step.text} className="flex gap-3">
                    <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${lesson.accent.soft} text-xs font-semibold ${lesson.accent.text}`}>
                      {index + 1}
                    </span>
                    <div className="pt-0.5 text-[15px] leading-6 text-gray-700">
                      <p>{step.text}</p>
                      {step.to && step.linkLabel && (
                        <Link
                          to={step.to}
                          onClick={onClose}
                          className={`mt-1 inline-flex items-center gap-1 text-sm font-medium ${lesson.accent.text} hover:underline`}
                        >
                          {step.linkLabel}
                          <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                        </Link>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          </div>
        </div>

        <div className="flex flex-col gap-3 border-t border-gray-200 bg-gray-50 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-7">
          <button
            type="button"
            onClick={completed ? handleReset : onComplete}
            className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition ${
              completed
                ? 'bg-green-100 text-green-700 hover:bg-green-200'
                : 'border border-gray-300 bg-white text-gray-700 hover:bg-gray-100'
            }`}
          >
            {completed ? (
              <>
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                Просмотрено — снять отметку
              </>
            ) : (
              <>
                <Circle className="h-4 w-4" aria-hidden="true" />
                Отметить просмотренным
              </>
            )}
          </button>

          {nextLesson ? (
            <button
              type="button"
              onClick={onNext}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-gray-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-gray-800"
            >
              Следующий: {nextLesson.title}
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </button>
          ) : (
            <button
              type="button"
              onClick={onClose}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-gray-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-gray-800"
            >
              <Check className="h-4 w-4" aria-hidden="true" />
              Курс пройден
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
