import apiClient from './client';
import type { AdminTransactionData } from './adminDashboard';

export type TransactionStatus = 'pending' | 'completed' | 'failed';

export interface AdminTransactionsPage {
  items: AdminTransactionData[];
  total: number;
  page: number;
  pages: number;
  page_size: number;
}

export interface AdminTransactionsFilters {
  page?: number;
  page_size?: number;
  status?: TransactionStatus;
}

export async function fetchAdminTransactions(
  filters: AdminTransactionsFilters = {},
): Promise<AdminTransactionsPage> {
  const res = await apiClient.get<AdminTransactionsPage>('/admin/finance/transactions', {
    params: filters,
  });
  return res.data;
}
