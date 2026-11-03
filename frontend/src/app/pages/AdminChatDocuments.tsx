import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import {
  Check,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  FileText,
  Image as ImageIcon,
  Inbox,
  Loader2,
  MessageSquare,
  Search,
  X,
} from 'lucide-react';
import { toast } from 'sonner';
import { fetchAdminClients, type ClientData } from '../api/clients';
import {
  assignChatDocument,
  fetchChatDocumentInbox,
  fetchChatDocumentInboxCount,
  fetchChatDocumentItem,
  ignoreChatDocument,
  type ChatDocumentCandidate,
  type ChatDocumentInboxItem,
  type ChatDocumentStatus,
} from '../api/chatDocuments';
import { fetchPartners } from '../api/partners';
import CustomSelect from '../components/ui/CustomSelect';
import { DOCUMENT_TYPE_OPTIONS, documentTypeLabel } from '../data/documentTypes';
import { STATUS_LABELS } from '../data/statusMaps';
import { useTimezone } from '../contexts/TimezoneContext';
import { formatFileSize } from '../utils/files';
import { formatDateShort, formatDateTime } from '../utils/formatDate';

type InboxTab = ChatDocumentStatus | 'all';

const TABS: Array<{ value: InboxTab; label: string }> = [
  { value: 'unassigned', label: 'На разборе' },
  { value: 'assigned', label: 'Привязанные' },
  { value: 'ignored', label: 'Не документ' },
  { value: 'all', label: 'Все' },
];

function extractError(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail: unknown = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (detail && typeof detail === 'object' && 'message' in detail) {
      const message = (detail as { message?: unknown }).message;
      if (typeof message === 'string') return message;
    }
  }
  return fallback;
}

function isImage(mimeType?: string | null): boolean {
  return Boolean(mimeType?.startsWith('image/'));
}

function guessDocumentType(item: ChatDocumentInboxItem): string {
  const haystack = `${item.attachment.filename} ${item.text}`.toLowerCase();
  if (haystack.includes('снилс')) return 'snils';
  if (haystack.includes('инн')) return 'inn_certificate';
  if (haystack.includes('егрн') || haystack.includes('выписк')) return 'tax_registry';
  if (haystack.includes('паспорт')) return 'passport';
  if (haystack.includes('2-ндфл') || haystack.includes('ндфл') || haystack.includes('справк')) return 'ndfl_2';
  return 'other';
}

function candidateChipClass(candidate: ChatDocumentCandidate): string {
  if (candidate.score >= 80) return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  return 'border-amber-200 bg-amber-50 text-amber-700';
}

function shortName(fullName: string): string {
  const parts = fullName.trim().split(/\s+/);
  if (parts.length < 2) return fullName;
  const initials = parts.slice(1, 3).map((part) => `${part[0]}.`).join(' ');
  return `${parts[0]} ${initials}`;
}

interface AssignDialogProps {
  item: ChatDocumentInboxItem;
  onClose: () => void;
}

function AssignDialog({ item, onClose }: AssignDialogProps) {
  const tz = useTimezone();
  const queryClient = useQueryClient();
  const [clientId, setClientId] = useState(item.candidates[0]?.client_id ?? '');
  const [clientSearch, setClientSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [documentType, setDocumentType] = useState(guessDocumentType(item));
  const [syncToBitrix, setSyncToBitrix] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(clientSearch), 300);
    return () => clearTimeout(timer);
  }, [clientSearch]);

  const clientsQuery = useQuery({
    queryKey: ['chatDocumentClients', item.partner_id, debouncedSearch],
    queryFn: () =>
      fetchAdminClients({ partner_id: item.partner_id, search: debouncedSearch || undefined, page_size: 30 }),
  });

  const clients: ClientData[] = clientsQuery.data?.items ?? [];

  const assignMutation = useMutation({
    mutationFn: () =>
      assignChatDocument(item.message_id, {
        client_id: clientId,
        document_type: documentType,
        sync_to_bitrix: syncToBitrix,
      }),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['chatDocumentInbox'] });
      queryClient.invalidateQueries({ queryKey: ['chatDocumentInboxCount'] });
      if (result.bitrix_sync_status === 'not_scheduled') {
        toast.success('Документ прикреплён к клиенту', {
          description: 'Клиент ещё не синхронизирован с Битрикс24 — файл отправится позже.',
        });
      } else {
        toast.success('Документ прикреплён к клиенту', {
          description: 'Файл добавлен в карточку и отправлен в Битрикс24.',
        });
      }
      onClose();
    },
    onError: (error) => toast.error(extractError(error, 'Не удалось прикрепить документ')),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/45 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Прикрепить документ"
        className="flex max-h-[92vh] w-full max-w-[600px] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
      >
        <div className="flex items-start gap-4 border-b border-gray-100 px-6 py-5">
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-semibold text-gray-900">Прикрепить документ</h2>
            <p className="mt-0.5 text-sm text-gray-500">Файл из чата станет документом клиента</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Закрыть"
            className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-6 py-4">
          <div className="flex items-center gap-3 rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg border border-gray-200 bg-white text-gray-500">
              {isImage(item.attachment.mime_type) ? (
                <ImageIcon className="h-5 w-5" />
              ) : (
                <FileText className="h-5 w-5" />
              )}
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-gray-900">{item.attachment.filename}</p>
              <p className="text-xs text-gray-500">
                {item.attachment.size ? `${formatFileSize(item.attachment.size)} · ` : ''}
                {formatDateTime(item.created_at, tz)}
              </p>
            </div>
            <a
              href={item.attachment.url}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-auto text-sm font-medium text-blue-600 hover:text-blue-700"
            >
              Открыть
            </a>
          </div>

          <div>
            <p className="mb-1.5 text-xs font-semibold text-gray-600">Партнёр</p>
            <div className="flex items-center gap-2.5 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-50 text-[10px] font-bold text-blue-700">
                {(item.partner_name ?? 'П').slice(0, 2).toUpperCase()}
              </span>
              <span className="text-sm text-gray-900">{item.partner_name ?? 'Партнёр'}</span>
              <span className="ml-auto text-xs text-gray-400">определён по чату</span>
            </div>
          </div>

          <div>
            <p className="mb-1.5 text-xs font-semibold text-gray-600">Клиент</p>
            {item.candidates.length > 0 && (
              <div className="mb-2 flex flex-wrap gap-1.5">
                {item.candidates.map((candidate) => (
                  <button
                    key={candidate.client_id}
                    type="button"
                    onClick={() => setClientId(candidate.client_id)}
                    className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors ${
                      clientId === candidate.client_id
                        ? 'border-blue-300 bg-blue-50 text-blue-700'
                        : candidateChipClass(candidate)
                    }`}
                  >
                    <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
                    <span className="max-w-[140px] truncate">{shortName(candidate.full_name)}</span>
                    <span className="font-semibold">{candidate.score}%</span>
                  </button>
                ))}
              </div>
            )}

            <div className="flex items-center gap-2 rounded-lg border border-gray-300 px-3 py-2">
              <Search className="h-4 w-4 flex-shrink-0 text-gray-400" />
              <input
                value={clientSearch}
                onChange={(event) => setClientSearch(event.target.value)}
                placeholder="Найти клиента партнёра"
                className="w-full bg-transparent text-sm text-gray-900 outline-none placeholder:text-gray-400"
              />
            </div>

            <div className="mt-2 max-h-36 overflow-y-auto rounded-lg border border-gray-200">
              {clientsQuery.isLoading ? (
                <div className="flex items-center justify-center py-6 text-gray-400">
                  <Loader2 className="h-5 w-5 animate-spin" />
                </div>
              ) : clients.length === 0 ? (
                <p className="px-3 py-4 text-sm text-gray-500">Клиенты не найдены</p>
              ) : (
                clients.map((client) => (
                  <button
                    key={client.id}
                    type="button"
                    onClick={() => setClientId(client.id)}
                    className={`flex w-full items-center gap-2.5 border-b border-gray-100 px-3 py-2.5 text-left last:border-b-0 hover:bg-gray-50 ${
                      clientId === client.id ? 'bg-blue-50' : ''
                    }`}
                  >
                    <span className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-gray-100 text-[10px] font-semibold text-gray-600">
                      {client.full_name
                        .split(' ')
                        .slice(0, 2)
                        .map((part) => part[0])
                        .join('')
                        .toUpperCase()}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-gray-900">{client.full_name}</span>
                      <span className="block text-xs text-gray-500">
                        {STATUS_LABELS[client.status] ?? client.status}
                      </span>
                    </span>
                    {clientId === client.id && <Check className="h-4 w-4 flex-shrink-0 text-blue-600" />}
                  </button>
                ))
              )}
            </div>
          </div>

          <div>
            <p className="mb-1.5 text-xs font-semibold text-gray-600">
              Тип документа <span className="font-normal text-gray-400">· влияет на готовность комплекта</span>
            </p>
            <CustomSelect
              value={documentType}
              onChange={setDocumentType}
              options={DOCUMENT_TYPE_OPTIONS.map((option) => ({ value: option.value, label: option.label }))}
              searchable
            />
          </div>

          <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-gray-200 px-4 py-3">
            <input
              type="checkbox"
              checked={syncToBitrix}
              onChange={(event) => setSyncToBitrix(event.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-gray-300 accent-blue-600"
            />
            <span>
              <span className="block text-sm font-medium text-gray-900">Отправить в Битрикс24</span>
              <span className="block text-xs text-gray-500">
                Диск: ПАРТНЕРЫ / {item.partner_name ?? 'партнёр'} / клиент / «Первоначальные документы» и
                комментарий в таймлайн сделки
              </span>
            </span>
          </label>

          <div className="rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-xs text-blue-800">
            Партнёру уйдёт в чат подтверждение, что документ принят.
          </div>
        </div>

        <div className="flex justify-end gap-2 border-t border-gray-100 bg-gray-50 px-6 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={() => assignMutation.mutate()}
            disabled={!clientId || assignMutation.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {assignMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Прикрепить
          </button>
        </div>
      </div>
    </div>
  );
}

function InboxRow({
  item,
  onAssign,
  onIgnore,
  isIgnoring,
}: {
  item: ChatDocumentInboxItem;
  onAssign: () => void;
  onIgnore: () => void;
  isIgnoring: boolean;
}) {
  const tz = useTimezone();
  const topCandidate = item.candidates[0];

  return (
    <div className="grid grid-cols-1 gap-3 border-b border-gray-100 px-4 py-4 last:border-b-0 hover:bg-gray-50/60 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1.2fr)_minmax(0,0.9fr)_auto] lg:items-center lg:gap-4">
      <div className="flex min-w-0 items-center gap-3">
        <div
          className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg ${
            item.status === 'assigned' ? 'bg-emerald-50 text-emerald-600' : 'bg-gray-100 text-gray-500'
          }`}
        >
          {isImage(item.attachment.mime_type) ? (
            <ImageIcon className="h-5 w-5" />
          ) : (
            <FileText className="h-5 w-5" />
          )}
        </div>
        <div className="min-w-0">
          <p className="truncate text-[11px] text-gray-500">
            {item.partner_name ?? 'Партнёр'}
            {item.sender_label === 'Партнёр' ? '' : ` · ${item.sender_label}`}
          </p>
          <p className="truncate text-sm font-medium text-gray-900" title={item.attachment.filename}>
            {item.attachment.filename}
          </p>
          <p className="truncate text-xs text-gray-500">
            {item.attachment.size ? `${formatFileSize(item.attachment.size)} · ` : ''}
            {formatDateShort(item.created_at, tz)}
          </p>
        </div>
      </div>

      <div className="min-w-0 text-sm text-gray-600">
        <p className="flex items-start gap-1.5">
          <MessageSquare className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-gray-400" />
          <span className="line-clamp-2 break-words">{item.text ? `«${item.text}»` : 'Без текста'}</span>
        </p>
      </div>

      <div className="min-w-0">
        {item.status === 'assigned' && item.assignment ? (
          <div>
            <p className="flex items-center gap-1.5 text-sm font-medium text-emerald-700">
              <Check className="h-4 w-4 flex-shrink-0" />
              <span className="truncate" title={item.assignment.client_name ?? undefined}>
                {item.assignment.client_name ?? 'Клиент'}
              </span>
            </p>
            <p className="mt-0.5 text-xs text-gray-500">
              {documentTypeLabel(item.assignment.document_type)}
              {item.assignment.bitrix_sync_status === 'synced'
                ? ' · в Битрикс24'
                : item.assignment.bitrix_sync_status === 'pending'
                  ? ' · отправка в Битрикс24'
                  : ''}
            </p>
          </div>
        ) : item.status === 'ignored' ? (
          <p className="text-sm text-gray-500">Отмечено как «не документ»</p>
        ) : topCandidate ? (
          <div>
            <span
              className={`inline-flex max-w-full items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs whitespace-nowrap ${candidateChipClass(topCandidate)}`}
            >
              <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full bg-current opacity-70" />
              <span className="truncate">{shortName(topCandidate.full_name)}</span>
              <span className="font-semibold">{topCandidate.score}%</span>
            </span>
            <p className="mt-1 text-xs text-gray-400">
              {topCandidate.matched_on === 'filename' ? 'совпадение по имени файла' : 'совпадение по тексту'}
            </p>
          </div>
        ) : (
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-gray-200 bg-gray-100 px-2.5 py-1 text-xs text-gray-500">
              нет подсказки
            </span>
            <p className="mt-1 text-xs text-gray-400">выберите клиента вручную</p>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-start gap-2 lg:justify-end">
        {item.status === 'assigned' && item.assignment?.client_id ? (
          <Link
            to={`/admin/clients/${item.assignment.client_id}`}
            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
          >
            Открыть карточку
            <ExternalLink className="h-3.5 w-3.5" />
          </Link>
        ) : item.status === 'ignored' ? null : (
          <>
            <button
              type="button"
              onClick={onIgnore}
              disabled={isIgnoring}
              className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              Не документ
            </button>
            <button
              type="button"
              onClick={onAssign}
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
            >
              Прикрепить
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export default function AdminChatDocuments() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const deepLinkMessageId = searchParams.get('message');

  const [tab, setTab] = useState<InboxTab>('unassigned');
  const [partnerId, setPartnerId] = useState('');
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [page, setPage] = useState(1);
  const [dialogItem, setDialogItem] = useState<ChatDocumentInboxItem | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    setPage(1);
  }, [tab, partnerId, debouncedSearch]);

  const partnersQuery = useQuery({
    queryKey: ['adminPartnersForInbox'],
    queryFn: () => fetchPartners({ page_size: 100 }),
  });

  const countQuery = useQuery({
    queryKey: ['chatDocumentInboxCount'],
    queryFn: () => fetchChatDocumentInboxCount(),
    refetchInterval: 30_000,
  });

  const inboxQuery = useQuery({
    queryKey: ['chatDocumentInbox', tab, partnerId, debouncedSearch, page],
    queryFn: () =>
      fetchChatDocumentInbox({
        status: tab,
        partner_id: partnerId || undefined,
        search: debouncedSearch || undefined,
        page,
        page_size: 20,
      }),
  });

  const deepLinkQuery = useQuery({
    queryKey: ['chatDocumentItem', deepLinkMessageId],
    queryFn: () => fetchChatDocumentItem(deepLinkMessageId as string),
    enabled: Boolean(deepLinkMessageId),
    retry: false,
  });

  useEffect(() => {
    if (!deepLinkQuery.data) return;
    if (deepLinkQuery.data.status === 'unassigned') {
      setDialogItem(deepLinkQuery.data);
      return;
    }
    toast.info(
      deepLinkQuery.data.status === 'assigned'
        ? 'Этот файл уже привязан к клиенту'
        : 'Файл отмечен как «не документ»',
    );
    const next = new URLSearchParams(searchParams);
    next.delete('message');
    setSearchParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deepLinkQuery.data]);

  useEffect(() => {
    if (deepLinkQuery.isError) {
      toast.error('Файл из чата не найден — возможно, сообщение удалено');
      const next = new URLSearchParams(searchParams);
      next.delete('message');
      setSearchParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deepLinkQuery.isError]);

  const ignoreMutation = useMutation({
    mutationFn: (messageId: string) => ignoreChatDocument(messageId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chatDocumentInbox'] });
      queryClient.invalidateQueries({ queryKey: ['chatDocumentInboxCount'] });
      toast.success('Файл убран из очереди');
    },
    onError: (error) => toast.error(extractError(error, 'Не удалось обновить статус')),
  });

  const closeDialog = () => {
    setDialogItem(null);
    if (deepLinkMessageId) {
      const next = new URLSearchParams(searchParams);
      next.delete('message');
      setSearchParams(next, { replace: true });
    }
  };

  const partnerOptions = useMemo(
    () => [
      { value: '', label: 'Все партнёры' },
      ...(partnersQuery.data?.items ?? []).map((partner) => ({
        value: partner.id,
        label: partner.company_name,
      })),
    ],
    [partnersQuery.data],
  );

  const data = inboxQuery.data;
  const count = countQuery.data?.unassigned ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h1 className="flex items-center gap-3 text-3xl font-semibold text-gray-900">
            <Inbox className="h-8 w-8 text-blue-600" />
            Документы из чата
          </h1>
          <p className="mt-2 max-w-3xl text-gray-600">
            Файлы, которые партнёры прислали в переписке. Привяжите файл к клиенту — он попадёт в карточку,
            в комплект документов и в Битрикс24.
          </p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-600">
          На разборе: <span className="text-lg font-semibold text-gray-900">{count}</span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {TABS.map((item) => (
          <button
            key={item.value}
            type="button"
            onClick={() => setTab(item.value)}
            className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              tab === item.value
                ? 'bg-blue-600 text-white'
                : 'border border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-3 rounded-xl border border-gray-200 bg-white p-3 md:flex-row md:items-center">
        <div className="md:w-64">
          <CustomSelect
            value={partnerId}
            onChange={setPartnerId}
            options={partnerOptions}
            searchable
            size="sm"
          />
        </div>
        <div className="flex flex-1 items-center gap-2 rounded-lg border border-gray-300 px-3 py-2">
          <Search className="h-4 w-4 flex-shrink-0 text-gray-400" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Поиск по файлу, партнёру или клиенту"
            className="w-full bg-transparent text-sm text-gray-900 outline-none placeholder:text-gray-400"
          />
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
        <div className="hidden grid-cols-[minmax(0,1.25fr)_minmax(0,1.2fr)_minmax(0,0.9fr)_auto] gap-4 border-b border-gray-200 bg-gray-50 px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-gray-500 lg:grid">
          <span>Файл и партнёр</span>
          <span>Сообщение</span>
          <span>Клиент</span>
          <span className="text-right">Действие</span>
        </div>

        {inboxQuery.isLoading ? (
          <div className="flex items-center justify-center py-16 text-gray-400">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : (data?.items.length ?? 0) === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Inbox className="h-12 w-12 text-gray-300" />
            <p className="mt-3 text-lg font-medium text-gray-700">Очередь пуста</p>
            <p className="mt-1 max-w-md text-sm text-gray-500">
              {tab === 'unassigned'
                ? 'Все файлы из чатов разобраны. Новые появятся здесь автоматически.'
                : 'В этой выборке пока нет файлов.'}
            </p>
          </div>
        ) : (
          data?.items.map((item) => (
            <InboxRow
              key={item.message_id}
              item={item}
              onAssign={() => setDialogItem(item)}
              onIgnore={() => ignoreMutation.mutate(item.message_id)}
              isIgnoring={ignoreMutation.isPending && ignoreMutation.variables === item.message_id}
            />
          ))
        )}
      </div>

      {data && data.pages > 1 && (
        <div className="flex items-center justify-between text-sm text-gray-600">
          <span>
            Страница {data.page} из {data.pages} · всего {data.total}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setPage((value) => Math.max(1, value - 1))}
              disabled={page <= 1}
              className="inline-flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-3 py-1.5 disabled:opacity-50"
            >
              <ChevronLeft className="h-4 w-4" />
              Назад
            </button>
            <button
              type="button"
              onClick={() => setPage((value) => Math.min(data.pages, value + 1))}
              disabled={page >= data.pages}
              className="inline-flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-3 py-1.5 disabled:opacity-50"
            >
              Вперёд
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {dialogItem && <AssignDialog item={dialogItem} onClose={closeDialog} />}
    </div>
  );
}
