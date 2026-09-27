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
    total_partners: number;
    total_active_partners: number;
    total_pending_partners: number;
    transmitting_partners: number;
    activated_new_partners: number;
    activation_rate: number;
    clients_per_active_partner: number;
  };
  movement_stats: {
    in_progress: number;
    completed: number;
    rejected: number;
    before_court: number;
    in_court: number;
    without_movement: number;
  };
  finance_stats: {
    total_cost: number;
    current_debt: number;
    overdue_debt: number;
    paid: number;
    collection_rate: number;
    overdue_share: number;
    partners_with_overdue: number;
  };
  comparison_stats: {
    new_partners_change_pct: number | null;
    active_partners_change_pct: number | null;
    clients_change_pct: number | null;
  };
  risk_stats: {
    partners_without_first_client: number;
    declining_partners: number;
    clients_without_movement: number;
    partners_with_overdue: number;
  };
  activity_trend: {
    month: string;
    new_partners: number;
    active_partners: number;
    clients: number;
  }[];
  top_partners: {
    id: string;
    company_name: string;
    status: string;
    clients_count: number;
    last_client_at: string | null;
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
