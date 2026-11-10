import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ClientFilters,
  ClientCreatePayload,
  ClientUpdatePayload,
  createClient,
  deleteClient,
  fetchClient,
  fetchClients,
  fetchClientStats,
  fetchClientProgress,
  changeClientStatus,
  fetchStatusHistory,
  fetchAdminClients,
  fetchAdminClient,
  updateAdminClient,
  retryAdminClientBitrix,
  updateClient,
} from '../api/clients';

export function useClients(filters: ClientFilters = {}) {
  return useQuery({
    queryKey: ['clients', filters],
    queryFn: () => fetchClients(filters),
  });
}

export function useInfiniteClients(filters: Omit<ClientFilters, 'page'> = {}) {
  return useInfiniteQuery({
    queryKey: ['clients', 'infinite', filters],
    queryFn: ({ pageParam = 1 }) => fetchClients({ ...filters, page: pageParam, page_size: 20 }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.pages ? lastPage.page + 1 : undefined,
  });
}

export function useClient(id: string, enabled = true) {
  return useQuery({
    queryKey: ['client', id],
    queryFn: () => fetchClient(id),
    enabled: !!id && enabled,
  });
}

export function useCreateClient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ClientCreatePayload) => createClient(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clients'] });
      queryClient.invalidateQueries({ queryKey: ['clientStats'] });
    },
  });
}

export function useUpdateClient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ClientUpdatePayload }) => updateClient(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clients'] });
      queryClient.invalidateQueries({ queryKey: ['client'] });
    },
  });
}

export function useDeleteClient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteClient(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clients'] });
      queryClient.invalidateQueries({ queryKey: ['clientStats'] });
    },
  });
}

export function useClientStats() {
  return useQuery({
    queryKey: ['clientStats'],
    queryFn: fetchClientStats,
  });
}

export function useAdminClients(filters: ClientFilters = {}) {
  return useQuery({
    queryKey: ['adminClients', filters],
    queryFn: () => fetchAdminClients(filters),
  });
}

export function useInfiniteAdminClients(filters: Omit<ClientFilters, 'page'> = {}) {
  return useInfiniteQuery({
    queryKey: ['adminClients', 'infinite', filters],
    queryFn: ({ pageParam = 1 }) => fetchAdminClients({ ...filters, page: pageParam, page_size: 20 }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.pages ? lastPage.page + 1 : undefined,
  });
}

export function useAdminClient(id: string, enabled = true) {
  return useQuery({
    queryKey: ['adminClient', id],
    queryFn: () => fetchAdminClient(id),
    enabled: !!id && enabled,
  });
}

export function useUpdateAdminClient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ClientUpdatePayload }) => updateAdminClient(id, data),
    onSuccess: (updatedClient, variables) => {
      // Сразу показываем сохранённые значения, не дожидаясь перезапроса.
      queryClient.setQueryData(['adminClient', variables.id], updatedClient);
      queryClient.invalidateQueries({ queryKey: ['adminClients'] });
      queryClient.invalidateQueries({ queryKey: ['adminClient'] });
    },
  });
}

export function useRetryAdminClientBitrix() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => retryAdminClientBitrix(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ['adminClients'] });
      queryClient.invalidateQueries({ queryKey: ['adminClient', id] });
      queryClient.invalidateQueries({ queryKey: ['bitrixAttention'] });
      queryClient.invalidateQueries({ queryKey: ['adminBitrixAttentionCount'] });
    },
  });
}

export function useClientProgress(clientId: string) {
  return useQuery({
    queryKey: ['clientProgress', clientId],
    queryFn: () => fetchClientProgress(clientId),
    enabled: !!clientId,
  });
}

export function useChangeClientStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ clientId, status, comment }: { clientId: string; status: string; comment?: string }) =>
      changeClientStatus(clientId, status, comment),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['client', variables.clientId] });
      queryClient.invalidateQueries({ queryKey: ['clientProgress', variables.clientId] });
      queryClient.invalidateQueries({ queryKey: ['statusHistory', variables.clientId] });
      queryClient.invalidateQueries({ queryKey: ['clients'] });
    },
  });
}

export function useStatusHistory(clientId: string) {
  return useQuery({
    queryKey: ['statusHistory', clientId],
    queryFn: () => fetchStatusHistory(clientId),
    enabled: !!clientId,
  });
}
