import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchPartners,
  fetchPartner,
  createPartner,
  updatePartner,
  deletePartner,
  fetchPartnerStats,
  bindPartnerBitrixCollab,
  retryPartnerBitrixSync,
  type PartnerFilters,
} from '@/app/api/partners';
import type { PartnerBitrixCollabBinding, PartnerCreate, PartnerUpdate } from '@/app/types';

export function usePartners(filters: PartnerFilters = {}) {
  return useQuery({
    queryKey: ['admin', 'partners', filters],
    queryFn: () => fetchPartners(filters),
  });
}

export function useInfinitePartners(filters: Omit<PartnerFilters, 'page'> = {}) {
  return useInfiniteQuery({
    queryKey: ['admin', 'partners', 'infinite', filters],
    queryFn: ({ pageParam = 1 }) => fetchPartners({ ...filters, page: pageParam, page_size: 20 }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.pages ? lastPage.page + 1 : undefined,
  });
}

export function usePartner(id: string | undefined) {
  return useQuery({
    queryKey: ['admin', 'partners', id],
    queryFn: () => fetchPartner(id!),
    enabled: !!id,
  });
}

export function useCreatePartner() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: PartnerCreate) => createPartner(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'partners'] });
    },
  });
}

export function useUpdatePartner() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: PartnerUpdate }) => updatePartner(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'partners'] });
    },
  });
}

export function useDeletePartner() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => deletePartner(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'partners'] });
    },
  });
}

export function usePartnerStats() {
  return useQuery({
    queryKey: ['admin', 'partners', 'stats'],
    queryFn: fetchPartnerStats,
  });
}

export function useRetryPartnerBitrixSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => retryPartnerBitrixSync(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'partners'] }),
  });
}

export function useBindPartnerBitrixCollab() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: PartnerBitrixCollabBinding }) =>
      bindPartnerBitrixCollab(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'partners'] }),
  });
}
