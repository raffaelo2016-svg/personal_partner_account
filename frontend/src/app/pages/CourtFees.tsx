import { AlertCircle, Users, TrendingUp, DollarSign, Loader2, Clock, Filter, Gift, CalendarDays } from 'lucide-react';
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchCourtFees, fetchCourtFeeSummary, payCourtFee } from '../api/finance';
import { formatDateShort, todayInMoscow } from '@/app/utils/formatDate';
import { useTimezone } from '@/app/contexts/TimezoneContext';
import PaymentModal from '../components/PaymentModal';
import CustomSelect from '../components/ui/CustomSelect';
import type { CourtFeeSummary } from '../api/finance';

const COURT_FEE_FILTERS = [
  { value: 'all', label: 'Все клиенты' },
  { value: 'unpaid', label: 'Требуют оплаты' },
  { value: 'current', label: 'Текущая задолженность' },
  { value: 'overdue', label: 'Просроченная задолженность' },
  { value: 'paid', label: 'Оплачено' },
  { value: 'promo_free', label: 'Бесплатно по предложению' },
];

function parseDateOnly(value: string) {
  const [year, month, day] = value.split('-').map(Number);
  return Date.UTC(year, month - 1, day);
}

function formatPromoDate(value?: string | null) {
  if (!value) return '—';
  const [year, month, day] = value.split('-').map(Number);
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long' }).format(
    new Date(year, month - 1, day),
  );
}

function PromotionTimeline({ summary }: { summary: CourtFeeSummary }) {
  if (!summary.free_client_limit || !summary.promotion_start_date) {
    return null;
  }

  const start = parseDateOnly(summary.promotion_start_date);
  const end = summary.promotion_end_date ? parseDateOnly(summary.promotion_end_date) : null;
  const today = parseDateOnly(todayInMoscow());
  const scheduled = today < start;
  const totalDays = end === null ? 0 : Math.max(1, Math.round((end - start) / 86_400_000));
  const elapsedDays = end === null ? 0 : Math.max(0, totalDays - summary.promotion_days_remaining);
  const timeProgress = totalDays ? Math.min(100, Math.round((elapsedDays / totalDays) * 100)) : 0;
  const clientProgress = Math.min(100, Math.round((summary.free_clients_used / summary.free_client_limit) * 100));
  const exhausted = summary.free_clients_used >= summary.free_client_limit;
  const endingSoon = summary.promotion_active && end !== null && summary.promotion_days_remaining <= 7;
  const statusLabel = summary.promotion_active
    ? end === null ? 'Без ограничения по сроку' : `Осталось ${summary.promotion_days_remaining} дн.`
    : scheduled
      ? `Начнётся ${formatPromoDate(summary.promotion_start_date)}`
    : exhausted
      ? 'Лимит использован'
      : 'Предложение завершено';

  return (
    <section className={`rounded-2xl border p-6 shadow-sm ${
      summary.promotion_active
        ? 'border-blue-200 bg-gradient-to-br from-blue-600 to-blue-500 text-white'
        : 'border-gray-200 bg-white text-gray-900'
    }`}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <div className={`rounded-xl p-2.5 ${summary.promotion_active ? 'bg-white/15' : 'bg-gray-100'}`}>
            <Gift className={`w-6 h-6 ${summary.promotion_active ? 'text-white' : 'text-gray-500'}`} />
          </div>
          <div>
            <h2 className="text-xl font-semibold">
              {end === null ? 'Бесплатные клиенты' : 'Льготный месяц для новых клиентов'}
            </h2>
            <p className={`text-sm mt-1 ${summary.promotion_active ? 'text-blue-100' : 'text-gray-500'}`}>
              Первые {summary.free_client_limit} клиентов без судебных расходов
              {end === null ? ' без ограничения по сроку' : ` до ${formatPromoDate(summary.promotion_end_date)}`}
            </p>
          </div>
        </div>
        <span className={`self-start rounded-full px-3 py-1.5 text-xs font-semibold ${
          endingSoon
            ? 'bg-amber-100 text-amber-800'
            : summary.promotion_active
              ? 'bg-white/15 text-white'
              : 'bg-gray-100 text-gray-600'
        }`}>
          {statusLabel}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
        <div className={`rounded-xl p-4 ${summary.promotion_active ? 'bg-white text-gray-900' : 'bg-gray-50'}`}>
          <div className="flex items-center justify-between text-sm mb-2">
            <span>Бесплатные клиенты</span>
            <strong>{summary.free_clients_used} из {summary.free_client_limit}</strong>
          </div>
          <div
            className="h-2.5 rounded-full bg-gray-200 overflow-hidden"
            role="progressbar"
            aria-label="Использовано бесплатных клиентов"
            aria-valuemin={0}
            aria-valuemax={summary.free_client_limit}
            aria-valuenow={summary.free_clients_used}
          >
            <div className="h-full rounded-full bg-emerald-500" style={{ width: `${clientProgress}%` }} />
          </div>
          <p className="text-xs text-gray-500 mt-2">
            {summary.promotion_active
              ? `Можно передать бесплатно ещё: ${summary.free_clients_remaining}`
              : `Бесплатно передано: ${summary.free_clients_used}`}
          </p>
        </div>
        <div className={`rounded-xl p-4 ${summary.promotion_active ? 'bg-white text-gray-900' : 'bg-gray-50'}`}>
          <div className="flex items-center justify-between text-sm mb-2">
            <span>Время предложения</span>
            <strong>{end === null ? 'Без ограничения' : `${elapsedDays} из ${totalDays} дней`}</strong>
          </div>
            {end !== null ? (
              <div
                className="h-2.5 rounded-full bg-gray-200 overflow-hidden"
                role="progressbar"
                aria-label="Прошло дней льготного периода"
                aria-valuemin={0}
                aria-valuemax={totalDays}
                aria-valuenow={elapsedDays}
              >
                <div className="h-full rounded-full bg-amber-400" style={{ width: `${timeProgress}%` }} />
              </div>
            ) : null}
          <p className="text-xs text-gray-500 mt-2">
            С {formatPromoDate(summary.promotion_start_date)}
            {end === null ? ', до исчерпания лимита' : ` — ${formatPromoDate(summary.promotion_end_date)}`}
          </p>
        </div>
      </div>

      <div className={`mt-5 rounded-xl border p-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between ${
        summary.promotion_active
          ? 'border-white/30 bg-white/10'
          : 'border-gray-200 bg-gray-50'
      }`}>
        <div>
          <strong className="text-sm">
            {summary.promotion_active
              ? `Можно передать ещё ${summary.free_clients_remaining} клиентов бесплатно`
              : scheduled
                ? `Предложение начнётся ${formatPromoDate(summary.promotion_start_date)}`
              : 'Для новых клиентов действует обычная стоимость'}
          </strong>
          <p className={`text-xs mt-1 ${summary.promotion_active ? 'text-blue-100' : 'text-gray-500'}`}>
            Экономия за период: {(summary.promotion_savings / 100).toLocaleString('ru-RU')} ₽
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm font-medium">
          <CalendarDays className="w-4 h-4" />
          {end === null
            ? 'Без ограничения по сроку'
            : `Неиспользованный остаток сгорит ${formatPromoDate(summary.promotion_end_date)}`}
        </div>
      </div>
    </section>
  );
}

export default function CourtFees() {
  const tz = useTimezone();
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
  const [selectedDebt, setSelectedDebt] = useState<string | null>(null);
  const [payDebtType, setPayDebtType] = useState<'overdue' | 'current' | 'all'>('all');
  const [feeFilter, setFeeFilter] = useState('all');
  const [page, setPage] = useState(1);
  const queryClient = useQueryClient();

  const { data: feesData, isLoading } = useQuery({
    queryKey: ['courtFees', page, feeFilter],
    queryFn: () => fetchCourtFees({
      page,
      ...(feeFilter !== 'all' ? { category: feeFilter } : {}),
    }),
  });
  const { data: summary } = useQuery({
    queryKey: ['courtFeeSummary'],
    queryFn: fetchCourtFeeSummary,
  });

  const payMutation = useMutation({
    mutationFn: (feeId: string) => payCourtFee(feeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['courtFees'] });
      queryClient.invalidateQueries({ queryKey: ['courtFeeSummary'] });
      setIsPaymentModalOpen(false);
    },
  });

  const partnerData = {
    courtFeePerClient: (summary?.fee_per_client ?? 0) / 100,
    totalDebt: (summary?.total_debt ?? 0) / 100,
    currentDebt: (summary?.current_debt ?? 0) / 100,
    overdueDebt: (summary?.overdue_debt ?? 0) / 100,
    totalClients: summary?.total_clients ?? 0,
    activeClients: summary?.unpaid_count ?? 0,
    currentCount: summary?.current_count ?? 0,
    overdueCount: summary?.overdue_count ?? 0,
    paidThisMonth: (summary?.paid_this_month ?? 0) / 100,
  };

  const STATUS_LABELS: Record<string, string> = {
    documents_collection: 'Сбор документов',
    documents_formation: 'Формирование документов',
    sent_to_court: 'Отправка в суд',
    documents_decision: 'Документы приняты / не приняты',
    waiting_hearing: 'Ожидание заседания',
    restructuring: 'Реструктуризация',
    auction: 'Торги',
    realization: 'Реализация',
  };

  const clientDebts = (feesData?.items ?? []).map((f) => ({
    id: f.id,
    clientName: f.client_name ?? 'Клиент',
    courtFee: f.amount / 100,
    baseAmount: f.base_amount / 100,
    discountAmount: f.discount_amount / 100,
    status: f.status,
    addedDate: f.created_at?.split('T')[0] ?? '',
    dueDate: f.due_date,
    paidDate: f.paid_at?.split('T')[0],
    stage: STATUS_LABELS[f.client_status ?? ''] ?? f.client_status ?? '',
    courtProcedureDate: f.court_procedure_date ?? null,
  }));

  const getStatusConfig = (status: string) => {
    switch (status) {
      case 'paid':
        return {
          label: 'Оплачено',
          color: 'bg-green-100 text-green-700 border-green-300',
        };
      case 'unpaid':
        return {
          label: 'Ожидает оплаты',
          color: 'bg-yellow-100 text-yellow-700 border-yellow-300',
        };
      case 'overdue':
        return {
          label: 'Просрочено',
          color: 'bg-red-100 text-red-700 border-red-300',
        };
      case 'promo_free':
        return {
          label: 'Бесплатно по предложению',
          color: 'bg-emerald-100 text-emerald-700 border-emerald-300',
        };
      default:
        return {
          label: status,
          color: 'bg-gray-100 text-gray-700 border-gray-300',
        };
    }
  };

  const unpaidCount = clientDebts.filter(
    (d) => d.status === 'unpaid' || d.status === 'overdue'
  ).length;
  const selectedFilterLabel = COURT_FEE_FILTERS.find((item) => item.value === feeFilter)?.label ?? 'Все клиенты';

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-semibold text-gray-900 mb-2">
          Судебные расходы
        </h1>
        <p className="text-gray-600">
          Управление оплатой судебных расходов за клиентов
        </p>
      </div>

      {summary ? <PromotionTimeline summary={summary} /> : null}

      {/* Alert - Debt Warning */}
      {partnerData.overdueDebt > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 flex items-start gap-4">
          <AlertCircle className="w-6 h-6 text-red-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h3 className="font-semibold text-red-900 mb-1">
              Требуется оплата судебных расходов
            </h3>
            <p className="text-sm text-red-700 mb-3">
              У вас есть просроченная непогашенная задолженность. Пожалуйста, погасите её для
              продолжения работы с клиентами.
            </p>
            <button 
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              onClick={() => {
                setSelectedDebt(null);
                setPayDebtType('overdue');
                setIsPaymentModalOpen(true);
              }}
            >
              Оплатить {partnerData.overdueDebt.toLocaleString('ru-RU')} ₽
            </button>
          </div>
        </div>
      )}
      {partnerData.overdueDebt === 0 && partnerData.currentDebt > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-6 flex items-start gap-4">
          <AlertCircle className="w-6 h-6 text-yellow-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h3 className="font-semibold text-yellow-900 mb-1">
              Требуется оплата судебных расходов
            </h3>
            <p className="text-sm text-yellow-700 mb-3">
              У вас есть непогашенная задолженность. Пожалуйста, погасите её для
              продолжения работы с клиентами.
            </p>
            <button
              className="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition-colors"
              onClick={() => {
                setSelectedDebt(null);
                setPayDebtType('current');
                setIsPaymentModalOpen(true);
              }}
            >
              Оплатить {partnerData.currentDebt.toLocaleString('ru-RU')} ₽
            </button>
          </div>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <DollarSign className="w-6 h-6 text-blue-600" />
            </div>
          </div>
          <p className="text-sm text-gray-600 mb-1">Общая стоимость судебных расходов</p>
          <p className="text-2xl font-bold text-gray-900">
            {partnerData.totalDebt.toLocaleString('ru-RU')} ₽
          </p>
          <p className="text-xs text-gray-500 mt-2">
            Стоимость за клиента: {partnerData.courtFeePerClient.toLocaleString('ru-RU')} ₽
          </p>
        </div>

        <div className="bg-white rounded-xl border border-orange-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center">
              <Clock className="w-6 h-6 text-orange-600" />
            </div>
          </div>
          <p className="text-sm text-gray-600 mb-1">Текущая задолженность</p>
          <p className="text-2xl font-bold text-orange-600">
            {partnerData.currentDebt.toLocaleString('ru-RU')} ₽
          </p>
          <p className="text-xs text-gray-500 mt-2">{partnerData.currentCount} клиентов</p>
        </div>

        <div className="bg-white rounded-xl border border-red-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 bg-red-100 rounded-lg flex items-center justify-center">
              <AlertCircle className="w-6 h-6 text-red-600" />
            </div>
          </div>
          <p className="text-sm text-gray-600 mb-1">Просроченная задолженность</p>
          <p className="text-2xl font-bold text-red-600">
            {partnerData.overdueDebt.toLocaleString('ru-RU')} ₽
          </p>
          <p className="text-xs text-gray-500 mt-2">{partnerData.overdueCount} клиентов</p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
              <TrendingUp className="w-6 h-6 text-green-600" />
            </div>
          </div>
          <p className="text-sm text-gray-600 mb-1">Оплачено</p>
          <p className="text-2xl font-bold text-gray-900">
            {partnerData.paidThisMonth.toLocaleString('ru-RU')} ₽
          </p>
          <p className="text-xs text-gray-500 mt-2">
            {clientDebts.filter((d) => d.status === 'paid').length} клиентов
          </p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
              <Users className="w-6 h-6 text-purple-600" />
            </div>
          </div>
          <p className="text-sm text-gray-600 mb-1">Всего клиентов</p>
          <p className="text-2xl font-bold text-gray-900">
            {partnerData.totalClients}
          </p>
          <p className="text-xs text-gray-500 mt-2">
            {partnerData.activeClients} требуют оплаты
          </p>
        </div>
      </div>

      {/* Client Debts Table */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="p-6 border-b border-gray-200 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">
              Судебные расходы по клиентам
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              Показано {clientDebts.length} из {feesData?.total ?? 0}
            </p>
          </div>
          <div className="w-full lg:w-72">
            <label className="sr-only">Фильтр клиентов по задолженности</label>
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-gray-400 flex-shrink-0" />
              <CustomSelect
                value={feeFilter}
                onChange={(value) => {
                  setFeeFilter(value);
                  setPage(1);
                }}
                options={COURT_FEE_FILTERS}
                className="flex-1 min-w-0"
                size="md"
              />
            </div>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Клиент
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Этап
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Стоимость
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Статус
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Дата банкротства
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Срок оплаты
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Действия
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {isLoading && (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center">
                    <Loader2 className="w-6 h-6 animate-spin text-gray-400 mx-auto mb-2" />
                    <p className="text-sm text-gray-500">Загрузка...</p>
                  </td>
                </tr>
              )}
              {!isLoading && clientDebts.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center">
                    <Users className="w-10 h-10 text-gray-300 mx-auto mb-2" />
                    <p className="text-sm text-gray-500">
                      {feeFilter === 'all' ? 'Нет клиентов' : `Нет клиентов: ${selectedFilterLabel.toLowerCase()}`}
                    </p>
                    <p className="text-xs text-gray-400 mt-1">
                      {feeFilter === 'all'
                        ? 'Клиенты появятся здесь после добавления'
                        : 'Выберите другой фильтр, чтобы посмотреть остальные судебные расходы'}
                    </p>
                  </td>
                </tr>
              )}
              {clientDebts.map((debt) => {
                const config = getStatusConfig(debt.status);
                return (
                  <tr key={debt.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {debt.clientName}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-gray-600 max-w-xs">
                        {debt.stage}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {debt.status === 'promo_free' ? (
                        <div>
                          <div className="text-xs text-gray-400 line-through">
                            {debt.baseAmount.toLocaleString('ru-RU')} ₽
                          </div>
                          <div className="text-sm font-semibold text-emerald-700">0 ₽</div>
                        </div>
                      ) : (
                        <div className="text-sm font-semibold text-gray-900">
                          {debt.courtFee.toLocaleString('ru-RU')} ₽
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${config.color}`}
                      >
                        {config.label}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                      {debt.courtProcedureDate
                        ? formatDateShort(debt.courtProcedureDate, tz)
                        : <span className="text-gray-400">—</span>}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                      {debt.status === 'promo_free'
                        ? <span className="text-emerald-700">Оплата не требуется</span>
                        : debt.status === 'paid'
                        ? `Оплачено ${formatDateShort(debt.paidDate!, tz)}`
                        : debt.courtProcedureDate
                          ? formatDateShort(debt.dueDate!, tz)
                          : <span className="text-gray-400">—</span>}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      {debt.status !== 'paid' && debt.status !== 'promo_free' && (
                        <button
                          className="text-blue-600 hover:text-blue-700 font-medium"
                          onClick={() => {
                            setSelectedDebt(debt.id);
                            setIsPaymentModalOpen(true);
                          }}
                        >
                          Оплатить
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Payment Info */}
      <div className="bg-blue-50 rounded-xl border border-blue-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Условия оплаты судебных расходов
        </h3>
        <ul className="space-y-2 text-sm text-gray-700">
          <li className="flex items-start gap-2">
            <span className="text-blue-600 mt-1">•</span>
            <span>
              Оплата судебных расходов производится за каждого добавленного клиента
            </span>
          </li>
          {summary?.free_client_limit ? (
            <li className="flex items-start gap-2">
              <span className="text-blue-600 mt-1">•</span>
              <span>
                Первые {summary.free_client_limit} клиентов бесплатны с{' '}
                {formatPromoDate(summary.promotion_start_date)}
                {summary.promotion_end_date
                  ? ` по ${formatPromoDate(summary.promotion_end_date)}`
                  : ' без ограничения по сроку, до исчерпания лимита'}
              </span>
            </li>
          ) : null}
          <li className="flex items-start gap-2">
            <span className="text-blue-600 mt-1">•</span>
            <span>
              Стоимость за клиента: {partnerData.courtFeePerClient.toLocaleString('ru-RU')} ₽
              (установлена при регистрации)
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-blue-600 mt-1">•</span>
            <span>Срок оплаты: {summary?.payment_term_days ?? 10} дней с момента добавления клиента</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-blue-600 mt-1">•</span>
            <span>
              При просрочке оплаты работа с клиентом может быть приостановлена
            </span>
          </li>
        </ul>
      </div>

      {(() => {
        const selectedClient = selectedDebt
          ? clientDebts.find((d) => d.id === selectedDebt)
          : null;
        let amount: number;
        let summaryTitle: string;
        let summarySubtitle: string;
        if (selectedClient) {
          amount = selectedClient.courtFee;
          summaryTitle = `Клиент: ${selectedClient.clientName}`;
          summarySubtitle = `Этап: ${selectedClient.stage}`;
        } else if (payDebtType === 'overdue') {
          amount = partnerData.overdueDebt;
          summaryTitle = 'Оплата просроченной задолженности';
          summarySubtitle = `${partnerData.overdueCount} ${partnerData.overdueCount === 1 ? 'клиент' : partnerData.overdueCount < 5 ? 'клиента' : 'клиентов'}`;
        } else if (payDebtType === 'current') {
          amount = partnerData.currentDebt;
          summaryTitle = 'Оплата текущей задолженности';
          summarySubtitle = `${partnerData.currentCount} ${partnerData.currentCount === 1 ? 'клиент' : partnerData.currentCount < 5 ? 'клиента' : 'клиентов'}`;
        } else {
          amount = partnerData.totalDebt;
          summaryTitle = 'Оплата общей задолженности';
          summarySubtitle = `${unpaidCount} ${unpaidCount === 1 ? 'клиент' : unpaidCount < 5 ? 'клиента' : 'клиентов'}`;
        }
        return (
          <PaymentModal
            isOpen={isPaymentModalOpen}
            onClose={() => setIsPaymentModalOpen(false)}
            amount={amount}
            feeIds={selectedClient ? [selectedClient.id] : null}
            debtType={selectedClient ? 'all' : payDebtType}
            summaryTitle={summaryTitle}
            summarySubtitle={summarySubtitle}
          />
        );
      })()}
    </div>
  );
}
