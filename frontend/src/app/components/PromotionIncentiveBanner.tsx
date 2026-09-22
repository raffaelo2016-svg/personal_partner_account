import { CalendarClock, Gift, Plus } from 'lucide-react';
import { Link } from 'react-router';
import type { CourtFeeSummary } from '@/app/api/finance';

function formatDate(value?: string | null) {
  if (!value) return '';
  const [year, month, day] = value.split('-').map(Number);
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long' }).format(
    new Date(year, month - 1, day),
  );
}

export function PromotionIncentiveBanner({ summary }: { summary?: CourtFeeSummary }) {
  if (!summary?.promotion_active) return null;

  const clientProgress = Math.min(
    100,
    Math.round((summary.free_clients_used / summary.free_client_limit) * 100),
  );

  return (
    <section className="rounded-2xl bg-gradient-to-r from-blue-700 to-blue-500 text-white p-6 shadow-lg shadow-blue-100">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-start gap-4">
          <div className="rounded-xl bg-white/15 p-3">
            <Gift className="w-7 h-7" />
          </div>
          <div>
            <h2 className="text-xl font-semibold">Передайте ещё {summary.free_clients_remaining} клиентов бесплатно</h2>
            <p className="text-sm text-blue-100 mt-1">
              {summary.promotion_end_date
                ? `Предложение действует до ${formatDate(summary.promotion_end_date)}. Неиспользованный остаток сгорит.`
                : 'Без ограничения по сроку — до исчерпания лимита.'}
            </p>
          </div>
        </div>
        <Link
          to="/dashboard/clients/new"
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-white px-4 py-2.5 text-sm font-semibold text-blue-700 hover:bg-blue-50"
        >
          <Plus className="w-4 h-4" />
          Добавить клиента
        </Link>
      </div>
      <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-[1fr_auto] md:items-center">
        <div>
          <div className="flex justify-between text-xs text-blue-100 mb-2">
            <span>Передано бесплатно: {summary.free_clients_used} из {summary.free_client_limit}</span>
            <span>Осталось: {summary.free_clients_remaining}</span>
          </div>
          <div
            className="h-2.5 rounded-full bg-white/20 overflow-hidden"
            role="progressbar"
            aria-label="Использовано бесплатных клиентов"
            aria-valuemin={0}
            aria-valuemax={summary.free_client_limit}
            aria-valuenow={summary.free_clients_used}
          >
            <div className="h-full rounded-full bg-emerald-300" style={{ width: `${clientProgress}%` }} />
          </div>
        </div>
        <Link
          to="/dashboard/finance/court-fees"
          className="flex items-center gap-2 text-sm font-medium text-white hover:text-blue-100"
        >
          <CalendarClock className="w-4 h-4" />
          {summary.promotion_end_date
            ? `${summary.promotion_days_remaining} дней до окончания`
            : 'Без ограничения по сроку'}
        </Link>
      </div>
    </section>
  );
}
