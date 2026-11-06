import { useState, useCallback, useMemo } from 'react';
import { CheckSquare, Plus, Calendar, User, AlertCircle, Clock, CheckCircle, Filter, Search, X, Loader2, Trash2, Edit2 } from 'lucide-react';
import { Link } from 'react-router';
import { useInfiniteTasks, useTaskStats, useCreateTask, useUpdateTask, useDeleteTask, useRetryTaskBitrix } from '../hooks/useTasks';
import { useClients } from '../hooks/useClients';
import { useIntersectionObserver } from '../hooks/useIntersectionObserver';
import { toast } from 'sonner';
import CustomSelect from '../components/ui/CustomSelect';
import { formatTaskDeadline, isTaskOverdue, taskDeadlineFields, taskDeadlinePayload, taskDeadlineTimestamp, taskDisplayStatus } from '../utils/taskDeadline';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import BitrixSyncStatus from '../components/BitrixSyncStatus';

export default function TasksList() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [direction, setDirection] = useState<'my' | 'from_uritech'>('my');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterPriority, setFilterPriority] = useState<string>('all');
  const [onlyOverdue, setOnlyOverdue] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const assignedToFilter = direction === 'my' ? 'uritech' : 'partner';

  const filters = {
    assigned_to: assignedToFilter,
    ...(filterStatus !== 'all' ? { status: filterStatus } : {}),
    ...(filterPriority !== 'all' ? { priority: filterPriority } : {}),
    ...(searchQuery ? { search: searchQuery } : {}),
  };

  const { data: tasksPages, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteTasks(filters);
  const { data: statsData } = useTaskStats({ assigned_to: assignedToFilter });
  const { data: clientsData } = useClients({ page_size: 100 });
  const createTaskMutation = useCreateTask();
  const updateTaskMutation = useUpdateTask();
  const deleteTaskMutation = useDeleteTask();
  const retryTaskMutation = useRetryTaskBitrix();

  const loadMore = useCallback(() => { if (hasNextPage) fetchNextPage(); }, [hasNextPage, fetchNextPage]);
  const sentinelRef = useIntersectionObserver(loadMore, !!hasNextPage && !isFetchingNextPage);

  const handleStatusChange = (taskId: string, newStatus: string) => {
    updateTaskMutation.mutate(
      { id: taskId, data: { status: newStatus } },
      {
        onSuccess: () => toast.success('Статус задачи обновлён'),
        onError: () => toast.error('Не удалось обновить статус'),
      },
    );
  };

  const [taskToDelete, setTaskToDelete] = useState<{ id: string; title: string } | null>(null);

  const handleDeleteTask = (taskId: string, title: string) => {
    setTaskToDelete({ id: taskId, title });
  };

  const confirmDeleteTask = () => {
    if (!taskToDelete) return;
    const id = taskToDelete.id;
    setTaskToDelete(null);
    deleteTaskMutation.mutate(id, {
      onSuccess: () => toast.success('Задача удалена'),
      onError: () => toast.error('Не удалось удалить задачу'),
    });
  };

  const [editingTask, setEditingTask] = useState<{
    id: string;
    title: string;
    description: string;
    priority: string;
    status: string;
    due_date: string;
    due_time: string;
    deadlineChanged: boolean;
  } | null>(null);

  const [newTask, setNewTask] = useState({
    title: '',
    description: '',
    client_id: '',
    priority: 'low',
    due_date: '',
    due_time: '',
  });

  const resetNewTask = () => {
    setNewTask({ title: '', description: '', client_id: '', priority: 'low', due_date: '', due_time: '' });
  };

  const handleCreateTask = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTask.title.trim()) {
      toast.error('Укажите название задачи');
      return;
    }
    createTaskMutation.mutate(
      {
        title: newTask.title.trim(),
        description: newTask.description.trim() || undefined,
        client_id: newTask.client_id || undefined,
        priority: newTask.priority,
        assigned_to: 'uritech',
        ...taskDeadlinePayload(newTask.due_date, newTask.due_time),
      },
      {
        onSuccess: () => {
          toast.success('Задача создана');
          resetNewTask();
          setShowCreateModal(false);
        },
        onError: () => {
          toast.error('Не удалось создать задачу');
        },
      },
    );
  };

  const handleEditTask = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingTask) return;
    updateTaskMutation.mutate(
      {
        id: editingTask.id,
        data: {
          title: editingTask.title.trim(),
          description: editingTask.description.trim() || undefined,
          priority: editingTask.priority,
          ...(editingTask.deadlineChanged ? taskDeadlinePayload(editingTask.due_date, editingTask.due_time) : {}),
        },
      },
      {
        onSuccess: () => {
          toast.success('Задача обновлена');
          setEditingTask(null);
        },
        onError: () => toast.error('Не удалось обновить задачу'),
      },
    );
  };

  const allItems = useMemo(
    () => tasksPages?.pages.flatMap((p) => p.items) ?? [],
    [tasksPages],
  );

  const tasks = allItems.map((t) => ({
    id: t.id,
    title: t.title,
    description: t.description ?? '',
    client: { id: t.client_id, name: t.client_name ?? 'Общая задача' },
    assignedBy: t.assigned_to as 'partner' | 'uritech',
    assignedTo: t.assigned_to as 'partner' | 'uritech',
    status: t.status as 'pending' | 'in_progress' | 'completed' | 'overdue',
    priority: t.priority as 'low' | 'medium' | 'high',
    due_date: t.due_date,
    due_at: t.due_at,
    displayStatus: taskDisplayStatus(t),
    createdAt: t.created_at,
    completedAt: t.completed_at ?? undefined,
    bitrixSyncStatus: t.bitrix_sync_status,
    bitrixSyncErrorCode: t.bitrix_sync_error_code,
  }));

  const priorityWeight: Record<string, number> = { high: 0, medium: 1, low: 2 };

  const filteredTasks = [...tasks]
    .filter((t) => !onlyOverdue || isTaskOverdue(t))
    .sort((a, b) => {
      const pa = priorityWeight[a.priority] ?? 3;
      const pb = priorityWeight[b.priority] ?? 3;
      if (pa !== pb) return pa - pb;
      return (taskDeadlineTimestamp(a) ?? Infinity) - (taskDeadlineTimestamp(b) ?? Infinity);
    });

  const getStatusInfo = (status: string) => {
    const statusMap = {
      pending: { label: 'Ожидает', color: 'bg-yellow-50 text-yellow-700 border-yellow-200', icon: Clock },
      in_progress: { label: 'В работе', color: 'bg-blue-50 text-blue-700 border-blue-200', icon: AlertCircle },
      completed: { label: 'Выполнено', color: 'bg-green-50 text-green-700 border-green-200', icon: CheckCircle },
      overdue: { label: 'Просрочено', color: 'bg-red-50 text-red-700 border-red-200', icon: AlertCircle },
    };
    return statusMap[status as keyof typeof statusMap] || statusMap.pending;
  };

  const getPriorityInfo = (priority: string) => {
    const priorityMap = {
      low: { label: 'Низкий', color: 'bg-gray-100 text-gray-700' },
      medium: { label: 'Средний', color: 'bg-yellow-100 text-yellow-700' },
      high: { label: 'Высокий', color: 'bg-red-100 text-red-700' },
    };
    return priorityMap[priority as keyof typeof priorityMap] || priorityMap.low;
  };

  const stats = {
    total: statsData?.total ?? 0,
    pending: statsData?.pending ?? 0,
    in_progress: statsData?.in_progress ?? 0,
    completed: statsData?.completed ?? 0,
    overdue: statsData?.overdue ?? 0,
  };

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-gray-900 mb-2">Список задач</h1>
          <p className="text-gray-600">Управление задачами</p>
        </div>
        {direction === 'my' && (
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-5 py-2.5 bg-pink-600 text-white rounded-xl hover:bg-pink-700 transition-all shadow-sm hover:shadow"
          >
            <Plus className="w-5 h-5" />
            Создать задачу
          </button>
        )}
      </div>

      {/* Direction Toggle */}
      <div className="bg-white rounded-2xl border border-gray-200 p-1.5 inline-flex gap-1">
        <button
          onClick={() => setDirection('my')}
          className={`px-5 py-2.5 rounded-xl text-sm font-medium transition-all ${
            direction === 'my'
              ? 'bg-pink-600 text-white shadow-sm'
              : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          Мои задачи
        </button>
        <button
          onClick={() => setDirection('from_uritech')}
          className={`px-5 py-2.5 rounded-xl text-sm font-medium transition-all ${
            direction === 'from_uritech'
              ? 'bg-pink-600 text-white shadow-sm'
              : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          Задачи от ЮРИТЕХ
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <div className="bg-white rounded-2xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm text-gray-600">Всего задач</p>
            <CheckSquare className="w-5 h-5 text-gray-400" />
          </div>
          <p className="text-3xl font-bold text-gray-900">{stats.total}</p>
        </div>
        <div className="bg-yellow-50 rounded-2xl border border-yellow-200 p-6">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm text-yellow-700">Ожидает</p>
            <Clock className="w-5 h-5 text-yellow-600" />
          </div>
          <p className="text-3xl font-bold text-yellow-900">{stats.pending}</p>
        </div>
        <div className="bg-blue-50 rounded-2xl border border-blue-200 p-6">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm text-blue-700">В работе</p>
            <AlertCircle className="w-5 h-5 text-blue-600" />
          </div>
          <p className="text-3xl font-bold text-blue-900">{stats.in_progress}</p>
        </div>
        <div className="bg-green-50 rounded-2xl border border-green-200 p-6">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm text-green-700">Выполнено</p>
            <CheckCircle className="w-5 h-5 text-green-600" />
          </div>
          <p className="text-3xl font-bold text-green-900">{stats.completed}</p>
        </div>
        <div className="bg-red-50 rounded-2xl border border-red-200 p-6">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm text-red-700">Просрочено</p>
            <AlertCircle className="w-5 h-5 text-red-600" />
          </div>
          <p className="text-3xl font-bold text-red-900">{stats.overdue}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-2xl border border-gray-200 p-6">
        <div className="flex items-center gap-4 mb-4">
          <Filter className="w-5 h-5 text-gray-400" />
          <h3 className="font-medium text-gray-900">Фильтры</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-center">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Поиск задач..."
              className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent"
            />
          </div>
          <CustomSelect
            value={filterStatus}
            onChange={setFilterStatus}
            options={[
              { value: 'all', label: 'Все статусы' },
              { value: 'pending', label: 'Ожидает' },
              { value: 'in_progress', label: 'В работе' },
              { value: 'completed', label: 'Выполнено' },
            ]}
          />
          <CustomSelect
            value={filterPriority}
            onChange={setFilterPriority}
            options={[
              { value: 'all', label: 'Все приоритеты' },
              { value: 'low', label: 'Низкий' },
              { value: 'medium', label: 'Средний' },
              { value: 'high', label: 'Высокий' },
            ]}
          />
          <label className={`flex items-center gap-2.5 px-4 py-2.5 rounded-xl border cursor-pointer transition-colors ${
            onlyOverdue
              ? 'bg-red-50 border-red-200 text-red-700'
              : 'bg-gray-50 border-gray-200 text-gray-500'
          }`}>
            <input
              type="checkbox"
              checked={onlyOverdue}
              onChange={(e) => setOnlyOverdue(e.target.checked)}
              className="w-4 h-4 rounded border-gray-300 text-red-600 focus:ring-red-500"
            />
            <AlertCircle className={`w-4 h-4 flex-shrink-0 ${onlyOverdue ? 'text-red-500' : 'text-gray-400'}`} />
            <span className="text-sm font-medium whitespace-nowrap">Просроченные</span>
            {stats.overdue > 0 && (
              <span className={`ml-auto px-1.5 py-0.5 text-xs font-bold rounded-full ${
                onlyOverdue ? 'bg-red-200 text-red-800' : 'bg-gray-200 text-gray-600'
              }`}>
                {stats.overdue}
              </span>
            )}
          </label>
        </div>
        {(filterStatus !== 'all' || filterPriority !== 'all' || searchQuery || onlyOverdue) && (
          <button
            onClick={() => {
              setFilterStatus('all');
              setFilterPriority('all');
              setSearchQuery('');
              setOnlyOverdue(false);
            }}
            className="mt-4 flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900"
          >
            <X className="w-4 h-4" />
            Сбросить фильтры
          </button>
        )}
      </div>

      {/* Tasks List */}
      <div className="space-y-3">
        {filteredTasks.map((task) => {
          const statusInfo = getStatusInfo(task.displayStatus);
          const priorityInfo = getPriorityInfo(task.priority);
          const StatusIcon = statusInfo.icon;

          return (
            <div
              key={task.id}
              className="bg-white rounded-2xl border border-gray-200 p-6 hover:shadow-md transition-all"
            >
              <div className="flex items-start gap-4">
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                  task.status === 'completed' ? 'bg-green-50' : 
                  task.displayStatus === 'overdue' ? 'bg-red-50' : 'bg-pink-50'
                }`}>
                  <CheckSquare className={`w-6 h-6 ${
                    task.status === 'completed' ? 'text-green-600' : 
                    task.displayStatus === 'overdue' ? 'text-red-600' : 'text-pink-600'
                  }`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <h3 className="font-semibold text-gray-900 mb-1">{task.title}</h3>
                      <p className="text-sm text-gray-600 mb-3">{task.description}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {direction === 'from_uritech' ? (
                        <CustomSelect
                          value={task.displayStatus}
                          onChange={(val) => handleStatusChange(task.id, val)}
                          options={[
                            { value: 'pending', label: 'Ожидает' },
                            ...(task.displayStatus === 'overdue' ? [{ value: 'overdue', label: 'Просрочено', disabled: true }] : []),
                            { value: 'in_progress', label: 'В работе' },
                            { value: 'completed', label: 'Выполнено' },
                          ]}
                          size="sm"
                          triggerClassName={statusInfo.color}
                        />
                      ) : (
                        <span className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border ${statusInfo.color}`}>
                          <StatusIcon className="w-4 h-4" />
                          {statusInfo.label}
                        </span>
                      )}
                      {direction === 'my' && (
                        <>
                          <button
                            onClick={() => setEditingTask({
                              id: task.id,
                              title: task.title,
                              description: task.description,
                              priority: task.priority,
                              status: task.status,
                              ...taskDeadlineFields(task),
                              deadlineChanged: false,
                            })}
                            className="p-1.5 rounded-lg text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
                            title="Редактировать задачу"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDeleteTask(task.id, task.title)}
                            className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                            title="Удалить задачу"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-6 text-sm">
                    {task.client.id ? (
                      <Link to={`/dashboard/clients/${task.client.id}`} className="flex items-center gap-2 text-blue-600 hover:text-blue-700">
                        <User className="w-4 h-4" />
                        {task.client.name}
                      </Link>
                    ) : (
                      <span className="flex items-center gap-2 text-gray-600"><User className="w-4 h-4" />Общая задача</span>
                    )}
                    <div className="flex items-center gap-2 text-gray-600">
                      <Calendar className="w-4 h-4" />
                      {formatTaskDeadline(task)}
                    </div>
                    <span className={`px-2.5 py-1 rounded-lg text-xs font-medium ${priorityInfo.color}`}>
                      {priorityInfo.label}
                    </span>
                    <span className="text-gray-500">
                      {task.assignedTo === 'partner' ? 'От Юритех' : 'Для ЮРИТЕХ'}
                    </span>
                  </div>
                  <div className="mt-3">
                    <BitrixSyncStatus
                      compact
                      status={task.bitrixSyncStatus}
                      errorCode={task.bitrixSyncErrorCode}
                      isRetrying={retryTaskMutation.isPending && retryTaskMutation.variables === task.id}
                      onRetry={task.assignedTo === 'partner' ? undefined : () => retryTaskMutation.mutate(task.id, {
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

      {(hasNextPage || isFetchingNextPage) && (
        <div ref={sentinelRef} className="flex justify-center py-6">
          <Loader2 className="w-6 h-6 animate-spin text-pink-500" />
        </div>
      )}

      {filteredTasks.length === 0 && !isLoading && (
        <div className="text-center py-12">
          <CheckSquare className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">Задачи не найдены</p>
        </div>
      )}

      {/* Create Task Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-3xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-8">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-semibold text-gray-900">Создать задачу</h2>
              <button
                onClick={() => setShowCreateModal(false)}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-6 h-6 text-gray-500" />
              </button>
            </div>
            <form className="space-y-6" onSubmit={handleCreateTask}>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Название задачи
                </label>
                <input
                  type="text"
                  value={newTask.title}
                  onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
                  required
                  className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                  placeholder="Введите название задачи"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Описание
                </label>
                <textarea
                  rows={4}
                  value={newTask.description}
                  onChange={(e) => setNewTask({ ...newTask, description: e.target.value })}
                  className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent resize-none"
                  placeholder="Опишите детали задачи"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Клиент
                  </label>
                  <CustomSelect
                    value={newTask.client_id}
                    onChange={(val) => setNewTask({ ...newTask, client_id: val })}
                    options={[
                      { value: '', label: 'Общая задача без клиента' },
                      ...(clientsData?.items ?? []).map((c) => ({ value: c.id, label: c.full_name })),
                    ]}
                    placeholder="Общая задача без клиента"
                    size="lg"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Исполнитель
                  </label>
                  <div className="w-full px-4 py-3 bg-gray-100 border border-gray-200 rounded-xl text-gray-700">
                    ЮРИТЕХ
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Приоритет
                  </label>
                  <CustomSelect
                    value={newTask.priority}
                    onChange={(val) => setNewTask({ ...newTask, priority: val })}
                    options={[
                      { value: 'low', label: 'Низкий' },
                      { value: 'medium', label: 'Средний' },
                      { value: 'high', label: 'Высокий' },
                    ]}
                    size="lg"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Срок выполнения (МСК)
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="date"
                      aria-label="Дата срока (МСК)"
                      value={newTask.due_date}
                      onChange={(e) => setNewTask({ ...newTask, due_date: e.target.value, due_time: e.target.value ? newTask.due_time : '' })}
                      className="w-full min-w-0 px-3 py-2.5 bg-white border border-gray-200 rounded-xl text-sm"
                    />
                    <input
                      type="time"
                      aria-label="Время срока (МСК)"
                      value={newTask.due_time}
                      disabled={!newTask.due_date}
                      onChange={(e) => setNewTask({ ...newTask, due_time: e.target.value })}
                      className="w-28 px-3 py-2.5 bg-white border border-gray-200 rounded-xl text-sm disabled:opacity-50"
                    />
                  </div>
                  <p className="mt-2 text-xs text-gray-500">Без времени — до конца дня. Без даты — без срока.</p>
                  {newTask.due_date && (
                    <button type="button" onClick={() => setNewTask({ ...newTask, due_date: '', due_time: '' })} className="mt-1 text-xs text-gray-500 hover:text-gray-700">Убрать срок</button>
                  )}
                </div>
              </div>
              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => { resetNewTask(); setShowCreateModal(false); }}
                  className="flex-1 px-6 py-3 border border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 transition-colors font-medium"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  disabled={createTaskMutation.isPending}
                  className="flex-1 px-6 py-3 bg-pink-600 text-white rounded-xl hover:bg-pink-700 transition-colors font-medium disabled:opacity-50"
                >
                  {createTaskMutation.isPending ? 'Создание...' : 'Создать задачу'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Task Modal */}
      {editingTask && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-3xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-8">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-semibold text-gray-900">Редактировать задачу</h2>
              <button
                onClick={() => setEditingTask(null)}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-6 h-6 text-gray-500" />
              </button>
            </div>
            <form className="space-y-6" onSubmit={handleEditTask}>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Название задачи
                </label>
                <input
                  type="text"
                  value={editingTask.title}
                  onChange={(e) => setEditingTask({ ...editingTask, title: e.target.value })}
                  required
                  className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Описание
                </label>
                <textarea
                  rows={4}
                  value={editingTask.description}
                  onChange={(e) => setEditingTask({ ...editingTask, description: e.target.value })}
                  className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-pink-500 focus:border-transparent resize-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Приоритет
                </label>
                <CustomSelect
                  value={editingTask.priority}
                  onChange={(val) => setEditingTask({ ...editingTask, priority: val })}
                  options={[
                    { value: 'low', label: 'Низкий' },
                    { value: 'medium', label: 'Средний' },
                    { value: 'high', label: 'Высокий' },
                  ]}
                  size="lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Срок выполнения (МСК)
                </label>
                <div className="flex gap-2">
                  <input
                    type="date"
                    aria-label="Дата срока (МСК)"
                    value={editingTask.due_date}
                    onChange={(e) => setEditingTask({ ...editingTask, due_date: e.target.value, due_time: e.target.value ? editingTask.due_time : '', deadlineChanged: true })}
                    className="w-full min-w-0 px-3 py-2.5 bg-white border border-gray-200 rounded-xl text-sm"
                  />
                  <input
                    type="time"
                    aria-label="Время срока (МСК)"
                    value={editingTask.due_time}
                    disabled={!editingTask.due_date}
                    onChange={(e) => setEditingTask({ ...editingTask, due_time: e.target.value, deadlineChanged: true })}
                    className="w-28 px-3 py-2.5 bg-white border border-gray-200 rounded-xl text-sm disabled:opacity-50"
                  />
                </div>
                <p className="mt-2 text-xs text-gray-500">Без времени — до конца дня. Без даты — без срока.</p>
                {editingTask.due_date && (
                  <button type="button" onClick={() => setEditingTask({ ...editingTask, due_date: '', due_time: '', deadlineChanged: true })} className="mt-1 text-xs text-gray-500 hover:text-gray-700">Убрать срок</button>
                )}
              </div>
              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setEditingTask(null)}
                  className="flex-1 px-6 py-3 border border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 transition-colors font-medium"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  disabled={updateTaskMutation.isPending}
                  className="flex-1 px-6 py-3 bg-pink-600 text-white rounded-xl hover:bg-pink-700 transition-colors font-medium disabled:opacity-50"
                >
                  {updateTaskMutation.isPending ? 'Сохранение...' : 'Сохранить'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={taskToDelete !== null}
        onOpenChange={(open) => { if (!open) setTaskToDelete(null); }}
        title="Удалить задачу?"
        description={taskToDelete ? `«${taskToDelete.title}» будет удалена безвозвратно.` : undefined}
        confirmText="Удалить"
        variant="destructive"
        onConfirm={confirmDeleteTask}
      />
    </div>
  );
}
