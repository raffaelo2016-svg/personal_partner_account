import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  TaskFilters,
  TaskCreatePayload,
  TaskUpdatePayload,
  createTask,
  deleteTask,
  fetchTasks,
  fetchTaskStats,
  fetchUrgentTasks,
  updateTask,
  retryTaskBitrix,
} from '../api/tasks';

export function useTasks(filters: TaskFilters = {}) {
  return useQuery({
    queryKey: ['tasks', filters],
    queryFn: () => fetchTasks(filters),
  });
}

export function useInfiniteTasks(filters: Omit<TaskFilters, 'page'> = {}) {
  return useInfiniteQuery({
    queryKey: ['tasks', 'infinite', filters],
    queryFn: ({ pageParam = 1 }) => fetchTasks({ ...filters, page: pageParam, page_size: 20 }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.pages ? lastPage.page + 1 : undefined,
  });
}

export function useCreateTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: TaskCreatePayload) => createTask(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      queryClient.invalidateQueries({ queryKey: ['taskStats'] });
      queryClient.invalidateQueries({ queryKey: ['urgentTasks'] });
    },
  });
}

export function useUpdateTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: TaskUpdatePayload }) => updateTask(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      queryClient.invalidateQueries({ queryKey: ['taskStats'] });
      queryClient.invalidateQueries({ queryKey: ['urgentTasks'] });
    },
  });
}

export function useDeleteTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteTask(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      queryClient.invalidateQueries({ queryKey: ['taskStats'] });
      queryClient.invalidateQueries({ queryKey: ['urgentTasks'] });
    },
  });
}

export function useRetryTaskBitrix() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => retryTaskBitrix(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      queryClient.invalidateQueries({ queryKey: ['urgentTasks'] });
      queryClient.invalidateQueries({ queryKey: ['bitrixAttention'] });
      queryClient.invalidateQueries({ queryKey: ['adminBitrixAttentionCount'] });
    },
  });
}

export function useTaskStats(params?: { assigned_to?: string }) {
  return useQuery({
    queryKey: ['taskStats', params],
    queryFn: () => fetchTaskStats(params),
  });
}

export function useUrgentTasks() {
  return useQuery({
    queryKey: ['urgentTasks'],
    queryFn: fetchUrgentTasks,
  });
}
