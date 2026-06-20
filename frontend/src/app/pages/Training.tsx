import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Play, Book, AlertCircle, HelpCircle, FileText, ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import {
  fetchTrainingVideos,
  fetchFAQ,
  fetchInstructions,
  fetchImportantNotes,
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
          videos.length === 0 ? (
            <div className="text-center py-20 text-gray-500">
              <Play className="w-12 h-12 mx-auto mb-4 text-gray-300" />
              <p className="text-lg font-medium">Видеоинструкции пока не добавлены</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {videos.map((video) => (
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
                      target="_blank"
                      rel="noopener noreferrer"
                      className="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
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
          )
        )}

        {activeTab === 'faq' && !faqLoading && (
          faqItems.length === 0 ? (
            <div className="text-center py-20 text-gray-500">
              <HelpCircle className="w-12 h-12 mx-auto mb-4 text-gray-300" />
              <p className="text-lg font-medium">Вопросов пока нет</p>
            </div>
          ) : (
            <div className="space-y-3">
              {faqItems.map((item) => {
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
          )
        )}

        {activeTab === 'important' && !importantLoading && (
          importantItems.length === 0 ? (
            <div className="text-center py-20 text-gray-500">
              <AlertCircle className="w-12 h-12 mx-auto mb-4 text-gray-300" />
              <p className="text-lg font-medium">Важных заметок пока нет</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {importantItems.map((item) => {
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
          )
        )}

        {activeTab === 'instructions' && !instructionsLoading && (
          instructions.length === 0 ? (
            <div className="text-center py-20 text-gray-500">
              <FileText className="w-12 h-12 mx-auto mb-4 text-gray-300" />
              <p className="text-lg font-medium">Инструкций пока нет</p>
            </div>
          ) : (
            <div className="space-y-6">
              {instructions.map((instruction) => {
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
          )
        )}
      </div>
    </div>
  );
}
