import { useState } from 'react';
import { CreditCard, Smartphone, Building2, Wallet, X, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { createYookassaPayment, type DebtType } from '../api/finance';

interface PaymentModalProps {
  isOpen: boolean;
  onClose: () => void;
  amount: number;
  /** Список court_fee.id для оплаты. null = по debtType. */
  feeIds?: string[] | null;
  /** Тип задолженности: 'overdue', 'current' или 'all'. Игнорируется если feeIds задан. */
  debtType?: DebtType;
  title?: string;
  subtitle?: string;
  summaryTitle?: string;
  summarySubtitle?: string;
}

export default function PaymentModal({
  isOpen,
  onClose,
  amount,
  feeIds = null,
  debtType = 'all',
  title = 'Выберите способ оплаты',
  subtitle = 'Оплата судебных расходов',
  summaryTitle = 'Оплата общей задолженности',
  summarySubtitle,
}: PaymentModalProps) {
  const [isCreating, setIsCreating] = useState(false);

  if (!isOpen) return null;

  const handleYoomoney = async () => {
    if (isCreating) return;
    setIsCreating(true);
    try {
      const res = await createYookassaPayment(feeIds, debtType);
      if (!res.confirmation_url) {
        toast.error('Платёжный сервис не вернул ссылку для оплаты');
        setIsCreating(false);
        return;
      }
      // Редирект на страницу ЮKassa, после оплаты пользователь вернётся по YOOKASSA_RETURN_URL.
      window.location.href = res.confirmation_url;
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Не удалось создать платёж');
      setIsCreating(false);
    }
  };

  const disabledTooltip = 'Скоро будет доступно';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}
      onClick={isCreating ? undefined : onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div>
            <h3 className="text-2xl font-semibold text-gray-900">{title}</h3>
            <p className="text-sm text-gray-600 mt-1">{subtitle}</p>
          </div>
          <button
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
            onClick={onClose}
            disabled={isCreating}
            aria-label="Закрыть"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium text-gray-900 mb-1">{summaryTitle}</p>
                {summarySubtitle ? (
                  <p className="text-sm text-gray-600">{summarySubtitle}</p>
                ) : null}
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-600">Сумма к оплате:</p>
                <p className="text-2xl font-bold text-blue-600">
                  {amount.toLocaleString('ru-RU')} ₽
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <button
              type="button"
              disabled
              title={disabledTooltip}
              className="flex items-start gap-4 p-5 border-2 border-gray-200 rounded-xl opacity-50 cursor-not-allowed"
            >
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
                <CreditCard className="w-6 h-6 text-blue-600" />
              </div>
              <div className="flex-1 text-left">
                <h4 className="font-semibold text-gray-900 mb-1">Банковская карта</h4>
                <p className="text-sm text-gray-600">Visa, MasterCard, Мир</p>
              </div>
            </button>

            <button
              type="button"
              disabled
              title={disabledTooltip}
              className="flex items-start gap-4 p-5 border-2 border-gray-200 rounded-xl opacity-50 cursor-not-allowed"
            >
              <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center flex-shrink-0">
                <Smartphone className="w-6 h-6 text-green-600" />
              </div>
              <div className="flex-1 text-left">
                <h4 className="font-semibold text-gray-900 mb-1">СБП</h4>
                <p className="text-sm text-gray-600">Система быстрых платежей</p>
              </div>
            </button>

            <button
              type="button"
              disabled
              title={disabledTooltip}
              className="flex items-start gap-4 p-5 border-2 border-gray-200 rounded-xl opacity-50 cursor-not-allowed"
            >
              <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center flex-shrink-0">
                <Building2 className="w-6 h-6 text-purple-600" />
              </div>
              <div className="flex-1 text-left">
                <h4 className="font-semibold text-gray-900 mb-1">Банковский перевод</h4>
                <p className="text-sm text-gray-600">По реквизитам компании</p>
              </div>
            </button>

            <button
              type="button"
              onClick={handleYoomoney}
              disabled={isCreating}
              className="flex items-start gap-4 p-5 border-2 border-gray-200 rounded-xl hover:border-yellow-500 hover:bg-yellow-50 transition-all group disabled:opacity-60 disabled:cursor-not-allowed"
            >
              <div className="w-12 h-12 bg-yellow-100 rounded-lg flex items-center justify-center flex-shrink-0 group-hover:bg-yellow-600 transition-colors">
                {isCreating ? (
                  <Loader2 className="w-6 h-6 text-yellow-600 group-hover:text-white animate-spin" />
                ) : (
                  <Wallet className="w-6 h-6 text-yellow-600 group-hover:text-white" />
                )}
              </div>
              <div className="flex-1 text-left">
                <h4 className="font-semibold text-gray-900 mb-1">ЮMoney</h4>
                <p className="text-sm text-gray-600">
                  {isCreating ? 'Создание платежа…' : 'Электронный кошелек'}
                </p>
              </div>
            </button>
          </div>

          <div className="bg-gray-50 rounded-xl p-4">
            <p className="text-sm text-gray-600">
              💡 После успешной оплаты статус автоматически обновится, и вы получите подтверждение на email.
            </p>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200 bg-gray-50">
          <button
            className="px-6 py-2.5 border border-gray-300 text-gray-700 rounded-lg hover:bg-white transition-colors font-medium disabled:opacity-50"
            onClick={onClose}
            disabled={isCreating}
          >
            Отменить
          </button>
        </div>
      </div>
    </div>
  );
}
