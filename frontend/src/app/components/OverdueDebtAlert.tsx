import { useState } from 'react';
import { AlertTriangle, AlertCircle, CreditCard } from 'lucide-react';
import PaymentModal from './PaymentModal';

interface Props {
  overdueDebt: number;
  currentDebt: number;
  unpaidCount?: number;
}

export default function OverdueDebtAlert({ overdueDebt, currentDebt, unpaidCount }: Props) {
  const [isPaymentOpen, setIsPaymentOpen] = useState(false);
  const isOverdue = overdueDebt > 0;
  const isCurrent = currentDebt > 0;

  if (!isOverdue && !isCurrent) return null;

  const gradient = isOverdue ? 'from-red-600 via-red-500 to-orange-500' : 'from-yellow-500 via-yellow-400 to-orange-400';
  const borderColor = isOverdue ? 'border-red-700' : 'border-yellow-500';
  const iconColor = isOverdue ? 'text-red-600' : 'text-yellow-600';
  const btnTextColor = isOverdue ? 'text-red-600' : 'text-yellow-700';
  const btnHoverBg = isOverdue ? 'hover:bg-red-50' : 'hover:bg-yellow-50';
  const subtextColor = isOverdue ? 'text-red-50' : 'text-yellow-50';
  const infoTextColor = isOverdue ? 'text-red-100' : 'text-yellow-100';
  const message = isOverdue
    ? 'У вас имеется просроченная задолженность перед платформой ЮРИТЕХ за судебные расходы по клиентам'
    : 'У вас имеется задолженность перед платформой ЮРИТЕХ за судебные расходы по клиентам';

  const amount = isOverdue ? overdueDebt : currentDebt;
  const summarySubtitle = unpaidCount
    ? `${unpaidCount} ${unpaidCount === 1 ? 'клиент' : unpaidCount < 5 ? 'клиента' : 'клиентов'}`
    : undefined;

  return (
    <>
      <div className={`relative overflow-hidden bg-gradient-to-r ${gradient} rounded-3xl shadow-2xl border-4 ${borderColor}`}>
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full -mr-32 -mt-32" />
        <div className="absolute bottom-0 left-0 w-48 h-48 bg-white/10 rounded-full -ml-24 -mb-24" />
        <div className="relative p-8">
          <div className="flex items-start justify-between gap-6">
            <div className="flex items-start gap-6 flex-1">
              <div className="w-20 h-20 bg-white rounded-2xl flex items-center justify-center flex-shrink-0 shadow-xl">
                <AlertTriangle className={`w-12 h-12 ${iconColor}`} />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-3">
                  <h2 className="text-2xl font-bold text-white">Важное уведомление</h2>
                  <span className="px-3 py-1 bg-white/20 backdrop-blur-sm text-white text-xs font-bold rounded-full uppercase tracking-wider">
                    Требует действия
                  </span>
                </div>
                <p className={`${subtextColor} text-lg mb-4 leading-relaxed`}>{message}</p>
                <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-5 mb-4">
                  <p className={`${infoTextColor} text-sm mb-1`}>{isOverdue ? 'Просроченная задолженность' : 'Текущая задолженность'}</p>
                  <p className="text-white text-3xl font-bold">{amount.toLocaleString('ru-RU')} ₽</p>
                </div>
                <div className={`flex items-center gap-3 ${subtextColor} text-sm`}>
                  <AlertCircle className="w-4 h-4" />
                  <p>При несвоевременной оплате доступ к функциям платформы может быть ограничен</p>
                </div>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setIsPaymentOpen(true)}
              className={`px-8 py-4 bg-white ${btnTextColor} rounded-2xl font-bold text-lg ${btnHoverBg} transition-all flex items-center gap-3 shadow-2xl hover:scale-105 transform flex-shrink-0`}
            >
              <CreditCard className="w-6 h-6" />
              Оплатить сейчас
            </button>
          </div>
        </div>
      </div>

      <PaymentModal
        isOpen={isPaymentOpen}
        onClose={() => setIsPaymentOpen(false)}
        amount={amount}
        feeIds={null}
        debtType={isOverdue ? 'overdue' : 'current'}
        summaryTitle={isOverdue ? 'Оплата просроченной задолженности' : 'Оплата текущей задолженности'}
        summarySubtitle={summarySubtitle}
      />
    </>
  );
}
