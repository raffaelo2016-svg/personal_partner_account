import { Link, useParams } from 'react-router';
import {
  Calendar,
  FileText,
  File as FileIcon,
  Image as ImageIcon,
  ExternalLink,
  User,
  CreditCard,
  Building,
  DollarSign,
  Plus,
  Download,
  Edit2,
  Save,
  X,
  Loader2,
  BarChart3,
  Trash2,
} from 'lucide-react';
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAdminClient, useRetryAdminClientBitrix, useUpdateAdminClient } from '@/app/hooks/useClients';
import { formatDate, formatDateShort } from '@/app/utils/formatDate';
import { useTimezone } from '@/app/contexts/TimezoneContext';
import { formatFileSize } from '@/app/utils/files';
import { fetchClientFiles, retryFileBitrix, type UploadedFileResponse } from '../api/upload';
import { toast } from 'sonner';
import apiClient from '../api/client';
import CustomSelect from '../components/ui/CustomSelect';
import DateInput from '../components/ui/DateInput';
import BitrixSyncStatus from '../components/BitrixSyncStatus';
import {
  CLIENT_STATUSES,
  STATUS_LABELS,
  getStatusBadgeClass,
  getStatusLabel,
  type ClientStatus,
} from '../data/clientStatuses';

const DOC_TYPE_LABELS: Record<string, string> = {
  passport: 'Паспорт',
  snils: 'СНИЛС',
  inn_certificate: 'Свидетельство ИНН',
  children_birth_cert: 'Свидетельство о рождении детей',
  marriage_cert: 'Свидетельство о браке/расторжении',
  employment_history: 'Справка о трудовой деятельности',
  pension_account: 'Справка о лицевом счёте ПФ',
  tax_registry: 'Выписка ЕГРН',
  no_ip_status: 'Справка об отсутствии ИП',
  ndfl_2: 'Справки 2-НДФЛ',
  tax_debt: 'Справка об исполнении обязанностей по налогам',
  credit_debt: 'Справка о задолженности по кредитам',
  credit_agreements: 'Копии кредитных договоров',
  court_fee: 'Квитанция госпошлины',
  criminal_record: 'Справка о судимости',
  deposit_payment: 'Квитанция на депозит',
  other: 'Прочее',
};

function getFileIcon(mimeType: string) {
  if (mimeType.startsWith('image/')) return ImageIcon;
  if (mimeType === 'application/pdf') return FileText;
  return FileIcon;
}

const ALL_STATUSES = CLIENT_STATUSES;

function parseFio(fullName: string) {
  const parts = fullName.trim().split(/\s+/);
  return {
    lastName: parts[0] ?? '',
    firstName: parts[1] ?? '',
    middleName: parts.slice(2).join(' '),
  };
}

export default function AdminDebtorDetails() {
  const tz = useTimezone();
  const { id } = useParams();
  const { data: client, isLoading } = useAdminClient(id!);
  const updateClient = useUpdateAdminClient();
  const retryClientBitrix = useRetryAdminClientBitrix();
  const queryClient = useQueryClient();
  const retryFileMutation = useMutation({
    mutationFn: retryFileBitrix,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminClientFiles', id] });
      queryClient.invalidateQueries({ queryKey: ['bitrixAttention'] });
      queryClient.invalidateQueries({ queryKey: ['adminBitrixAttentionCount'] });
      toast.success('Документ снова поставлен в очередь Битрикс24');
    },
    onError: () => toast.error('Не удалось повторить отправку документа'),
  });

  const [showStatusChange, setShowStatusChange] = useState(false);
  const [newStatus, setNewStatus] = useState('');
  const [isEditingBankruptcyDate, setIsEditingBankruptcyDate] = useState(false);
  const [tempBankruptcyDate, setTempBankruptcyDate] = useState('');

  const { data: feesData } = useQuery({
    queryKey: ['adminClientFees', id],
    queryFn: async () => {
      const { data } = await apiClient.get(`/admin/clients/${id}/fees`, { params: { page_size: 50 } });
      return data;
    },
    enabled: !!id,
  });
  const clientFees = feesData?.items ?? [];

  const { data: clientFiles = [], isLoading: isFilesLoading } = useQuery({
    queryKey: ['adminClientFiles', id],
    queryFn: () => fetchClientFiles(id!),
    enabled: !!id,
  });

  const bankruptcyDate = client?.court_procedure_date ?? '';

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
      </div>
    );
  }

  if (!client) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-500">
        <p className="text-lg">Клиент не найден</p>
        <Link to="/admin/clients" className="mt-4 text-blue-600 hover:underline">
          Вернуться к списку
        </Link>
      </div>
    );
  }

  const fio = parseFio(client.full_name);
  const statusLabel = getStatusLabel(client.status);
  const statusColor = getStatusBadgeClass(client.status, true);

  const handleStatusChange = () => {
    if (!newStatus || newStatus === client.status) return;
    updateClient.mutate(
      { id: client.id, data: { status: newStatus as ClientStatus } },
      {
        onSuccess: () => {
          toast.success(`Статус изменён на «${getStatusLabel(newStatus)}»`);
          setShowStatusChange(false);
          setNewStatus('');
        },
        onError: () => toast.error('Не удалось изменить статус'),
      },
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-semibold text-gray-900 mb-2">
              {client.full_name.toUpperCase()}
            </h1>
            <p className="text-gray-600">ID: {client.id}</p>
          </div>
        </div>
      </div>

      {/* Quick Info */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <Calendar className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">Дата создания</p>
              <p className="font-semibold text-gray-900">{formatDate(client.created_at, tz)}</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
              <Building className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">Партнер</p>
              {client.partner_name ? (
                <Link
                  to={`/admin/partners/${client.partner_id}`}
                  className="font-semibold text-blue-600 hover:text-blue-700 hover:underline"
                >
                  {client.partner_name}
                </Link>
              ) : (
                <p className="font-semibold text-gray-900">—</p>
              )}
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <FileText className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">Номер дела</p>
              <p className="font-semibold text-gray-900 font-mono">{client.case_number || '—'}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Основная информация */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <User className="w-5 h-5" />
              Основная информация
            </h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-600 mb-1">Фамилия</p>
                <p className="text-gray-900 font-medium">{fio.lastName || '—'}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600 mb-1">Имя</p>
                <p className="text-gray-900 font-medium">{fio.firstName || '—'}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600 mb-1">Отчество</p>
                <p className="text-gray-900 font-medium">{fio.middleName || '—'}</p>
              </div>
              {client.date_of_birth && (
                <div>
                  <p className="text-sm text-gray-600 mb-1">Дата рождения</p>
                  <p className="text-gray-900">{formatDate(client.date_of_birth, tz)}</p>
                </div>
              )}
              <div>
                <p className="text-sm text-gray-600 mb-1">Телефон</p>
                <p className="text-gray-900">{client.phone || '—'}</p>
              </div>
              {client.email && (
                <div>
                  <p className="text-sm text-gray-600 mb-1">Email</p>
                  <a href={`mailto:${client.email}`} className="text-blue-600 hover:underline text-sm">
                    {client.email}
                  </a>
                </div>
              )}
              <div>
                <p className="text-sm text-gray-600 mb-1">Регион</p>
                <p className="text-gray-900">{client.region || '—'}</p>
              </div>
              {client.inn && (
                <div>
                  <p className="text-sm text-gray-600 mb-1">ИНН</p>
                  <p className="text-gray-900 font-mono">{client.inn}</p>
                </div>
              )}
              {client.snils && (
                <div>
                  <p className="text-sm text-gray-600 mb-1">СНИЛС</p>
                  <p className="text-gray-900 font-mono">{client.snils}</p>
                </div>
              )}
              <div>
                <p className="text-sm text-gray-600 mb-1">Тип</p>
                <p className="text-gray-900">{client.type === 'before_court' ? 'До суда' : 'В суде'}</p>
              </div>
            </div>
          </div>

          {/* Обмен с Битрикс24 */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h3 className="font-semibold text-gray-900 mb-3">Обмен с Битрикс24</h3>
            <BitrixSyncStatus
              status={client.bitrix_sync_status}
              errorCode={client.bitrix_sync_error_code}
              isRetrying={retryClientBitrix.isPending}
              onRetry={() => retryClientBitrix.mutate(client.id, {
                onSuccess: () => toast.success('Клиент снова поставлен в очередь Битрикс24'),
                onError: () => toast.error('Не удалось повторить отправку клиента'),
              })}
            />
            {client.bitrix_deal_id && (
              <p className="mt-2 text-xs text-gray-500">Карточка сделки: {client.bitrix_deal_id}</p>
            )}
          </div>

          {/* Паспортные данные */}
          {(client.passport_series || client.passport_number) && (
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <CreditCard className="w-5 h-5" />
                Паспорт
              </h2>
              <div className="grid grid-cols-2 gap-4">
                {client.passport_series && (
                  <div>
                    <p className="text-sm text-gray-600 mb-1">Серия</p>
                    <p className="text-gray-900 font-medium">{client.passport_series}</p>
                  </div>
                )}
                {client.passport_number && (
                  <div>
                    <p className="text-sm text-gray-600 mb-1">Номер</p>
                    <p className="text-gray-900 font-medium">{client.passport_number}</p>
                  </div>
                )}
                {client.passport_issue_date && (
                  <div>
                    <p className="text-sm text-gray-600 mb-1">Дата выдачи</p>
                    <p className="text-gray-900">{formatDate(client.passport_issue_date, tz)}</p>
                  </div>
                )}
                {client.passport_issued_by && (
                  <div className="col-span-2">
                    <p className="text-sm text-gray-600 mb-1">Выдан</p>
                    <p className="text-gray-900">{client.passport_issued_by}</p>
                  </div>
                )}
                {client.registration_address && (
                  <div className="col-span-2">
                    <p className="text-sm text-gray-600 mb-1">Адрес регистрации</p>
                    <p className="text-gray-900">{client.registration_address}</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Судебная информация */}
          {(client.arbitrage_court || client.case_number || client.court_procedure_date) && (
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <FileText className="w-5 h-5" />
                Судебная информация
              </h2>
              <div className="grid grid-cols-2 gap-4">
                {client.arbitrage_court && (
                  <div className="col-span-2">
                    <p className="text-sm text-gray-600 mb-1">Арбитражный суд</p>
                    <p className="text-gray-900">{client.arbitrage_court}</p>
                  </div>
                )}
                {client.case_number && (
                  <div>
                    <p className="text-sm text-gray-600 mb-1">Номер дела</p>
                    <p className="text-gray-900 font-mono">{client.case_number}</p>
                  </div>
                )}
                {client.court_procedure_date && (
                  <div>
                    <p className="text-sm text-gray-600 mb-1">Дата процедуры</p>
                    <p className="text-gray-900">{formatDate(client.court_procedure_date, tz)}</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Дата признания банкротом */}
          <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-xl border-2 border-green-200 p-6">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 bg-green-600 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Calendar className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">
                    Дата признания банкротом
                  </h3>
                  <p className="text-sm text-gray-600 mt-1">
                    Укажите дату вынесения судом определения о признании банкротом
                  </p>
                </div>
              </div>
            </div>

            {!isEditingBankruptcyDate ? (
              <div className="space-y-3">
                {bankruptcyDate ? (
                  <div className="bg-white rounded-lg border border-green-300 p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-gray-600 mb-1">Дата определения суда:</p>
                        <p className="text-xl font-bold text-green-700">
                          {formatDateShort(bankruptcyDate, tz)}
                        </p>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => {
                            setTempBankruptcyDate(bankruptcyDate);
                            setIsEditingBankruptcyDate(true);
                          }}
                          className="p-2 text-green-600 hover:bg-green-100 rounded-lg transition-colors"
                        >
                          <Edit2 className="w-5 h-5" />
                        </button>
                        <button
                          onClick={() => {
                            updateClient.mutate(
                              { id: id!, data: { court_procedure_date: null } },
                              {
                                onSuccess: () => toast.success('Дата признания банкротом удалена'),
                                onError: () => toast.error('Ошибка удаления'),
                              },
                            );
                          }}
                          disabled={updateClient.isPending}
                          className="p-2 text-red-500 hover:bg-red-100 rounded-lg transition-colors"
                        >
                          <Trash2 className="w-5 h-5" />
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => setIsEditingBankruptcyDate(true)}
                    className="w-full px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium flex items-center justify-center gap-2"
                  >
                    <Plus className="w-5 h-5" />
                    Добавить дату признания банкротом
                  </button>
                )}
              </div>
            ) : (
              <div className="bg-white rounded-lg border border-green-300 p-4">
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Выберите дату определения суда
                    </label>
                    <DateInput
                      value={tempBankruptcyDate}
                      onChange={(val) => setTempBankruptcyDate(val)}
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => {
                        if (!tempBankruptcyDate) return;
                        updateClient.mutate(
                          { id: id!, data: { court_procedure_date: tempBankruptcyDate } },
                          {
                            onSuccess: () => {
                              toast.success('Дата признания банкротом сохранена');
                              setIsEditingBankruptcyDate(false);
                              setTempBankruptcyDate('');
                            },
                            onError: () => toast.error('Ошибка сохранения'),
                          },
                        );
                      }}
                      disabled={!tempBankruptcyDate || updateClient.isPending}
                      className="flex-1 px-4 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {updateClient.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                      Сохранить
                    </button>
                    <button
                      onClick={() => {
                        setIsEditingBankruptcyDate(false);
                        setTempBankruptcyDate('');
                      }}
                      className="px-4 py-2.5 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors font-medium flex items-center justify-center gap-2"
                    >
                      <X className="w-4 h-4" />
                      Отменить
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Status */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h3 className="font-semibold text-gray-900 mb-3">Статус</h3>
            <span className={`inline-flex items-center px-3 py-2 text-sm font-medium rounded-lg border ${statusColor}`}>
              {statusLabel}
            </span>

            {!showStatusChange ? (
              <button
                onClick={() => {
                  setNewStatus(client.status);
                  setShowStatusChange(true);
                }}
                className="mt-4 w-full px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-100 transition-colors flex items-center justify-center gap-2"
              >
                <BarChart3 className="w-4 h-4" />
                Изменить статус
              </button>
            ) : (
              <div className="mt-4 space-y-3">
                <CustomSelect
                  value={newStatus}
                  onChange={setNewStatus}
                  options={ALL_STATUSES.map((s) => ({ value: s, label: STATUS_LABELS[s] }))}
                />
                <div className="flex gap-2">
                  <button
                    onClick={handleStatusChange}
                    disabled={updateClient.isPending || newStatus === client.status}
                    className="flex-1 px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors disabled:opacity-50"
                  >
                    {updateClient.isPending ? 'Сохранение...' : 'Сохранить'}
                  </button>
                  <button
                    onClick={() => setShowStatusChange(false)}
                    className="px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    Отмена
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Начисления */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <DollarSign className="w-5 h-5" />
                Начисления
              </h3>
            </div>
            {clientFees.length === 0 ? (
              <div className="text-center py-8">
                <DollarSign className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                <p className="text-sm text-gray-500">Нет начислений</p>
              </div>
            ) : (
              <div className="space-y-3">
                {clientFees.map((fee: { id: string; amount: number; status: string; due_date: string | null; paid_at: string | null; created_at: string }) => {
                  const statusCfg = fee.status === 'paid'
                    ? { label: 'Оплачено', color: 'bg-green-100 text-green-700 border-green-300' }
                    : fee.status === 'overdue'
                      ? { label: 'Просрочено', color: 'bg-red-100 text-red-700 border-red-300' }
                      : { label: 'Ожидает оплаты', color: 'bg-yellow-100 text-yellow-700 border-yellow-300' };
                  return (
                    <div key={fee.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div>
                        <p className="text-sm font-medium text-gray-900">
                          {(fee.amount / 100).toLocaleString('ru-RU')} ₽
                        </p>
                        <p className="text-xs text-gray-500">
                          {fee.due_date ? `Срок: ${formatDateShort(fee.due_date, tz)}` : 'Срок не установлен'}
                          {fee.paid_at ? ` · Оплачено ${formatDateShort(fee.paid_at, tz)}` : ''}
                        </p>
                      </div>
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${statusCfg.color}`}>
                        {statusCfg.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Документы */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <FileText className="w-5 h-5" />
              Документы
              {clientFiles.length > 0 && (
                <span className="ml-1 px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-600 rounded-full">
                  {clientFiles.length}
                </span>
              )}
            </h3>
            {isFilesLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
              </div>
            ) : clientFiles.length === 0 ? (
              <div className="text-center py-8">
                <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                <p className="text-sm text-gray-500">Документы не загружены</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
                {clientFiles.map((file: UploadedFileResponse) => {
                  const Icon = getFileIcon(file.mime_type);
                  return (
                    <div
                      key={file.file_id}
                      className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors group"
                    >
                      <Icon className="w-5 h-5 text-gray-400 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {file.filename}
                        </p>
                        <p className="text-xs text-gray-500">
                          {DOC_TYPE_LABELS[file.document_type] || file.document_type}
                          {' · '}
                          {formatFileSize(file.size)}
                          {' · '}
                          {formatDateShort(file.created_at, tz)}
                        </p>
                        <div className="mt-2">
                          <BitrixSyncStatus
                            compact
                            status={file.bitrix_sync_status}
                            errorCode={file.bitrix_sync_error_code}
                            isRetrying={retryFileMutation.isPending && retryFileMutation.variables === file.file_id}
                            onRetry={() => retryFileMutation.mutate(file.file_id)}
                          />
                        </div>
                      </div>
                      <a
                        href={file.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-1.5 text-gray-400 hover:text-blue-600 opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Открыть"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                      <a
                        href={file.url}
                        download
                        className="p-1.5 text-gray-400 hover:text-blue-600 opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Скачать"
                      >
                        <Download className="w-4 h-4" />
                      </a>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
