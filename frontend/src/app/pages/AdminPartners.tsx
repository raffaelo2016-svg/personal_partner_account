import { Users, Mail, Phone, Calendar, Search, Filter, Plus, Loader2 } from 'lucide-react';
import { useState, useCallback, useMemo } from 'react';
import { Link } from 'react-router';
import CustomSelect from '../components/ui/CustomSelect';
import DateInput from '../components/ui/DateInput';
import { useInfinitePartners, usePartnerStats, useUpdatePartner } from '@/app/hooks/usePartners';
import type { Partner, PartnerStatus } from '@/app/types';
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
  active: 'bg-white text-green-700 border-green-200 hover:border-green-300',
  pending: 'bg-white text-amber-700 border-amber-200 hover:border-amber-300',
  blocked: 'bg-white text-red-700 border-red-200 hover:border-red-300',
};

const STATUS_OPTIONS = [
  { value: 'pending', label: 'На проверке' },
  { value: 'active', label: 'Активный' },
  { value: 'blocked', label: 'Заблокирован' },
];

function formatMoney(kopecks: number | undefined): string {
  return `${((kopecks ?? 0) / 100).toLocaleString('ru-RU')} ₽`;
}

function formatClientCount(count: number): string {
  const lastTwoDigits = Math.abs(count) % 100;
  const lastDigit = lastTwoDigits % 10;

  if (lastTwoDigits >= 11 && lastTwoDigits <= 14) return `${count} клиентов`;
  if (lastDigit === 1) return `${count} клиент`;
  if (lastDigit >= 2 && lastDigit <= 4) return `${count} клиента`;
  return `${count} клиентов`;
}

function MetricRow({
  label,
  value,
  dotClassName,
  valueClassName = 'text-slate-700',
}: {
  label: string;
  value: string;
  dotClassName: string;
  valueClassName?: string;
}) {
  return (
    <div className="grid grid-cols-[10px_minmax(0,1fr)_auto] items-center gap-2 text-sm">
      <span className={`h-2 w-2 rounded-full ${dotClassName}`} aria-hidden="true" />
      <span className="truncate text-slate-600">{label}</span>
      <span className={`font-medium tabular-nums ${valueClassName}`}>{value}</span>
    </div>
  );
}

function PartnerRow({
  partner,
  timezone,
  onStatusChange,
}: {
  partner: Partner;
  timezone: string;
  onStatusChange: (partnerId: string, status: PartnerStatus) => void;
}) {
  const clientsCount = partner.clients_count ?? 0;
  const overdueDebt = partner.finance_overdue_debt ?? 0;

  return (
    <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition-colors hover:border-blue-200 hover:bg-blue-50/20">
      <div className="grid grid-cols-[minmax(280px,1.35fr)_minmax(250px,1.15fr)_minmax(210px,0.9fr)_minmax(230px,1fr)_minmax(170px,0.72fr)_minmax(160px,0.68fr)]">
        <section className="min-w-0 p-5">
          <p className="mb-4 text-xs font-medium text-slate-500">Партнёр</p>
          <div className="flex items-start gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-50">
              <Users className="h-5 w-5 text-blue-600" aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <Link
                to={`/admin/partners/${partner.id}`}
                className="block font-semibold leading-snug text-blue-600 transition-colors hover:text-blue-800 hover:underline"
              >
                {partner.company_name}
              </Link>
              <p className="mt-1 truncate text-sm text-slate-600">{partner.director_name}</p>
              <p className="mt-1 text-xs text-slate-400">ИНН {partner.inn}</p>
            </div>
          </div>
        </section>

        <section className="min-w-0 border-l border-slate-200 p-5">
          <p className="mb-4 text-xs font-medium text-slate-500">Контакты</p>
          <div className="space-y-2.5">
            {partner.email ? (
              <a
                href={`mailto:${partner.email}`}
                className="flex min-w-0 items-center gap-2 text-sm text-slate-600 transition-colors hover:text-blue-600"
              >
                <Mail className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className="truncate">{partner.email}</span>
              </a>
            ) : (
              <div className="flex items-center gap-2 text-sm text-slate-400">
                <Mail className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span>Не указана</span>
              </div>
            )}
            <a
              href={`tel:${partner.phone}`}
              className="flex items-center gap-2 text-sm text-slate-600 transition-colors hover:text-blue-600"
            >
              <Phone className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span>{partner.phone}</span>
            </a>
          </div>
        </section>

        <section className="min-w-0 border-l border-slate-200 p-5">
          <p className="mb-3 text-xs font-medium text-slate-500">Клиенты</p>
          <p className="text-lg font-semibold text-slate-900 tabular-nums">
            {formatClientCount(clientsCount)}
          </p>
          <div className="mt-2.5 space-y-1.5">
            <MetricRow
              label="В процессе"
              value={String(partner.in_court_count ?? 0)}
              dotClassName="bg-blue-500"
              valueClassName="text-blue-600"
            />
            <MetricRow
              label="На подготовке"
              value={String(partner.before_court_count ?? 0)}
              dotClassName="bg-slate-400"
            />
            <MetricRow
              label="Завершено"
              value={String(partner.completed_count ?? 0)}
              dotClassName="bg-green-500"
              valueClassName="text-green-600"
            />
          </div>
        </section>

        <section className="min-w-0 border-l border-slate-200 p-5">
          <p className="mb-3 text-xs font-medium text-slate-500">Финансы</p>
          <p className="text-lg font-semibold text-slate-900 tabular-nums">
            {formatMoney(partner.finance_total_cost)}
          </p>
          <div className="mt-2.5 space-y-1.5">
            <MetricRow
              label="К оплате"
              value={formatMoney(partner.finance_current_debt)}
              dotClassName="bg-amber-500"
              valueClassName="text-amber-600"
            />
            <MetricRow
              label="Просрочено"
              value={formatMoney(overdueDebt)}
              dotClassName={overdueDebt > 0 ? 'bg-red-500' : 'bg-slate-400'}
              valueClassName={overdueDebt > 0 ? 'text-red-600' : 'text-slate-700'}
            />
            <MetricRow
              label="Оплачено"
              value={formatMoney(partner.finance_paid)}
              dotClassName="bg-green-500"
              valueClassName="text-green-600"
            />
          </div>
        </section>

        <section className="min-w-0 border-l border-slate-200 p-5">
          <p className="mb-4 text-xs font-medium text-slate-500">Статус</p>
          <CustomSelect
            value={partner.status}
            onChange={(value) => onStatusChange(partner.id, value as PartnerStatus)}
            options={STATUS_OPTIONS}
            size="sm"
            triggerClassName={STATUS_COLORS[partner.status] || 'bg-white text-slate-700 border-slate-200'}
          />
        </section>

        <section className="min-w-0 border-l border-slate-200 p-5">
          <p className="mb-4 text-xs font-medium text-slate-500">Добавлен</p>
          <div className="flex items-start gap-2 text-sm leading-snug text-slate-600">
            <Calendar className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <time dateTime={partner.created_at}>{formatDate(partner.created_at, timezone)}</time>
          </div>
        </section>
      </div>
    </article>
  );
}

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

      {/* Список партнёров */}
      <div>
        {isLoading ? (
          <div className="flex items-center justify-center rounded-xl border border-gray-200 bg-white py-20 shadow-sm">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          </div>
        ) : partners.length === 0 ? (
          <div className="rounded-xl border border-gray-200 bg-white py-20 text-center text-gray-500 shadow-sm">
            <Users className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p className="text-lg font-medium">Партнеры не найдены</p>
            <p className="text-sm mt-1">Попробуйте изменить параметры поиска</p>
          </div>
        ) : (
          <div className="overflow-x-auto pb-1">
            <div className="min-w-[1320px] space-y-3">
              {partners.map((partner) => (
                <PartnerRow
                  key={partner.id}
                  partner={partner}
                  timezone={tz}
                  onStatusChange={handleStatusChange}
                />
              ))}
            </div>
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
