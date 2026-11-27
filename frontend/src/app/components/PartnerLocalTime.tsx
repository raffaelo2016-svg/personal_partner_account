import { Clock3 } from 'lucide-react';
import { useEffect, useState } from 'react';

import { formatPartnerTime, timezoneForRegion, utcOffsetLabel } from '../utils/partnerTime';

interface PartnerLocalTimeProps {
  region?: string | null;
  className?: string;
}

/**
 * Плашка «Сейчас у партнёра»: время по часовому поясу региона партнёра,
 * с реальным смещением пояса и названием региона/города.
 */
export function PartnerLocalTime({ region, className = '' }: PartnerLocalTimeProps) {
  const timeZone = timezoneForRegion(region);
  const place = region?.trim() || 'Москва';
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 15_000);
    return () => window.clearInterval(timer);
  }, []);

  const time = formatPartnerTime(now, timeZone);
  const offset = utcOffsetLabel(now, timeZone);

  return (
    <div
      className={`flex items-center gap-3 rounded-xl border border-gray-200 bg-white px-4 py-2.5 shadow-sm ${className}`}
      title={`Время по региону партнёра: ${place} (${offset})`}
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-50">
        <Clock3 className="h-4 w-4 text-blue-600" aria-hidden="true" />
      </span>
      <div className="min-w-0">
        <p className="whitespace-nowrap text-[10px] font-semibold uppercase tracking-wide text-gray-500">
          Сейчас у партнёра
        </p>
        <p className="whitespace-nowrap text-lg font-semibold leading-tight text-gray-900">{time}</p>
        <p className="truncate whitespace-nowrap text-xs text-gray-500">
          {offset} · {place}
        </p>
      </div>
    </div>
  );
}
