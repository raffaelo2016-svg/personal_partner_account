import { Users, ArrowRight, Wallet, CreditCard, TrendingUp, Calendar, X, Loader2, DollarSign, Clock, AlertCircle } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { fetchAdminDashboard } from '../api/adminDashboard';
import DateInput from '../components/ui/DateInput';
import { formatDateShort } from '@/app/utils/formatDate';
import { useTimezone } from '@/app/contexts/TimezoneContext';

function toIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function addDays(d: Date, days: number): Date {
  const copy = new Date(d);
  copy.setDate(copy.getDate() + days);
  return copy;
}

function derivePeriodRange(
  period: string,
  customFrom: string,
  customTo: string,
): { date_from?: string; date_to?: string } {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  switch (period) {
    case 'Сегодня':
      return { date_from: toIsoDate(today), date_to: toIsoDate(today) };
    case 'Вчера': {
      const y = addDays(today, -1);
      return { date_from: toIsoDate(y), date_to: toIsoDate(y) };
    }
    case '7 дней':
      return { date_from: toIsoDate(addDays(today, -6)), date_to: toIsoDate(today) };
    case '30 дней':
      return { date_from: toIsoDate(addDays(today, -29)), date_to: toIsoDate(today) };
    case 'Указать период':
      return customFrom && customTo
        ? { date_from: customFrom, date_to: customTo }
        : {};
    default:
      return {};
  }
}

const BG_COLORS = [
  'bg-yellow-100', 'bg-blue-50', 'bg-orange-100', 'bg-purple-50', 'bg-green-50',
  'bg-pink-50', 'bg-indigo-50', 'bg-teal-50', 'bg-cyan-50', 'bg-amber-50',
];

export default function AdminDashboard() {
  const tz = useTimezone();
  const [activePeriod, setActivePeriod] = useState('Сегодня');
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [customPeriodLabel, setCustomPeriodLabel] = useState('');

  const dateRange = useMemo(
    () => derivePeriodRange(activePeriod, startDate, endDate),
    [activePeriod, startDate, endDate],
  );

  const { data: dashboard, isLoading } = useQuery({
    queryKey: ['adminDashboard', dateRange.date_from ?? '', dateRange.date_to ?? ''],
    queryFn: () => fetchAdminDashboard(dateRange),
  });

  const d = dashboard;

  const periods = ['Сегодня', 'Вчера', '7 дней', '30 дней', 'Указать период'];

  type FinanceTab = 'total_cost' | 'current_debt' | 'overdue_debt' | 'paid';
  const [financeTab, setFinanceTab] = useState<FinanceTab>('total_cost');

  const financeTabConfig: { key: FinanceTab; label: string }[] = [
    { key: 'total_cost', label: 'Общая стоимость' },
    { key: 'current_debt', label: 'Текущая' },
    { key: 'overdue_debt', label: 'Просроченная' },
    { key: 'paid', label: 'Оплачено' },
  ];

  const financeFieldMap: Record<FinanceTab, keyof NonNullable<typeof d>['top_partners'][number]> = {
    total_cost: 'finance_total_cost',
    current_debt: 'finance_current_debt',
    overdue_debt: 'finance_overdue_debt',
    paid: 'finance_paid',
  };

  const sortedTopPartners = [...(d?.top_partners ?? [])]
    .sort((a, b) => (b[financeFieldMap[financeTab]] as number) - (a[financeFieldMap[financeTab]] as number))
    .slice(0, 10);

  const topPartners = sortedTopPartners.map((p, i) => ({
    id: p.id,
    name: p.company_name,
    value: ((p[financeFieldMap[financeTab]] as number) / 100).toLocaleString('ru-RU') + ' ₽',
    color: BG_COLORS[i % BG_COLORS.length],
  }));

  const STATUS_MAP: Record<string, string> = { completed: 'Завершено', pending: 'В обработке', failed: 'Ошибка' };
  const transactions = (d?.recent_transactions ?? []).map((t) => ({
    id: t.id.slice(0, 8),
    partner: t.partner_name,
    client: t.client_name ?? '—',
    amount: (t.amount / 100).toLocaleString('ru-RU'),
    date: formatDateShort(t.created_at, tz),
    status: STATUS_MAP[t.status] ?? t.status,
  }));

  const handlePeriodClick = (period: string) => {
    if (period === 'Указать период') {
      setShowDatePicker(true);
    } else {
      setActivePeriod(period);
      setCustomPeriodLabel('');
    }
  };

  const handleApplyCustomPeriod = () => {
    if (startDate && endDate) {
      const formattedLabel = `${formatDateShort(startDate, tz)} - ${formatDateShort(endDate, tz)}`;
      setCustomPeriodLabel(formattedLabel);
      setActivePeriod('Указать период');
      setShowDatePicker(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Вкладки периодов */}
      <div className="bg-white rounded-xl shadow-sm p-1">
        <div className="flex gap-1">
          {periods.map((period) => (
            <button
              key={period}
              onClick={() => handlePeriodClick(period)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                activePeriod === period
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {period === 'Указать период' && customPeriodLabel ? (
                <span className="flex items-center gap-1">
                  <Calendar className="w-4 h-4" />
                  {customPeriodLabel}
                </span>
              ) : (
                period
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Модальное окно выбора периода */}
      {showDatePicker && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 pointer-events-auto border border-gray-200">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-semibold text-gray-900">
                Укажите период
              </h3>
              <button
                onClick={() => setShowDatePicker(false)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Дата начала
                </label>
                <DateInput
                  value={startDate}
                  onChange={(val) => setStartDate(val)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Дата окончания
                </label>
                <DateInput
                  value={endDate}
                  onChange={(val) => setEndDate(val)}
                  min={startDate}
                />
              </div>
            </div>

            <div className="mt-6 flex gap-3">
              <button
                onClick={() => setShowDatePicker(false)}
                className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
              >
                Отмена
              </button>
              <button
                onClick={handleApplyCustomPeriod}
                disabled={!startDate || !endDate}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed"
              >
                Применить
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Статистика */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <DollarSign className="w-5 h-5 text-blue-600" />
            </div>
          </div>
          <p className="text-sm text-gray-600 mb-1">Общая стоимость судебных расходов</p>
          <p className="text-2xl font-bold text-gray-900">
            {((d?.finance_stats.total_cost ?? 0) / 100).toLocaleString('ru-RU')} ₽
          </p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="w-10 h-10 bg-yellow-100 rounded-lg flex items-center justify-center">
              <Clock className="w-5 h-5 text-yellow-600" />
            </div>
          </div>
          <p className="text-sm text-gray-600 mb-1">Текущая задолженность</p>
          <p className="text-2xl font-bold text-yellow-600">
            {((d?.finance_stats.current_debt ?? 0) / 100).toLocaleString('ru-RU')} ₽
          </p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
              <AlertCircle className="w-5 h-5 text-red-600" />
            </div>
          </div>
          <p className="text-sm text-gray-600 mb-1">Просроченная задолженность</p>
          <p className="text-2xl font-bold text-red-600">
            {((d?.finance_stats.overdue_debt ?? 0) / 100).toLocaleString('ru-RU')} ₽
          </p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <TrendingUp className="w-5 h-5 text-green-600" />
            </div>
          </div>
          <p className="text-sm text-gray-600 mb-1">Оплачено</p>
          <p className="text-2xl font-bold text-green-600">
            {((d?.finance_stats.paid ?? 0) / 100).toLocaleString('ru-RU')} ₽
          </p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
              <Users className="w-5 h-5 text-indigo-600" />
            </div>
          </div>
          <p className="text-sm text-gray-600 mb-1">Партнёров</p>
          <p className="text-2xl font-bold text-gray-900">{d?.main_stats.partners_count ?? 0}</p>
          <p className="text-xs text-gray-500 mt-1">Клиентов: {d?.main_stats.total_clients ?? 0}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Топ партнеров */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">
              Топ-10 партнеров
            </h3>
            <Link to="/admin/partners" className="text-sm text-blue-600 hover:underline">
              Список партнеров
            </Link>
          </div>

          <div className="flex flex-wrap gap-1 mb-4 bg-gray-100 p-1 rounded-lg">
            {financeTabConfig.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setFinanceTab(tab.key)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  financeTab === tab.key
                    ? 'bg-white text-blue-600 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-4 text-xs text-gray-500 font-medium pb-2">
              <div>Партнер</div>
              <div className="text-right">Сумма</div>
            </div>
            {topPartners.map((partner, index) => (
              <Link
                key={partner.id}
                to={`/admin/partners/${partner.id}`}
                className={`grid grid-cols-2 gap-4 p-3 rounded-lg hover:opacity-80 transition-opacity ${partner.color}`}
              >
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center">
                    <Users className="w-4 h-4 text-gray-600" />
                  </div>
                  <span className="text-sm font-medium text-gray-900">{partner.name}</span>
                </div>
                <div className="text-right text-sm font-semibold text-gray-900">
                  {partner.value}
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* Последние транзакции */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold text-gray-900">Транзакции за период</h3>
            <Link to="/admin/transactions" className="text-sm text-blue-600 hover:underline">
              Все транзакции
            </Link>
          </div>

          {transactions.length > 0 ? (
            <div className="space-y-4">
              {transactions.map((transaction) => (
                <div
                  key={transaction.id}
                  className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <CreditCard className="w-5 h-5 text-gray-400" />
                      <span className="text-sm font-medium text-gray-900">
                        {transaction.id}
                      </span>
                    </div>
                    <span
                      className={`text-xs px-2 py-1 rounded-full ${
                        transaction.status === 'Завершено'
                          ? 'bg-green-100 text-green-700'
                          : 'bg-yellow-100 text-yellow-700'
                      }`}
                    >
                      {transaction.status}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-600">{transaction.partner}</p>
                      <p className="text-xs text-gray-500 mt-0.5">Клиент: {transaction.client}</p>
                      <p className="text-xs text-gray-400 mt-0.5">{transaction.date}</p>
                    </div>
                    <p className="text-lg font-semibold text-gray-900">
                      {transaction.amount} ₽
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <p className="text-gray-500">Данные не найдены</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}