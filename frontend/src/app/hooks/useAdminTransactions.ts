import { useInfiniteQuery } from '@tanstack/react-query';
import {
  fetchAdminTransactions,
  type AdminTransactionsFilters,
} from '@/app/api/adminTransactions';

export function useInfiniteAdminTransactions(
  filters: Omit<AdminTransactionsFilters, 'page'> = {},
) {
  return useInfiniteQuery({
    queryKey: ['admin', 'transactions', 'infinite', filters],
    queryFn: ({ pageParam = 1 }) =>
      fetchAdminTransactions({ ...filters, page: pageParam, page_size: 20 }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.pages ? lastPage.page + 1 : undefined,
  });
}
