import { Users, Mail, Phone, Calendar, Search, Filter, Plus, X, Loader2 } from 'lucide-react';
import { useState, useCallback, useMemo } from 'react';
import { Link } from 'react-router';
import CustomSelect from '../components/ui/CustomSelect';
import DateInput from '../components/ui/DateInput';
import { useInfinitePartners, usePartnerStats, useUpdatePartner } from '@/app/hooks/usePartners';
import type { PartnerStatus } from '@/app/types';
import { toast } from 'sonner';
import { useIntersectionObserver } from '@/app/hooks/useIntersectionObserver';
import { formatDate } from '@/app/utils/formatDate';
import { useTimezone } from '@/app/contexts/TimezoneContext';

const STATUS_LABELS: Record<string, string> = {
  active: 'Активный',
  pending: 'На проверке',
  blocked: 'Заблокирован',
};

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-100 text-green-700 border-green-200',
  pending: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  blocked: 'bg-red-100 text-red-700 border-red-200',
};

export default function AdminPartners() {
  const tz = useTimezone();
  const [searchQuery, setSearchQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('all');

  const filters = {
    search: searchQuery || undefined,
    status: selectedStatus !== 'all' ? selectedStatus : undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  };

  const { data: pages, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfinitePartners(filters);
  const { data: stats } = usePartnerStats();

  const loadMore = useCallback(() => { if (hasNextPage) fetchNextPage(); }, [hasNextPage, fetchNextPage]);
  const sentinelRef = useIntersectionObserver(loadMore, !!hasNextPage && !isFetchingNextPage);

  const partners = useMemo(() => pages?.pages.flatMap((p) => p.items) ?? [], [pages]);
  const total = pages?.pages[0]?.total ?? 0;

  const updatePartnerMutation = useUpdatePartner();

  const handleStatusChange = (partnerId: string, newStatus: PartnerStatus) => {
    updatePartnerMutation.mutate(
      { id: partnerId, data: { status: newStatus } },
      {
        onSuccess: () => toast.success(`Статус партнёра изменён на «${STATUS_LABELS[newStatus]}»`),
        onError: () => toast.error('Не удалось изменить статус'),
      },
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-gray-900">
            Партнеры
          </h1>
          <p className="text-gray-600 mt-2">
            Всего партнеров: {stats?.total_partners ?? total}
          </p>
        </div>
        <Link
          to="/admin/partners/new"
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
        >
          <Plus className="w-5 h-5" />
          Добавить партнера
        </Link>
      </div>

      {/* Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <Users className="w-5 h-5 text-green-600" />
            </div>
            <h3 className="font-medium text-gray-900">Активные партнеры</h3>
          </div>
          <p className="text-3xl font-semibold text-gray-900">
            {stats?.active_partners ?? '-'}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <Users className="w-5 h-5 text-blue-600" />
            </div>
            <h3 className="font-medium text-gray-900">Всего партнёров</h3>
          </div>
          <p className="text-3xl font-semibold text-gray-900">
            {stats?.total_partners ?? '-'}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center">
              <Calendar className="w-5 h-5 text-orange-600" />
            </div>
            <h3 className="font-medium text-gray-900">На проверке</h3>
          </div>
          <p className="text-3xl font-semibold text-gray-900">
            {stats?.pending_partners ?? '-'}
          </p>
        </div>
      </div>

      {/* Поиск и фильтры */}
      <div className="bg-white rounded-xl shadow-sm p-4 border border-gray-200">
        <div className="flex gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Поиск по названию, ИНН или директору..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button 
            className="flex items-center gap-2 px-4 py-2.5 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors" 
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter className="w-5 h-5" />
            Фильтры
          </button>
        </div>
        {showFilters && (
          <div className="mt-4 p-4 bg-gray-50 rounded-lg">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Период от:</label>
                <DateInput
                  value={dateFrom}
                  onChange={(val) => setDateFrom(val)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Период до:</label>
                <DateInput
                  value={dateTo}
                  onChange={(val) => setDateTo(val)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Статус:</label>
                <CustomSelect
                  value={selectedStatus}
                  onChange={setSelectedStatus}
                  options={[
                    { value: 'all', label: 'Все' },
                    { value: 'active', label: 'Активный' },
                    { value: 'pending', label: 'На проверке' },
                    { value: 'blocked', label: 'Заблокирован' },
                  ]}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button 
                className="flex items-center gap-2 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-white transition-colors" 
                onClick={() => {
                  setDateFrom('');
                  setDateTo('');
                  setSelectedStatus('all');
                  setSearchQuery('');
                }}
              >
                Сбросить
              </button>
              <button 
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors" 
                onClick={() => setShowFilters(false)}
              >
                Применить
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Таблица партнеров */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden border border-gray-200">
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          </div>
        ) : partners.length === 0 ? (
          <div className="text-center py-20 text-gray-500">
            <Users className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p className="text-lg font-medium">Партнеры не найдены</p>
            <p className="text-sm mt-1">Попробуйте изменить параметры поиска</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gradient-to-r from-gray-50 to-gray-100 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                    Партнер
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                    Контакты
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                    ИНН
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                    Клиенты
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                    Финансы
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                    Статус
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                    Регистрация
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {partners.map((partner) => (
                  <tr key={partner.id} className="hover:bg-blue-50/50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-gradient-to-br from-blue-100 to-indigo-100 rounded-lg flex items-center justify-center shadow-sm">
                          <Users className="w-5 h-5 text-blue-600" />
                        </div>
                        <div>
                          <Link 
                            to={`/admin/partners/${partner.id}`}
                            className="font-semibold text-blue-600 hover:text-blue-800 hover:underline transition-colors"
                          >
                            {partner.company_name}
                          </Link>
                          <p className="text-sm text-gray-600">{partner.director_name}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 text-sm text-gray-600">
                          <Mail className="w-4 h-4" />
                          {partner.email || '—'}
                        </div>
                        <div className="flex items-center gap-2 text-sm text-gray-600">
                          <Phone className="w-4 h-4" />
                          {partner.phone}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <p className="text-sm font-mono text-gray-900">{partner.inn}</p>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm space-y-0.5">
                        <p className="font-medium text-gray-900">{partner.clients_count ?? 0} клиентов</p>
                        <p className="text-gray-500">{partner.before_court_count ?? 0} подготовка</p>
                        <p className="text-blue-600">{partner.in_court_count ?? 0} в процессе</p>
                        <p className="text-green-600">{partner.completed_count ?? 0} завершено</p>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm space-y-0.5">
                        <p className="text-gray-700">
                          <span className="text-gray-500">Общая:</span>{' '}
                          <span className="font-medium">{((partner.finance_total_cost ?? 0) / 100).toLocaleString('ru-RU')} ₽</span>
                        </p>
                        <p className="text-yellow-600">
                          <span className="text-gray-500">Текущая:</span>{' '}
                          <span className="font-medium">{((partner.finance_current_debt ?? 0) / 100).toLocaleString('ru-RU')} ₽</span>
                        </p>
                        <p className="text-red-600">
                          <span className="text-gray-500">Просрочено:</span>{' '}
                          <span className="font-medium">{((partner.finance_overdue_debt ?? 0) / 100).toLocaleString('ru-RU')} ₽</span>
                        </p>
                        <p className="text-green-600">
                          <span className="text-gray-500">Оплачено:</span>{' '}
                          <span className="font-medium">{((partner.finance_paid ?? 0) / 100).toLocaleString('ru-RU')} ₽</span>
                        </p>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <CustomSelect
                        value={partner.status}
                        onChange={(val) => handleStatusChange(partner.id, val as PartnerStatus)}
                        options={[
                          { value: 'pending', label: 'На проверке' },
                          { value: 'active', label: 'Активный' },
                          { value: 'blocked', label: 'Заблокирован' },
                        ]}
                        size="sm"
                        triggerClassName={STATUS_COLORS[partner.status] || 'bg-gray-100 text-gray-700 border-gray-200'}
                      />
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2 text-sm text-gray-600">
                        <Calendar className="w-4 h-4" />
                        {formatDate(partner.created_at, tz)}
                      </div>
                    </td>
                  </tr>
                ))}
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
