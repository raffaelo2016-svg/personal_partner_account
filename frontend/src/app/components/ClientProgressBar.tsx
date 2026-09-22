import { FileText, FileCog, Send, Gavel, Clock, RefreshCw, Scale, Target, CheckCircle } from 'lucide-react';

const STATUS_ORDER = [
  'documents_collection',
  'documents_formation',
  'sent_to_court',
  'documents_decision',
  'waiting_hearing',
  'restructuring',
  'auction',
  'realization',
];

const STAGE_DEFS = [
  { key: 'documents_collection', title: 'Сбор документов', icon: FileText, activeGradient: 'from-blue-400 to-blue-600', activeShadow: 'shadow-blue-500/50', activeGlow: 'shadow-blue-400/30' },
  { key: 'documents_formation', title: 'Формирование документов', icon: FileCog, activeGradient: 'from-indigo-400 to-indigo-600', activeShadow: 'shadow-indigo-500/50', activeGlow: 'shadow-indigo-400/30' },
  { key: 'sent_to_court', title: 'Отправка в суд', icon: Send, activeGradient: 'from-orange-400 to-orange-600', activeShadow: 'shadow-orange-500/50', activeGlow: 'shadow-orange-400/30' },
  { key: 'documents_decision', title: 'Документы приняты / не приняты', icon: Gavel, activeGradient: 'from-emerald-400 to-emerald-600', activeShadow: 'shadow-emerald-500/50', activeGlow: 'shadow-emerald-400/30' },
  { key: 'waiting_hearing', title: 'Ожидание заседания', icon: Clock, activeGradient: 'from-cyan-400 to-cyan-600', activeShadow: 'shadow-cyan-500/50', activeGlow: 'shadow-cyan-400/30' },
  { key: 'restructuring', title: 'Реструктуризация', icon: RefreshCw, activeGradient: 'from-purple-400 to-purple-600', activeShadow: 'shadow-purple-500/50', activeGlow: 'shadow-purple-400/30' },
  { key: 'auction', title: 'Торги', icon: Scale, activeGradient: 'from-amber-400 to-amber-600', activeShadow: 'shadow-amber-500/50', activeGlow: 'shadow-amber-400/30' },
  { key: 'realization', title: 'Реализация', icon: Target, activeGradient: 'from-green-400 to-green-600', activeShadow: 'shadow-green-500/50', activeGlow: 'shadow-green-400/30' },
];

interface Props {
  currentStatus: string;
}

export default function ClientProgressBar({ currentStatus }: Props) {
  const currentIndex = STATUS_ORDER.indexOf(currentStatus);

  const stages = STAGE_DEFS.map((def, idx) => {
    let status: 'completed' | 'in-progress' | 'pending';
    let color: { gradient: string; shadow: string; glow: string };

    if (idx < currentIndex) {
      status = 'completed';
      color = { gradient: 'from-green-400 to-green-600', shadow: 'shadow-green-500/50', glow: 'shadow-green-400/30' };
    } else if (idx === currentIndex) {
      status = 'in-progress';
      color = { gradient: def.activeGradient, shadow: def.activeShadow, glow: def.activeGlow };
    } else {
      status = 'pending';
      color = { gradient: 'from-gray-300 to-gray-400', shadow: 'shadow-gray-400/30', glow: 'shadow-gray-300/20' };
    }

    return { ...def, status, color };
  });

  const progress = (() => {
    const completed = stages.filter((s) => s.status === 'completed').length;
    const inProgress = stages.filter((s) => s.status === 'in-progress').length;
    return ((completed + inProgress * 0.5) / stages.length) * 100;
  })();

  return (
    <div className="bg-white rounded-2xl shadow-md border border-gray-200 p-4 sm:p-6">
      <div className="relative lg:hidden">
        <div className="absolute left-6 top-6 bottom-6 w-0.5 bg-gray-200" aria-hidden="true" />
        <ol className="space-y-4" aria-label="Этапы дела">
          {stages.map((stage) => {
            const StageIcon = stage.icon;
            const isActive = stage.status === 'in-progress';
            const isCompleted = stage.status === 'completed';

            return (
              <li key={stage.key} className="relative flex items-center gap-4 min-w-0" aria-current={isActive ? 'step' : undefined}>
                <div className={`relative z-10 flex h-12 w-12 shrink-0 items-center justify-center rounded-full border-2 border-white bg-gradient-to-br ${stage.color.gradient} shadow-md`}>
                  {isCompleted ? <CheckCircle className="h-6 w-6 text-white" aria-hidden="true" /> : <StageIcon className="h-6 w-6 text-white" aria-hidden="true" />}
                </div>
                <div className="min-w-0">
                  <p className={`text-sm font-semibold leading-snug ${isCompleted ? 'text-green-700' : isActive ? 'text-indigo-700' : 'text-gray-600'}`}>
                    {stage.title}
                  </p>
                  <p className="mt-0.5 text-xs text-gray-500">
                    {isCompleted ? 'Завершён' : isActive ? 'Текущий этап' : 'Впереди'}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      </div>

      <div className="hidden overflow-x-auto lg:block">
        <div className="relative min-w-[960px] pb-2">
          <div className="absolute top-8 left-0 right-0 h-1.5 bg-gradient-to-r from-gray-200 via-gray-200 to-gray-200 rounded-full" style={{ zIndex: 0 }} />
          <div
            className="absolute top-8 left-0 h-1.5 bg-gradient-to-r from-green-500 via-indigo-500 to-indigo-500 rounded-full transition-all duration-1000 shadow-lg shadow-indigo-300/50"
            style={{ width: `${progress}%`, zIndex: 0 }}
          />
          <div className="relative flex justify-between" style={{ zIndex: 1 }}>
            {stages.map((stage, index) => {
              const StageIcon = stage.icon;
              const isActive = stage.status === 'in-progress';
              const isCompleted = stage.status === 'completed';

              return (
                <div key={stage.key} className="flex flex-col items-center" style={{ width: `${100 / stages.length}%` }}>
                  <div className="relative group cursor-pointer">
                    {(isActive || isCompleted) && (
                      <div className={`absolute inset-0 rounded-full ${stage.color.glow} blur-xl opacity-60 group-hover:opacity-80 transition-opacity`} />
                    )}
                    <div
                      className={`relative w-16 h-16 rounded-full bg-gradient-to-br ${stage.color.gradient} flex items-center justify-center transition-all duration-300 shadow-lg ${stage.color.shadow} ${isActive ? 'scale-110 shadow-2xl animate-pulse' : 'scale-100'} group-hover:scale-110 group-hover:shadow-2xl border-2 ${isCompleted ? 'border-white' : isActive ? 'border-white/50' : 'border-gray-300/50'}`}
                      style={{
                        boxShadow: `0 4px 14px 0 ${isCompleted ? 'rgba(34,197,94,0.4)' : isActive ? 'rgba(99,102,241,0.4)' : 'rgba(0,0,0,0.1)'}, inset 0 -2px 4px rgba(0,0,0,0.2), inset 0 2px 4px rgba(255,255,255,0.5)`,
                      }}
                    >
                      <div className="absolute inset-0 rounded-full bg-gradient-to-b from-white/40 via-transparent to-transparent" />
                      <div className="relative z-10">
                        {isCompleted ? <CheckCircle className="w-7 h-7 text-white drop-shadow-lg" strokeWidth={2.5} /> : <StageIcon className="w-7 h-7 text-white drop-shadow-lg" strokeWidth={2.5} />}
                      </div>
                      <div className="absolute inset-x-2 bottom-1 h-1 bg-black/10 rounded-full blur-sm" />
                    </div>
                  </div>
                  <div className="mt-4 text-center px-2 max-w-[120px]">
                    <p className={`text-xs font-semibold transition-colors leading-tight ${isCompleted ? 'text-green-700' : isActive ? 'text-indigo-700' : 'text-gray-500'}`}>
                      {stage.title}
                    </p>
                  </div>
                  {index < stages.length - 1 && (
                    <div className="absolute left-1/2 top-8 h-1.5 bg-transparent" style={{ width: `${100 / stages.length}%`, zIndex: -1 }} />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
