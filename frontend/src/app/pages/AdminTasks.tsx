import { useState, useMemo, useCallback } from 'react';
import { useSearchParams } from 'react-router';
import {
  CheckSquare, Plus, Calendar, User, AlertCircle, Clock, CheckCircle,
  Filter, Search, X, Loader2, Trash2, Edit2,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useInfiniteTasks, useTaskStats, useCreateTask, useUpdateTask, useDeleteTask, useRetryTaskBitrix } from '../hooks/useTasks';
import { usePartners } from '../hooks/usePartners';
import { fetchAdminClients } from '../api/clients';
import { useIntersectionObserver } from '../hooks/useIntersectionObserver';
import { toast } from 'sonner';
import CustomSelect from '../components/ui/CustomSelect';
import DateInput from '../components/ui/DateInput';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import BitrixSyncStatus from '../components/BitrixSyncStatus';

export default function AdminTasks() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();

  const directionRaw = searchParams.get('direction') ?? 'from_partners';
  const direction: 'my' | 'from_partners' = directionRaw === 'my' ? 'my' : 'from_partners';
  const filterStatus = searchParams.get('status') ?? 'all';
  const filterPriority = searchParams.get('priority') ?? 'all';
  const onlyOverdue = searchParams.get('overdue') === '1';
  const searchQuery = searchParams.get('q') ?? '';

  const updateParam = useCallback(
    (key: string, value: string, defaultValue: string) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (!value || value === defaultValue) next.delete(key);
          else next.set(key, value);
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const setDirection = (v: 'my' | 'from_partners') => updateParam('direction', v, 'from_partners');
  const setFilterStatus = (v: string) => updateParam('status', v, 'all');
  const setFilterPriority = (v: string) => updateParam('priority', v, 'all');
  const setOnlyOverdue = (v: boolean) => updateParam('overdue', v ? '1' : '', '');
  const setSearchQuery = (v: string) => updateParam('q', v, '');

  const assignedToFilter = direction === 'my' ? 'partner' : 'uritech';

  const filters = {
    assigned_to: assignedToFilter,
    ...(filterStatus !== 'all' ? { status: filterStatus } : {}),
    ...(filterPriority !== 'all' ? { priority: filterPriority } : {}),
    ...(searchQuery ? { search: searchQuery } : {}),
  };

  const { data: tasksPages, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteTasks(filters);
  const { data: statsData } = useTaskStats({ assigned_to: assignedToFilter });
  const { data: partnersData } = usePartners({ page_size: 100 });
  const { data: clientsData } = useQuery({
    queryKey: ['adminClients', { page_size: 100 }],
    queryFn: () => fetchAdminClients({ page_size: 100 }),
  });
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
    due_date: string;
  } | null>(null);

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
          due_date: editingTask.due_date,
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

  const [selectedPartnerId, setSelectedPartnerId] = useState('');

  const partnerClients = useMemo(() => {
    if (!selectedPartnerId || !clientsData?.items) return [];
    return clientsData.items.filter((c) => c.partner_id === selectedPartnerId);
  }, [selectedPartnerId, clientsData]);

  const [newTask, setNewTask] = useState({
    title: '',
    description: '',
    client_id: '',
    priority: 'low',
    due_date: '',
  });

  const resetNewTask = () => {
    setNewTask({ title: '', description: '', client_id: '', priority: 'low', due_date: '' });
    setSelectedPartnerId('');
  };

  const handleCreateTask = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTask.title.trim() || !selectedPartnerId || !newTask.due_date) {
      toast.error('Заполните обязательные поля: название, партнёр и срок выполнения');
      return;
    }
    if (partnerClients.length > 0 && !newTask.client_id) {
      toast.error('Выберите клиента партнёра');
      return;
    }
    createTaskMutation.mutate(
      {
        client_id: newTask.client_id,
        title: newTask.title.trim(),
        description: newTask.description.trim() || undefined,
        priority: newTask.priority,
        assigned_to: 'partner',
        due_date: newTask.due_date,
      },
      {
        onSuccess: () => {
          toast.success('Задача создана и отправлена партнёру');
          resetNewTask();
          setShowCreateModal(false);
        },
        onError: () => {
          toast.error('Не удалось создать задачу');
        },
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
    client: { id: t.client_id, name: t.client_name ?? '' },
    assignedTo: t.assigned_to as 'partner' | 'uritech',
    status: t.status as 'pending' | 'in_progress' | 'completed' | 'overdue',
    priority: t.priority as 'low' | 'medium' | 'high',
    dueDate: t.due_date,
    createdAt: t.created_at,
    completedAt: t.completed_at ?? undefined,
    bitrixSyncStatus: t.bitrix_sync_status,
    bitrixSyncErrorCode: t.bitrix_sync_error_code,
  }));

  const priorityWeight: Record<string, number> = { high: 0, medium: 1, low: 2 };

  const isTaskOverdue = (task: { status: string; dueDate: string }) => {
    if (task.status === 'completed') return false;
    if (task.status === 'overdue') return true;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return new Date(task.dueDate) < today;
  };

  const filteredTasks = [...tasks]
    .filter((t) => !onlyOverdue || isTaskOverdue(t))
    .sort((a, b) => {
      const pa = priorityWeight[a.priority] ?? 3;
      const pb = priorityWeight[b.priority] ?? 3;
      if (pa !== pb) return pa - pb;
      return new Date(a.dueDate).getTime() - new Date(b.dueDate).getTime();
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

  const getDaysRemaining = (dueDate: string) => {
    const today = new Date();
    const due = new Date(dueDate);
    const diff = Math.ceil((due.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
    if (diff < 0) return `Просрочено на ${Math.abs(diff)} дн.`;
    if (diff === 0) return 'Сегодня';
    if (diff === 1) return 'Завтра';
    return `Осталось ${diff} дн.`;
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
          <h1 className="text-3xl font-semibold text-gray-900 mb-2">Задачи</h1>
          <p className="text-gray-600">Управление задачами партнёров</p>
        </div>
        {direction === 'my' && (
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-all shadow-sm hover:shadow"
          >
            <Plus className="w-5 h-5" />
            Создать задачу
          </button>
        )}
      </div>

      {/* Direction Toggle */}
      <div className="bg-white rounded-2xl border border-gray-200 p-1.5 inline-flex gap-1">
        <button
          onClick={() => setDirection('from_partners')}
          className={`px-5 py-2.5 rounded-xl text-sm font-medium transition-all ${
            direction === 'from_partners'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          Задачи от партнёров
        </button>
        <button
          onClick={() => setDirection('my')}
          className={`px-5 py-2.5 rounded-xl text-sm font-medium transition-all ${
            direction === 'my'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          Мои задачи
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
              className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            />
          </div>
          <CustomSelect
            value={filterStatus}
            onChange={(val) => setFilterStatus(val)}
            options={[
              { value: 'all', label: 'Все статусы' },
              { value: 'pending', label: 'Ожидает' },
              { value: 'in_progress', label: 'В работе' },
              { value: 'completed', label: 'Выполнено' },
            ]}
          />
          <CustomSelect
            value={filterPriority}
            onChange={(val) => setFilterPriority(val)}
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
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
        </div>
      ) : (
        <div className="space-y-3">
          {filteredTasks.map((task) => {
            const statusInfo = getStatusInfo(task.status);
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
                    task.status === 'overdue' ? 'bg-red-50' : 'bg-indigo-50'
                  }`}>
                    <CheckSquare className={`w-6 h-6 ${
                      task.status === 'completed' ? 'text-green-600' :
                      task.status === 'overdue' ? 'text-red-600' : 'text-indigo-600'
                    }`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <h3 className="font-semibold text-gray-900 mb-1">{task.title}</h3>
                        <p className="text-sm text-gray-600 mb-3">{task.description}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <CustomSelect
                          value={task.status}
                          onChange={(val) => handleStatusChange(task.id, val)}
                          options={[
                            { value: 'pending', label: 'Ожидает' },
                            { value: 'in_progress', label: 'В работе' },
                            { value: 'completed', label: 'Выполнено' },
                          ]}
                          size="sm"
                          triggerClassName={statusInfo.color}
                        />
                        <button
                          onClick={() => setEditingTask({
                            id: task.id,
                            title: task.title,
                            description: task.description,
                            priority: task.priority,
                            due_date: task.dueDate,
                          })}
                          className="p-1.5 rounded-lg text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 transition-colors"
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
                      </div>
                    </div>
                    <div className="flex items-center gap-6 text-sm">
                      <span className="flex items-center gap-2 text-gray-700">
                        <User className="w-4 h-4" />
                        {task.client.name}
                      </span>
                      <div className="flex items-center gap-2 text-gray-600">
                        <Calendar className="w-4 h-4" />
                        {getDaysRemaining(task.dueDate)}
                      </div>
                      <span className={`px-2.5 py-1 rounded-lg text-xs font-medium ${priorityInfo.color}`}>
                        {priorityInfo.label}
                      </span>
                      <span className="text-gray-500">
                        {task.assignedTo === 'partner' ? 'Для партнёра' : 'Для ЮРИТЕХ'}
                      </span>
                    </div>
                    <div className="mt-3">
                      <BitrixSyncStatus
                        compact
                        status={task.bitrixSyncStatus}
                        errorCode={task.bitrixSyncErrorCode}
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

      {(hasNextPage || isFetchingNextPage) && (
        <div ref={sentinelRef} className="flex justify-center py-6">
          <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
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
              <h2 className="text-2xl font-semibold text-gray-900">Создать задачу для партнёра</h2>
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
                  Название задачи <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={newTask.title}
                  onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
                  required
                  className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
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
                  className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
                  placeholder="Опишите детали задачи"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Партнёр <span className="text-red-500">*</span>
                </label>
                <CustomSelect
                  value={selectedPartnerId}
                  onChange={(val) => {
                    setSelectedPartnerId(val);
                    setNewTask({ ...newTask, client_id: '' });
                  }}
                  options={[
                    { value: '', label: 'Выберите партнёра' },
                    ...(partnersData?.items ?? []).map((p) => ({ value: p.id, label: `${p.company_name} (${p.director_name})` })),
                  ]}
                  placeholder="Выберите партнёра"
                  size="lg"
                />
              </div>
              {selectedPartnerId && partnerClients.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Клиент партнёра <span className="text-red-500">*</span>
                  </label>
                  <CustomSelect
                    value={newTask.client_id}
                    onChange={(val) => setNewTask({ ...newTask, client_id: val })}
                    options={[
                      { value: '', label: 'Выберите клиента' },
                      ...partnerClients.map((c) => ({ value: c.id, label: c.full_name })),
                    ]}
                    placeholder="Выберите клиента"
                    size="lg"
                  />
                </div>
              )}
              {selectedPartnerId && partnerClients.length === 0 && (
                <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-xl text-sm text-yellow-700">
                  У этого партнёра нет клиентов
                </div>
              )}
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
                    Срок выполнения <span className="text-red-500">*</span>
                  </label>
                  <DateInput
                    value={newTask.due_date}
                    onChange={(val) => setNewTask({ ...newTask, due_date: val })}
                    required
                  />
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
                  className="flex-1 px-6 py-3 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-colors font-medium disabled:opacity-50"
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
                  className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
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
                  className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
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
                    Срок выполнения
                  </label>
                  <DateInput
                    value={editingTask.due_date}
                    onChange={(val) => setEditingTask({ ...editingTask, due_date: val })}
                    required
                  />
                </div>
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
                  className="flex-1 px-6 py-3 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-colors font-medium disabled:opacity-50"
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
