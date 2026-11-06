import apiClient from './client';

export interface DashboardStats {
  total_clients: number;
  new_this_week: number;
  before_court: number;
  in_court: number;
  completed: number;
}

export interface DashboardTask {
  id: string;
  title: string;
  status: string;
  priority: string;
  due_date: string | null;
  due_at?: string | null;
  client_id?: string | null;
  client_name?: string | null;
}

export interface DashboardClient {
  id: string;
  full_name: string;
  type: string;
  status: string;
  created_at: string;
}

export interface DashboardData {
  stats: DashboardStats;
  urgent_tasks: DashboardTask[];
  task_completion: {
    percent: number;
    total: number;
    completed: number;
  };
  recent_clients: DashboardClient[];
}

export async function fetchDashboard(): Promise<DashboardData> {
  const res = await apiClient.get<DashboardData>('/dashboard');
  return res.data;
}
