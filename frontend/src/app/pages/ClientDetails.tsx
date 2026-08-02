import { Link, useParams } from 'react-router';
import { 
  ArrowLeft, 
  Edit, 
  Mail, 
  Phone, 
  MapPin, 
  Calendar,
  FileText,
  Building,
  User,
  CreditCard,
  CheckSquare,
  Clock,
  CheckCircle,
  AlertCircle,
  FileCog,
  Send,
  Gavel,
  RefreshCw,
  Scale,
  Target,
  Loader2,
  Download,
  ExternalLink,
  Image,
  File,
} from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import ClientProgressBar from '../components/ClientProgressBar';
import { useState, useRef } from 'react';
import { useClient } from '../hooks/useClients';
import { useRetryTaskBitrix, useTasks } from '../hooks/useTasks';
import { fetchClientFiles, retryFileBitrix, uploadFile, type UploadedFileResponse } from '../api/upload';
import { toast } from 'sonner';
import { captureError } from '@/app/sentry';
import { uploadAllSettled } from '@/app/utils/files';
import { formatDateShort, formatDateTime as fmtDateTime } from '@/app/utils/formatDate';
import { useTimezone } from '@/app/contexts/TimezoneContext';
import BitrixSyncStatus from '../components/BitrixSyncStatus';

function getFileIcon(mimeType: string) {
  if (mimeType.startsWith('image/')) return Image;
  if (mimeType === 'application/pdf') return FileText;
  return File;
}

function formatFileSize(bytes: number) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

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

export default function ClientDetails() {
  const tz = useTimezone();
  const { id } = useParams();
  const { data: apiClient, isLoading } = useClient(id ?? '');
  const queryClient = useQueryClient();
  const { data: clientFiles = [], isLoading: isFilesLoading } = useQuery({
    queryKey: ['clientFiles', id],
    queryFn: () => fetchClientFiles(id!),
    enabled: !!id,
  });
  const { data: tasksData } = useTasks({ client_id: id, page_size: 5 });
  const clientTasks = tasksData?.items ?? [];
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const retryTaskMutation = useRetryTaskBitrix();
  const retryFileMutation = useMutation({
    mutationFn: retryFileBitrix,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clientFiles', id] });
      queryClient.invalidateQueries({ queryKey: ['bitrixAttention'] });
      queryClient.invalidateQueries({ queryKey: ['adminBitrixAttentionCount'] });
      toast.success('Документ снова поставлен в очередь Битрикс24');
    },
    onError: () => toast.error('Не удалось повторить отправку документа'),
  });

  const handleDirectUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0 || !id) return;
    setIsUploading(true);
    try {
      const items = Array.from(files);
      const result = await uploadAllSettled(items, (f) => uploadFile(f, id, 'other'));
      queryClient.invalidateQueries({ queryKey: ['clientFiles', id] });
      if (result.failed.length === 0) {
        toast.success(`Загружено файлов: ${result.succeeded.length}`);
      } else {
        result.failed.forEach(({ item, error }) => {
          captureError(error, { context: 'client_details_upload', fileName: item.name });
        });
        const failedNames = result.failed.map((f) => f.item.name).join(', ');
        if (result.succeeded.length > 0) {
          toast.warning(`Загружено: ${result.succeeded.length}. Не удалось: ${failedNames}`);
        } else {
          toast.error(`Не удалось загрузить файлы: ${failedNames}`);
        }
      }
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };
  
  const client = apiClient
    ? {
        id: apiClient.id,
        fullName: apiClient.full_name,
        type: apiClient.type,
        status: apiClient.status,
        caseNumber: apiClient.case_number ?? '',
        dateOfBirth: apiClient.date_of_birth ?? '',
        passportSeries: apiClient.passport_series ?? '',
        passportNumber: apiClient.passport_number ?? '',
        passportIssueDate: apiClient.passport_issue_date ?? '',
        passportIssuedBy: apiClient.passport_issued_by ?? '',
        registrationAddress: apiClient.registration_address ?? '',
        inn: apiClient.inn ?? '',
        snils: apiClient.snils ?? '',
        phone: apiClient.phone ?? '—',
        email: apiClient.email ?? '—',
        region: apiClient.region ?? '—',
        arbitrageCourt: apiClient.arbitrage_court ?? '—',
        createdAt: apiClient.created_at,
        updatedAt: apiClient.updated_at,
      }
    : {
        id: id || '1',
        fullName: '',
        type: 'before_court',
        status: 'documents_collection',
        caseNumber: '',
        dateOfBirth: '',
        passportSeries: '',
        passportNumber: '',
        passportIssueDate: '',
        passportIssuedBy: '',
        registrationAddress: '',
        inn: '',
        snils: '',
        phone: '',
        email: '',
        region: '',
        arbitrageCourt: '',
        createdAt: '',
        updatedAt: '',
      };
  
  const getTypeLabel = (type: string) => {
    return type === 'before_court' ? 'ДО подачи в суд' : 'УЖЕ в суде';
  };
  
  const getStatusLabel = (status: string) => {
    const labels: Record<string, string> = {
      documents_collection: 'Сбор документов',
      documents_formation: 'Формирование документов',
      sent_to_court: 'Отправка в суд',
      documents_decision: 'Документы приняты / не приняты',
      waiting_hearing: 'Ожидание заседания',
      restructuring: 'Реструктуризация',
      auction: 'Торги',
      realization: 'Реализация',
    };
    return labels[status] || status;
  };
  
  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      documents_collection: 'bg-blue-100 text-blue-700',
      documents_formation: 'bg-indigo-100 text-indigo-700',
      sent_to_court: 'bg-orange-100 text-orange-700',
      documents_decision: 'bg-emerald-100 text-emerald-700',
      waiting_hearing: 'bg-cyan-100 text-cyan-700',
      restructuring: 'bg-purple-100 text-purple-700',
      auction: 'bg-amber-100 text-amber-700',
      realization: 'bg-green-100 text-green-700',
    };
    return colors[status] || 'bg-gray-100 text-gray-700';
  };
  
  const formatDate = (dateStr: string) => formatDateShort(dateStr, tz);
  const formatDateTime = (dateStr: string) => fmtDateTime(dateStr, tz);
  
  const STATUS_ORDER = [
    'documents_collection',
    'documents_formation',
    'sent_to_court',
    'documents_decision',
    'waiting_hearing',
    'restructuring',
    'auction',
    'realization',
  ];

  const STAGE_DEFS = [
    { id: 1, key: 'documents_collection', title: 'Сбор документов', icon: FileText, activeGradient: 'from-blue-400 to-blue-600', activeShadow: 'shadow-blue-500/50', activeGlow: 'shadow-blue-400/30' },
    { id: 2, key: 'documents_formation', title: 'Формирование документов', icon: FileCog, activeGradient: 'from-indigo-400 to-indigo-600', activeShadow: 'shadow-indigo-500/50', activeGlow: 'shadow-indigo-400/30' },
    { id: 3, key: 'sent_to_court', title: 'Отправка в суд', icon: Send, activeGradient: 'from-orange-400 to-orange-600', activeShadow: 'shadow-orange-500/50', activeGlow: 'shadow-orange-400/30' },
    { id: 4, key: 'documents_decision', title: 'Документы приняты / не приняты', icon: Gavel, activeGradient: 'from-emerald-400 to-emerald-600', activeShadow: 'shadow-emerald-500/50', activeGlow: 'shadow-emerald-400/30' },
    { id: 5, key: 'waiting_hearing', title: 'Ожидание заседания', icon: Clock, activeGradient: 'from-cyan-400 to-cyan-600', activeShadow: 'shadow-cyan-500/50', activeGlow: 'shadow-cyan-400/30' },
    { id: 6, key: 'restructuring', title: 'Реструктуризация', icon: RefreshCw, activeGradient: 'from-purple-400 to-purple-600', activeShadow: 'shadow-purple-500/50', activeGlow: 'shadow-purple-400/30' },
    { id: 7, key: 'auction', title: 'Торги', icon: Scale, activeGradient: 'from-amber-400 to-amber-600', activeShadow: 'shadow-amber-500/50', activeGlow: 'shadow-amber-400/30' },
    { id: 8, key: 'realization', title: 'Реализация', icon: Target, activeGradient: 'from-green-400 to-green-600', activeShadow: 'shadow-green-500/50', activeGlow: 'shadow-green-400/30' },
  ];

  const currentStageIndex = STATUS_ORDER.indexOf(client.status);

  const progressStages = STAGE_DEFS.map((def, idx) => {
    let status: string;
    let color: { gradient: string; shadow: string; glow: string };

    if (idx < currentStageIndex) {
      status = 'completed';
      color = { gradient: 'from-green-400 to-green-600', shadow: 'shadow-green-500/50', glow: 'shadow-green-400/30' };
    } else if (idx === currentStageIndex) {
      status = 'in-progress';
      color = { gradient: def.activeGradient, shadow: def.activeShadow, glow: def.activeGlow };
    } else {
      status = 'pending';
      color = { gradient: 'from-gray-300 to-gray-400', shadow: 'shadow-gray-400/30', glow: 'shadow-gray-300/20' };
    }

    return { id: def.id, title: def.title, icon: def.icon, status, color };
  });

  const calculateProgress = () => {
    const completed = progressStages.filter((s) => s.status === 'completed').length;
    const inProgress = progressStages.filter((s) => s.status === 'in-progress').length;
    return ((completed + inProgress * 0.5) / progressStages.length) * 100;
  };
  
  if (isLoading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-6">
        <Link
          to="/dashboard/clients"
          className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeft className="w-5 h-5" />
          Назад к списку
        </Link>
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-3xl font-semibold text-gray-900 mb-2">
              {client.fullName}
            </h1>
            <div className="flex items-center gap-3">
              <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(client.status)}`}>
                {getStatusLabel(client.status)}
              </span>
              <span className="text-gray-600">
                {getTypeLabel(client.type)}
              </span>
            </div>
          </div>
          <Link 
            to={`/dashboard/clients/${client.id}/edit`}
            className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-all shadow-lg hover:shadow-xl font-medium"
          >
            <Edit className="w-5 h-5" />
            Редактировать
          </Link>
        </div>

        {/* Progress Bar */}
        <ClientProgressBar currentStatus={client.status} />
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Info */}
        <div className="lg:col-span-2 space-y-6">
          {client.type === 'in_court' ? (
            <>
              {/* Case Info */}
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Gavel className="w-5 h-5" />
                  Информация о судебном деле
                </h2>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-600 mb-1">Номер судебного дела</p>
                    <p className="text-gray-900 font-medium">{client.caseNumber || '—'}</p>
                  </div>
                </div>
              </div>

              {/* Contact Info */}
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">
                  Контактная информация
                </h2>
                <div className="space-y-3">
                  {client.phone && client.phone !== '—' && (
                    <div className="flex items-center gap-3">
                      <Phone className="w-5 h-5 text-gray-400" />
                      <span className="text-gray-900">{client.phone}</span>
                    </div>
                  )}
                  {client.email && client.email !== '—' && (
                    <div className="flex items-center gap-3">
                      <Mail className="w-5 h-5 text-gray-400" />
                      <span className="text-gray-900">{client.email}</span>
                    </div>
                  )}
                  {!client.phone && !client.email && (
                    <p className="text-sm text-gray-500">Контактные данные не указаны</p>
                  )}
                </div>
              </div>
            </>
          ) : (
            <>
              {/* Contact Info */}
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">
                  Контактная информация
                </h2>
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <Phone className="w-5 h-5 text-gray-400" />
                    <span className="text-gray-900">{client.phone || '—'}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Mail className="w-5 h-5 text-gray-400" />
                    <span className="text-gray-900">{client.email || '—'}</span>
                  </div>
                  <div className="flex items-start gap-3">
                    <MapPin className="w-5 h-5 text-gray-400 mt-0.5" />
                    <span className="text-gray-900">{client.registrationAddress || '—'}</span>
                  </div>
                </div>
              </div>
              
              {/* Personal Data */}
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <User className="w-5 h-5" />
                  Персональные данные
                </h2>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-600 mb-1">Дата рождения</p>
                    <p className="text-gray-900">{formatDate(client.dateOfBirth)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600 mb-1">ИНН</p>
                    <p className="text-gray-900">{client.inn || '—'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600 mb-1">СНИЛС</p>
                    <p className="text-gray-900">{client.snils || '—'}</p>
                  </div>
                </div>
              </div>
              
              {/* Passport Data */}
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <CreditCard className="w-5 h-5" />
                  Паспортные данные
                </h2>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-600 mb-1">Серия и номер</p>
                    <p className="text-gray-900">
                      {client.passportSeries || client.passportNumber
                        ? `${client.passportSeries} ${client.passportNumber}`
                        : '—'}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600 mb-1">Дата выдачи</p>
                    <p className="text-gray-900">{formatDate(client.passportIssueDate)}</p>
                  </div>
                  <div className="col-span-2">
                    <p className="text-sm text-gray-600 mb-1">Кем выдан</p>
                    <p className="text-gray-900">{client.passportIssuedBy || '—'}</p>
                  </div>
                </div>
              </div>
              
              {/* Legal Info */}
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Building className="w-5 h-5" />
                  Юридическая информация
                </h2>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-600 mb-1">Регион подачи</p>
                    <p className="text-gray-900">{client.region}</p>
                  </div>
                  <div className="col-span-2">
                    <p className="text-sm text-gray-600 mb-1">Арбитражный суд</p>
                    <p className="text-gray-900">{client.arbitrageCourt}</p>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
        
        {/* Sidebar */}
        <div className="space-y-6">
          {/* Timeline */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Calendar className="w-5 h-5" />
              Временная шкала
            </h2>
            <div className="space-y-4">
              <div className="flex gap-3">
                <div className="w-2 h-2 rounded-full bg-blue-500 mt-2" />
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    Последнее обновление
                  </p>
                  <p className="text-sm text-gray-600">
                    {formatDateTime(client.updatedAt)}
                  </p>
                </div>
              </div>
              <div className="flex gap-3">
                <div className="w-2 h-2 rounded-full bg-gray-300 mt-2" />
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    Карточка создана
                  </p>
                  <p className="text-sm text-gray-600">
                    {formatDateTime(client.createdAt)}
                  </p>
                </div>
              </div>
            </div>
          </div>
          
          {/* Documents */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".jpg,.jpeg,.png,.pdf,.doc,.docx"
              className="hidden"
              onChange={handleDirectUpload}
            />
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <FileText className="w-5 h-5" />
              Документы
              {clientFiles.length > 0 && (
                <span className="ml-1 px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-600 rounded-full">
                  {clientFiles.length}
                </span>
              )}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
                className="ml-auto text-xs font-medium text-blue-600 hover:text-blue-700 flex items-center gap-1"
              >
                {isUploading ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Download className="w-3.5 h-3.5" />
                )}
                {isUploading ? 'Загрузка...' : 'Загрузить'}
              </button>
            </h2>
            {isFilesLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
              </div>
            ) : clientFiles.length === 0 ? (
              <div className="text-center py-8">
                <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                <p className="text-sm text-gray-500">Документы не загружены</p>
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="mt-3 text-sm text-blue-600 hover:text-blue-700 font-medium"
                >
                  Загрузить документы
                </button>
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
          
          {/* Task History */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <CheckSquare className="w-5 h-5" />
              История задач
            </h2>
            {clientTasks.length === 0 ? (
              <div className="text-center py-6">
                <CheckSquare className="w-10 h-10 text-gray-300 mx-auto mb-2" />
                <p className="text-sm text-gray-500">Задач пока нет</p>
              </div>
            ) : (
              <div className="space-y-3">
                {clientTasks.map((task) => {
                  const isCompleted = task.status === 'completed';
                  const isInProgress = task.status === 'in_progress';
                  const bg = isCompleted
                    ? 'bg-green-50 border-green-200'
                    : isInProgress
                      ? 'bg-blue-50 border-blue-200'
                      : 'bg-yellow-50 border-yellow-200';
                  const Icon = isCompleted ? CheckCircle : isInProgress ? AlertCircle : Clock;
                  const iconColor = isCompleted
                    ? 'text-green-600'
                    : isInProgress
                      ? 'text-blue-600'
                      : 'text-yellow-600';
                  const statusLabel = isCompleted
                    ? `Выполнено ${task.completed_at ? formatDate(task.completed_at) : ''}`
                    : `${isInProgress ? 'В работе' : 'Ожидает'} • Срок: ${formatDate(task.due_date)}`;

                  return (
                    <div key={task.id} className={`p-3 rounded-lg border ${bg}`}>
                      <div className="flex items-start gap-3">
                        <Icon className={`w-4 h-4 ${iconColor} mt-0.5 flex-shrink-0`} />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900">{task.title}</p>
                          <p className="text-xs text-gray-500 mt-1">{statusLabel}</p>
                          <div className="mt-2">
                            <BitrixSyncStatus
                              compact
                              status={task.bitrix_sync_status}
                              errorCode={task.bitrix_sync_error_code}
                              isRetrying={retryTaskMutation.isPending && retryTaskMutation.variables === task.id}
                              onRetry={() => retryTaskMutation.mutate(task.id, {
                                onSuccess: () => toast.success('Задача снова поставлена в очередь Битрикс24'),
                                onError: () => toast.error('Не удалось повторить отправку задачи'),
                              })}
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            <Link
              to="/dashboard/tasks"
              className="mt-4 block text-center text-sm text-blue-600 hover:text-blue-700 font-medium"
            >
              Все задачи клиента
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
