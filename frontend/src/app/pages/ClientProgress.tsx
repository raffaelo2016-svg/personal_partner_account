import { useState } from 'react';
import { CheckCircle, Circle, Clock, FileText, Send, Gavel, AlertCircle, FileCog } from 'lucide-react';

interface StatusStep {
  id: number;
  title: string;
  substatus?: string;
  status: 'completed' | 'in-progress' | 'pending' | 'rejected';
  date?: string;
  time?: string;
  comment?: string;
  progress?: number;
}

export default function ClientProgress() {
  const [activeStageIndex, setActiveStageIndex] = useState(1);

  const stages: { id: number; title: string; icon: typeof FileText; color: string; steps: StatusStep[] }[] = [
    {
      id: 1,
      title: 'Сбор документов',
      icon: FileText,
      color: 'blue',
      steps: [
        {
          id: 1,
          title: 'Загрузка документов',
          status: 'completed',
          progress: 100,
          date: '10.02.2026',
          time: '14:30',
          comment: 'Все обязательные документы загружены',
        },
      ],
    },
    {
      id: 2,
      title: 'Формирование документов',
      icon: FileCog,
      color: 'indigo',
      steps: [
        {
          id: 1,
          title: 'Генерация',
          substatus: 'Автоматическое формирование документов',
          status: 'completed',
          date: '11.02.2026',
          time: '10:15',
          comment: 'Документы успешно сформированы системой',
        },
        {
          id: 2,
          title: 'Проверка',
          substatus: 'Проверка корректности данных',
          status: 'in-progress',
          date: '11.02.2026',
          time: '10:20',
          comment: 'Документы находятся на проверке юристом',
        },
        {
          id: 3,
          title: 'Готово',
          substatus: 'Документы готовы к отправке',
          status: 'pending',
        },
      ],
    },
    {
      id: 3,
      title: 'Отправка в суд',
      icon: Send,
      color: 'orange',
      steps: [
        {
          id: 1,
          title: 'Подготовка пакета',
          substatus: 'Формирование финального пакета',
          status: 'pending',
        },
        {
          id: 2,
          title: 'Отправлено',
          substatus: 'Документы отправлены в арбитражный суд',
          status: 'pending',
        },
        {
          id: 3,
          title: 'Ожидание принятия',
          substatus: 'Ожидание решения суда',
          status: 'pending',
        },
      ],
    },
    {
      id: 4,
      title: 'Документы приняты / не приняты',
      icon: Gavel,
      color: 'emerald',
      steps: [
        {
          id: 1,
          title: 'Приняты судом',
          substatus: 'Дело принято к производству',
          status: 'pending',
        },
        {
          id: 2,
          title: 'Оставлены без движения',
          substatus: 'Требуется устранение недостатков',
          status: 'pending',
        },
        {
          id: 3,
          title: 'Возвращены',
          substatus: 'Документы возвращены на доработку',
          status: 'pending',
        },
        {
          id: 4,
          title: 'Отказано в принятии',
          substatus: 'Суд отказал в принятии заявления',
          status: 'pending',
        },
      ],
    },
    {
      id: 5,
      title: 'Ожидание заседания',
      icon: Clock,
      color: 'cyan',
      steps: [
        {
          id: 1,
          title: 'Назначено судебное заседание',
          substatus: 'Определение даты и времени заседания',
          status: 'pending',
        },
        {
          id: 2,
          title: 'Подготовка к заседанию',
          substatus: 'Подготовка необходимых материалов',
          status: 'pending',
        },
        {
          id: 3,
          title: 'Ожидание явки',
          substatus: 'Ожидание даты проведения заседания',
          status: 'pending',
        },
      ],
    },
  ];

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-6 h-6 text-green-600" />;
      case 'in-progress':
        return <Clock className="w-6 h-6 text-blue-600 animate-pulse" />;
      case 'rejected':
        return <AlertCircle className="w-6 h-6 text-red-600" />;
      default:
        return <Circle className="w-6 h-6 text-gray-300" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-700 border-green-300';
      case 'in-progress':
        return 'bg-blue-100 text-blue-700 border-blue-300';
      case 'rejected':
        return 'bg-red-100 text-red-700 border-red-300';
      default:
        return 'bg-gray-100 text-gray-500 border-gray-300';
    }
  };

  const calculateOverallProgress = () => {
    const totalSteps = stages.reduce((acc, stage) => acc + stage.steps.length, 0);
    const completedSteps = stages.reduce(
      (acc, stage) => acc + stage.steps.filter((step) => step.status === 'completed').length,
      0
    );
    return Math.round((completedSteps / totalSteps) * 100);
  };

  const getStageStatus = (stage: typeof stages[0]) => {
    const allCompleted = stage.steps.every((step) => step.status === 'completed');
    const hasInProgress = stage.steps.some((step) => step.status === 'in-progress');
    const hasRejected = stage.steps.some((step) => step.status === 'rejected');
    
    if (allCompleted) return 'completed';
    if (hasRejected) return 'rejected';
    if (hasInProgress) return 'in-progress';
    return 'pending';
  };

  const getStageColorClasses = (status: string, color: string) => {
    if (status === 'completed') {
      return {
        bg: 'bg-green-500',
        border: 'border-green-500',
        text: 'text-green-700',
        lightBg: 'bg-green-50',
      };
    }
    if (status === 'in-progress') {
      const colorMap: Record<string, { bg: string; border: string; text: string; lightBg: string }> = {
        blue: { bg: 'bg-blue-500', border: 'border-blue-500', text: 'text-blue-700', lightBg: 'bg-blue-50' },
        indigo: { bg: 'bg-indigo-500', border: 'border-indigo-500', text: 'text-indigo-700', lightBg: 'bg-indigo-50' },
        orange: { bg: 'bg-orange-500', border: 'border-orange-500', text: 'text-orange-700', lightBg: 'bg-orange-50' },
        emerald: { bg: 'bg-emerald-500', border: 'border-emerald-500', text: 'text-emerald-700', lightBg: 'bg-emerald-50' },
        cyan: { bg: 'bg-cyan-500', border: 'border-cyan-500', text: 'text-cyan-700', lightBg: 'bg-cyan-50' },
      };
      return colorMap[color] || colorMap.blue;
    }
    if (status === 'rejected') {
      return {
        bg: 'bg-red-500',
        border: 'border-red-500',
        text: 'text-red-700',
        lightBg: 'bg-red-50',
      };
    }
    return {
      bg: 'bg-gray-300',
      border: 'border-gray-300',
      text: 'text-gray-500',
      lightBg: 'bg-gray-50',
    };
  };

  const activeStage = stages[activeStageIndex];

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-semibold text-gray-900 mb-2">
          Прогресс-бар статусов
        </h1>
        <p className="text-gray-600">
          В карточке клиента отображается визуальный прогресс процедуры
        </p>
      </div>

      {/* Overall Progress Card */}
      <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl shadow-sm p-6 border border-blue-100">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-gray-900">Общий прогресс</h2>
          <div className="flex items-center gap-2">
            <span className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
              {calculateOverallProgress()}%
            </span>
          </div>
        </div>
        <div className="relative w-full bg-white/50 rounded-full h-3 overflow-hidden shadow-inner">
          <div
            className="absolute inset-y-0 left-0 bg-gradient-to-r from-blue-500 via-indigo-500 to-purple-500 rounded-full transition-all duration-700 ease-out"
            style={{ width: `${calculateOverallProgress()}%` }}
          >
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-pulse" />
          </div>
        </div>
      </div>

      {/* Horizontal Stepper */}
      <div className="bg-white rounded-2xl shadow-sm p-6 border border-gray-200">
        <div className="relative">
          {/* Progress Line */}
          <div className="absolute top-6 left-0 right-0 h-1 bg-gray-200 rounded-full" style={{ zIndex: 0 }} />
          <div
            className="absolute top-6 left-0 h-1 bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full transition-all duration-700"
            style={{
              width: `${(activeStageIndex / (stages.length - 1)) * 100}%`,
              zIndex: 0,
            }}
          />

          {/* Stages */}
          <div className="relative flex justify-between" style={{ zIndex: 1 }}>
            {stages.map((stage, index) => {
              const StageIcon = stage.icon;
              const stageStatus = getStageStatus(stage);
              const colors = getStageColorClasses(stageStatus, stage.color);
              const isActive = index === activeStageIndex;

              return (
                <div
                  key={stage.id}
                  className="flex flex-col items-center cursor-pointer group"
                  style={{ width: `${100 / stages.length}%` }}
                  onClick={() => setActiveStageIndex(index)}
                >
                  {/* Icon Circle */}
                  <div
                    className={`relative w-12 h-12 rounded-full flex items-center justify-center transition-all duration-300 ${
                      colors.bg
                    } ${
                      isActive ? 'scale-110 shadow-lg ring-4 ring-white' : 'scale-100'
                    } group-hover:scale-110`}
                  >
                    {stageStatus === 'completed' ? (
                      <CheckCircle className="w-6 h-6 text-white" />
                    ) : stageStatus === 'in-progress' ? (
                      <StageIcon className="w-6 h-6 text-white animate-pulse" />
                    ) : stageStatus === 'rejected' ? (
                      <AlertCircle className="w-6 h-6 text-white" />
                    ) : (
                      <StageIcon className="w-6 h-6 text-white" />
                    )}
                  </div>

                  {/* Stage Title */}
                  <div className="mt-3 text-center px-2">
                    <p
                      className={`text-xs font-semibold transition-colors ${
                        isActive ? colors.text : 'text-gray-600'
                      }`}
                    >
                      {stage.title}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Active Stage Details */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
        {/* Stage Header */}
        <div className={`p-6 ${getStageColorClasses(getStageStatus(activeStage), activeStage.color).lightBg} border-b border-gray-200`}>
          <div className="flex items-center gap-4">
            {(() => {
              const StageIcon = activeStage.icon;
              const colors = getStageColorClasses(getStageStatus(activeStage), activeStage.color);
              return (
                <>
                  <div className={`w-14 h-14 rounded-xl ${colors.bg} flex items-center justify-center shadow-lg`}>
                    <StageIcon className="w-7 h-7 text-white" />
                  </div>
                  <div className="flex-1">
                    <h3 className="text-xl font-bold text-gray-900">
                      {activeStageIndex + 1}. {activeStage.title}
                    </h3>
                    <p className="text-sm text-gray-600 mt-1">
                      {activeStage.steps.filter((s) => s.status === 'completed').length} из {activeStage.steps.length} завершено
                    </p>
                  </div>
                </>
              );
            })()}
          </div>
        </div>

        {/* Steps */}
        <div className="p-6 space-y-4">
          {activeStage.steps.map((step, stepIndex) => (
            <div
              key={step.id}
              className={`relative border-2 rounded-xl p-5 transition-all ${getStatusColor(
                step.status
              )} hover:shadow-md`}
            >
              <div className="flex items-start gap-4">
                {/* Icon */}
                <div className="relative z-10 bg-white rounded-full p-1 shadow-sm">
                  {getStatusIcon(step.status)}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-4 mb-2">
                    <div className="flex-1">
                      <h4 className="font-semibold text-gray-900 text-lg">{step.title}</h4>
                      {step.substatus && (
                        <p className="text-sm text-gray-600 mt-1">{step.substatus}</p>
                      )}
                    </div>
                    {step.date && step.time && (
                      <div className="text-right flex-shrink-0">
                        <p className="text-sm font-medium text-gray-900">{step.date}</p>
                        <p className="text-xs text-gray-600">{step.time}</p>
                      </div>
                    )}
                  </div>

                  {/* Progress Bar */}
                  {step.progress !== undefined && (
                    <div className="mb-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium text-gray-600">Прогресс выполнения</span>
                        <span className="text-xs font-bold text-gray-900">
                          {step.progress}%
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
                        <div
                          className="bg-gradient-to-r from-blue-500 to-indigo-500 h-2.5 rounded-full transition-all duration-500"
                          style={{ width: `${step.progress}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Comment */}
                  {step.comment && (
                    <div className="mt-3 p-4 bg-white/70 rounded-lg border border-gray-200">
                      <p className="text-sm text-gray-700">
                        <span className="font-semibold text-gray-900">💬 Комментарий:</span>{' '}
                        {step.comment}
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Connecting Line */}
              {stepIndex < activeStage.steps.length - 1 && (
                <div className="absolute left-9 top-14 w-0.5 h-full bg-gray-200" />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="bg-white rounded-2xl shadow-sm p-6 border border-gray-200">
        <h3 className="font-semibold text-gray-900 mb-4">Легенда статусов</h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="flex items-center gap-3 p-3 rounded-lg bg-green-50 border border-green-200">
            <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0" />
            <span className="text-sm font-medium text-gray-700">Завершено</span>
          </div>
          <div className="flex items-center gap-3 p-3 rounded-lg bg-blue-50 border border-blue-200">
            <Clock className="w-5 h-5 text-blue-600 flex-shrink-0" />
            <span className="text-sm font-medium text-gray-700">В процессе</span>
          </div>
          <div className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 border border-gray-200">
            <Circle className="w-5 h-5 text-gray-400 flex-shrink-0" />
            <span className="text-sm font-medium text-gray-700">Ожидает</span>
          </div>
          <div className="flex items-center gap-3 p-3 rounded-lg bg-red-50 border border-red-200">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
            <span className="text-sm font-medium text-gray-700">Отклонено</span>
          </div>
        </div>
      </div>
    </div>
  );
}