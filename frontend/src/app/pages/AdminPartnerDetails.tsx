import {
  ArrowLeft, Mail, Phone, Calendar, Users, Briefcase,
  Building, Edit, Ban, CheckCircle, AlertCircle, Loader2, ShieldCheck, X, Trash2,
} from 'lucide-react';
import { useState } from 'react';
import { Link, useParams, useNavigate } from 'react-router';
import { usePartner, useUpdatePartner, useDeletePartner } from '@/app/hooks/usePartners';
import { formatDate } from '@/app/utils/formatDate';
import { useTimezone } from '@/app/contexts/TimezoneContext';
import { toast } from 'sonner';
import type { Partner, PartnerUpdate } from '@/app/types';

const STATUS_LABELS: Record<string, string> = {
  active: 'Активный',
  pending: 'На проверке',
  blocked: 'Заблокирован',
};

const STATUS_STYLES: Record<string, string> = {
  active: 'bg-green-100 text-green-700',
  pending: 'bg-yellow-100 text-yellow-700',
  blocked: 'bg-red-100 text-red-700',
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  active: <CheckCircle className="w-5 h-5" />,
  pending: <AlertCircle className="w-5 h-5" />,
  blocked: <Ban className="w-5 h-5" />,
};

const PARTNER_TYPE_LABELS: Record<string, string> = {
  individual: 'Физическое лицо',
  legal: 'Юридическое лицо',
  entrepreneur: 'Индивидуальный предприниматель',
};

function parseFio(full: string) {
  const parts = full.trim().split(/\s+/);
  return { lastName: parts[0] ?? '', firstName: parts[1] ?? '', middleName: parts.slice(2).join(' ') };
}

function EditPartnerModal({
  partner,
  onClose,
  onDelete,
  isDeleting,
}: {
  partner: Partner;
  onClose: () => void;
  onDelete: () => void;
  isDeleting: boolean;
}) {
  const updatePartner = useUpdatePartner();
  const type = partner.partner_type;
  const fio = parseFio(partner.director_name);

  const [lastName, setLastName] = useState(fio.lastName);
  const [firstName, setFirstName] = useState(fio.firstName);
  const [middleName, setMiddleName] = useState(fio.middleName);

  const [companyName, setCompanyName] = useState(partner.company_name);
  const [fullLegalName, setFullLegalName] = useState(partner.full_legal_name ?? '');
  const [shortName, setShortName] = useState(partner.short_name ?? '');
  const [phone, setPhone] = useState(partner.phone);
  const [inn, setInn] = useState(partner.inn);
  const [kpp, setKpp] = useState(partner.kpp ?? '');
  const [legalAddress, setLegalAddress] = useState(partner.legal_address ?? '');
  const [postalAddress, setPostalAddress] = useState(partner.postal_address ?? '');
  const [courtFee, setCourtFee] = useState(String(partner.court_fee_per_client / 100));
  const [paymentDays, setPaymentDays] = useState(String(partner.payment_term_days));

  const handleSave = () => {
    const directorName =
      type === 'legal'
        ? companyName
        : `${lastName} ${firstName} ${middleName}`.trim();

    const payload: PartnerUpdate = {
      company_name: type === 'legal' ? (shortName || fullLegalName || companyName) : directorName,
      director_name: directorName,
      phone,
      inn,
      kpp: type === 'legal' ? kpp || undefined : undefined,
      short_name: shortName || undefined,
      full_legal_name: fullLegalName || undefined,
      legal_address: legalAddress || undefined,
      postal_address: postalAddress || undefined,
      court_fee_per_client: Math.round(Number(courtFee) * 100),
      payment_term_days: Number(paymentDays),
    };

    updatePartner.mutate(
      { id: partner.id, data: payload },
      {
        onSuccess: () => {
          toast.success('Данные партнёра обновлены');
          onClose();
        },
        onError: () => toast.error('Не удалось сохранить изменения'),
      },
    );
  };

  const inputCls =
    'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm';
  const labelCls = 'block text-sm font-medium text-gray-700 mb-1';

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b border-gray-200 sticky top-0 bg-white rounded-t-xl z-10">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Редактирование партнёра</h3>
            <p className="text-sm text-gray-500 mt-0.5">
              {PARTNER_TYPE_LABELS[type] || type}
            </p>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded-lg">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {/* --- Физическое лицо --- */}
          {type === 'individual' && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className={labelCls}>Фамилия</label>
                  <input className={inputCls} value={lastName} onChange={(e) => setLastName(e.target.value)} />
                </div>
                <div>
                  <label className={labelCls}>Имя</label>
                  <input className={inputCls} value={firstName} onChange={(e) => setFirstName(e.target.value)} />
                </div>
                <div>
                  <label className={labelCls}>Отчество</label>
                  <input className={inputCls} value={middleName} onChange={(e) => setMiddleName(e.target.value)} />
                </div>
              </div>
              <div>
                <label className={labelCls}>Телефон</label>
                <input className={inputCls} value={phone} onChange={(e) => setPhone(e.target.value)} />
              </div>
            </>
          )}

          {/* --- Юридическое лицо --- */}
          {type === 'legal' && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className={labelCls}>Полное наименование</label>
                  <input className={inputCls} value={fullLegalName} onChange={(e) => setFullLegalName(e.target.value)} />
                </div>
                <div>
                  <label className={labelCls}>Сокращённое наименование</label>
                  <input className={inputCls} value={shortName} onChange={(e) => setShortName(e.target.value)} />
                </div>
              </div>
              <div>
                <label className={labelCls}>Телефон</label>
                <input className={inputCls} value={phone} onChange={(e) => setPhone(e.target.value)} />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className={labelCls}>ИНН</label>
                  <input className={inputCls} value={inn} maxLength={10} onChange={(e) => setInn(e.target.value)} />
                  <p className="text-xs text-gray-500 mt-1">10 цифр</p>
                </div>
                <div>
                  <label className={labelCls}>КПП</label>
                  <input className={inputCls} value={kpp} maxLength={9} onChange={(e) => setKpp(e.target.value)} />
                  <p className="text-xs text-gray-500 mt-1">9 цифр</p>
                </div>
              </div>
              <div>
                <label className={labelCls}>Юридический адрес</label>
                <input className={inputCls} value={legalAddress} onChange={(e) => setLegalAddress(e.target.value)} />
              </div>
              <div>
                <label className={labelCls}>Почтовый адрес</label>
                <input className={inputCls} value={postalAddress} onChange={(e) => setPostalAddress(e.target.value)} />
              </div>
            </>
          )}

          {/* --- ИП --- */}
          {type === 'entrepreneur' && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className={labelCls}>Фамилия</label>
                  <input className={inputCls} value={lastName} onChange={(e) => setLastName(e.target.value)} />
                </div>
                <div>
                  <label className={labelCls}>Имя</label>
                  <input className={inputCls} value={firstName} onChange={(e) => setFirstName(e.target.value)} />
                </div>
                <div>
                  <label className={labelCls}>Отчество</label>
                  <input className={inputCls} value={middleName} onChange={(e) => setMiddleName(e.target.value)} />
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className={labelCls}>Телефон</label>
                  <input className={inputCls} value={phone} onChange={(e) => setPhone(e.target.value)} />
                </div>
                <div>
                  <label className={labelCls}>ИНН</label>
                  <input className={inputCls} value={inn} maxLength={12} onChange={(e) => setInn(e.target.value)} />
                  <p className="text-xs text-gray-500 mt-1">12 цифр</p>
                </div>
              </div>
            </>
          )}

          {/* --- Общие поля: финансы --- */}
          <div className="border-t border-gray-200 pt-5">
            <h4 className="text-sm font-semibold text-gray-900 mb-3">Условия сотрудничества</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className={labelCls}>Стоимость клиента (₽)</label>
                <input type="number" min="1" className={inputCls} value={courtFee} onChange={(e) => setCourtFee(e.target.value)} />
              </div>
              <div>
                <label className={labelCls}>Срок оплаты (дней)</label>
                <input type="number" min="1" className={inputCls} value={paymentDays} onChange={(e) => setPaymentDays(e.target.value)} />
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between p-6 border-t border-gray-200 sticky bottom-0 bg-white rounded-b-xl">
          <button
            onClick={onDelete}
            disabled={isDeleting}
            className="flex items-center gap-2 px-4 py-2 text-sm text-red-600 border border-red-300 rounded-lg hover:bg-red-50 transition-colors disabled:opacity-50"
          >
            <Trash2 className="w-4 h-4" />
            {isDeleting ? 'Удаление...' : 'Удалить партнера'}
          </button>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Отмена
            </button>
            <button
              onClick={handleSave}
              disabled={updatePartner.isPending}
              className="px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {updatePartner.isPending ? 'Сохранение...' : 'Сохранить'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AdminPartnerDetails() {
  const tz = useTimezone();
  const { id } = useParams();
  const navigate = useNavigate();
  const { data: partner, isLoading } = usePartner(id);
  const updatePartner = useUpdatePartner();
  const deletePartnerMutation = useDeletePartner();
  const [showConfirm, setShowConfirm] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showEdit, setShowEdit] = useState(false);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
      </div>
    );
  }

  if (!partner) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-500">
        <p className="text-lg">Партнёр не найден</p>
        <Link to="/admin/partners" className="mt-4 text-blue-600 hover:underline">
          Вернуться к списку
        </Link>
      </div>
    );
  }

  const statusStyle = STATUS_STYLES[partner.status] || 'bg-gray-100 text-gray-700';
  const statusLabel = STATUS_LABELS[partner.status] || partner.status;
  const statusIcon = STATUS_ICONS[partner.status] ?? null;

  return (
    <div className="space-y-6">
      {/* Шапка */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            to="/admin/partners"
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-gray-600" />
          </Link>
          <div>
            <h1 className="text-3xl font-semibold text-gray-900">{partner.company_name}</h1>
            <p className="text-gray-600 mt-1">Детальная информация о партнере</p>
          </div>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => setShowEdit(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Edit className="w-4 h-4" />
            Редактировать
          </button>
        </div>
      </div>

      {/* Статистика */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Всего клиентов</p>
              <p className="text-2xl font-semibold text-gray-900 mt-1">{partner.clients_count ?? 0}</p>
            </div>
            <div className="p-3 bg-blue-50 rounded-lg">
              <Users className="w-6 h-6 text-blue-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Активные дела</p>
              <p className="text-2xl font-semibold text-gray-900 mt-1">{partner.active_cases_count ?? 0}</p>
            </div>
            <div className="p-3 bg-green-50 rounded-lg">
              <Briefcase className="w-6 h-6 text-green-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Тип партнёра</p>
              <p className="text-lg font-semibold text-gray-900 mt-1">
                {PARTNER_TYPE_LABELS[partner.partner_type] || partner.partner_type}
              </p>
            </div>
            <div className="p-3 bg-purple-50 rounded-lg">
              <Building className="w-6 h-6 text-purple-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Статус</p>
              <p className="text-lg font-semibold text-gray-900 mt-1">{statusLabel}</p>
            </div>
            <div className={`p-3 rounded-lg ${statusStyle}`}>
              {statusIcon}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Основная информация */}
        <div className="lg:col-span-2 space-y-6">
          {/* Контактная информация */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Контактная информация</h2>
            <div className="space-y-4">
              {partner.email && (
                <div className="flex items-start gap-3">
                  <Mail className="w-5 h-5 text-gray-400 mt-0.5" />
                  <div>
                    <p className="text-sm text-gray-600">Email</p>
                    <a href={`mailto:${partner.email}`} className="text-blue-600 hover:underline">
                      {partner.email}
                    </a>
                  </div>
                </div>
              )}
              <div className="flex items-start gap-3">
                <Phone className="w-5 h-5 text-gray-400 mt-0.5" />
                <div>
                  <p className="text-sm text-gray-600">Телефон</p>
                  <a href={`tel:${partner.phone}`} className="text-blue-600 hover:underline">
                    {partner.phone}
                  </a>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <Calendar className="w-5 h-5 text-gray-400 mt-0.5" />
                <div>
                  <p className="text-sm text-gray-600">Дата регистрации</p>
                  <p className="text-gray-900">{formatDate(partner.created_at, tz)}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Реквизиты */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Реквизиты компании</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-600 mb-1">ИНН</p>
                <p className="text-gray-900 font-mono">{partner.inn || '—'}</p>
              </div>
              {partner.kpp && (
                <div>
                  <p className="text-sm text-gray-600 mb-1">КПП</p>
                  <p className="text-gray-900 font-mono">{partner.kpp}</p>
                </div>
              )}
              {partner.full_legal_name && (
                <div className="md:col-span-2">
                  <p className="text-sm text-gray-600 mb-1">Полное наименование</p>
                  <p className="text-gray-900">{partner.full_legal_name}</p>
                </div>
              )}
              {partner.short_name && (
                <div className="md:col-span-2">
                  <p className="text-sm text-gray-600 mb-1">Краткое наименование</p>
                  <p className="text-gray-900">{partner.short_name}</p>
                </div>
              )}
              {partner.legal_address && (
                <div className="md:col-span-2">
                  <p className="text-sm text-gray-600 mb-1">Юридический адрес</p>
                  <p className="text-gray-900">{partner.legal_address}</p>
                </div>
              )}
              {partner.postal_address && (
                <div className="md:col-span-2">
                  <p className="text-sm text-gray-600 mb-1">Почтовый адрес</p>
                  <p className="text-gray-900">{partner.postal_address}</p>
                </div>
              )}
            </div>
          </div>

          {/* Руководитель */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Руководитель</h2>
            <p className="text-gray-900 font-medium">{partner.director_name}</p>
          </div>

          {/* Условия сотрудничества */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Условия сотрудничества</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-600 mb-1">Стоимость клиента</p>
                <p className="text-gray-900 font-medium">
                  {(partner.court_fee_per_client / 100).toLocaleString('ru-RU')} ₽
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600 mb-1">Срок оплаты</p>
                <p className="text-gray-900 font-medium">{partner.payment_term_days} дней</p>
              </div>
            </div>
          </div>
        </div>

        {/* Правая колонка */}
        <div className="space-y-6">
          {/* Действия */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Действия</h2>
            <div className="space-y-2">
              <Link
                to={`/admin/clients?partner=${partner.id}`}
                className="w-full flex items-center gap-3 px-4 py-3 text-left border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <Users className="w-5 h-5 text-gray-600" />
                <span className="text-sm text-gray-900">Клиенты партнёра</span>
              </Link>
              {partner.status === 'blocked' ? (
                <button
                  onClick={() => setShowConfirm(true)}
                  className="w-full flex items-center gap-3 px-4 py-3 text-left border border-green-200 rounded-lg hover:bg-green-50 transition-colors text-green-600"
                >
                  <ShieldCheck className="w-5 h-5" />
                  <span className="text-sm">Разблокировать партнера</span>
                </button>
              ) : (
                <button
                  onClick={() => setShowConfirm(true)}
                  className="w-full flex items-center gap-3 px-4 py-3 text-left border border-red-200 rounded-lg hover:bg-red-50 transition-colors text-red-600"
                >
                  <Ban className="w-5 h-5" />
                  <span className="text-sm">Заблокировать партнера</span>
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className={`p-2 rounded-lg ${partner.status === 'blocked' ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600'}`}>
                {partner.status === 'blocked' ? <ShieldCheck className="w-6 h-6" /> : <Ban className="w-6 h-6" />}
              </div>
              <h3 className="text-lg font-semibold text-gray-900">
                {partner.status === 'blocked' ? 'Разблокировать партнера?' : 'Заблокировать партнера?'}
              </h3>
            </div>
            <p className="text-sm text-gray-600 mb-6">
              {partner.status === 'blocked'
                ? `Партнёр «${partner.company_name}» сможет снова входить в систему и работать с клиентами.`
                : `Партнёр «${partner.company_name}» потеряет доступ к системе. Это действие можно отменить.`
              }
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowConfirm(false)}
                className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Отмена
              </button>
              <button
                disabled={updatePartner.isPending}
                onClick={() => {
                  const newStatus = partner.status === 'blocked' ? 'active' : 'blocked';
                  updatePartner.mutate(
                    { id: partner.id, data: { status: newStatus } },
                    {
                      onSuccess: () => {
                        toast.success(
                          newStatus === 'blocked'
                            ? `Партнёр «${partner.company_name}» заблокирован`
                            : `Партнёр «${partner.company_name}» разблокирован`,
                        );
                        setShowConfirm(false);
                      },
                      onError: () => {
                        toast.error('Не удалось изменить статус партнёра');
                      },
                    },
                  );
                }}
                className={`px-4 py-2 text-sm text-white rounded-lg transition-colors disabled:opacity-50 ${
                  partner.status === 'blocked'
                    ? 'bg-green-600 hover:bg-green-700'
                    : 'bg-red-600 hover:bg-red-700'
                }`}
              >
                {updatePartner.isPending
                  ? 'Сохранение...'
                  : partner.status === 'blocked'
                    ? 'Разблокировать'
                    : 'Заблокировать'
                }
              </button>
            </div>
          </div>
        </div>
      )}

      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60] p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-lg bg-red-100 text-red-600">
                <Trash2 className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">Удалить партнера?</h3>
            </div>
            <p className="text-sm text-gray-600 mb-6">
              Партнёр «{partner.company_name}» и все его данные (клиенты, задачи, чаты, финансы) будут удалены безвозвратно.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Отмена
              </button>
              <button
                disabled={deletePartnerMutation.isPending}
                onClick={() => {
                  deletePartnerMutation.mutate(partner.id, {
                    onSuccess: () => {
                      toast.success(`Партнёр «${partner.company_name}» удалён`);
                      navigate('/admin/partners');
                    },
                    onError: () => toast.error('Не удалось удалить партнёра'),
                  });
                }}
                className="px-4 py-2 text-sm text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {deletePartnerMutation.isPending ? 'Удаление...' : 'Удалить'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showEdit && (
        <EditPartnerModal
          partner={partner}
          onClose={() => setShowEdit(false)}
          onDelete={() => setShowDeleteConfirm(true)}
          isDeleting={deletePartnerMutation.isPending}
        />
      )}
    </div>
  );
}
