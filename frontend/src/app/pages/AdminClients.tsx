import { Search, Filter, Users, FileText, Plus, X, Calendar, Loader2 } from 'lucide-react';
import { useState, useCallback, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router';
import { useInfiniteAdminClients } from '../hooks/useClients';
import { useIntersectionObserver } from '../hooks/useIntersectionObserver';
import CustomSelect from '../components/ui/CustomSelect';
import { formatDateShort } from '@/app/utils/formatDate';
import { useTimezone } from '@/app/contexts/TimezoneContext';
import CaseArbitrLink from '../components/CaseArbitrLink';

export default function AdminClients() {
  const tz = useTimezone();
  const [searchParams, setSearchParams] = useSearchParams();
  const partnerIdParam = searchParams.get('partner') || undefined;

  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [showFilters, setShowFilters] = useState(false);

  const filters = {
    search: searchQuery || undefined,
    status: filterStatus !== 'all' ? filterStatus : undefined,
    partner_id: partnerIdParam,
  };

  const { data: pages, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteAdminClients(filters);

  const loadMore = useCallback(() => { if (hasNextPage) fetchNextPage(); }, [hasNextPage, fetchNextPage]);
  const sentinelRef = useIntersectionObserver(loadMore, !!hasNextPage && !isFetchingNextPage);

  const clients = useMemo(() => pages?.pages.flatMap((p) => p.items) ?? [], [pages]);
  const total = pages?.pages[0]?.total ?? 0;

  const getStatusLabel = (status: string) => {
    const labels: Record<string, string> = {
      documents_collection: 'Сбор документов',
      documents_formation: 'Формирование документов',
      sent_to_court: 'Отправка в суд',
      documents_decision: 'Документы приняты / не приняты',
      waiting_hearing: 'Ожидание заседания',
      restructuring: 'Реструктуризация',
      auction: 'Торги',
      realization: 'Реализация',
      completed: 'Завершено',
    };
    return labels[status] || status;
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      documents_collection: 'bg-blue-100 text-blue-700 border-blue-200',
      documents_formation: 'bg-indigo-100 text-indigo-700 border-indigo-200',
      sent_to_court: 'bg-orange-100 text-orange-700 border-orange-200',
      documents_decision: 'bg-emerald-100 text-emerald-700 border-emerald-200',
      waiting_hearing: 'bg-cyan-100 text-cyan-700 border-cyan-200',
      restructuring: 'bg-purple-100 text-purple-700 border-purple-200',
      auction: 'bg-amber-100 text-amber-700 border-amber-200',
      realization: 'bg-green-100 text-green-700 border-green-200',
      completed: 'bg-teal-100 text-teal-700 border-teal-200',
    };
    return colors[status] || 'bg-gray-100 text-gray-700 border-gray-200';
  };

  const fmtDate = (dateStr: string) => formatDateShort(dateStr, tz);

  const activeFiltersCount = [filterStatus].filter(f => f !== 'all').length + (partnerIdParam ? 1 : 0);
  const partnerNameFromClients = partnerIdParam ? clients.find(c => c.partner_id === partnerIdParam)?.partner_name : undefined;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-gray-900">Клиенты</h1>
          <p className="text-gray-600 mt-2">
            {partnerIdParam
              ? <>Клиенты партнёра{partnerNameFromClients ? ` «${partnerNameFromClients}»` : ''}.{' '}
                  <button
                    className="text-blue-600 hover:underline"
                    onClick={() => setSearchParams({})}
                  >
                    Показать всех
                  </button>
                </>
              : <>Последние Должники, созданные за последний год.</>
            }
          </p>
        </div>
      </div>

      {/* Поиск и фильтры */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="p-4 flex gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Поиск по имени, номеру дела, партнеру..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            />
          </div>
          <button
            className={`flex items-center gap-2 px-4 py-2 border rounded-lg transition-colors text-sm ${
              showFilters 
                ? 'bg-blue-50 border-blue-300 text-blue-700' 
                : 'border-gray-300 hover:bg-gray-50 text-gray-700'
            }`}
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter className="w-4 h-4" />
            Фильтры
            {activeFiltersCount > 0 && (
              <span className="ml-1 bg-blue-600 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                {activeFiltersCount}
              </span>
            )}
          </button>
        </div>
        
        {showFilters && (
          <div className="px-4 pb-4 border-t border-gray-200">
            <div className="pt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Статус</label>
                <CustomSelect
                  value={filterStatus}
                  onChange={setFilterStatus}
                  options={[
                    { value: 'all', label: 'Все статусы' },
                    { value: 'documents_collection', label: 'Сбор документов' },
                    { value: 'documents_formation', label: 'Формирование документов' },
                    { value: 'sent_to_court', label: 'Отправка в суд' },
                    { value: 'documents_decision', label: 'Документы приняты / не приняты' },
                    { value: 'waiting_hearing', label: 'Ожидание заседания' },
                    { value: 'restructuring', label: 'Реструктуризация' },
                    { value: 'auction', label: 'Торги' },
                    { value: 'realization', label: 'Реализация' },
                    { value: 'completed', label: 'Завершено' },
                  ]}
                />
              </div>
            </div>
            
            {activeFiltersCount > 0 && (
              <div className="mt-3 flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <Filter className="w-4 h-4" />
                  <span>Активных фильтров: {activeFiltersCount}</span>
                </div>
                <button
                  className="flex items-center gap-1 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
                  onClick={() => {
                    setFilterStatus('all');
                    setSearchQuery('');
                  }}
                >
                  <X className="w-4 h-4" />
                  Сбросить все
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Результаты */}
      <div className="flex items-center justify-between text-sm text-gray-600">
        <span>Найдено записей: <span className="font-medium text-gray-900">{total}</span></span>
      </div>

      {/* Таблица клиентов */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden border border-gray-200">
        {isLoading ? (
          <div className="px-4 py-12 text-center flex items-center justify-center gap-2">
            <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
            <span className="text-gray-500">Загрузка...</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-600 uppercase">ФИО</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-600 uppercase">Партнёр</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-600 uppercase">Тип</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-600 uppercase">Статус</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-600 uppercase">Регион</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-600 uppercase">Номер дела</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-600 uppercase">Стоимость</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-600 uppercase">Дата создания</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {clients.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-12 text-center text-gray-500">
                      <div className="flex flex-col items-center gap-2">
                        <Search className="w-12 h-12 text-gray-300" />
                        <p className="text-sm">Ничего не найдено</p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  clients.map((client) => (
                    <tr key={client.id} className="hover:bg-blue-50/30 transition-colors">
                      <td className="px-3 py-3">
                        <Link
                          to={`/admin/clients/${client.id}`}
                          className="text-sm font-medium text-blue-600 hover:text-blue-700 hover:underline"
                        >
                          {client.full_name}
                        </Link>
                      </td>
                      <td className="px-3 py-3">
                        {client.partner_name ? (
                          <Link
                            to={`/admin/partners/${client.partner_id}`}
                            className="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline"
                          >
                            {client.partner_name}
                          </Link>
                        ) : (
                          <span className="text-sm text-gray-400">—</span>
                        )}
                      </td>
                      <td className="px-3 py-3">
                        <p className="text-sm text-gray-600">
                          {client.type === 'before_court' ? 'До суда' : 'В суде'}
                        </p>
                        {client.type === 'before_court' ? (
                          <span className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${
                            client.document_preparation_mode === 'uritech'
                              ? 'bg-indigo-50 text-indigo-700'
                              : 'bg-violet-50 text-violet-700'
                          }`}>
                            {client.document_preparation_mode === 'uritech' ? 'Готовит ЮРИТЕХ' : 'Готовит партнёр'}
                          </span>
                        ) : null}
                      </td>
                      <td className="px-3 py-3">
                        <span className={`inline-flex items-center px-2.5 py-0.5 text-xs font-medium rounded-full border ${getStatusColor(client.status)}`}>
                          {getStatusLabel(client.status)}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        <p className="text-sm text-gray-600">{client.region ?? '—'}</p>
                      </td>
                      <td className="px-3 py-3">
                        <p className="text-sm font-mono text-gray-700">
                          <CaseArbitrLink caseNumber={client.case_number} />
                        </p>
                      </td>
                      <td className="px-3 py-3">
                        <p className="text-sm font-semibold text-gray-900">
                          {client.court_fee_per_client != null
                            ? `${(client.court_fee_per_client / 100).toLocaleString('ru-RU')} ₽`
                            : '—'}
                        </p>
                      </td>
                      <td className="px-3 py-3">
                        <p className="text-sm text-gray-600">{fmtDate(client.created_at)}</p>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {(hasNextPage || isFetchingNextPage) && (
          <div ref={sentinelRef} className="flex justify-center py-4 border-t border-gray-200">
            <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
          </div>
        )}
      </div>
    </div>
  );
}
