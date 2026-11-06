import { ExternalLink } from 'lucide-react';
import { normalizeCaseNumber, resolveCaseUrl } from '../utils/courtCase';

interface CaseArbitrLinkProps {
  /** Номер дела, например «А66-5146/2026». */
  caseNumber?: string | null;
  /** Сохранённая ссылка на карточку дела в КАД (имеет приоритет над номером). */
  explicitUrl?: string | null;
  /** Классы для самого номера/ссылки (например, font-mono). */
  className?: string;
  /** Что показать, если номер дела не заполнен. */
  emptyLabel?: string;
}

/**
 * Номер судебного дела, который открывает карточку дела в КАД Арбитр
 * (kad.arbitr.ru) в новой вкладке. Если номера нет — показывает прочерк.
 */
export default function CaseArbitrLink({
  caseNumber,
  explicitUrl,
  className = '',
  emptyLabel = '—',
}: CaseArbitrLinkProps) {
  const number = normalizeCaseNumber(caseNumber);
  const url = resolveCaseUrl(caseNumber, explicitUrl);

  if (!number || !url) {
    return <span className={className}>{number || emptyLabel}</span>;
  }

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      title="Открыть дело в КАД Арбитр"
      className={`inline-flex items-center gap-1.5 rounded text-blue-600 hover:text-blue-700 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 ${className}`}
    >
      {number}
      <ExternalLink className="w-3.5 h-3.5 flex-shrink-0" aria-hidden="true" />
      <span className="sr-only">— открыть дело в КАД Арбитр в новой вкладке</span>
    </a>
  );
}
