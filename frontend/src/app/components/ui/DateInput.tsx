import { useState, useRef, useEffect, useCallback } from 'react';
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight } from 'lucide-react';

interface DateInputProps {
  value: string;
  onChange: (isoDate: string) => void;
  placeholder?: string;
  className?: string;
  required?: boolean;
  min?: string;
  disabled?: boolean;
}

const MONTHS = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
];
const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

function isoToDisplay(iso: string): string {
  if (!iso) return '';
  const [y, m, d] = iso.split('-');
  if (!y || !m || !d) return '';
  return `${d}.${m}.${y}`;
}

function displayToIso(display: string): string {
  const clean = display.replace(/\D/g, '');
  if (clean.length !== 8) return '';
  const d = clean.slice(0, 2);
  const m = clean.slice(2, 4);
  const y = clean.slice(4, 8);
  const day = parseInt(d, 10);
  const month = parseInt(m, 10);
  const year = parseInt(y, 10);
  if (month < 1 || month > 12 || day < 1 || day > 31 || year < 1900 || year > 2100) return '';
  return `${y}-${m}-${d}`;
}

function formatWithDots(raw: string): string {
  const digits = raw.replace(/\D/g, '').slice(0, 8);
  let result = '';
  for (let i = 0; i < digits.length; i++) {
    if (i === 2 || i === 4) result += '.';
    result += digits[i];
  }
  return result;
}

function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(year: number, month: number): number {
  const day = new Date(year, month, 1).getDay();
  return day === 0 ? 6 : day - 1;
}

export default function DateInput({
  value,
  onChange,
  placeholder = 'ДД.ММ.ГГГГ',
  className = '',
  required,
  min,
  disabled,
}: DateInputProps) {
  const [displayValue, setDisplayValue] = useState(() => isoToDisplay(value));
  const [showCalendar, setShowCalendar] = useState(false);
  const [calYear, setCalYear] = useState(() => {
    if (value) return parseInt(value.split('-')[0], 10);
    return new Date().getFullYear();
  });
  const [calMonth, setCalMonth] = useState(() => {
    if (value) return parseInt(value.split('-')[1], 10) - 1;
    return new Date().getMonth();
  });
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setDisplayValue(isoToDisplay(value));
  }, [value]);

  useEffect(() => {
    if (value) {
      setCalYear(parseInt(value.split('-')[0], 10));
      setCalMonth(parseInt(value.split('-')[1], 10) - 1);
    }
  }, [value]);

  const close = useCallback(() => setShowCalendar(false), []);

  useEffect(() => {
    if (!showCalendar) return;
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) close();
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [showCalendar, close]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const formatted = formatWithDots(e.target.value);
    setDisplayValue(formatted);

    const iso = displayToIso(formatted);
    if (iso) {
      onChange(iso);
    } else if (formatted === '') {
      onChange('');
    }
  };

  const handleDayClick = (day: number) => {
    const m = String(calMonth + 1).padStart(2, '0');
    const d = String(day).padStart(2, '0');
    const iso = `${calYear}-${m}-${d}`;
    onChange(iso);
    close();
  };

  const prevMonth = () => {
    if (calMonth === 0) { setCalMonth(11); setCalYear(calYear - 1); }
    else setCalMonth(calMonth - 1);
  };

  const nextMonth = () => {
    if (calMonth === 11) { setCalMonth(0); setCalYear(calYear + 1); }
    else setCalMonth(calMonth + 1);
  };

  const daysInMonth = getDaysInMonth(calYear, calMonth);
  const firstDay = getFirstDayOfMonth(calYear, calMonth);

  const selectedDay = (() => {
    if (!value) return -1;
    const [y, m, d] = value.split('-').map(Number);
    if (y === calYear && m === calMonth + 1) return d;
    return -1;
  })();

  const today = new Date();
  const isToday = (day: number) =>
    today.getFullYear() === calYear && today.getMonth() === calMonth && today.getDate() === day;

  const isBeforeMin = (day: number): boolean => {
    if (!min) return false;
    const d = new Date(calYear, calMonth, day);
    const minDate = new Date(min);
    return d < minDate;
  };

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          inputMode="numeric"
          value={displayValue}
          onChange={handleInputChange}
          placeholder={placeholder}
          required={required}
          disabled={disabled}
          maxLength={10}
          className={`
            w-full pl-4 pr-10 py-2.5 text-sm
            bg-white border border-gray-200 rounded-xl
            transition-all duration-200
            hover:border-gray-300 hover:shadow-sm
            focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400
            disabled:opacity-50 disabled:cursor-not-allowed
            placeholder:text-gray-400
            ${showCalendar ? 'border-blue-400 ring-2 ring-blue-500/20 shadow-sm' : ''}
          `}
        />
        <button
          type="button"
          tabIndex={-1}
          disabled={disabled}
          onClick={() => setShowCalendar(!showCalendar)}
          className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-blue-500 transition-colors rounded-lg hover:bg-gray-50"
        >
          <CalendarIcon className="w-4 h-4" />
        </button>
      </div>

      {showCalendar && (
        <div
          className="
            absolute z-50 mt-1.5
            bg-white border border-gray-200 rounded-xl
            shadow-lg shadow-gray-200/50
            p-4 w-[280px]
          "
          style={{ animationDuration: '150ms' }}
        >
          <div className="flex items-center justify-between mb-3">
            <button
              type="button"
              onClick={prevMonth}
              className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-sm font-semibold text-gray-900">
              {MONTHS[calMonth]} {calYear}
            </span>
            <button
              type="button"
              onClick={nextMonth}
              className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-7 gap-0 mb-1">
            {WEEKDAYS.map((wd) => (
              <div key={wd} className="text-center text-[11px] font-medium text-gray-400 py-1">
                {wd}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-0">
            {Array.from({ length: firstDay }).map((_, i) => (
              <div key={`empty-${i}`} />
            ))}
            {Array.from({ length: daysInMonth }, (_, i) => i + 1).map((day) => {
              const selected = day === selectedDay;
              const todayMark = isToday(day);
              const beforeMin = isBeforeMin(day);
              return (
                <button
                  key={day}
                  type="button"
                  disabled={beforeMin}
                  onClick={() => handleDayClick(day)}
                  className={`
                    w-9 h-9 rounded-lg text-sm font-medium
                    flex items-center justify-center
                    transition-all duration-100
                    ${selected
                      ? 'bg-blue-600 text-white shadow-sm'
                      : todayMark
                        ? 'bg-blue-50 text-blue-700 font-semibold'
                        : beforeMin
                          ? 'text-gray-300 cursor-not-allowed'
                          : 'text-gray-700 hover:bg-gray-100'
                    }
                  `}
                >
                  {day}
                </button>
              );
            })}
          </div>

          <div className="mt-3 pt-3 border-t border-gray-100 flex justify-between">
            <button
              type="button"
              onClick={() => {
                const t = new Date();
                setCalYear(t.getFullYear());
                setCalMonth(t.getMonth());
                handleDayClick(t.getDate());
              }}
              className="text-xs text-blue-600 hover:text-blue-700 font-medium px-2 py-1 rounded-lg hover:bg-blue-50 transition-colors"
            >
              Сегодня
            </button>
            {value && (
              <button
                type="button"
                onClick={() => { onChange(''); close(); }}
                className="text-xs text-gray-500 hover:text-gray-700 font-medium px-2 py-1 rounded-lg hover:bg-gray-100 transition-colors"
              >
                Очистить
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
