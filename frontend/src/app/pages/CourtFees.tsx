import { AlertCircle, Users, TrendingUp, DollarSign, Loader2, Clock } from 'lucide-react';
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchCourtFees, fetchCourtFeeSummary, payCourtFee } from '../api/finance';
import { formatDateShort } from '@/app/utils/formatDate';
import { useTimezone } from '@/app/contexts/TimezoneContext';
import PaymentModal from '../components/PaymentModal';

export default function CourtFees() {
  const tz = useTimezone();
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
  const [selectedDebt, setSelectedDebt] = useState<string | null>(null);
  const [payDebtType, setPayDebtType] = useState<'overdue' | 'current' | 'all'>('all');
  const [page, setPage] = useState(1);
  const queryClient = useQueryClient();

  const { data: feesData, isLoading } = useQuery({
    queryKey: ['courtFees', page],
    queryFn: () => fetchCourtFees({ page }),
  });
  const { data: summary } = useQuery({
    queryKey: ['courtFeeSummary'],
    queryFn: fetchCourtFeeSummary,
  });

  const payMutation = useMutation({
    mutationFn: (feeId: string) => payCourtFee(feeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['courtFees'] });
      queryClient.invalidateQueries({ queryKey: ['courtFeeSummary'] });
      setIsPaymentModalOpen(false);
    },
  });

  const partnerData = {
    courtFeePerClient: (summary?.fee_per_client ?? 0) / 100,
    totalDebt: (summary?.total_debt ?? 0) / 100,
    currentDebt: (summary?.current_debt ?? 0) / 100,
    overdueDebt: (summary?.overdue_debt ?? 0) / 100,
    totalClients: summary?.total_clients ?? 0,
    activeClients: summary?.unpaid_count ?? 0,
    currentCount: summary?.current_count ?? 0,
    overdueCount: summary?.overdue_count ?? 0,
    paidThisMonth: (summary?.paid_this_month ?? 0) / 100,
  };

  const STATUS_LABELS: Record<string, string> = {
    documents_collection: 'Сбор документов',
    documents_formation: 'Формирование документов',
    sent_to_court: 'Отправка в суд',
    documents_decision: 'Документы приняты / не приняты',
    waiting_hearing: 'Ожидание заседания',
    restructuring: 'Реструктуризация',
    auction: 'Торги',
    realization: 'Реализация',
  };

  const clientDebts = (feesData?.items ?? []).map((f) => ({
    id: f.id,
    clientName: f.client_name ?? 'Клиент',
    courtFee: f.amount / 100,
    status: f.status,
    addedDate: f.created_at?.split('T')[0] ?? '',
    dueDate: f.due_date,
    paidDate: f.paid_at?.split('T')[0],
    stage: STATUS_LABELS[f.client_status ?? ''] ?? f.client_status ?? '',
    courtProcedureDate: f.court_procedure_date ?? null,
  }));

  const getStatusConfig = (status: string) => {
    switch (status) {
      case 'paid':
        return {
          label: 'Оплачено',
          color: 'bg-green-100 text-green-700 border-green-300',
        };
      case 'unpaid':
        return {
          label: 'Ожидает оплаты',
          color: 'bg-yellow-100 text-yellow-700 border-yellow-300',
        };
      case 'overdue':
        return {
          label: 'Просрочено',
          color: 'bg-red-100 text-red-700 border-red-300',
        };
      default:
        return {
          label: status,
          color: 'bg-gray-100 text-gray-700 border-gray-300',
        };
    }
  };

  const unpaidCount = clientDebts.filter(
    (d) => d.status === 'unpaid' || d.status === 'overdue'
  ).length;

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-semibold text-gray-900 mb-2">
          Судебные расходы
        </h1>
        <p className="text-gray-600">
          Управление оплатой судебных расходов за клиентов
        </p>
      </div>

      {/* Alert - Debt Warning */}
      {partnerData.overdueDebt > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 flex items-start gap-4">
          <AlertCircle className="w-6 h-6 text-red-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h3 className="font-semibold text-red-900 mb-1">
              Требуется оплата судебных расходов
            </h3>
            <p className="text-sm text-red-700 mb-3">
              У вас есть просроченная непогашенная задолженность. Пожалуйста, погасите её для
              продолжения работы с клиентами.
            </p>
            <button 
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              onClick={() => {
                setSelectedDebt(null);
                setPayDebtType('overdue');
                setIsPaymentModalOpen(true);
              }}
            >
              Оплатить {partnerData.overdueDebt.toLocaleString('ru-RU')} ₽
            </button>
          </div>
        </div>
      )}
      {partnerData.overdueDebt === 0 && partnerData.currentDebt > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-6 flex items-start gap-4">
          <AlertCircle className="w-6 h-6 text-yellow-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h3 className="font-semibold text-yellow-900 mb-1">
              Требуется оплата судебных расходов
            </h3>
            <p className="text-sm text-yellow-700 mb-3">
              У вас есть непогашенная задолженность. Пожалуйста, погасите её для
              продолжения работы с клиентами.
            </p>
            <button
              className="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition-colors"
              onClick={() => {
                setSelectedDebt(null);
                setPayDebtType('current');
                setIsPaymentModalOpen(true);
              }}
            >
              Оплатить {partnerData.currentDebt.toLocaleString('ru-RU')} ₽
            </button>
          </div>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <DollarSign className="w-6 h-6 text-blue-600" />
            </div>
          </div>
          <p className="text-sm text-gray-600 mb-1">Общая стоимость судебных расходов</p>
          <p className="text-2xl font-bold text-gray-900">
            {partnerData.totalDebt.toLocaleString('ru-RU')} ₽
          </p>
          <p className="text-xs text-gray-500 mt-2">
            Стоимость за клиента: {partnerData.courtFeePerClient.toLocaleString('ru-RU')} ₽
          </p>
        </div>

        <div className="bg-white rounded-xl border border-orange-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center">
              <Clock className="w-6 h-6 text-orange-600" />
            </div>
          </div>
          <p className="text-sm text-gray-600 mb-1">Текущая задолженность</p>
          <p className="text-2xl font-bold text-orange-600">
            {partnerData.currentDebt.toLocaleString('ru-RU')} ₽
          </p>
          <p className="text-xs text-gray-500 mt-2">{partnerData.currentCount} клиентов</p>
        </div>

        <div className="bg-white rounded-xl border border-red-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 bg-red-100 rounded-lg flex items-center justify-center">
              <AlertCircle className="w-6 h-6 text-red-600" />
            </div>
          </div>
          <p className="text-sm text-gray-600 mb-1">Просроченная задолженность</p>
          <p className="text-2xl font-bold text-red-600">
            {partnerData.overdueDebt.toLocaleString('ru-RU')} ₽
          </p>
          <p className="text-xs text-gray-500 mt-2">{partnerData.overdueCount} клиентов</p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
              <TrendingUp className="w-6 h-6 text-green-600" />
            </div>
          </div>
          <p className="text-sm text-gray-600 mb-1">Оплачено</p>
          <p className="text-2xl font-bold text-gray-900">
            {partnerData.paidThisMonth.toLocaleString('ru-RU')} ₽
          </p>
          <p className="text-xs text-gray-500 mt-2">
            {clientDebts.filter((d) => d.status === 'paid').length} клиентов
          </p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
              <Users className="w-6 h-6 text-purple-600" />
            </div>
          </div>
          <p className="text-sm text-gray-600 mb-1">Всего клиентов</p>
          <p className="text-2xl font-bold text-gray-900">
            {partnerData.totalClients}
          </p>
          <p className="text-xs text-gray-500 mt-2">
            {partnerData.activeClients} требуют оплаты
          </p>
        </div>
      </div>

      {/* Client Debts Table */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">
            Судебные расходы по клиентам
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Клиент
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Этап
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Стоимость
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Статус
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Дата банкротства
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Срок оплаты
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Действия
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {isLoading && (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center">
                    <Loader2 className="w-6 h-6 animate-spin text-gray-400 mx-auto mb-2" />
                    <p className="text-sm text-gray-500">Загрузка...</p>
                  </td>
                </tr>
              )}
              {!isLoading && clientDebts.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center">
                    <Users className="w-10 h-10 text-gray-300 mx-auto mb-2" />
                    <p className="text-sm text-gray-500">Нет клиентов</p>
                    <p className="text-xs text-gray-400 mt-1">Клиенты появятся здесь после добавления</p>
                  </td>
                </tr>
              )}
              {clientDebts.map((debt) => {
                const config = getStatusConfig(debt.status);
                return (
                  <tr key={debt.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {debt.clientName}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-gray-600 max-w-xs">
                        {debt.stage}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-semibold text-gray-900">
                        {debt.courtFee.toLocaleString('ru-RU')} ₽
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${config.color}`}
                      >
                        {config.label}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                      {debt.courtProcedureDate
                        ? formatDateShort(debt.courtProcedureDate, tz)
                        : <span className="text-gray-400">—</span>}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                      {debt.status === 'paid'
                        ? `Оплачено ${formatDateShort(debt.paidDate!, tz)}`
                        : debt.courtProcedureDate
                          ? formatDateShort(debt.dueDate!, tz)
                          : <span className="text-gray-400">—</span>}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      {debt.status !== 'paid' && (
                        <button
                          className="text-blue-600 hover:text-blue-700 font-medium"
                          onClick={() => {
                            setSelectedDebt(debt.id);
                            setIsPaymentModalOpen(true);
                          }}
                        >
                          Оплатить
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Payment Info */}
      <div className="bg-blue-50 rounded-xl border border-blue-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Условия оплаты судебных расходов
        </h3>
        <ul className="space-y-2 text-sm text-gray-700">
          <li className="flex items-start gap-2">
            <span className="text-blue-600 mt-1">•</span>
            <span>
              Оплата судебных расходов производится за каждого добавленного клиента
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-blue-600 mt-1">•</span>
            <span>
              Стоимость за клиента: {partnerData.courtFeePerClient.toLocaleString('ru-RU')} ₽
              (установлена при регистрации)
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-blue-600 mt-1">•</span>
            <span>Срок оплаты: {summary?.payment_term_days ?? 10} дней с момента добавления клиента</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-blue-600 mt-1">•</span>
            <span>
              При просрочке оплаты работа с клиентом может быть приостановлена
            </span>
          </li>
        </ul>
      </div>

      {(() => {
        const selectedClient = selectedDebt
          ? clientDebts.find((d) => d.id === selectedDebt)
          : null;
        let amount: number;
        let summaryTitle: string;
        let summarySubtitle: string;
        if (selectedClient) {
          amount = selectedClient.courtFee;
          summaryTitle = `Клиент: ${selectedClient.clientName}`;
          summarySubtitle = `Этап: ${selectedClient.stage}`;
        } else if (payDebtType === 'overdue') {
          amount = partnerData.overdueDebt;
          summaryTitle = 'Оплата просроченной задолженности';
          summarySubtitle = `${partnerData.overdueCount} ${partnerData.overdueCount === 1 ? 'клиент' : partnerData.overdueCount < 5 ? 'клиента' : 'клиентов'}`;
        } else if (payDebtType === 'current') {
          amount = partnerData.currentDebt;
          summaryTitle = 'Оплата текущей задолженности';
          summarySubtitle = `${partnerData.currentCount} ${partnerData.currentCount === 1 ? 'клиент' : partnerData.currentCount < 5 ? 'клиента' : 'клиентов'}`;
        } else {
          amount = partnerData.totalDebt;
          summaryTitle = 'Оплата общей задолженности';
          summarySubtitle = `${unpaidCount} ${unpaidCount === 1 ? 'клиент' : unpaidCount < 5 ? 'клиента' : 'клиентов'}`;
        }
        return (
          <PaymentModal
            isOpen={isPaymentModalOpen}
            onClose={() => setIsPaymentModalOpen(false)}
            amount={amount}
            feeIds={selectedClient ? [selectedClient.id] : null}
            debtType={selectedClient ? 'all' : payDebtType}
            summaryTitle={summaryTitle}
            summarySubtitle={summarySubtitle}
          />
        );
      })()}
    </div>
  );
}