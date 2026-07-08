import apiClient from './client';

export interface CourtFeeData {
  id: string;
  client_id: string;
  partner_id: string;
  amount: number;
  status: string;
  due_date: string;
  paid_at?: string | null;
  created_at: string;
  client_name?: string | null;
  client_status?: string | null;
  court_procedure_date?: string | null;
}

export interface CourtFeeSummary {
  fee_per_client: number;
  total_debt: number;
  current_debt: number;
  overdue_debt: number;
  paid_this_month: number;
  unpaid_count: number;
  current_count: number;
  overdue_count: number;
  total_clients: number;
  payment_term_days: number;
}

export interface DebtBanner {
  total_debt: number;
  overdue: number;
  has_debt: boolean;
  days_until_next_payment?: number | null;
}

export interface TransactionData {
  id: string;
  partner_id: string;
  court_fee_id?: string | null;
  amount: number;
  status: string;
  payment_method?: string | null;
  external_id?: string | null;
  created_at: string;
}

export interface PaginatedCourtFees {
  items: CourtFeeData[];
  total: number;
  page: number;
  pages: number;
  page_size: number;
}

export interface PaginatedTransactions {
  items: TransactionData[];
  total: number;
  page: number;
  pages: number;
  page_size: number;
}

export async function fetchCourtFees(params: { status?: string; category?: string; page?: number } = {}): Promise<PaginatedCourtFees> {
  const res = await apiClient.get<PaginatedCourtFees>('/finance/court-fees', { params });
  return res.data;
}

export async function fetchCourtFeeSummary(): Promise<CourtFeeSummary> {
  const res = await apiClient.get<CourtFeeSummary>('/finance/court-fees/summary');
  return res.data;
}

export async function fetchDebtBanner(): Promise<DebtBanner> {
  const res = await apiClient.get<DebtBanner>('/finance/debt-banner');
  return res.data;
}

export async function payCourtFee(courtFeeId: string, paymentMethod = 'card'): Promise<TransactionData> {
  const res = await apiClient.post<TransactionData>('/finance/pay', {
    court_fee_id: courtFeeId,
    payment_method: paymentMethod,
  });
  return res.data;
}

export interface CreatePaymentResponse {
  payment_id: string;
  confirmation_url: string | null;
  amount_cents: number;
}

export type DebtType = 'overdue' | 'current' | 'all';

export async function createYookassaPayment(
  feeIds: string[] | null,
  debtType: DebtType = 'all',
): Promise<CreatePaymentResponse> {
  const res = await apiClient.post<CreatePaymentResponse>('/finance/payments', {
    fee_ids: feeIds,
    debt_type: debtType,
  });
  return res.data;
}

export async function fetchTransactions(params: { page?: number } = {}): Promise<PaginatedTransactions> {
  const res = await apiClient.get<PaginatedTransactions>('/finance/history', { params });
  return res.data;
}
