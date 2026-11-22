import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertCircle,
  ArrowRight,
  BookOpen,
  ChevronDown,
  Clock,
  HelpCircle,
  Info,
  Play,
  Search,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  completeTrainingLesson,
  fetchTrainingProgress,
  fetchTrainingVideos,
  resetTrainingLesson,
  type TrainingVideoData,
} from '../api/training';
import {
  TRAINING_FAQ,
  TRAINING_INSTRUCTIONS,
  TRAINING_LESSONS,
  TRAINING_NOTES,
  TRAINING_TOTAL_DURATION,
  formatLessonDuration,
  type TrainingLesson,
} from '../data/trainingCourse';
import TrainingLessonModal from '../components/TrainingLessonModal';
import TrainingWebinarModal from '../components/TrainingWebinarModal';

const NOTE_STYLES: Record<string, { wrap: string; icon: string }> = {
  alert: { wrap: 'border-red-200 bg-red-50', icon: 'text-red-600' },
  warning: { wrap: 'border-orange-200 bg-orange-50', icon: 'text-orange-600' },
  info: { wrap: 'border-blue-200 bg-blue-50', icon: 'text-blue-600' },
  default: { wrap: 'border-amber-200 bg-amber-50', icon: 'text-amber-600' },
};

/**
 * Обложки вебинаров лежат в public/training как тяжёлые PNG. Рядом положили
 * облегчённые JPG — их и грузим, а если файла нет, возвращаемся к оригиналу.
 */
function optimizedCover(url: string | null): string | null {
  if (!url) return null;
  return url.replace(/\.png$/i, '.jpg');
}

function WebinarCard({ video, onPlay }: { video: TrainingVideoData; onPlay: () => void }) {
  const [cover, setCover] = useState<string | null>(optimizedCover(video.thumbnail_url));

  return (
    <article className="group flex flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
      <button
        type="button"
        onClick={onPlay}
        aria-label={`Смотреть вебинар: ${video.title}`}
        className="relative aspect-video overflow-hidden bg-slate-200"
      >
        {cover ? (
          <img
            src={cover}
            alt=""
            loading="lazy"
            decoding="async"
            onError={() => {
              if (cover !== video.thumbnail_url) setCover(video.thumbnail_url);
            }}
            className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.03]"
          />
        ) : (
          <span className="flex h-full w-full items-center justify-center bg-gradient-to-br from-slate-700 to-slate-900">
            <Play className="h-10 w-10 text-white/80" aria-hidden="true" />
          </span>
        )}
        <span className="absolute inset-0 bg-gradient-to-t from-black/55 via-black/5 to-transparent" />
        <span className="absolute left-4 top-3 rounded-lg bg-white/15 px-2 py-1 text-xs font-semibold text-white backdrop-blur-sm">
          Вебинар
        </span>
        <span className="absolute inset-0 flex items-center justify-center opacity-0 transition group-hover:opacity-100">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-white shadow-lg">
            <Play className="ml-0.5 h-6 w-6 fill-slate-900 text-slate-900" aria-hidden="true" />
          </span>
        </span>
        {video.duration ? (
          <span className="absolute bottom-3 right-3 rounded-lg bg-black/70 px-2 py-0.5 text-xs font-medium text-white backdrop-blur-sm">
            {formatLessonDuration(video.duration)}
          </span>
        ) : null}
      </button>

      <div className="flex flex-1 flex-col p-5">
        <h3 className="font-semibold text-gray-900">{video.title}</h3>
        {video.description && (
          <p className="mt-1 line-clamp-2 flex-1 text-sm leading-6 text-gray-600">
            {video.description}
          </p>
        )}
        <button
          type="button"
          onClick={onPlay}
          className="mt-3 inline-flex items-center gap-1.5 self-start text-sm font-medium text-blue-600 hover:underline"
        >
          Смотреть запись
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </article>
  );
}

const TABS = [
  { id: 'faq' as const, label: 'Частые вопросы', icon: HelpCircle },
  { id: 'notes' as const, label: 'Важно', icon: AlertCircle },
  { id: 'instructions' as const, label: 'Инструкции', icon: BookOpen },
];

export default function Training() {
  const queryClient = useQueryClient();
  const [activeLesson, setActiveLesson] = useState<TrainingLesson | null>(null);
  const [activeWebinar, setActiveWebinar] = useState<TrainingVideoData | null>(null);
  const [activeTab, setActiveTab] = useState<(typeof TABS)[number]['id']>('faq');
  const [expandedFaq, setExpandedFaq] = useState<string | null>(null);
  const [faqQuery, setFaqQuery] = useState('');

  const { data: completed = [] } = useQuery({
    queryKey: ['training', 'progress'],
    queryFn: fetchTrainingProgress,
    staleTime: 30_000,
  });

  // Записи вебинаров приходят из базы и живут на Яндекс Клауде.
  const { data: videos = [] } = useQuery({
    queryKey: ['training', 'videos'],
    queryFn: fetchTrainingVideos,
    staleTime: 10 * 60_000,
  });

  const webinars = useMemo(
    () => videos.filter((video) => video.video_url && video.video_url !== '#'),
    [videos],
  );

  const applyProgress = (keys: string[]) => {
    queryClient.setQueryData(['training', 'progress'], keys);
  };

  const completeMutation = useMutation({
    mutationFn: (lessonKey: string) => completeTrainingLesson(lessonKey),
    onSuccess: applyProgress,
    onError: () => toast.error('Не удалось сохранить прогресс. Попробуйте ещё раз.'),
  });

  const resetMutation = useMutation({
    mutationFn: (lessonKey: string) => resetTrainingLesson(lessonKey),
    onSuccess: applyProgress,
    onError: () => toast.error('Не удалось сохранить прогресс. Попробуйте ещё раз.'),
  });

  const completedSet = useMemo(() => new Set(completed), [completed]);
  const doneCount = TRAINING_LESSONS.filter((lesson) => completedSet.has(lesson.key)).length;
  const total = TRAINING_LESSONS.length;
  const percent = Math.round((doneCount / total) * 100);
  const nextLesson =
    TRAINING_LESSONS.find((lesson) => !completedSet.has(lesson.key)) ?? TRAINING_LESSONS[0];
  const courseFinished = doneCount === total;

  const filteredFaq = useMemo(() => {
    const query = faqQuery.trim().toLowerCase();
    if (!query) return TRAINING_FAQ;
    return TRAINING_FAQ.filter(
      (item) =>
        item.question.toLowerCase().includes(query) ||
        item.answer.toLowerCase().includes(query),
    );
  }, [faqQuery]);

  const openLesson = (lesson: TrainingLesson) => setActiveLesson(lesson);

  const handleComplete = (lesson: TrainingLesson) => {
    if (!completedSet.has(lesson.key) && !completeMutation.isPending) {
      completeMutation.mutate(lesson.key);
    }
  };

  const handleReset = (lesson: TrainingLesson) => {
    if (resetMutation.isPending) return;
    resetMutation.mutate(lesson.key);
  };

  const modalIndex = activeLesson
    ? TRAINING_LESSONS.findIndex((lesson) => lesson.key === activeLesson.key)
    : -1;
  const nextAfterActive =
    modalIndex >= 0 && modalIndex < TRAINING_LESSONS.length - 1
      ? TRAINING_LESSONS[modalIndex + 1]
      : null;

  return (
    <div className="space-y-6 p-4 sm:p-6 lg:p-8">
      <header>
        <h1 className="text-2xl font-semibold text-gray-900 sm:text-3xl">Обучение</h1>
        <p className="mt-1 text-gray-600">
          Шесть коротких уроков о том, как работать в кабинете. Всё вместе —{' '}
          {formatLessonDuration(TRAINING_TOTAL_DURATION)}.
        </p>
      </header>

      <section className="overflow-hidden rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-700 text-white shadow-lg">
        <div className="flex flex-col gap-6 p-6 sm:p-8 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-xl">
            <p className="text-sm font-medium text-white/70">
              {courseFinished ? 'Курс пройден' : 'Ваш прогресс'}
            </p>
            <p className="mt-1 text-2xl font-semibold sm:text-3xl">
              {doneCount} из {total} уроков
            </p>
            <div
              className="mt-4 h-2 w-full overflow-hidden rounded-full bg-white/20"
              role="progressbar"
              aria-valuenow={percent}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Прогресс обучения"
            >
              <div
                className="h-full rounded-full bg-white transition-all duration-500"
                style={{ width: `${percent}%` }}
              />
            </div>
            <p className="mt-2 text-sm text-white/80">
              {courseFinished
                ? 'Все уроки позади. Конспекты и инструкции остаются под рукой.'
                : `Следующий урок: «${nextLesson.title}» · ${formatLessonDuration(nextLesson.duration)}`}
            </p>
          </div>

          <button
            type="button"
            onClick={() => openLesson(nextLesson)}
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-semibold text-blue-700 shadow-sm transition hover:bg-blue-50"
          >
            <Play className="h-4 w-4 fill-current" aria-hidden="true" />
            {doneCount === 0 ? 'Начать обучение' : courseFinished ? 'Повторить первый урок' : 'Продолжить обучение'}
          </button>
        </div>
      </section>

      <section>
        <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Уроки курса</h2>
            <p className="text-sm text-gray-600">По порядку — каждый занимает меньше минуты.</p>
          </div>
          <p className="text-sm text-gray-500">
            <Clock className="mr-1 inline h-4 w-4 align-[-2px]" aria-hidden="true" />
            всего {formatLessonDuration(TRAINING_TOTAL_DURATION)}
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          {TRAINING_LESSONS.map((lesson) => {
            const isDone = completedSet.has(lesson.key);
            return (
              <article
                key={lesson.key}
                className="group flex flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
              >
                <button
                  type="button"
                  onClick={() => openLesson(lesson)}
                  aria-label={`Смотреть урок: ${lesson.title}`}
                  className="relative aspect-video overflow-hidden bg-slate-200"
                >
                  <img
                    src={lesson.cover}
                    alt=""
                    loading="lazy"
                    decoding="async"
                    className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.03]"
                  />
                  <span className="absolute inset-0 bg-gradient-to-t from-black/55 via-black/5 to-transparent" />
                  <span className="absolute left-4 top-3 rounded-lg bg-white/15 px-2 py-1 text-xs font-semibold text-white backdrop-blur-sm">
                    Урок {lesson.number}
                  </span>
                  <span className="absolute bottom-3 right-3 rounded-lg bg-black/70 px-2 py-0.5 text-xs font-medium text-white backdrop-blur-sm">
                    {formatLessonDuration(lesson.duration)}
                  </span>
                  <span className="absolute inset-0 flex items-center justify-center opacity-0 transition group-hover:opacity-100 group-focus-visible:opacity-100">
                    <span className="flex h-14 w-14 items-center justify-center rounded-full bg-white shadow-lg">
                      <Play className="ml-0.5 h-6 w-6 fill-slate-900 text-slate-900" aria-hidden="true" />
                    </span>
                  </span>
                </button>

                <div className="flex flex-1 flex-col p-5">
                  <h3 className="font-semibold text-gray-900">{lesson.title}</h3>
                  <p className="mt-1 line-clamp-2 flex-1 text-sm leading-6 text-gray-600">
                    {lesson.subtitle}
                  </p>
                  <button
                    type="button"
                    onClick={() => openLesson(lesson)}
                    className="mt-3 inline-flex items-center gap-1.5 self-start text-sm font-medium text-blue-600 hover:underline"
                  >
                    {isDone ? 'Пересмотреть' : 'Смотреть урок'}
                    <ArrowRight className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      {webinars.length > 0 && (
        <section>
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Записи вебинаров</h2>
            <p className="text-sm text-gray-600">
              Подробные разборы от команды ЮРИТЕХ — на 2–6 минут, по конкретным процедурам.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {webinars.map((video) => (
              <WebinarCard key={video.id} video={video} onPlay={() => setActiveWebinar(video)} />
            ))}
          </div>
        </section>
      )}

      <section className="rounded-2xl border border-gray-200 bg-white">
        <div className="flex flex-col gap-3 border-b border-gray-200 p-3 sm:flex-row sm:items-center sm:justify-between sm:p-4">
          <div className="grid grid-cols-3 gap-2 sm:flex sm:flex-wrap">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  aria-pressed={isActive}
                  className={`flex flex-col items-center justify-center gap-1 rounded-xl px-2 py-2.5 text-center text-xs font-medium leading-tight transition sm:flex-row sm:gap-2 sm:px-4 sm:py-2 sm:text-sm ${
                    isActive
                      ? 'bg-gray-900 text-white'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  {tab.label}
                </button>
              );
            })}
          </div>

          {activeTab === 'faq' && (
            <label className="relative sm:w-72">
              <span className="sr-only">Поиск по частым вопросам</span>
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" aria-hidden="true" />
              <input
                type="search"
                value={faqQuery}
                onChange={(event) => setFaqQuery(event.target.value)}
                placeholder="Поиск по вопросам"
                className="w-full rounded-xl border border-gray-300 py-2 pl-9 pr-3 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
              />
            </label>
          )}
        </div>

        <div className="p-4 sm:p-6">
          {activeTab === 'faq' && (
            <div className="space-y-2">
              {filteredFaq.length === 0 && (
                <p className="py-8 text-center text-sm text-gray-500">
                  По запросу «{faqQuery}» ничего не нашлось. Напишите в чат — подскажем.
                </p>
              )}
              {filteredFaq.map((item) => {
                const isExpanded = expandedFaq === item.id;
                return (
                  <div key={item.id} className="overflow-hidden rounded-xl border border-gray-200">
                    <button
                      type="button"
                      onClick={() => setExpandedFaq(isExpanded ? null : item.id)}
                      aria-expanded={isExpanded}
                      className="flex w-full items-center justify-between gap-4 px-4 py-3.5 text-left transition hover:bg-gray-50"
                    >
                      <span className="font-medium text-gray-900">{item.question}</span>
                      <ChevronDown
                        className={`h-4 w-4 shrink-0 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                        aria-hidden="true"
                      />
                    </button>
                    {isExpanded && (
                      <p className="border-t border-gray-100 px-4 py-3.5 text-[15px] leading-6 text-gray-700">
                        {item.answer}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {activeTab === 'notes' && (
            <div className="grid gap-4 sm:grid-cols-2">
              {TRAINING_NOTES.map((note) => {
                const styles = NOTE_STYLES[note.icon] ?? NOTE_STYLES.default;
                const Icon = note.icon === 'info' ? Info : AlertCircle;
                return (
                  <div key={note.id} className={`rounded-xl border p-4 ${styles.wrap}`}>
                    <div className="flex gap-3">
                      <Icon className={`mt-0.5 h-5 w-5 shrink-0 ${styles.icon}`} aria-hidden="true" />
                      <div>
                        <h3 className="font-semibold text-gray-900">{note.title}</h3>
                        <p className="mt-1 text-sm leading-6 text-gray-700">{note.description}</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {activeTab === 'instructions' && (
            <div className="grid gap-4 lg:grid-cols-2">
              {TRAINING_INSTRUCTIONS.map((instruction) => (
                <div key={instruction.id} className="rounded-xl border border-gray-200 p-5">
                  <h3 className="font-semibold text-gray-900">{instruction.title}</h3>
                  <p className="mt-1 text-sm text-gray-600">{instruction.summary}</p>
                  <ol className="mt-4 space-y-2.5">
                    {instruction.steps.map((step, index) => (
                      <li key={step} className="flex gap-3 text-sm leading-6 text-gray-700">
                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-50 text-xs font-semibold text-blue-600">
                          {index + 1}
                        </span>
                        <span>{step}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-2xl border border-gray-200 bg-white p-5">
          <h2 className="font-semibold text-gray-900">Нужна помощь по кабинету?</h2>
          <p className="mt-1 text-sm text-gray-600">
            Напишите в техподдержку — ответим прямо в кабинете.
          </p>
          <Link
            to="/dashboard/chat"
            className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:underline"
          >
            Открыть чат
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-5">
          <h2 className="font-semibold text-gray-900">Реквизиты для суда</h2>
          <p className="mt-1 text-sm text-gray-600">
            Копируются одним нажатием — вставляйте прямо в заявление.
          </p>
          <Link
            to="/dashboard/sro"
            className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:underline"
          >
            Открыть реквизиты СРО
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </div>
      </section>

      {activeWebinar && (
        <TrainingWebinarModal video={activeWebinar} onClose={() => setActiveWebinar(null)} />
      )}

      {activeLesson && (
        <TrainingLessonModal
          lesson={activeLesson}
          completed={completedSet.has(activeLesson.key)}
          nextLesson={nextAfterActive}
          onClose={() => setActiveLesson(null)}
          onComplete={() => handleComplete(activeLesson)}
          onReset={() => handleReset(activeLesson)}
          onNext={() => nextAfterActive && setActiveLesson(nextAfterActive)}
        />
      )}
    </div>
  );
}
