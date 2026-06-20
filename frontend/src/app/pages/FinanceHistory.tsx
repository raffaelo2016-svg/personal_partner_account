import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { TrendingUp, TrendingDown, DollarSign, Filter, Loader2 } from 'lucide-react';
import { fetchTransactions, fetchCourtFeeSummary } from '../api/finance';
import type { TransactionData } from '../api/finance';
import { formatDateTime } from '@/app/utils/formatDate';
import { useTimezone } from '@/app/contexts/TimezoneContext';

function formatMoney(kopecks: number): string {
  const rub = Math.abs(kopecks) / 100;
  return rub.toLocaleString('ru-RU') + ' ₽';
}

function getStatusConfig(status: string) {
  switch (status) {
    case 'completed':
      return { label: 'Завершено', color: 'bg-green-100 text-green-700' };
    case 'pending':
      return { label: 'Ожидает', color: 'bg-yellow-100 text-yellow-700' };
    case 'failed':
      return { label: 'Ошибка', color: 'bg-red-100 text-red-700' };
    default:
      return { label: status, color: 'bg-gray-100 text-gray-700' };
  }
}

export default function FinanceHistory() {
  const tz = useTimezone();
  const [page, setPage] = useState(1);

  const { data: txData, isLoading } = useQuery({
    queryKey: ['transactions', page],
    queryFn: () => fetchTransactions({ page }),
  });

  const { data: summary } = useQuery({
    queryKey: ['courtFeeSummary'],
    queryFn: fetchCourtFeeSummary,
  });

  const transactions = txData?.items ?? [];
  const totalPages = txData?.pages ?? 1;

  const totalPaid = summary?.paid_this_month ?? 0;
  const totalDebt = summary?.total_debt ?? 0;

  return (
    <div className="p-8 space-y-8">
      <div>
        <h1 className="text-3xl font-semibold text-gray-900 mb-2">История операций</h1>
        <p className="text-gray-600">Полная история всех начислений и платежей ЮРИТЕХ</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <p className="text-sm text-gray-600 mb-2">Оплачено в этом месяце</p>
          <p className="text-2xl font-bold text-gray-900 mb-1">{formatMoney(totalPaid)}</p>
          <div className="flex items-center gap-1 text-sm text-green-600">
            <TrendingUp className="w-4 h-4" />
            <span>Оплачено</span>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <p className="text-sm text-gray-600 mb-2">Текущая задолженность</p>
          <p className={`text-2xl font-bold mb-1 ${totalDebt > 0 ? 'text-red-600' : 'text-green-600'}`}>
            {formatMoney(totalDebt)}
          </p>
          <div className="flex items-center gap-1 text-sm text-gray-600">
            <TrendingDown className="w-4 h-4" />
            <span>{totalDebt > 0 ? 'Требуется оплата' : 'Нет задолженности'}</span>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <p className="text-sm text-gray-600 mb-2">Всего операций</p>
          <p className="text-2xl font-bold text-gray-900 mb-1">{txData?.total ?? 0}</p>
          <div className="flex items-center gap-1 text-sm text-gray-600">
            <Filter className="w-4 h-4" />
            <span>За всё время</span>
          </div>
        </div>
      </div>

      {/* Transactions List */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">
            Все операции ({txData?.total ?? 0})
          </h2>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
          </div>
        ) : transactions.length === 0 ? (
          <div className="text-center py-16 text-gray-500">
            <DollarSign className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p className="text-lg font-medium">Операций пока нет</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {transactions.map((tx: TransactionData) => {
              const statusConfig = getStatusConfig(tx.status);
              const isPayment = tx.status === 'completed';
              return (
                <div key={tx.id} className="p-6 hover:bg-gray-50 transition-colors">
                  <div className="flex items-start gap-4">
                    <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${isPayment ? 'bg-green-50' : 'bg-yellow-50'}`}>
                      {isPayment ? (
                        <TrendingUp className="w-6 h-6 text-green-600" />
                      ) : (
                        <DollarSign className="w-6 h-6 text-yellow-600" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className="text-base font-medium text-gray-900">
                              {tx.payment_method ? `Оплата (${tx.payment_method})` : 'Платёж'}
                            </h3>
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${statusConfig.color}`}>
                              {statusConfig.label}
                            </span>
                          </div>
                          <p className="text-sm text-gray-600">
                            {formatDateTime(tx.created_at, tz)}
                            {tx.external_id && <span> • {tx.external_id}</span>}
                          </p>
                        </div>
                        <div className="text-right ml-4">
                          <p className="text-lg font-bold text-gray-900">{formatMoney(tx.amount)}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="p-4 border-t border-gray-200 flex items-center justify-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1 rounded-lg border text-sm disabled:opacity-50 hover:bg-gray-50"
            >
              Назад
            </button>
            <span className="text-sm text-gray-600">
              {page} из {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="px-3 py-1 rounded-lg border text-sm disabled:opacity-50 hover:bg-gray-50"
            >
              Далее
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
