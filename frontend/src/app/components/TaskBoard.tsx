import { Link } from 'react-router';
import { AlertCircle, Calendar, CheckCircle, Clock, MessageSquare, Paperclip } from 'lucide-react';
import type { TaskData } from '../api/tasks';
import { formatTaskDeadline, isTaskOverdue } from '../utils/taskDeadline';

interface TaskBoardProps {
  tasks: TaskData[];
  basePath: string;
  showPartner?: boolean;
}

const COLUMNS = [
  { key: 'new', title: 'Новые', dot: 'bg-yellow-400', empty: 'Новых задач нет' },
  { key: 'in_progress', title: 'В работе', dot: 'bg-blue-500', empty: 'В работе пусто' },
  { key: 'review', title: 'На проверке', dot: 'bg-purple-500', empty: 'На проверке пусто' },
  { key: 'done', title: 'Готово', dot: 'bg-green-500', empty: 'Готовых задач нет' },
] as const;

function columnFor(task: TaskData): string {
  if (task.status === 'completed') return 'done';
  if (task.review_requested_at) return 'review';
  if (task.status === 'in_progress') return 'in_progress';
  return 'new';
}

const PRIORITY: Record<string, { label: string; className: string }> = {
  high: { label: 'Высокий', className: 'bg-red-50 text-red-700 border-red-200' },
  medium: { label: 'Средний', className: 'bg-yellow-50 text-yellow-700 border-yellow-200' },
  low: { label: 'Низкий', className: 'bg-gray-50 text-gray-600 border-gray-200' },
};

export default function TaskBoard({ tasks, basePath, showPartner = false }: TaskBoardProps) {
  const grouped = new Map<string, TaskData[]>();
  COLUMNS.forEach((column) => grouped.set(column.key, []));
  tasks.forEach((task) => {
    const key = columnFor(task);
    grouped.get(key)?.push(task);
  });

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
      {COLUMNS.map((column) => {
        const items = grouped.get(column.key) ?? [];
        return (
          <section key={column.key} className="flex min-h-[260px] flex-col rounded-2xl border border-gray-200 bg-gray-50/70">
            <div className="flex items-center gap-2 px-4 py-3.5">
              <span className={`h-2.5 w-2.5 rounded-full ${column.dot}`} />
              <h3 className="text-sm font-semibold text-gray-800">{column.title}</h3>
              <span className="ml-auto rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-gray-500">
                {items.length}
              </span>
            </div>
            <div className="flex flex-1 flex-col gap-2.5 px-3 pb-3">
              {items.length === 0 ? (
                <div className="flex flex-1 items-center justify-center rounded-xl border border-dashed border-gray-200 bg-white/50 px-3 py-8 text-center text-xs text-gray-400">
                  {column.empty}
                </div>
              ) : (
                items.map((task) => {
                  const priority = PRIORITY[task.priority] ?? PRIORITY.medium;
                  const overdue = isTaskOverdue(task);
                  return (
                    <Link
                      key={task.id}
                      to={`${basePath}/${task.id}`}
                      className="group rounded-xl border border-gray-200 bg-white p-3.5 shadow-sm transition hover:-translate-y-0.5 hover:border-pink-200 hover:shadow-md"
                    >
                      <div className="flex items-start gap-2">
                        <span className={`mt-0.5 h-5 w-1 shrink-0 rounded-full ${
                          task.status === 'completed'
                            ? 'bg-green-400'
                            : task.review_requested_at
                              ? 'bg-purple-400'
                              : overdue
                                ? 'bg-red-400'
                                : task.status === 'in_progress'
                                  ? 'bg-blue-400'
                                  : 'bg-yellow-400'
                        }`} />
                        <div className="min-w-0 flex-1">
                          <p className="line-clamp-2 text-sm font-semibold leading-snug text-gray-900 group-hover:text-pink-700">
                            {task.title}
                          </p>
                          <p className="mt-1 truncate text-xs text-gray-500">
                            {task.client_name || 'Без клиента'}
                          </p>
                        </div>
                        {!!task.unread_count && (
                          <span className="rounded-full bg-pink-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
                            {task.unread_count}
                          </span>
                        )}
                      </div>

                      <div className="mt-3 flex flex-wrap items-center gap-1.5">
                        <span className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium ${
                          overdue ? 'border-red-200 bg-red-50 text-red-700' : 'border-gray-200 bg-gray-50 text-gray-600'
                        }`}>
                          {overdue ? <AlertCircle className="h-3 w-3" /> : <Clock className="h-3 w-3" />}
                          {formatTaskDeadline(task)}
                        </span>
                        <span className={`rounded-md border px-1.5 py-0.5 text-[10px] font-medium ${priority.className}`}>
                          {priority.label}
                        </span>
                      </div>

                      <div className="mt-2.5 flex items-center gap-3 text-[10px] text-gray-400">
                        <span className="inline-flex items-center gap-1">
                          <Paperclip className="h-3 w-3" />
                          {task.files_count ?? 0}
                        </span>
                        <span className="inline-flex items-center gap-1">
                          <MessageSquare className="h-3 w-3" />
                          {task.messages_count ?? 0}
                        </span>
                        {showPartner && task.partner_name && (
                          <span className="ml-auto truncate">{task.partner_name}</span>
                        )}
                        {!showPartner && (
                          <span className="ml-auto inline-flex items-center gap-1">
                            {task.status === 'completed' ? (
                              <CheckCircle className="h-3 w-3 text-green-500" />
                            ) : (
                              <Calendar className="h-3 w-3" />
                            )}
                            {task.assigned_to === 'partner' ? 'от ЮРИТЕХ' : 'для ЮРИТЕХ'}
                          </span>
                        )}
                      </div>
                    </Link>
                  );
                })
              )}
            </div>
          </section>
        );
      })}
    </div>
  );
}
