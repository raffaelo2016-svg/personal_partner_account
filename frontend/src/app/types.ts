// Auth & User types

export type UserRole = 'partner' | 'admin';

export interface User {
  id: string;
  email: string;
  role: UserRole;
}

// Partner types

export type PartnerStatus = 'pending' | 'active' | 'blocked';

export type PartnerType = 'individual' | 'legal' | 'entrepreneur';

export interface Partner {
  id: string;
  user_id: string;
  email?: string | null;
  partner_type: PartnerType;
  company_name: string;
  director_name: string;
  inn: string;
  phone: string;
  short_name?: string | null;
  full_legal_name?: string | null;
  legal_address?: string | null;
  postal_address?: string | null;
  kpp?: string | null;
  court_fee_per_client: number;
  payment_term_days: number;
  free_client_limit: number;
  promotion_start_date?: string | null;
  promotion_end_date?: string | null;
  status: PartnerStatus;
  created_at: string;
  updated_at: string;
  bitrix_sync_status: 'not_scheduled' | 'pending' | 'processing' | 'synced' | 'failed' | 'conflict';
  bitrix_sync_error_code?: string | null;
  bitrix_partner_item_id?: string | null;
  bitrix_collab_status: 'not_linked' | 'binding_required' | 'linked';
  bitrix_collab_id?: string | null;
  bitrix_chat_id?: string | null;
  bitrix_root_folder_id?: string | null;
  bitrix_sync_requested_at?: string | null;
  bitrix_synced_at?: string | null;
  clients_count?: number;
  active_cases_count?: number;
  before_court_count?: number;
  in_court_count?: number;
  completed_count?: number;
  finance_total_cost?: number;
  finance_current_debt?: number;
  finance_overdue_debt?: number;
  finance_paid?: number;
}

export interface PartnerBitrixCollabBinding {
  collab_id?: string;
  chat_id?: string;
  root_folder_id?: string;
}

export interface PartnerCreate {
  email: string;
  password: string;
  partner_type?: PartnerType;
  company_name: string;
  director_name: string;
  inn: string;
  phone: string;
  short_name?: string;
  full_legal_name?: string;
  legal_address?: string;
  postal_address?: string;
  kpp?: string;
  court_fee_per_client?: number;
  payment_term_days?: number;
  free_client_limit?: number;
  promotion_start_date?: string | null;
}

export interface PartnerUpdate {
  partner_type?: PartnerType;
  company_name?: string;
  director_name?: string;
  inn?: string;
  phone?: string;
  short_name?: string | null;
  full_legal_name?: string | null;
  legal_address?: string | null;
  postal_address?: string | null;
  kpp?: string | null;
  court_fee_per_client?: number;
  payment_term_days?: number;
  free_client_limit?: number;
  promotion_start_date?: string | null;
  status?: PartnerStatus;
}

// Client types

export type ClientType = 'before_court' | 'in_court';

export type ClientStatus = 'new' | 'documents_preparing' | 'ready_to_submit' | 'submitted' | 'in_process';

export interface Client {
  id: string;
  type: ClientType;
  status: ClientStatus;
  
  // Персональные данные
  fullName: string;
  dateOfBirth: string;
  passportSeries: string;
  passportNumber: string;
  passportIssueDate: string;
  passportIssuedBy: string;
  registrationAddress: string;
  inn: string;
  snils: string;
  
  // Контактные данные
  phone: string;
  email: string;
  
  // Юридическая информация
  region: string;
  arbitrageCourt: string;
  
  // Метаданные
  createdAt: string;
  updatedAt: string;
}
