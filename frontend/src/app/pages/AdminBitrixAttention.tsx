import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router';
import {
  AlertTriangle,
  CheckSquare,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  FileDown,
  FileText,
  Loader2,
  UserRound,
  UserPlus,
  Users,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  fetchBitrixAttention,
  retryInboundClientImport,
  retryInboundFileImport,
  retryInboundTaskImport,
  type AttentionEntityType,
  type AttentionSyncStatus,
  type BitrixAttentionItem,
} from '../api/bitrixAttention';
import { retryAdminClientBitrix } from '../api/clients';
import { retryFileBitrix } from '../api/upload';
import { retryTaskBitrix } from '../api/tasks';
import { retryPartnerBitrixSync } from '../api/partners';
import BitrixSyncStatus from '../components/BitrixSyncStatus';
import CustomSelect from '../components/ui/CustomSelect';
import { formatDateTime } from '../utils/formatDate';
import { useTimezone } from '../contexts/TimezoneContext';

const ENTITY_CONFIG = {
  partner: { label: 'Партнёры', singular: 'Партнёр', icon: Users, color: 'bg-violet-100 text-violet-700' },
  client: { label: 'Клиенты', singular: 'Клиент', icon: UserRound, color: 'bg-blue-100 text-blue-700' },
  file: { label: 'Документы', singular: 'Документ', icon: FileText, color: 'bg-amber-100 text-amber-700' },
  task: { label: 'Задачи', singular: 'Задача', icon: CheckSquare, color: 'bg-emerald-100 text-emerald-700' },
  inbound_client: { label: 'Входящие клиенты', singular: 'Клиент из Битрикс24', icon: UserPlus, color: 'bg-orange-100 text-orange-700' },
  inbound_task: { label: 'Входящие задачи', singular: 'Задача из Битрикс24', icon: CheckSquare, color: 'bg-teal-100 text-teal-700' },
  inbound_file: { label: 'Входящие документы', singular: 'Документ из Битрикс24', icon: FileDown, color: 'bg-cyan-100 text-cyan-700' },
} as const;

function itemLink(item: BitrixAttentionItem): string | null {
  if (item.entity_type === 'partner') return `/admin/partners/${item.entity_id}`;
  if (item.entity_type === 'client') return `/admin/clients/${item.entity_id}`;
  if (item.entity_type === 'file' && item.parent_id) return `/admin/clients/${item.parent_id}`;
  if (item.entity_type === 'task') return '/admin/tasks';
  return null;
}

async function retryItem(item: BitrixAttentionItem) {
  if (item.entity_type === 'partner') return retryPartnerBitrixSync(item.entity_id);
  if (item.entity_type === 'client') return retryAdminClientBitrix(item.entity_id);
  if (item.entity_type === 'file') return retryFileBitrix(item.entity_id);
  if (item.entity_type === 'task') return retryTaskBitrix(item.entity_id);
  if (item.entity_type === 'inbound_client') return retryInboundClientImport(item.entity_id);
  if (item.entity_type === 'inbound_task') return retryInboundTaskImport(item.entity_id);
  return retryInboundFileImport(item.entity_id);
}

export default function AdminBitrixAttention() {
  const tz = useTimezone();
  const queryClient = useQueryClient();
  const [entityType, setEntityType] = useState<AttentionEntityType>('all');
  const [syncStatus, setSyncStatus] = useState<AttentionSyncStatus>('all');
  const [page, setPage] = useState(1);

  const query = useQuery({
    queryKey: ['bitrixAttention', entityType, syncStatus, page],
    queryFn: () => fetchBitrixAttention({ entity_type: entityType, sync_status: syncStatus, page, page_size: 20 }),
    refetchInterval: 30_000,
  });

  const retryMutation = useMutation({
    mutationFn: retryItem,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bitrixAttention'] });
      queryClient.invalidateQueries({ queryKey: ['adminBitrixAttentionCount'] });
      toast.success('Объект снова поставлен в очередь Битрикс24');
    },
    onError: () => toast.error('Не удалось повторить отправку'),
  });

  const data = query.data;
  const totalAttention = data ? Object.values(data.counts).reduce((sum, value) => sum + value, 0) : 0;

  const selectEntity = (type: AttentionEntityType) => {
    setEntityType(type);
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-gray-900 flex items-center gap-3">
          <AlertTriangle className="w-8 h-8 text-red-500" />
          Требует внимания
        </h1>
        <p className="text-gray-600 mt-2">
          Актуальные проблемы обмена с Битрикс24. Персональные данные в журнале не показываются.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-8 gap-4">
        <button
          type="button"
          onClick={() => selectEntity('all')}
          className={`text-left rounded-xl border p-4 transition-all ${entityType === 'all' ? 'border-red-400 bg-red-50 ring-2 ring-red-100' : 'border-gray-200 bg-white hover:border-gray-300'}`}
        >
          <p className="text-sm text-gray-600">Все проблемы</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{totalAttention}</p>
        </button>
        {(Object.keys(ENTITY_CONFIG) as Array<Exclude<AttentionEntityType, 'all'>>).map((type) => {
          const config = ENTITY_CONFIG[type];
          const Icon = config.icon;
          return (
            <button
              key={type}
              type="button"
              onClick={() => selectEntity(type)}
              className={`text-left rounded-xl border p-4 transition-all ${entityType === type ? 'border-blue-400 bg-blue-50 ring-2 ring-blue-100' : 'border-gray-200 bg-white hover:border-gray-300'}`}
            >
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-600">{config.label}</p>
                <span className={`p-1.5 rounded-lg ${config.color}`}><Icon className="w-4 h-4" /></span>
              </div>
              <p className="text-2xl font-bold text-gray-900 mt-1">{data?.counts[type] ?? 0}</p>
            </button>
          );
        })}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-4 flex flex-col sm:flex-row sm:items-center gap-3">
        <span className="text-sm font-medium text-gray-700">Показать:</span>
        <div className="w-full sm:w-72">
          <CustomSelect
            value={syncStatus}
            onChange={(value) => { setSyncStatus(value as AttentionSyncStatus); setPage(1); }}
            options={[
              { value: 'all', label: 'Все состояния' },
              { value: 'failed', label: 'Ошибка — нужен повтор' },
              { value: 'conflict', label: 'Требуется ручная проверка' },
              { value: 'pending', label: 'Ожидает автоматического повтора' },
              { value: 'not_scheduled', label: 'Не поставлено в очередь' },
            ]}
          />
        </div>
        <p className="text-sm text-gray-500 sm:ml-auto">Найдено: {data?.total ?? 0}</p>
      </div>

      {query.isLoading ? (
        <div className="flex justify-center py-16"><Loader2 className="w-8 h-8 animate-spin text-blue-600" /></div>
      ) : query.isError ? (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
          <p className="font-medium text-red-800">Не удалось загрузить журнал</p>
          <button type="button" onClick={() => query.refetch()} className="mt-3 text-sm text-red-700 underline">Повторить загрузку</button>
        </div>
      ) : data?.items.length === 0 ? (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-10 text-center">
          <p className="text-lg font-semibold text-emerald-800">Проблем не найдено</p>
          <p className="text-sm text-emerald-700 mt-1">По выбранному фильтру вмешательство сотрудников не требуется.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {data?.items.map((item) => {
            const config = ENTITY_CONFIG[item.entity_type];
            const Icon = config.icon;
            const link = itemLink(item);
            const isRetrying = retryMutation.isPending && retryMutation.variables?.entity_id === item.entity_id;
            return (
              <div key={`${item.entity_type}:${item.entity_id}`} className="bg-white rounded-xl border border-gray-200 p-5">
                <div className="flex flex-col lg:flex-row lg:items-center gap-4">
                  <div className="flex items-center gap-3 min-w-0 lg:w-64">
                    <span className={`p-2 rounded-lg flex-shrink-0 ${config.color}`}><Icon className="w-5 h-5" /></span>
                    <div className="min-w-0">
                      <p className="font-medium text-gray-900">{config.singular}</p>
                      <p className="text-xs text-gray-500 font-mono truncate" title={item.remote_id ?? item.entity_id}>
                        {item.entity_type === 'inbound_client'
                          ? `Сделка № ${item.remote_id ?? '—'}`
                          : item.entity_type === 'inbound_file'
                            ? `Запись CRM № ${item.remote_id ?? '—'}`
                            : item.entity_type === 'inbound_task'
                              ? `Задача № ${item.remote_id ?? '—'}`
                            : `ID: ${item.entity_id}`}
                      </p>
                    </div>
                  </div>
                  <div className="flex-1">
                    <BitrixSyncStatus
                      status={item.sync_status}
                      errorCode={item.error_code}
                      isRetrying={isRetrying}
                      onRetry={() => retryMutation.mutate(item)}
                    />
                  </div>
                  <div className="flex items-center gap-3 lg:justify-end">
                    <span className="text-xs text-gray-500 whitespace-nowrap">{formatDateTime(item.occurred_at, tz)}</span>
                    {link && (
                      <Link to={link} className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-700">
                        Открыть <ExternalLink className="w-4 h-4" />
                      </Link>
                    )}
                    {item.external_url && (
                      <a
                        href={item.external_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-700"
                      >
                        Открыть сделку <ExternalLink className="w-4 h-4" />
                      </a>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {data && data.pages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} className="p-2 rounded-lg border border-gray-300 bg-white disabled:opacity-40">
            <ChevronLeft className="w-5 h-5" />
          </button>
          <span className="text-sm text-gray-600">Страница {page} из {data.pages}</span>
          <button type="button" disabled={page >= data.pages} onClick={() => setPage((value) => value + 1)} className="p-2 rounded-lg border border-gray-300 bg-white disabled:opacity-40">
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>
      )}
    </div>
  );
}
