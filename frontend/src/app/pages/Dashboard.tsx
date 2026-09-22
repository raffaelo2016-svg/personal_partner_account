import { Users, UserCheck, Clock, TrendingUp, AlertCircle, CheckSquare, BarChart3, AlertTriangle, CreditCard } from 'lucide-react';
import { Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { fetchDashboard } from '../api/dashboard';
import { fetchCourtFeeSummary } from '../api/finance';
import { formatDateShort } from '@/app/utils/formatDate';
import { useTimezone } from '@/app/contexts/TimezoneContext';
import { SkeletonCard } from '../components/ui/skeleton';
import OverdueDebtAlert from '../components/OverdueDebtAlert';
import { PromotionIncentiveBanner } from '../components/PromotionIncentiveBanner';
import NewsPreview from '../components/NewsPreview';

export default function Dashboard() {
  const tz = useTimezone();
  const { data: dashboard, isLoading } = useQuery({ queryKey: ['dashboard'], queryFn: fetchDashboard });
  const { data: feeSummary } = useQuery({ queryKey: ['courtFeeSummary'], queryFn: fetchCourtFeeSummary });

  const d = dashboard;

  const stats = [
    {
      title: 'Всего клиентов',
      value: String(d?.stats.total_clients ?? 0),
      change: `+${d?.stats.new_this_week ?? 0} за неделю`,
      icon: Users,
      color: 'bg-blue-500',
    },
    {
      title: 'ДО подачи в суд',
      value: String(d?.stats.before_court ?? 0),
      change: 'Подготовка документов',
      icon: Clock,
      color: 'bg-yellow-500',
    },
    {
      title: 'УЖЕ в суде',
      value: String(d?.stats.in_court ?? 0),
      change: 'В процессе',
      icon: UserCheck,
      color: 'bg-green-500',
    },
    {
      title: 'Успешно завершено',
      value: String(d?.stats.completed ?? 0),
      change: 'Всего',
      icon: TrendingUp,
      color: 'bg-purple-500',
    },
  ];

  const urgentTasks = (d?.urgent_tasks ?? []).map((t) => ({
    id: t.id,
    title: t.title,
    client: '',
    clientId: t.id,
    dueDate: formatDateShort(t.due_date, tz),
    priority: t.priority,
    daysLeft: Math.max(0, Math.ceil((new Date(t.due_date).getTime() - Date.now()) / 86400000)),
  }));

  const recentClients = (d?.recent_clients ?? []).map((c) => ({
    id: c.id,
    name: c.full_name,
    type: c.type === 'before_court' ? 'ДО подачи в суд' : 'УЖЕ в суде',
    status: c.status,
    date: formatDateShort(c.created_at, tz),
  }));

  const completionRate = d?.task_completion?.percent ?? 0;
  
  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-semibold text-gray-900 mb-2">
          Партнерский кабинет
        </h1>
        <p className="text-gray-600">
          Добро пожаловать в систему управления клиентами URITECH Partner
        </p>
      </div>

      <NewsPreview />

      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      )}

      <OverdueDebtAlert
        overdueDebt={(feeSummary?.overdue_debt ?? 0) / 100}
        currentDebt={(feeSummary?.current_debt ?? 0) / 100}
        unpaidCount={feeSummary?.unpaid_count}
      />

      <PromotionIncentiveBanner summary={feeSummary} />
      
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.title}
              className="bg-white rounded-xl p-6 border border-gray-200 hover:shadow-lg transition-shadow"
            >
              <div className="flex items-start justify-between mb-4">
                <div className={`${stat.color} w-12 h-12 rounded-lg flex items-center justify-center`}>
                  <Icon className="w-6 h-6 text-white" />
                </div>
              </div>
              <h3 className="text-gray-600 text-sm mb-1">{stat.title}</h3>
              <p className="text-3xl font-semibold text-gray-900 mb-1">
                {stat.value}
              </p>
              <p className="text-sm text-gray-500">{stat.change}</p>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Urgent Tasks */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-2xl border border-gray-200">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
                  <AlertCircle className="w-5 h-5 text-red-600" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">
                    Срочные задачи
                  </h2>
                  <p className="text-sm text-gray-500">Требуют внимания</p>
                </div>
              </div>
              <Link
                to="/dashboard/tasks"
                className="text-sm text-blue-600 hover:text-blue-700 font-medium"
              >
                Все задачи
              </Link>
            </div>
            <div className="p-6 space-y-3">
              {urgentTasks.map((task) => (
                <div
                  key={task.id}
                  className="flex items-start gap-4 p-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors"
                >
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
                    task.priority === 'high' ? 'bg-red-100' : 'bg-yellow-100'
                  }`}>
                    <CheckSquare className={`w-5 h-5 ${
                      task.priority === 'high' ? 'text-red-600' : 'text-yellow-600'
                    }`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h4 className="font-medium text-gray-900 mb-1">{task.title}</h4>
                    <Link 
                      to={`/dashboard/clients/${task.clientId}`}
                      className="text-sm text-blue-600 hover:text-blue-700 mb-2 inline-block"
                    >
                      {task.client}
                    </Link>
                    <div className="flex items-center gap-4 text-xs text-gray-500">
                      <span>Срок: {task.dueDate}</span>
                      <span className={`px-2 py-1 rounded ${
                        task.daysLeft <= 2 ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'
                      }`}>
                        Осталось {task.daysLeft} дн.
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Task Completion Chart */}
        <div className="bg-white rounded-2xl border border-gray-200 p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
              <BarChart3 className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Выполнение задач</h3>
              <p className="text-sm text-gray-500">Текущий месяц</p>
            </div>
          </div>
          
          <div className="mb-6">
            <div className="flex items-baseline gap-2 mb-2">
              <span className="text-3xl font-bold text-gray-900">{completionRate}%</span>
              <span className="text-sm text-gray-500">выполнено</span>
            </div>
            <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full transition-all"
                style={{ width: `${completionRate}%` }}
              />
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600">Выполнено</span>
              <span className="text-gray-900 font-medium">
                {d?.task_completion?.completed ?? 0}/{d?.task_completion?.total ?? 0}
              </span>
            </div>
          </div>

          <Link
            to="/dashboard/tasks"
            className="mt-6 w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-purple-50 text-purple-700 rounded-xl hover:bg-purple-100 transition-colors font-medium text-sm"
          >
            Подробная статистика
          </Link>
        </div>
      </div>
      
      {/* Recent Clients */}
      <div className="bg-white rounded-2xl border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            Последние клиенты
          </h2>
          <Link
            to="/dashboard/clients"
            className="text-sm text-blue-600 hover:text-blue-700 font-medium"
          >
            Смотреть все
          </Link>
        </div>
        <div className="divide-y divide-gray-200">
          {recentClients.map((client) => (
            <Link
              key={client.id}
              to={`/dashboard/clients/${client.id}`}
              className="px-6 py-4 hover:bg-gray-50 transition-colors flex items-center justify-between group"
            >
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-gray-200 rounded-full flex items-center justify-center">
                  <span className="text-sm font-medium text-gray-700">
                    {client.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
                  </span>
                </div>
                <div>
                  <p className="font-medium text-gray-900 group-hover:text-blue-600">
                    {client.name}
                  </p>
                  <p className="text-sm text-gray-500">{client.type}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-900">{client.status}</p>
                <p className="text-sm text-gray-500">{client.date}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>

    </div>
  );
}
