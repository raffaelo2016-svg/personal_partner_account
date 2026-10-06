import { AlertCircle, CheckCircle2, Clock3, Loader2, RefreshCw } from 'lucide-react';
import type { BitrixSyncStatus as SyncStatus } from '../api/clients';

const STATUS_CONFIG: Record<SyncStatus, { label: string; className: string; icon: typeof Clock3 }> = {
  not_scheduled: { label: 'Не отправлено в Битрикс24', className: 'bg-gray-100 text-gray-700 border-gray-200', icon: Clock3 },
  pending: { label: 'Ожидает отправки в Битрикс24', className: 'bg-amber-50 text-amber-700 border-amber-200', icon: Clock3 },
  processing: { label: 'Отправляется в Битрикс24', className: 'bg-blue-50 text-blue-700 border-blue-200', icon: Loader2 },
  synced: { label: 'Передано в Битрикс24', className: 'bg-emerald-50 text-emerald-700 border-emerald-200', icon: CheckCircle2 },
  failed: { label: 'Ошибка отправки в Битрикс24', className: 'bg-red-50 text-red-700 border-red-200', icon: AlertCircle },
  conflict: { label: 'Требуется проверка в Битрикс24', className: 'bg-orange-50 text-orange-700 border-orange-200', icon: AlertCircle },
};

const ERROR_MESSAGES: Record<string, string> = {
  INSTALLATION_NOT_FOUND: 'Подключение к Битрикс24 не найдено',
  CLIENT_NOT_SYNCED: 'Сначала должна быть передана карточка клиента',
  LOCAL_FILE_UNAVAILABLE: 'Файл временно недоступен',
  TIMEOUT: 'Битрикс24 не ответил вовремя',
  TRANSPORT_ERROR: 'Нет связи с Битрикс24',
  QUERY_LIMIT_EXCEEDED: 'Битрикс24 временно ограничил число запросов',
  INVALID_RESPONSE: 'Битрикс24 вернул неполный ответ',
  UNKNOWN_ERROR: 'Причина ошибки не сохранена. Повторите обмен для диагностики',
  HTTP_400: 'Битрикс24 отклонил запрос',
  HTTP_403: 'В Битрикс24 недостаточно прав для этой операции',
  HTTP_404: 'Объект в Битрикс24 не найден',
  INVALID_UPLOAD_URL: 'Битрикс24 вернул небезопасный адрес загрузки',
  PARTNER_NOT_LINKED: 'В сделке не выбран партнёр ЮРИТЕХ',
  PARTNER_NOT_FOUND: 'Выбранный партнёр не связан с кабинетом',
  CONTACT_NOT_LINKED: 'В сделке не выбран контакт клиента',
  CONTACT_ALREADY_LINKED: 'Этот контакт уже связан с другим клиентом',
  CLIENT_NAME_REQUIRED: 'В контакте не заполнено имя клиента',
  CLIENT_TYPE_REQUIRED: 'В сделке не заполнен тип клиента ЮРИТЕХ',
  CLIENT_STATUS_REQUIRED: 'В сделке не заполнен статус клиента ЮРИТЕХ',
  INVALID_DEAL_RESPONSE: 'Не удалось прочитать карточку сделки',
  INVALID_CONTACT_RESPONSE: 'Не удалось прочитать контакт клиента',
  CLIENT_DEAL_NOT_FOUND: 'Сделка не связана с клиентом кабинета',
  CLIENT_NOT_FOUND: 'Связанный клиент не найден в кабинете',
  REMOTE_FILE_ID_MISSING: 'Битрикс24 не передал идентификатор файла',
  INVALID_FILE_RESPONSE: 'Не удалось прочитать сведения о файле',
  INVALID_DOWNLOAD_URL: 'Битрикс24 вернул небезопасную ссылку на файл',
  FILE_TOO_LARGE: 'Размер файла превышает 10 МБ',
  UNSUPPORTED_FILE_TYPE: 'Тип файла не поддерживается кабинетом',
  INVALID_FILE_CONTENT: 'Содержимое файла не соответствует его типу',
};

interface Props {
  status?: SyncStatus | string | null;
  errorCode?: string | null;
  onRetry?: () => void;
  isRetrying?: boolean;
  compact?: boolean;
}

export default function BitrixSyncStatus({ status, errorCode, onRetry, isRetrying = false, compact = false }: Props) {
  const normalized = status && status in STATUS_CONFIG ? status as SyncStatus : 'not_scheduled';
  const config = STATUS_CONFIG[normalized];
  const Icon = config.icon;
  const canRetry = Boolean(onRetry && (normalized === 'failed' || normalized === 'conflict' || errorCode));
  const errorMessage = errorCode ? (ERROR_MESSAGES[errorCode] ?? 'Не удалось завершить обмен') : null;

  return (
    <div className={compact ? 'space-y-1.5' : 'space-y-2'}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`inline-flex items-center gap-1.5 rounded-lg border font-medium ${compact ? 'px-2 py-1 text-xs' : 'px-3 py-2 text-sm'} ${config.className}`}>
          <Icon className={`${compact ? 'w-3.5 h-3.5' : 'w-4 h-4'} ${normalized === 'processing' ? 'animate-spin' : ''}`} />
          {config.label}
        </span>
        {canRetry && (
          <button
            type="button"
            onClick={onRetry}
            disabled={isRetrying}
            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-2.5 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRetrying ? 'animate-spin' : ''}`} />
            {isRetrying ? 'Отправляем…' : 'Повторить'}
          </button>
        )}
      </div>
      {errorMessage && <p className="text-xs text-red-600">{errorMessage}</p>}
    </div>
  );
}
