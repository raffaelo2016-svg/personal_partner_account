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
  fetchTask,
  fetchTaskMessages,
  fetchClientTaskFiles,
  uploadTaskFile,
  deleteTaskFile,
  sendTaskMessage,
  resendTaskMessage,
  reviewTask,
  updateTask,
  retryTaskBitrix,
  type TaskReviewAction,
} from '../api/tasks';

export function useTasks(filters: TaskFilters = {}) {
  return useQuery({
    queryKey: ['tasks', filters],
    queryFn: () => fetchTasks(filters),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}

export function useInfiniteTasks(filters: Omit<TaskFilters, 'page'> = {}) {
  return useInfiniteQuery({
    queryKey: ['tasks', 'infinite', filters],
    queryFn: ({ pageParam = 1 }) => fetchTasks({ ...filters, page: pageParam, page_size: 20 }),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
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
      queryClient.invalidateQueries({ queryKey: ['task'] });
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
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}

export function useUrgentTasks() {
  return useQuery({
    queryKey: ['urgentTasks'],
    queryFn: fetchUrgentTasks,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}

export function useTask(id: string | undefined) {
  return useQuery({
    queryKey: ['task', id],
    queryFn: () => fetchTask(id!),
    enabled: !!id,
    refetchInterval: 20_000,
  });
}

export function useTaskMessages(id: string | undefined) {
  return useQuery({
    queryKey: ['taskMessages', id],
    queryFn: () => fetchTaskMessages(id!),
    enabled: !!id,
    refetchInterval: 3_000,
    refetchIntervalInBackground: false,
  });
}

export function useClientTaskFiles(clientId: string | undefined) {
  return useQuery({
    queryKey: ['clientTaskFiles', clientId],
    queryFn: () => fetchClientTaskFiles(clientId!),
    enabled: !!clientId,
  });
}

export function useUploadTaskFile(taskId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, onProgress }: { file: File; onProgress?: (percent: number) => void }) =>
      uploadTaskFile(taskId!, file, onProgress),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['task', taskId] });
      queryClient.invalidateQueries({ queryKey: ['taskFiles', taskId] });
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      queryClient.invalidateQueries({ queryKey: ['clientTaskFiles'] });
    },
  });
}

export function useDeleteTaskFile(taskId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (fileId: string) => deleteTaskFile(taskId!, fileId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['task', taskId] });
      queryClient.invalidateQueries({ queryKey: ['taskFiles', taskId] });
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      queryClient.invalidateQueries({ queryKey: ['clientTaskFiles'] });
    },
  });
}

export function useSendTaskMessage(taskId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (text: string) => sendTaskMessage(taskId!, text),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['taskMessages', taskId] });
      queryClient.invalidateQueries({ queryKey: ['task', taskId] });
    },
  });
}

export function useResendTaskMessage(taskId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (messageId: string) => resendTaskMessage(taskId!, messageId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['taskMessages', taskId] });
    },
  });
}

export function useTaskReview(taskId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (action: TaskReviewAction) => reviewTask(taskId!, action),
    onSuccess: (data) => {
      queryClient.setQueryData(['task', taskId], data);
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      queryClient.invalidateQueries({ queryKey: ['taskStats'] });
      queryClient.invalidateQueries({ queryKey: ['task', taskId] });
    },
  });
}
