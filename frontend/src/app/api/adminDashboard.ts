import apiClient from './client';

export interface AdminTransactionData {
  id: string;
  partner_id: string;
  partner_name: string;
  client_name: string | null;
  amount: number;
  status: string;
  payment_method: string | null;
  external_id: string | null;
  created_at: string;
}

export interface AdminDashboardData {
  recent_transactions: AdminTransactionData[];
  main_stats: {
    partners_count: number;
    active_partners: number;
    pending_partners: number;
    new_debtors: number;
    total_clients: number;
  };
  movement_stats: {
    in_progress: number;
    completed: number;
    rejected: number;
  };
  finance_stats: {
    total_cost: number;
    current_debt: number;
    overdue_debt: number;
    paid: number;
  };
  top_partners: {
    id: string;
    company_name: string;
    status: string;
    clients_count: number;
    finance_total_cost: number;
    finance_current_debt: number;
    finance_overdue_debt: number;
    finance_paid: number;
  }[];
}

export interface AdminDashboardFilters {
  date_from?: string;
  date_to?: string;
}

export async function fetchAdminDashboard(
  filters: AdminDashboardFilters = {},
): Promise<AdminDashboardData> {
  const res = await apiClient.get<AdminDashboardData>('/admin/dashboard', {
    params: filters,
  });
  return res.data;
}
