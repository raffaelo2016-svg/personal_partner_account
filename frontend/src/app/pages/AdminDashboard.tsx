import type { ReactNode } from 'react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  AlertCircle,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Calendar,
  ChevronRight,
  CircleDollarSign,
  Clock3,
  FileWarning,
  Loader2,
  Receipt,
  TrendingDown,
  TrendingUp,
  UserCheck,
  UserPlus,
  Users,
  WalletCards,
  X,
  type LucideIcon,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { fetchAdminDashboard } from '../api/adminDashboard';
import DateInput from '../components/ui/DateInput';
import { formatDateShort, todayInMoscow } from '@/app/utils/formatDate';
import { useTimezone } from '@/app/contexts/TimezoneContext';

type PeriodKey = 'month' | 'quarter' | 'year' | 'custom';
type Tone = 'blue' | 'violet' | 'green' | 'amber' | 'red' | 'slate';

const PERIODS: { key: PeriodKey; label: string }[] = [
  { key: 'month', label: 'Месяц' },
  { key: 'quarter', label: 'Квартал' },
  { key: 'year', label: 'Год' },
  { key: 'custom', label: 'Период' },
];

const TONE_STYLES: Record<Tone, { icon: string; value: string }> = {
  blue: { icon: 'bg-blue-100 text-blue-700', value: 'text-gray-950' },
  violet: { icon: 'bg-violet-100 text-violet-700', value: 'text-gray-950' },
  green: { icon: 'bg-emerald-100 text-emerald-700', value: 'text-emerald-800' },
  amber: { icon: 'bg-amber-100 text-amber-700', value: 'text-amber-700' },
  red: { icon: 'bg-red-100 text-red-700', value: 'text-red-700' },
  slate: { icon: 'bg-slate-100 text-slate-700', value: 'text-gray-950' },
};

const MONTH_FORMATTER = new Intl.DateTimeFormat('ru-RU', { month: 'short', timeZone: 'UTC' });
const MONEY_FORMATTER = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 });

function toIsoDate(value: Date): string {
  const year = value.getUTCFullYear();
  const month = String(value.getUTCMonth() + 1).padStart(2, '0');
  const day = String(value.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function getPeriodRange(
  period: PeriodKey,
  customFrom: string,
  customTo: string,
): { date_from?: string; date_to?: string } {
  const today = new Date(`${todayInMoscow()}T00:00:00Z`);

  if (period === 'custom') {
    return customFrom && customTo ? { date_from: customFrom, date_to: customTo } : {};
  }

  const start = new Date(today);
  if (period === 'month') start.setUTCDate(1);
  if (period === 'quarter') start.setUTCMonth(Math.floor(today.getUTCMonth() / 3) * 3, 1);
  if (period === 'year') start.setUTCMonth(0, 1);

  return { date_from: toIsoDate(start), date_to: toIsoDate(today) };
}

function formatMoney(value: number): string {
  return `${MONEY_FORMATTER.format(value / 100)} ₽`;
}

function formatDelta(value: number | null): { label: string; positive: boolean } | null {
  if (value === null) return null;
  return { label: `${value > 0 ? '+' : ''}${value}%`, positive: value >= 0 };
}

function SectionShell({
  title,
  description,
  icon: Icon,
  tone,
  action,
  children,
}: {
  title: string;
  description: string;
  icon: LucideIcon;
  tone: 'blue' | 'violet' | 'green' | 'red';
  action?: ReactNode;
  children: ReactNode;
}) {
  const sectionStyles = {
    blue: 'border-blue-200 bg-blue-50/45',
    violet: 'border-violet-200 bg-violet-50/45',
    green: 'border-emerald-200 bg-emerald-50/50',
    red: 'border-red-200 bg-red-50/45',
  };
  const iconStyles = {
    blue: 'bg-blue-600 text-white',
    violet: 'bg-violet-600 text-white',
    green: 'bg-emerald-600 text-white',
    red: 'bg-red-600 text-white',
  };

  return (
    <section className={`rounded-2xl border p-4 lg:p-5 ${sectionStyles[tone]}`}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${iconStyles[tone]}`}>
            <Icon className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-950">{title}</h2>
            <p className="text-sm text-gray-600">{description}</p>
          </div>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function MetricCard({
  label,
  value,
  context,
  icon: Icon,
  tone,
  delta,
}: {
  label: string;
  value: string | number;
  context: string;
  icon: LucideIcon;
  tone: Tone;
  delta?: number | null;
}) {
  const deltaInfo = delta === undefined ? null : formatDelta(delta);
  return (
    <article className="min-w-0 rounded-xl border border-white/80 bg-white p-4 shadow-sm shadow-gray-200/40">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-gray-600">{label}</p>
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${TONE_STYLES[tone].icon}`}>
          <Icon className="h-4 w-4" aria-hidden="true" />
        </span>
      </div>
      <div className="mt-2 flex flex-wrap items-baseline gap-2">
        <p className={`text-2xl font-semibold tracking-tight ${TONE_STYLES[tone].value}`}>{value}</p>
        {deltaInfo ? (
          <span className={`inline-flex items-center text-xs font-semibold ${deltaInfo.positive ? 'text-emerald-700' : 'text-red-600'}`}>
            {deltaInfo.positive ? <ArrowUpRight className="mr-0.5 h-3.5 w-3.5" /> : <ArrowDownRight className="mr-0.5 h-3.5 w-3.5" />}
            {deltaInfo.label}
          </span>
        ) : null}
      </div>
      <p className="mt-1 text-xs leading-5 text-gray-500">{context}</p>
    </article>
  );
}

function RiskItem({
  icon: Icon,
  label,
  description,
  value,
  critical = false,
  to,
}: {
  icon: LucideIcon;
  label: string;
  description: string;
  value: number;
  critical?: boolean;
  to?: string;
}) {
  const content = (
    <>
      <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${critical ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'}`}>
        <Icon className="h-4 w-4" aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-gray-900">{label}</p>
        <p className="text-xs text-gray-500">{description}</p>
      </div>
      <span className={`text-xl font-semibold ${critical ? 'text-red-700' : 'text-amber-700'}`}>{value}</span>
      {to && <ChevronRight className="h-4 w-4 shrink-0 text-gray-400" aria-hidden="true" />}
    </>
  );

  if (to) {
    return (
      <Link
        to={to}
        className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white p-3 transition-colors hover:border-blue-300 hover:bg-blue-50/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      >
        {content}
      </Link>
    );
  }

  return <div className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white p-3">{content}</div>;
}

export default function AdminDashboard() {
  const tz = useTimezone();
  const [activePeriod, setActivePeriod] = useState<PeriodKey>('month');
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const dateRange = useMemo(
    () => getPeriodRange(activePeriod, startDate, endDate),
    [activePeriod, startDate, endDate],
  );

  const { data: dashboard, isLoading, isError } = useQuery({
    queryKey: ['adminDashboard', dateRange.date_from ?? '', dateRange.date_to ?? ''],
    queryFn: () => fetchAdminDashboard(dateRange),
  });

  const periodLabel = useMemo(() => {
    if (!dateRange.date_from || !dateRange.date_to) return 'Выберите период';
    return `${formatDateShort(dateRange.date_from, tz)} — ${formatDateShort(dateRange.date_to, tz)}`;
  }, [dateRange.date_from, dateRange.date_to, tz]);

  const trend = useMemo(
    () => (dashboard?.activity_trend ?? []).map((item) => ({
      ...item,
      label: MONTH_FORMATTER.format(new Date(`${item.month}T00:00:00`)).replace('.', ''),
    })),
    [dashboard?.activity_trend],
  );

  const rankedPartners = useMemo(
    () => [...(dashboard?.top_partners ?? [])]
      .sort((a, b) => b.clients_count - a.clients_count || b.finance_paid - a.finance_paid)
      .slice(0, 8),
    [dashboard?.top_partners],
  );

  const handlePeriodClick = (period: PeriodKey) => {
    if (period === 'custom') {
      setShowDatePicker(true);
      return;
    }
    setActivePeriod(period);
  };

  const applyCustomPeriod = () => {
    if (!startDate || !endDate) return;
    setActivePeriod('custom');
    setShowDatePicker(false);
  };

  if (isLoading && !dashboard) {
    return (
      <div className="flex min-h-[420px] items-center justify-center rounded-2xl border border-gray-200 bg-white">
        <div className="text-center text-gray-500">
          <Loader2 className="mx-auto mb-3 h-7 w-7 animate-spin" />
          Загружаем аналитику
        </div>
      </div>
    );
  }

  if (isError || !dashboard) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-800">
        Не удалось загрузить показатели дашборда. Обновите страницу или повторите попытку позже.
      </div>
    );
  }

  const d = dashboard;
  const clientStatusData = [
    { name: 'До суда', value: d.movement_stats.before_court, color: '#7c3aed' },
    { name: 'В суде', value: d.movement_stats.in_court, color: '#a78bfa' },
    { name: 'Завершено', value: d.movement_stats.completed, color: '#c4b5fd' },
  ];
  const financeChartData = [
    { name: 'Начислено', value: d.finance_stats.total_cost, fill: '#059669' },
    { name: 'Оплачено', value: d.finance_stats.paid, fill: '#34d399' },
    { name: 'Текущий долг', value: d.finance_stats.current_debt, fill: '#f59e0b' },
    { name: 'Просрочено', value: d.finance_stats.overdue_debt, fill: '#ef4444' },
  ];

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-gray-950">Обзор партнёрской сети</h1>
          <p className="mt-1 text-sm text-gray-500">Ключевые показатели, клиентский поток, финансы и риски</p>
          <p className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-blue-700">
            <Calendar className="h-3.5 w-3.5" aria-hidden="true" />
            {periodLabel}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-gray-200 bg-white p-1 shadow-sm">
          {PERIODS.map((period) => (
            <button
              key={period.key}
              type="button"
              onClick={() => handlePeriodClick(period.key)}
              aria-pressed={activePeriod === period.key}
              className={`rounded-lg px-3 py-2 text-sm transition-colors ${
                activePeriod === period.key
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
              }`}
            >
              {period.label}
            </button>
          ))}
        </div>
      </header>

      {showDatePicker ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-950/35 p-4" role="dialog" aria-modal="true" aria-labelledby="period-dialog-title">
          <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-6 shadow-2xl">
            <div className="mb-5 flex items-center justify-between">
              <h2 id="period-dialog-title" className="text-lg font-semibold text-gray-950">Указать период</h2>
              <button type="button" onClick={() => setShowDatePicker(false)} aria-label="Закрыть" className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-700">
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">Дата начала</label>
                <DateInput value={startDate} onChange={setStartDate} />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">Дата окончания</label>
                <DateInput value={endDate} onChange={setEndDate} min={startDate} />
              </div>
            </div>
            <div className="mt-6 flex gap-3">
              <button type="button" onClick={() => setShowDatePicker(false)} className="flex-1 rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">Отмена</button>
              <button type="button" onClick={applyCustomPeriod} disabled={!startDate || !endDate} className="flex-1 rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-300">Применить</button>
            </div>
          </div>
        </div>
      ) : null}

      <SectionShell
        title="Управленческие показатели"
        description="Рост и активность партнёрской сети"
        icon={BarChart3}
        tone="blue"
        action={<Link to="/admin/partners" className="inline-flex items-center gap-1 text-sm font-medium text-blue-700 hover:underline">Все партнёры <ArrowRight className="h-4 w-4" /></Link>}
      >
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Новые партнёры" value={d.main_stats.partners_count} context={`${d.main_stats.pending_partners} ожидают модерации`} icon={UserPlus} tone="blue" delta={d.comparison_stats.new_partners_change_pct} />
          <MetricCard label="Передающие партнёры" value={d.main_stats.transmitting_partners} context="Передали хотя бы одного клиента" icon={Activity} tone="blue" delta={d.comparison_stats.active_partners_change_pct} />
          <MetricCard label="Конверсия в активацию" value={`${d.main_stats.activation_rate}%`} context={`${d.main_stats.activated_new_partners} новых партнёров передали клиента`} icon={UserCheck} tone="blue" />
          <MetricCard label="Всего партнёров" value={d.main_stats.total_partners} context={`${d.main_stats.total_active_partners} в статусе «Активен»`} icon={Users} tone="slate" />
        </div>
      </SectionShell>

      <SectionShell
        title="Клиентский поток"
        description="Поступление, распределение и движение клиентов"
        icon={Users}
        tone="violet"
        action={<Link to="/admin/clients" className="inline-flex items-center gap-1 text-sm font-medium text-violet-700 hover:underline">Все клиенты <ArrowRight className="h-4 w-4" /></Link>}
      >
        <div className="mb-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <MetricCard label="Передано клиентов" value={d.main_stats.total_clients} context="Созданы за выбранный период" icon={Users} tone="violet" delta={d.comparison_stats.clients_change_pct} />
          <MetricCard label="На партнёра" value={d.main_stats.clients_per_active_partner.toLocaleString('ru-RU')} context="Среднее среди передающих" icon={TrendingUp} tone="violet" />
          <MetricCard label="До суда" value={d.movement_stats.before_court} context="Новые клиенты периода" icon={Receipt} tone="violet" />
          <MetricCard label="В суде" value={d.movement_stats.in_court} context="Новые клиенты периода" icon={CircleDollarSign} tone="violet" />
          <MetricCard label="Завершено" value={d.movement_stats.completed} context="Реализация и завершённые дела" icon={UserCheck} tone="green" />
          <MetricCard label="Без движения" value={d.movement_stats.without_movement} context="Нет обновлений более 14 дней" icon={Clock3} tone="amber" />
        </div>

        <div className="grid gap-3 xl:grid-cols-[minmax(0,1.7fr)_minmax(280px,0.7fr)]">
          <div className="rounded-xl border border-white/80 bg-white p-4">
            <div className="mb-3">
              <h3 className="text-sm font-semibold text-gray-900">Динамика партнёрского канала</h3>
              <p className="text-xs text-gray-500">Последние шесть месяцев</p>
            </div>
            <div className="h-64" aria-label="График динамики партнёров и клиентов">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={trend} margin={{ top: 10, right: 12, left: -16, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                  <XAxis dataKey="label" tick={{ fill: '#6b7280', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#6b7280', fontSize: 12 }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <Tooltip contentStyle={{ borderRadius: 12, borderColor: '#e5e7eb', fontSize: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 12, paddingTop: 10 }} />
                  <Bar dataKey="clients" name="Клиенты" fill="#8b5cf6" radius={[5, 5, 0, 0]} maxBarSize={42} />
                  <Line type="monotone" dataKey="active_partners" name="Передающие партнёры" stroke="#2563eb" strokeWidth={2.5} dot={{ r: 3 }} />
                  <Line type="monotone" dataKey="new_partners" name="Новые партнёры" stroke="#10b981" strokeWidth={2.5} dot={{ r: 3 }} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="rounded-xl border border-white/80 bg-white p-4">
            <h3 className="text-sm font-semibold text-gray-900">Статусы новых клиентов</h3>
            <p className="text-xs text-gray-500">По выбранному периоду</p>
            {d.main_stats.total_clients > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={clientStatusData} dataKey="value" nameKey="name" innerRadius={52} outerRadius={82} paddingAngle={3}>
                      {clientStatusData.map((entry) => <Cell key={entry.name} fill={entry.color} />)}
                    </Pie>
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="flex h-64 items-center justify-center text-sm text-gray-500">Нет клиентов за период</div>
            )}
          </div>
        </div>
      </SectionShell>

      <SectionShell
        title="Финансовые показатели"
        description="Начисления, оплаты и задолженность партнёров"
        icon={CircleDollarSign}
        tone="green"
        action={<Link to="/admin/transactions" className="inline-flex items-center gap-1 text-sm font-medium text-emerald-700 hover:underline">Все транзакции <ArrowRight className="h-4 w-4" /></Link>}
      >
        <div className="grid gap-3 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.75fr)]">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <MetricCard label="Начислено" value={formatMoney(d.finance_stats.total_cost)} context="Новые начисления за период" icon={Receipt} tone="green" />
            <MetricCard label="Оплачено" value={formatMoney(d.finance_stats.paid)} context="Платежи за выбранный период" icon={WalletCards} tone="green" />
            <MetricCard label="Текущий долг" value={formatMoney(d.finance_stats.current_debt)} context="Остаток на конец периода" icon={Clock3} tone="amber" />
            <MetricCard label="Просрочено" value={formatMoney(d.finance_stats.overdue_debt)} context={`${d.finance_stats.partners_with_overdue} партнёров с просрочкой`} icon={AlertCircle} tone="red" />
            <MetricCard label="Собираемость" value={`${d.finance_stats.collection_rate}%`} context={`Доля просрочки — ${d.finance_stats.overdue_share}%`} icon={TrendingUp} tone="green" />
          </div>

          <div className="rounded-xl border border-white/80 bg-white p-4">
            <h3 className="text-sm font-semibold text-gray-900">Структура финансов</h3>
            <p className="text-xs text-gray-500">Период и остатки на дату окончания</p>
            <div className="mt-2 h-56" aria-label="Диаграмма финансовых показателей">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={financeChartData} layout="vertical" margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={false} />
                  <XAxis type="number" hide />
                  <YAxis type="category" dataKey="name" width={92} tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip formatter={(value) => formatMoney(Number(value))} contentStyle={{ borderRadius: 12, borderColor: '#e5e7eb', fontSize: 12 }} />
                  <Bar dataKey="value" radius={[0, 6, 6, 0]} maxBarSize={24}>
                    {financeChartData.map((entry) => <Cell key={entry.name} fill={entry.fill} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </SectionShell>

      <SectionShell
        title="Риски и внимание"
        description="События, требующие управленческого решения"
        icon={AlertCircle}
        tone="red"
        action={<Link to="/admin/bitrix-attention" className="inline-flex items-center gap-1 text-sm font-medium text-red-700 hover:underline">Требует внимания <ArrowRight className="h-4 w-4" /></Link>}
      >
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <RiskItem
            icon={Clock3}
            label="Нет первого клиента"
            description="Активны более 14 дней"
            value={d.risk_stats.partners_without_first_client}
            to="/admin/partners/without-clients?mode=no_clients"
          />
          <RiskItem icon={TrendingDown} label="Снижение потока" description="Более чем на 50% к прошлому периоду" value={d.risk_stats.declining_partners} critical />
          <RiskItem icon={FileWarning} label="Клиенты без движения" description="Нет обновлений более 14 дней" value={d.risk_stats.clients_without_movement} critical />
          <RiskItem icon={CircleDollarSign} label="Партнёры с просрочкой" description="Есть неоплаченный просроченный счёт" value={d.risk_stats.partners_with_overdue} critical />
        </div>
      </SectionShell>

      <section className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm lg:p-5">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-gray-950">Рейтинг партнёров</h2>
            <p className="text-sm text-gray-500">По клиентскому потоку и платёжной дисциплине за выбранный период</p>
          </div>
          <Link to="/admin/partners" className="inline-flex items-center gap-1 text-sm font-medium text-blue-700 hover:underline">Полный список <ArrowRight className="h-4 w-4" /></Link>
        </div>

        {rankedPartners.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[880px] border-collapse text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs font-medium text-gray-500">
                  <th className="px-3 py-3">Партнёр</th>
                  <th className="px-3 py-3 text-right">Клиенты</th>
                  <th className="px-3 py-3 text-right">Последняя передача</th>
                  <th className="px-3 py-3 text-right">Начислено</th>
                  <th className="px-3 py-3 text-right">Оплачено</th>
                  <th className="px-3 py-3 text-right">Просрочено</th>
                  <th className="px-3 py-3 text-right">Собираемость</th>
                </tr>
              </thead>
              <tbody>
                {rankedPartners.map((partner, index) => {
                  const partnerCollection = partner.finance_total_cost > 0
                    ? Math.round((partner.finance_paid / partner.finance_total_cost) * 100)
                    : 0;
                  return (
                    <tr key={partner.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
                      <td className="px-3 py-3">
                        <Link to={`/admin/partners/${partner.id}`} className="flex items-center gap-3 font-medium text-gray-900 hover:text-blue-700">
                          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-50 text-xs font-semibold text-blue-700">{index + 1}</span>
                          {partner.company_name}
                        </Link>
                      </td>
                      <td className="px-3 py-3 text-right font-semibold text-gray-950">{partner.clients_count}</td>
                      <td className="px-3 py-3 text-right text-gray-600">{partner.last_client_at ? formatDateShort(partner.last_client_at, tz) : '—'}</td>
                      <td className="px-3 py-3 text-right text-gray-600">{formatMoney(partner.finance_total_cost)}</td>
                      <td className="px-3 py-3 text-right text-emerald-700">{formatMoney(partner.finance_paid)}</td>
                      <td className={`px-3 py-3 text-right ${partner.finance_overdue_debt > 0 ? 'font-medium text-red-700' : 'text-gray-500'}`}>{formatMoney(partner.finance_overdue_debt)}</td>
                      <td className="px-3 py-3 text-right">
                        <span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${partnerCollection >= 80 ? 'bg-emerald-100 text-emerald-700' : partnerCollection >= 50 ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>
                          {partnerCollection}%
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="rounded-xl bg-gray-50 py-12 text-center text-sm text-gray-500">За выбранный период партнёры не передавали клиентов</div>
        )}
      </section>
    </div>
  );
}
