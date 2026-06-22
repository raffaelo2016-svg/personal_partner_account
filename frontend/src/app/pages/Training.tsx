import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Play, Book, AlertCircle, HelpCircle, FileText, ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import {
  fetchTrainingVideos,
  fetchFAQ,
  fetchInstructions,
  fetchImportantNotes,
  type FAQData,
  type ImportantNoteData,
  type InstructionData,
  type TrainingVideoData,
} from '../api/training';

function formatDuration(seconds: number | null): string {
  if (!seconds) return '0:00';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

const ICON_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  alert: { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-600' },
  warning: { bg: 'bg-orange-50', border: 'border-orange-200', text: 'text-orange-600' },
  info: { bg: 'bg-purple-50', border: 'border-purple-200', text: 'text-purple-600' },
  default: { bg: 'bg-yellow-50', border: 'border-yellow-200', text: 'text-yellow-600' },
};

const PLACEHOLDER_CREATED_AT = '2026-01-01T00:00:00.000Z';

const PLACEHOLDER_VIDEOS: TrainingVideoData[] = [
  {
    id: 'placeholder-video-intro',
    title: 'Введение в платформу ЮРИТЕХ Partner',
    description: 'Основные возможности и интерфейс платформы',
    duration: 525,
    video_url: '#',
    thumbnail_url: '/training/video-intro.svg',
    order: 1,
    created_at: PLACEHOLDER_CREATED_AT,
  },
  {
    id: 'placeholder-video-client',
    title: 'Добавление нового клиента',
    description: 'Пошаговая инструкция по созданию карточки клиента',
    duration: 750,
    video_url: '#',
    thumbnail_url: '/training/video-client.svg',
    order: 2,
    created_at: PLACEHOLDER_CREATED_AT,
  },
  {
    id: 'placeholder-video-docs',
    title: 'Работа с документами',
    description: 'Загрузка, управление и формирование документов',
    duration: 920,
    video_url: '#',
    thumbnail_url: '/training/video-documents.svg',
    order: 3,
    created_at: PLACEHOLDER_CREATED_AT,
  },
  {
    id: 'placeholder-video-tasks',
    title: 'Система задач и уведомлений',
    description: 'Создание задач, отслеживание дедлайнов и напоминаний',
    duration: 615,
    video_url: '#',
    thumbnail_url: '/training/video-tasks.svg',
    order: 4,
    created_at: PLACEHOLDER_CREATED_AT,
  },
  {
    id: 'placeholder-video-finance',
    title: 'Финансы и оплаты',
    description: 'Управление судебными расходами и платежами',
    duration: 580,
    video_url: '#',
    thumbnail_url: '/training/video-finance.svg',
    order: 5,
    created_at: PLACEHOLDER_CREATED_AT,
  },
  {
    id: 'placeholder-video-chat',
    title: 'Чат и коммуникация с ЮРИТЕХ',
    description: 'Эффективное общение через встроенный чат',
    duration: 390,
    video_url: '#',
    thumbnail_url: '/training/video-chat.svg',
    order: 6,
    created_at: PLACEHOLDER_CREATED_AT,
  },
];

const PLACEHOLDER_FAQ: FAQData[] = [
  {
    id: 'placeholder-faq-approval',
    question: 'Когда партнёр получает доступ к кабинету?',
    answer: 'После отправки заявки администратор проверяет данные партнёра. После одобрения можно войти через страницу входа и работать в кабинете.',
    order: 1,
    created_at: PLACEHOLDER_CREATED_AT,
  },
  {
    id: 'placeholder-faq-client',
    question: 'Как добавить нового клиента?',
    answer: 'Откройте раздел "Клиенты" или пункт "Добавить клиента", заполните карточку клиента и сохраните данные. После этого клиент появится в общем списке.',
    order: 2,
    created_at: PLACEHOLDER_CREATED_AT,
  },
  {
    id: 'placeholder-faq-files',
    question: 'Где загружать документы по клиенту?',
    answer: 'Документы загружаются в карточке клиента. Система сохранит файлы и покажет их в истории работы по делу.',
    order: 3,
    created_at: PLACEHOLDER_CREATED_AT,
  },
  {
    id: 'placeholder-faq-payments',
    question: 'Как отслеживать судебные расходы?',
    answer: 'Раздел "Финансы" показывает начисления, сроки оплаты, историю платежей и задолженность по клиентам.',
    order: 4,
    created_at: PLACEHOLDER_CREATED_AT,
  },
];

const PLACEHOLDER_IMPORTANT: ImportantNoteData[] = [
  {
    id: 'placeholder-important-data',
    title: 'Проверяйте данные клиента перед подачей',
    description: 'Ошибки в ФИО, телефоне, паспортных данных или реквизитах могут замедлить подготовку документов и движение дела.',
    icon: 'warning',
    order: 1,
    created_at: PLACEHOLDER_CREATED_AT,
  },
  {
    id: 'placeholder-important-payment',
    title: 'Следите за сроками оплаты',
    description: 'Судебные расходы отображаются в разделе финансов. Просрочка может ограничить доступ к отдельным возможностям платформы.',
    icon: 'alert',
    order: 2,
    created_at: PLACEHOLDER_CREATED_AT,
  },
  {
    id: 'placeholder-important-chat',
    title: 'Используйте чат для рабочих вопросов',
    description: 'Если по клиенту нужна помощь или уточнение, пишите в чат. Так история коммуникации останется в кабинете.',
    icon: 'info',
    order: 3,
    created_at: PLACEHOLDER_CREATED_AT,
  },
  {
    id: 'placeholder-important-tasks',
    title: 'Не пропускайте задачи',
    description: 'Задачи помогают не терять дедлайны по документам, оплатам и коммуникации с клиентами.',
    icon: 'default',
    order: 4,
    created_at: PLACEHOLDER_CREATED_AT,
  },
];

const PLACEHOLDER_INSTRUCTIONS: InstructionData[] = [
  {
    id: 'placeholder-instruction-start',
    title: 'Первый вход и настройка кабинета',
    steps: {
      items: [
        'Войдите в кабинет через страницу входа.',
        'Откройте настройки и проверьте контактные данные.',
        'Убедитесь, что уведомления включены и email указан корректно.',
      ],
    },
    order: 1,
    created_at: PLACEHOLDER_CREATED_AT,
  },
  {
    id: 'placeholder-instruction-client',
    title: 'Создание карточки клиента',
    steps: {
      items: [
        'Перейдите в раздел "Добавить клиента".',
        'Заполните основные данные и тип процедуры.',
        'Сохраните карточку и загрузите необходимые документы.',
      ],
    },
    order: 2,
    created_at: PLACEHOLDER_CREATED_AT,
  },
  {
    id: 'placeholder-instruction-finance',
    title: 'Работа с начислениями',
    steps: {
      items: [
        'Откройте раздел "Финансы".',
        'Проверьте сумму, срок оплаты и статус начисления.',
        'После оплаты контролируйте обновление статуса в истории.',
      ],
    },
    order: 3,
    created_at: PLACEHOLDER_CREATED_AT,
  },
];

export default function Training() {
  const [activeTab, setActiveTab] = useState<'videos' | 'faq' | 'important' | 'instructions'>('videos');
  const [expandedFaq, setExpandedFaq] = useState<string | null>(null);

  const { data: videos = [], isLoading: videosLoading } = useQuery({
    queryKey: ['training', 'videos'],
    queryFn: fetchTrainingVideos,
  });

  const { data: faqItems = [], isLoading: faqLoading } = useQuery({
    queryKey: ['training', 'faq'],
    queryFn: fetchFAQ,
  });

  const { data: importantItems = [], isLoading: importantLoading } = useQuery({
    queryKey: ['training', 'important'],
    queryFn: fetchImportantNotes,
  });

  const { data: instructions = [], isLoading: instructionsLoading } = useQuery({
    queryKey: ['training', 'instructions'],
    queryFn: fetchInstructions,
  });

  const tabs = [
    { id: 'videos', label: 'Видеоинструкции', icon: Play },
    { id: 'faq', label: 'Частые вопросы', icon: HelpCircle },
    { id: 'important', label: 'Важно', icon: AlertCircle },
    { id: 'instructions', label: 'Инструкции', icon: FileText },
  ];

  const isLoading =
    (activeTab === 'videos' && videosLoading) ||
    (activeTab === 'faq' && faqLoading) ||
    (activeTab === 'important' && importantLoading) ||
    (activeTab === 'instructions' && instructionsLoading);

  const displayVideos = videos.length > 0 ? videos : PLACEHOLDER_VIDEOS;
  const displayFaqItems = faqItems.length > 0 ? faqItems : PLACEHOLDER_FAQ;
  const displayImportantItems = importantItems.length > 0 ? importantItems : PLACEHOLDER_IMPORTANT;
  const displayInstructions = instructions.length > 0 ? instructions : PLACEHOLDER_INSTRUCTIONS;

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-gray-900 mb-2">Обучение</h1>
        <p className="text-gray-600">Все необходимое для эффективной работы с платформой</p>
      </div>

      <div className="bg-white rounded-2xl border border-gray-200 p-2">
        <div className="flex gap-2">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={`flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-xl font-medium transition-all ${
                  isActive
                    ? 'bg-indigo-600 text-white shadow-lg'
                    : 'text-gray-600 hover:bg-gray-50'
                }`}
              >
                <Icon className="w-5 h-5" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      <div>
        {isLoading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
          </div>
        )}

        {activeTab === 'videos' && !videosLoading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {displayVideos.map((video) => (
              <div key={video.id} className="bg-white rounded-2xl border border-gray-200 overflow-hidden hover:shadow-lg transition-all group">
                <div className="relative h-48 bg-gray-100 overflow-hidden">
                  {video.thumbnail_url ? (
                    <img
                      src={video.thumbnail_url}
                      alt={video.title}
                      loading="lazy"
                      decoding="async"
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center bg-indigo-50">
                      <Play className="w-12 h-12 text-indigo-300" />
                    </div>
                  )}
                  <a
                    href={video.video_url}
                    target={video.video_url === '#' ? undefined : '_blank'}
                    rel={video.video_url === '#' ? undefined : 'noopener noreferrer'}
                    aria-label={`Открыть видео: ${video.title}`}
                    className="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={(e) => {
                      if (video.video_url === '#') e.preventDefault();
                    }}
                  >
                    <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center">
                      <Play className="w-8 h-8 text-indigo-600 ml-1" />
                    </div>
                  </a>
                  <div className="absolute bottom-3 right-3 px-2 py-1 bg-black/70 backdrop-blur-sm text-white text-xs rounded-lg font-medium">
                    {formatDuration(video.duration)}
                  </div>
                </div>
                <div className="p-5">
                  <h3 className="font-semibold text-gray-900 mb-2">{video.title}</h3>
                  {video.description && (
                    <p className="text-sm text-gray-600">{video.description}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'faq' && !faqLoading && (
          <div className="space-y-3">
            {displayFaqItems.map((item) => {
              const isExpanded = expandedFaq === item.id;
              return (
                <div key={item.id} className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
                  <button
                    onClick={() => setExpandedFaq(isExpanded ? null : item.id)}
                    className="w-full px-6 py-5 flex items-center justify-between hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex items-start gap-4 flex-1 text-left">
                      <div className="w-10 h-10 bg-indigo-50 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5">
                        <HelpCircle className="w-5 h-5 text-indigo-600" />
                      </div>
                      <span className="font-medium text-gray-900">{item.question}</span>
                    </div>
                    {isExpanded ? (
                      <ChevronDown className="w-5 h-5 text-gray-400 flex-shrink-0" />
                    ) : (
                      <ChevronRight className="w-5 h-5 text-gray-400 flex-shrink-0" />
                    )}
                  </button>
                  {isExpanded && (
                    <div className="px-6 pb-5 pl-20">
                      <p className="text-gray-700 leading-relaxed">{item.answer}</p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {activeTab === 'important' && !importantLoading && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {displayImportantItems.map((item) => {
              const colors = ICON_COLORS[item.icon || 'default'] || ICON_COLORS.default;
              return (
                <div key={item.id} className={`rounded-2xl border-2 p-6 ${colors.bg} ${colors.border}`}>
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 bg-white rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm">
                      <AlertCircle className={`w-6 h-6 ${colors.text}`} />
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-900 mb-2">{item.title}</h3>
                      <p className="text-sm text-gray-700 leading-relaxed">{item.description}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {activeTab === 'instructions' && !instructionsLoading && (
          <div className="space-y-6">
            {displayInstructions.map((instruction) => {
              const steps: string[] = Array.isArray(instruction.steps)
                ? instruction.steps
                : (instruction.steps as { items?: string[] }).items || [];
              return (
                <div key={instruction.id} className="bg-white rounded-2xl border border-gray-200 p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 bg-indigo-100 rounded-xl flex items-center justify-center">
                      <Book className="w-5 h-5 text-indigo-600" />
                    </div>
                    <h3 className="text-xl font-semibold text-gray-900">{instruction.title}</h3>
                  </div>
                  <div className="space-y-3 ml-13">
                    {steps.map((step, stepIndex) => (
                      <div key={stepIndex} className="flex items-start gap-4">
                        <div className="w-7 h-7 bg-indigo-100 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                          <span className="text-sm font-semibold text-indigo-600">{stepIndex + 1}</span>
                        </div>
                        <p className="text-gray-700 pt-1">{step}</p>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
