import { useEffect, useState } from 'react';
import { CheckCircle2, Loader2 } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getAgentMe, saveRequisites } from '@/app/api/agent';
import { getApiErrorMessage } from '@/app/utils/apiError';

const STATUS: Record<string, { label: string; className: string }> = {
  empty: { label: 'Не заполнены', className: 'bg-gray-100 text-gray-600 border-gray-200' },
  sent: { label: 'На проверке', className: 'bg-amber-50 text-amber-700 border-amber-200' },
  accepted: { label: 'Подтверждены', className: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  needs_fix: { label: 'Нужны правки', className: 'bg-red-50 text-red-700 border-red-200' },
};

const FIELDS: Record<string, { key: string; label: string; placeholder?: string }[]> = {
  individual: [
    { key: 'fio', label: 'ФИО получателя' },
    { key: 'inn', label: 'ИНН', placeholder: '12 цифр' },
    { key: 'bank_name', label: 'Банк' },
    { key: 'bik', label: 'БИК', placeholder: '9 цифр' },
    { key: 'account', label: 'Счёт получателя', placeholder: '20 цифр' },
  ],
  ip: [
    { key: 'fio', label: 'ФИО ИП' },
    { key: 'inn', label: 'ИНН ИП', placeholder: '12 цифр' },
    { key: 'bank_name', label: 'Банк' },
    { key: 'bik', label: 'БИК', placeholder: '9 цифр' },
    { key: 'account', label: 'Расчётный счёт', placeholder: '20 цифр' },
  ],
  company: [
    { key: 'legal_name', label: 'Название организации' },
    { key: 'inn', label: 'ИНН', placeholder: '10 цифр' },
    { key: 'kpp', label: 'КПП', placeholder: '9 цифр' },
    { key: 'bank_name', label: 'Банк' },
    { key: 'bik', label: 'БИК', placeholder: '9 цифр' },
    { key: 'account', label: 'Расчётный счёт', placeholder: '20 цифр' },
  ],
};

export default function AgentRequisites() {
  const queryClient = useQueryClient();
  const { data: me } = useQuery({ queryKey: ['agent', 'me'], queryFn: getAgentMe });
  const [recipientType, setRecipientType] = useState('individual');
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (me) {
      setRecipientType(me.profile.requisites_recipient_type || 'individual');
    }
  }, [me]);

  const mutation = useMutation({
    mutationFn: () =>
      saveRequisites({
        recipient_type: recipientType,
        data: Object.fromEntries(
          FIELDS[recipientType].map((field) => [field.key, (values[field.key] ?? '').trim()]),
        ),
      }),
    onSuccess: async () => {
      setError(null);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      await queryClient.invalidateQueries({ queryKey: ['agent'] });
    },
    onError: (err) => setError(getApiErrorMessage(err)),
  });

  const status = STATUS[me?.profile.requisites_status ?? 'empty'] ?? STATUS.empty;

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Реквизиты</h1>
        <p className="text-sm text-gray-500 mt-1">
          Нужны для выплат. После изменения реквизиты снова проверяет администратор.
        </p>
      </div>

      <div className="flex items-center gap-3">
        <span className={`inline-flex px-2.5 py-1 rounded-full border text-xs ${status.className}`}>
          {status.label}
        </span>
        {me?.profile.requisites_status === 'needs_fix' && (
          <span className="text-xs text-red-600">Проверьте данные и отправьте заново</span>
        )}
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{error}</div>
      )}
      {saved && (
        <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-sm text-emerald-700 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          Реквизиты отправлены на проверку
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate();
        }}
        className="bg-white border border-gray-200 rounded-xl p-5 space-y-4"
      >
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Кто получатель</label>
          <div className="flex flex-wrap gap-2">
            {[
              ['individual', 'Физлицо'],
              ['ip', 'ИП'],
              ['company', 'Организация'],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setRecipientType(value)}
                className={`px-3 py-2 rounded-lg border text-sm ${
                  recipientType === value
                    ? 'border-emerald-500 bg-emerald-50 text-emerald-700'
                    : 'border-gray-200 text-gray-600'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {FIELDS[recipientType].map((field) => (
          <div key={field.key}>
            <label className="block text-sm font-medium text-gray-700 mb-1">{field.label}</label>
            <input
              value={values[field.key] ?? ''}
              onChange={(e) => setValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
              placeholder={field.placeholder}
              required
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
        ))}

        <div className="pt-2">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 disabled:opacity-50"
          >
            {mutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
            Сохранить и отправить на проверку
          </button>
        </div>
      </form>
    </div>
  );
}
