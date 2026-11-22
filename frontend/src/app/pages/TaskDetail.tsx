import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router';
import {
  AlertCircle,
  ArrowLeft,
  Calendar,
  CheckCircle,
  Clock,
  Download,
  File,
  FileImage,
  FileSpreadsheet,
  FileText,
  History,
  Loader2,
  MessageSquare,
  Paperclip,
  Send,
  Trash2,
  Upload,
  User,
  X,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  useDeleteTaskFile,
  useSendTaskMessage,
  useTask,
  useTaskMessages,
  useTaskReview,
  useUpdateTask,
  useUploadTaskFile,
} from '../hooks/useTasks';
import { taskFileUrl, type TaskDetailData, type TaskEventData, type TaskFileData, type TaskMessageData } from '../api/tasks';
import { formatTaskDeadline, isTaskOverdue } from '../utils/taskDeadline';
import { formatDateTime } from '../utils/formatDate';
import { formatFileSize } from '../utils/files';

const TASK_FILE_MAX_BYTES = 50 * 1024 * 1024;
const TASK_FILE_EXTENSIONS = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.heic'];

const STATUS_LABELS: Record<string, string> = {
  pending: 'Ожидает',
  in_progress: 'В работе',
  completed: 'Выполнено',
  overdue: 'Просрочено',
};

const PRIORITY_LABELS: Record<string, string> = {
  low: 'Низкий',
  medium: 'Средний',
  high: 'Высокий',
};

function taskState(task: TaskDetailData): string {
  if (task.status === 'completed') return 'completed';
  if (task.review_requested_at) return 'review';
  if (isTaskOverdue(task)) return 'overdue';
  return task.status === 'overdue' ? 'pending' : task.status;
}

function stateLabel(task: TaskDetailData): string {
  const state = taskState(task);
  if (state === 'review') return 'На проверке';
  return STATUS_LABELS[state] ?? state;
}

function stateClasses(task: TaskDetailData): string {
  const state = taskState(task);
  if (state === 'completed') return 'bg-green-50 text-green-700 border-green-200';
  if (state === 'review') return 'bg-purple-50 text-purple-700 border-purple-200';
  if (state === 'overdue') return 'bg-red-50 text-red-700 border-red-200';
  if (state === 'in_progress') return 'bg-blue-50 text-blue-700 border-blue-200';
  return 'bg-yellow-50 text-yellow-700 border-yellow-200';
}

function fileIcon(mime: string) {
  if (mime.startsWith('image/')) return FileImage;
  if (mime.includes('spreadsheet') || mime.includes('excel')) return FileSpreadsheet;
  if (mime === 'application/pdf') return FileText;
  return File;
}

function eventText(event: TaskEventData): string {
  const name = typeof event.payload.name === 'string' ? event.payload.name : 'документ';
  switch (event.type) {
    case 'created':
      return 'Задача создана';
    case 'status_changed': {
      const to = typeof event.payload.to === 'string' ? event.payload.to : '';
      return `Статус изменён на «${STATUS_LABELS[to] ?? to}»`;
    }
    case 'review_requested':
      return 'Задача отправлена на проверку';
    case 'review_approved':
      return 'Проверка пройдена, задача завершена';
    case 'review_returned':
      return 'Задача возвращена в работу';
    case 'file_uploaded':
      return `Загружен файл «${name}»`;
    case 'file_deleted':
      return `Удалён файл «${name}»`;
    default:
      return 'Задача обновлена';
  }
}

function eventIcon(event: TaskEventData) {
  if (event.type === 'file_uploaded') return Paperclip;
  if (event.type === 'file_deleted') return Trash2;
  if (event.type === 'review_requested') return Clock;
  if (event.type === 'review_approved') return CheckCircle;
  if (event.type === 'review_returned') return AlertCircle;
  return History;
}

function MessageBubble({ message }: { message: TaskMessageData }) {
  return (
    <div className={`flex ${message.is_mine ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[85%] ${message.is_mine ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
        <div className="flex items-baseline gap-2 px-1">
          <span className="text-xs font-semibold text-gray-700">{message.author_name}</span>
          <span className="text-[10px] text-gray-400">{formatDateTime(message.created_at).slice(-5)}</span>
        </div>
        <div
          className={`rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words ${
            message.is_mine
              ? 'bg-pink-600 text-white rounded-br-md'
              : 'bg-gray-100 text-gray-800 rounded-bl-md'
          }`}
        >
          {message.text}
        </div>
      </div>
    </div>
  );
}

export default function TaskDetail() {
  const { id } = useParams();
  const { data: task, isLoading, isError } = useTask(id);
  const { data: messagesData } = useTaskMessages(id);
  const updateTask = useUpdateTask();
  const reviewTask = useTaskReview(id);
  const uploadFile = useUploadTaskFile(id);
  const deleteFile = useDeleteTaskFile(id);
  const sendMessage = useSendTaskMessage(id);

  const [text, setText] = useState('');
  const [progress, setProgress] = useState<number | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const messages = messagesData ?? task?.messages ?? [];
  const files = task?.files ?? [];
  const events = task?.events ?? [];
  const basePath = task?.permissions.is_admin ? '/admin/tasks' : '/dashboard/tasks';
  const clientPath = task?.permissions.is_admin ? '/admin/clients' : '/dashboard/clients';

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length]);

  const canStart = !!task && !task.permissions.is_admin && task.status === 'pending' && !task.review_requested_at;
  const canRequestReview = !!task?.permissions.can_request_review;
  const canApprove = !!task?.permissions.can_approve;
  const canReturn = !!task?.permissions.can_return;
  const canCompleteDirectly =
    !!task && task.permissions.is_admin && !task.review_requested_at && task.status !== 'completed';
  const canReopen = !!task && task.permissions.is_admin && task.status === 'completed';

  const statusChip = useMemo(() => (task ? stateLabel(task) : ''), [task]);

  const handleUpload = async (file: File) => {
    const ext = '.' + (file.name.split('.').pop() || '').toLowerCase();
    if (!TASK_FILE_EXTENSIONS.includes(ext)) {
      toast.error('Такой формат не поддерживается');
      return;
    }
    if (file.size > TASK_FILE_MAX_BYTES) {
      toast.error('Файл больше 50 МБ');
      return;
    }
    setProgress(0);
    try {
      await uploadFile.mutateAsync({ file, onProgress: setProgress });
      toast.success('Документ загружен');
      setShowUpload(false);
    } catch {
      toast.error('Не удалось загрузить документ');
    } finally {
      setProgress(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDeleteFile = async (file: TaskFileData) => {
    if (!window.confirm(`Удалить файл «${file.original_name}»? Он исчезнет из задачи и из карточки клиента.`)) return;
    try {
      await deleteFile.mutateAsync(file.id);
      toast.success('Файл удалён');
    } catch {
      toast.error('Не удалось удалить файл');
    }
  };

  const handleReview = async (action: 'request' | 'approve' | 'return') => {
    try {
      await reviewTask.mutateAsync(action);
      toast.success(
        action === 'request'
          ? 'Задача отправлена на проверку'
          : action === 'approve'
            ? 'Задача завершена'
            : 'Задача возвращена в работу',
      );
    } catch {
      toast.error('Не удалось изменить статус задачи');
    }
  };

  const handleStatus = async (status: string) => {
    if (!task) return;
    try {
      await updateTask.mutateAsync({ id: task.id, data: { status } });
      toast.success(status === 'completed' ? 'Задача завершена' : 'Статус обновлён');
    } catch {
      toast.error('Не удалось изменить статус');
    }
  };

  const handleSend = async () => {
    const clean = text.trim();
    if (!clean || sendMessage.isPending) return;
    setText('');
    try {
      await sendMessage.mutateAsync(clean);
    } catch {
      setText(clean);
      toast.error('Не удалось отправить сообщение');
    }
  };

  if (isLoading) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center">
        <Loader2 className="h-7 w-7 animate-spin text-pink-500" />
      </div>
    );
  }

  if (isError || !task) {
    return (
      <div className="p-8">
        <p className="text-gray-600">Задача не найдена или недоступна.</p>
        <Link to={basePath} className="mt-3 inline-flex text-sm font-medium text-pink-600">
          Вернуться к задачам
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1500px] p-4 lg:p-8">
      <div className="mb-4 flex items-center gap-2 text-sm text-gray-500">
        <Link to={basePath} className="inline-flex items-center gap-1 hover:text-gray-800">
          <ArrowLeft className="h-4 w-4" />
          Задачи
        </Link>
        <span className="text-gray-300">/</span>
        <span className="truncate">{task.title}</span>
      </div>

      <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-lg border px-2.5 py-1 text-xs font-semibold ${stateClasses(task)}`}>
              {statusChip}
            </span>
            <span className="rounded-lg border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-600">
              {PRIORITY_LABELS[task.priority] ?? task.priority} приоритет
            </span>
            {task.due_date || task.due_at ? (
              <span className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1 text-xs font-medium ${
                isTaskOverdue(task) ? 'border-red-200 bg-red-50 text-red-700' : 'border-gray-200 bg-white text-gray-600'
              }`}>
                <Calendar className="h-3.5 w-3.5" />
                {formatTaskDeadline(task)}
              </span>
            ) : null}
          </div>
          <h1 className="mt-3 text-2xl font-semibold leading-tight text-gray-900 lg:text-3xl">{task.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-500">
            <span>{task.assigned_to === 'partner' ? 'Задача от ЮРИТЕХ' : 'Задача для ЮРИТЕХ'}</span>
            {task.client ? (
              <Link to={`${clientPath}/${task.client.id}`} className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-700">
                <User className="h-4 w-4" />
                {task.client.full_name}
              </Link>
            ) : (
              <span>Без клиента</span>
            )}
            <span className="inline-flex items-center gap-1">
              <MessageSquare className="h-4 w-4" />
              {messages.length}
            </span>
            <span className="inline-flex items-center gap-1">
              <Paperclip className="h-4 w-4" />
              {files.length}
            </span>
          </div>
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {canStart && (
            <button
              type="button"
              onClick={() => handleStatus('in_progress')}
              disabled={updateTask.isPending}
              className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-2.5 text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-50"
            >
              Взять в работу
            </button>
          )}
          {canRequestReview && (
            <button
              type="button"
              onClick={() => handleReview('request')}
              disabled={reviewTask.isPending}
              className="rounded-xl bg-pink-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-pink-700 disabled:opacity-50"
            >
              {reviewTask.isPending ? 'Отправляем…' : 'Отправить на проверку'}
            </button>
          )}
          {canApprove && (
            <button
              type="button"
              onClick={() => handleReview('approve')}
              disabled={reviewTask.isPending}
              className="rounded-xl bg-green-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-green-700 disabled:opacity-50"
            >
              Завершить
            </button>
          )}
          {canReturn && (
            <button
              type="button"
              onClick={() => handleReview('return')}
              disabled={reviewTask.isPending}
              className="rounded-xl border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              Вернуть в работу
            </button>
          )}
          {canCompleteDirectly && (
            <button
              type="button"
              onClick={() => handleStatus('completed')}
              disabled={updateTask.isPending}
              className="rounded-xl bg-green-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-green-700 disabled:opacity-50"
            >
              Завершить
            </button>
          )}
          {canReopen && (
            <button
              type="button"
              onClick={() => handleStatus('in_progress')}
              disabled={updateTask.isPending}
              className="rounded-xl border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              Вернуть в работу
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="min-w-0 space-y-5">
          <section className="rounded-2xl border border-gray-200 bg-white p-5 lg:p-6">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">Описание</h2>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
              {task.description || 'Описание не заполнено.'}
            </p>
          </section>

          {task.client && (
            <section className="rounded-2xl border border-gray-200 bg-white p-5 lg:p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Клиент и дело</h2>
                  <Link
                    to={`${clientPath}/${task.client.id}`}
                    className="mt-2 inline-flex items-center gap-2 text-lg font-semibold text-gray-900 hover:text-blue-600"
                  >
                    <User className="h-5 w-5 text-gray-400" />
                    {task.client.full_name}
                  </Link>
                  <p className="mt-1 text-sm text-gray-500">
                    Дело {task.client.case_number || 'без номера'}
                    {task.client.arbitrage_court ? ` · ${task.client.arbitrage_court}` : ''}
                  </p>
                </div>
                <Link
                  to={`${clientPath}/${task.client.id}`}
                  className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
                >
                  Карточка клиента
                </Link>
              </div>
            </section>
          )}

          <section className="rounded-2xl border border-gray-200 bg-white p-5 lg:p-6">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
                <Paperclip className="h-4 w-4" />
                Документы
                {files.length > 0 && (
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
                    {files.length}
                  </span>
                )}
              </h2>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={!task.permissions.can_upload || progress !== null}
                className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                {progress !== null ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
                {progress !== null ? `Загрузка ${progress}%` : 'Загрузить'}
              </button>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept={TASK_FILE_EXTENSIONS.join(',')}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void handleUpload(file);
                }}
              />
            </div>

            {progress !== null && (
              <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-gray-100">
                <div className="h-full rounded-full bg-pink-500 transition-all" style={{ width: `${progress}%` }} />
              </div>
            )}

            {files.length === 0 ? (
              <button
                type="button"
                onClick={() => setShowUpload(true)}
                className="flex w-full flex-col items-center justify-center rounded-xl border border-dashed border-gray-300 px-4 py-8 text-center hover:border-pink-300 hover:bg-pink-50/30"
              >
                <Upload className="mb-2 h-6 w-6 text-gray-400" />
                <span className="text-sm font-medium text-gray-700">Добавить первый документ</span>
                <span className="mt-1 text-xs text-gray-500">PDF, DOCX, XLSX, JPG, PNG · до 50 МБ</span>
              </button>
            ) : (
              <div className="space-y-2">
                {files.map((file) => {
                  const Icon = fileIcon(file.mime_type);
                  return (
                    <div
                      key={file.id}
                      className="group flex items-center gap-3 rounded-xl border border-gray-100 bg-gray-50/70 px-3 py-2.5"
                    >
                      <Icon className="h-5 w-5 shrink-0 text-gray-400" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-gray-900">{file.original_name}</p>
                        <p className="mt-0.5 text-xs text-gray-500">
                          {formatFileSize(file.size)} · {formatDateTime(file.created_at)} · {file.uploader_name}
                        </p>
                      </div>
                      <a
                        href={taskFileUrl(file)}
                        className="rounded-lg p-1.5 text-gray-400 hover:bg-white hover:text-blue-600"
                        title="Скачать"
                      >
                        <Download className="h-4 w-4" />
                      </a>
                      {file.can_delete && (
                        <button
                          type="button"
                          onClick={() => void handleDeleteFile(file)}
                          className="rounded-lg p-1.5 text-gray-400 hover:bg-white hover:text-red-600"
                          title="Удалить"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            <p className="mt-3 text-xs text-gray-400">
              Файлы из задачи автоматически видны в карточке клиента — это один и тот же документ.
            </p>
          </section>

          <section className="rounded-2xl border border-gray-200 bg-white p-5 lg:p-6">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
              <History className="h-4 w-4" />
              История
            </h2>
            {events.length === 0 ? (
              <p className="text-sm text-gray-500">Событий пока нет.</p>
            ) : (
              <div className="space-y-3">
                {events.map((event) => {
                  const Icon = eventIcon(event);
                  return (
                    <div key={event.id} className="flex items-start gap-3">
                      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gray-100 text-gray-500">
                        <Icon className="h-3.5 w-3.5" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-gray-700">
                          {event.actor_name ? <span className="font-medium">{event.actor_name}</span> : null}
                          {event.actor_name ? ' · ' : ''}
                          {eventText(event)}
                        </p>
                        <p className="mt-0.5 text-xs text-gray-400">{formatDateTime(event.created_at)}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>

        <aside className="flex min-h-[560px] flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white lg:sticky lg:top-4 lg:h-[calc(100vh-22rem)] lg:min-h-[520px]">
          <div className="flex items-center gap-2 border-b border-gray-100 px-4 py-3.5">
            <MessageSquare className="h-4 w-4 text-pink-500" />
            <div className="min-w-0 flex-1">
              <h2 className="text-sm font-semibold text-gray-900">Обсуждение</h2>
              <p className="text-xs text-gray-500">Партнёр и администратор</p>
            </div>
            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-500">
              {task.unread_count ? `${task.unread_count} новых` : 'онлайн'}
            </span>
          </div>

          <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
            {messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center px-6 text-center">
                <MessageSquare className="mb-3 h-9 w-9 text-gray-300" />
                <p className="text-sm font-medium text-gray-700">Обсуждения пока нет</p>
                <p className="mt-1 text-xs leading-relaxed text-gray-500">
                  Задайте вопрос по задаче — ответ придёт сюда и в уведомления.
                </p>
              </div>
            ) : (
              messages.map((message) => <MessageBubble key={message.id} message={message} />)
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="border-t border-gray-100 p-3">
            <div className="flex items-end gap-2 rounded-xl border border-gray-200 bg-gray-50 px-2 py-1.5 focus-within:border-pink-300 focus-within:bg-white">
              <textarea
                value={text}
                onChange={(event) => setText(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    void handleSend();
                  }
                }}
                rows={1}
                placeholder="Написать сообщение…"
                className="max-h-28 min-h-[34px] flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-gray-800 outline-none placeholder:text-gray-400"
              />
              <button
                type="button"
                onClick={() => void handleSend()}
                disabled={!text.trim() || sendMessage.isPending}
                className="mb-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-pink-600 text-white hover:bg-pink-700 disabled:opacity-40"
                title="Отправить"
              >
                {sendMessage.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
            </div>
            <p className="mt-2 px-1 text-[10px] text-gray-400">
              Клиент не видит обсуждение и файлы задачи
            </p>
          </div>
        </aside>
      </div>

      {showUpload && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="presentation">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Загрузить документ</h3>
                <p className="mt-1 text-sm text-gray-500">PDF, DOCX, XLSX, JPG, PNG · до 50 МБ</p>
              </div>
              <button type="button" onClick={() => setShowUpload(false)} className="rounded-lg p-1 text-gray-400 hover:bg-gray-100">
                <X className="h-5 w-5" />
              </button>
            </div>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="mt-5 flex w-full flex-col items-center rounded-xl border border-dashed border-gray-300 px-4 py-8 hover:border-pink-300 hover:bg-pink-50/30"
            >
              <Upload className="mb-2 h-7 w-7 text-gray-400" />
              <span className="text-sm font-medium text-gray-700">Выбрать файл</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
