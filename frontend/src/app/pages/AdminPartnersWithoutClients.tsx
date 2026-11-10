import { ArrowLeft, Clock3, Loader2, Phone, Users } from 'lucide-react';
import { useCallback, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router';
import type { PartnerClientPauseMode } from '@/app/api/partners';
import { useTimezone } from '@/app/contexts/TimezoneContext';
import { useIntersectionObserver } from '@/app/hooks/useIntersectionObserver';
import { useInfinitePartnersWithoutClients } from '@/app/hooks/usePartners';
import { formatDateShort } from '@/app/utils/formatDate';
import {
  formatPauseDays,
  partnerPauseTone,
  PARTNER_PAUSE_BLUE_AFTER_DAYS,
  PARTNER_PAUSE_LIST_DAYS,
  PARTNER_PAUSE_RED_AFTER_DAYS,
  type PartnerPauseTone,
} from '@/app/utils/partnerPause';

const TABS: { mode: PartnerClientPauseMode; label: string; hint: string }[] = [
  { mode: 'no_clients', label: 'Не рабочие', hint: 'Ни одного клиента за всё время' },
  { mode: 'stalled', label: 'Затихшие', hint: 'Клиенты были, но последний — давно' },
];

const TONE_ROW: Record<PartnerPauseTone, string> = {
  neutral: 'border-l-transparent',
  blue: 'border-l-sky-500 bg-sky-50/60',
  red: 'border-l-red-500 bg-red-50/70',
};

const TONE_BADGE: Record<PartnerPauseTone, string> = {
  neutral: 'bg-gray-100 text-gray-600 border-gray-200',
  blue: 'bg-sky-100 text-sky-700 border-sky-200',
  red: 'bg-red-100 text-red-700 border-red-200',
};

const TONE_TEXT: Record<PartnerPauseTone, string> = {
  neutral: 'text-gray-600',
  blue: 'text-sky-700',
  red: 'text-red-700',
};

export default function AdminPartnersWithoutClients() {
  const tz = useTimezone();
  const [searchParams, setSearchParams] = useSearchParams();
  const mode: PartnerClientPauseMode = searchParams.get('mode') === 'stalled' ? 'stalled' : 'no_clients';

  const { data: pages, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useInfinitePartnersWithoutClients(mode);

  const loadMore = useCallback(() => { if (hasNextPage) fetchNextPage(); }, [hasNextPage, fetchNextPage]);
  const sentinelRef = useIntersectionObserver(loadMore, !!hasNextPage && !isFetchingNextPage);

  const partners = useMemo(() => pages?.pages.flatMap((p) => p.items) ?? [], [pages]);
  const total = pages?.pages[0]?.total ?? 0;
  const counts = pages?.pages[0]?.counts ?? { no_clients: 0, stalled: 0 };

  const activeTab = TABS.find((tab) => tab.mode === mode) ?? TABS[0];
  const isNoClients = mode === 'no_clients';

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/admin/partners"
          className="mb-3 inline-flex items-center gap-1 text-sm font-medium text-gray-500 hover:text-gray-900"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Все партнёры
        </Link>
        <h1 className="text-3xl font-semibold text-gray-900">Партнёры без клиентов</h1>
        <p className="mt-2 max-w-3xl text-gray-600">
          Активные партнёры без клиентского потока больше {PARTNER_PAUSE_LIST_DAYS} дней. «Не рабочие» не
          передали ни одного клиента за всё время, «затихшие» передавали, но последний был давно. Красным
          подсвечены паузы больше {PARTNER_PAUSE_RED_AFTER_DAYS} дней, синим — больше{' '}
          {PARTNER_PAUSE_BLUE_AFTER_DAYS}. Список считается по тому же правилу, что и карточка «Нет первого
          клиента» на дашборде.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {TABS.map((tab) => {
          const isActive = tab.mode === mode;
          const count = tab.mode === 'no_clients' ? counts.no_clients : counts.stalled;
          return (
            <button
              key={tab.mode}
              type="button"
              onClick={() => setSearchParams({ mode: tab.mode })}
              className={`inline-flex items-center gap-2 rounded-xl border px-4 py-2 text-sm transition-colors ${
                isActive
                  ? 'border-blue-300 bg-blue-50 text-blue-700'
                  : 'border-gray-200 bg-white text-gray-600 hover:border-blue-200 hover:text-blue-700'
              }`}
              aria-pressed={isActive}
            >
              <span className="font-medium">{tab.label}</span>
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums ${
                  isActive ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'
                }`}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>

      <p className="text-sm text-gray-500">{activeTab.hint}</p>

      <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
        <span className="font-medium text-gray-700">Подсветка:</span>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-red-200 bg-red-50 px-2.5 py-1 text-red-700">
          <span className="h-2 w-2 rounded-full bg-red-500" aria-hidden="true" />
          больше {PARTNER_PAUSE_RED_AFTER_DAYS} дней
        </span>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-sky-700">
          <span className="h-2 w-2 rounded-full bg-sky-500" aria-hidden="true" />
          больше {PARTNER_PAUSE_BLUE_AFTER_DAYS} дней
        </span>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-gray-200 bg-white px-2.5 py-1 text-gray-600">
          <span className="h-2 w-2 rounded-full bg-gray-300" aria-hidden="true" />
          {PARTNER_PAUSE_LIST_DAYS}–{PARTNER_PAUSE_BLUE_AFTER_DAYS} дней
        </span>
      </div>

      <div className="flex items-center justify-between text-sm text-gray-600">
        <span>
          Найдено партнёров: <span className="font-medium text-gray-900">{total}</span>
        </span>
        <Link to="/admin/partners" className="text-blue-600 hover:underline">
          Все партнёры
        </Link>
      </div>

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
        {isLoading ? (
          <div className="flex items-center justify-center gap-2 px-4 py-12">
            <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
            <span className="text-gray-500">Загрузка...</span>
          </div>
        ) : partners.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-4 py-12 text-center text-gray-500">
            <Users className="h-10 w-10 text-gray-300" aria-hidden="true" />
            <p className="text-sm">
              {isNoClients
                ? 'Все активные партнёры уже передали хотя бы одного клиента'
                : 'Нет партнёров с длинной паузой в клиентах'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[880px]">
              <thead className="border-b border-gray-200 bg-gray-50">
                <tr>
                  <th className="px-3 py-2.5 text-left text-xs font-medium uppercase text-gray-600">Партнёр</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium uppercase text-gray-600">Директор</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium uppercase text-gray-600">
                    {isNoClients ? 'Без клиента' : 'Пауза без клиента'}
                  </th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium uppercase text-gray-600">
                    Последний клиент
                  </th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium uppercase text-gray-600">Регистрация</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium uppercase text-gray-600">Телефон</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {partners.map((partner) => {
                  const tone = partnerPauseTone(partner.days_without_client);
                  return (
                    <tr
                      key={partner.id}
                      className={`border-l-4 transition-colors hover:bg-blue-50/40 ${TONE_ROW[tone]}`}
                    >
                      <td className="px-3 py-3">
                        <Link
                          to={`/admin/partners/${partner.id}`}
                          className="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline"
                        >
                          {partner.company_name}
                        </Link>
                        <p className="mt-0.5 text-xs text-gray-400">
                          {partner.clients_count > 0
                            ? `Клиентов за всё время: ${partner.clients_count}`
                            : 'Клиентов за всё время: 0'}
                        </p>
                      </td>
                      <td className="px-3 py-3 text-sm text-gray-600">{partner.director_name}</td>
                      <td className="px-3 py-3">
                        <span
                          className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold tabular-nums ${TONE_BADGE[tone]}`}
                        >
                          <Clock3 className="h-3.5 w-3.5" aria-hidden="true" />
                          {formatPauseDays(partner.days_without_client)}
                        </span>
                      </td>
                      <td className={`px-3 py-3 text-sm ${TONE_TEXT[tone]}`}>
                        {partner.last_client_at ? formatDateShort(partner.last_client_at, tz) : '— не было'}
                      </td>
                      <td className="px-3 py-3 text-sm text-gray-600">{formatDateShort(partner.created_at, tz)}</td>
                      <td className="px-3 py-3">
                        <a
                          href={`tel:${partner.phone}`}
                          className="inline-flex items-center gap-1.5 text-sm text-gray-600 hover:text-blue-700"
                        >
                          <Phone className="h-3.5 w-3.5" aria-hidden="true" />
                          {partner.phone}
                        </a>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {(hasNextPage || isFetchingNextPage) && (
          <div ref={sentinelRef} className="flex justify-center border-t border-gray-200 py-4">
            <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
          </div>
        )}
      </div>
    </div>
  );
}
