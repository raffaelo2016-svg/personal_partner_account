import { useState, useRef, useEffect } from 'react';
import { ChevronDown, Search, Clock, X } from 'lucide-react';

const TIMEZONES = [
  { value: 'Europe/Kaliningrad', label: 'Калининград', offset: 'UTC+2' },
  { value: 'Europe/Moscow', label: 'Москва', offset: 'UTC+3' },
  { value: 'Europe/Samara', label: 'Самара', offset: 'UTC+4' },
  { value: 'Asia/Yekaterinburg', label: 'Екатеринбург', offset: 'UTC+5' },
  { value: 'Asia/Omsk', label: 'Омск', offset: 'UTC+6' },
  { value: 'Asia/Krasnoyarsk', label: 'Красноярск', offset: 'UTC+7' },
  { value: 'Asia/Irkutsk', label: 'Иркутск', offset: 'UTC+8' },
  { value: 'Asia/Yakutsk', label: 'Якутск', offset: 'UTC+9' },
  { value: 'Asia/Vladivostok', label: 'Владивосток', offset: 'UTC+10' },
  { value: 'Asia/Magadan', label: 'Магадан', offset: 'UTC+11' },
  { value: 'Asia/Kamchatka', label: 'Камчатка', offset: 'UTC+12' },
  { value: 'Europe/London', label: 'Лондон', offset: 'UTC+0' },
  { value: 'Europe/Berlin', label: 'Берлин', offset: 'UTC+1' },
  { value: 'Europe/Paris', label: 'Париж', offset: 'UTC+1' },
  { value: 'Europe/Istanbul', label: 'Стамбул', offset: 'UTC+3' },
  { value: 'Asia/Dubai', label: 'Дубай', offset: 'UTC+4' },
  { value: 'Asia/Tashkent', label: 'Ташкент', offset: 'UTC+5' },
  { value: 'Asia/Almaty', label: 'Алматы', offset: 'UTC+6' },
  { value: 'Asia/Bangkok', label: 'Бангкок', offset: 'UTC+7' },
  { value: 'Asia/Shanghai', label: 'Шанхай', offset: 'UTC+8' },
  { value: 'Asia/Tokyo', label: 'Токио', offset: 'UTC+9' },
  { value: 'America/New_York', label: 'Нью-Йорк', offset: 'UTC-5' },
  { value: 'America/Chicago', label: 'Чикаго', offset: 'UTC-6' },
  { value: 'America/Denver', label: 'Денвер', offset: 'UTC-7' },
  { value: 'America/Los_Angeles', label: 'Лос-Анджелес', offset: 'UTC-8' },
  { value: 'Pacific/Honolulu', label: 'Гонолулу', offset: 'UTC-10' },
];

interface TimezoneSelectProps {
  value: string;
  onChange: (value: string) => void;
}

export default function TimezoneSelect({ value, onChange }: TimezoneSelectProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setSearch('');
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  useEffect(() => {
    if (open && inputRef.current) inputRef.current.focus();
  }, [open]);

  const selected = TIMEZONES.find((tz) => tz.value === value);
  const query = search.toLowerCase();
  const filtered = TIMEZONES.filter(
    (tz) =>
      tz.label.toLowerCase().includes(query) ||
      tz.value.toLowerCase().includes(query) ||
      tz.offset.toLowerCase().includes(query),
  );

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between gap-2 px-4 py-2.5 bg-white border border-gray-300 rounded-lg hover:border-gray-400 transition-colors text-left"
      >
        <div className="flex items-center gap-2 min-w-0">
          <Clock className="w-4 h-4 text-gray-400 shrink-0" />
          <span className="text-sm text-gray-900 truncate">
            {selected ? `${selected.label} (${selected.offset})` : value}
          </span>
        </div>
        <ChevronDown className={`w-4 h-4 text-gray-400 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-full bg-white border border-gray-200 rounded-xl shadow-xl overflow-hidden">
          <div className="p-2 border-b border-gray-100">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                ref={inputRef}
                type="text"
                placeholder="Поиск часового пояса..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-9 pr-8 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              {search && (
                <button
                  onClick={() => setSearch('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
          <div className="max-h-64 overflow-y-auto">
            {filtered.length === 0 ? (
              <div className="px-4 py-6 text-center text-sm text-gray-500">Ничего не найдено</div>
            ) : (
              filtered.map((tz) => (
                <button
                  key={tz.value}
                  type="button"
                  onClick={() => {
                    onChange(tz.value);
                    setOpen(false);
                    setSearch('');
                  }}
                  className={`w-full flex items-center justify-between px-4 py-2.5 text-sm hover:bg-blue-50 transition-colors ${
                    value === tz.value ? 'bg-blue-50 text-blue-700' : 'text-gray-700'
                  }`}
                >
                  <span>{tz.label}</span>
                  <span className="text-xs text-gray-400 font-mono">{tz.offset}</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
