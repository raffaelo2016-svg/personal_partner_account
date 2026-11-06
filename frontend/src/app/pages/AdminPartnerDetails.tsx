import {
  ArrowLeft, Mail, Phone, Calendar, Users, Briefcase,
  Building, Edit, Ban, CheckCircle, AlertCircle, Loader2, ShieldCheck, X, Trash2, RefreshCw, Link2,
  WalletCards, CircleDollarSign, Clock3, Gift, CalendarClock, Search, ChevronLeft, ChevronRight,
} from 'lucide-react';
import { useDeferredValue, useEffect, useState } from 'react';
import { Link, useParams, useNavigate } from 'react-router';
import {
  useBindPartnerBitrixCollab,
  useDeletePartner,
  usePartner,
  useRetryPartnerBitrixSync,
  useUpdatePartner,
} from '@/app/hooks/usePartners';
import { useAdminClients } from '@/app/hooks/useClients';
import { getStatusBadgeClass, getStatusLabel } from '@/app/data/clientStatuses';
import { formatDate, formatDateShort } from '@/app/utils/formatDate';
import { useTimezone } from '@/app/contexts/TimezoneContext';
import { toast } from 'sonner';
import type { Partner, PartnerUpdate } from '@/app/types';
import CaseArbitrLink from '../components/CaseArbitrLink';
import CustomSelect from '../components/ui/CustomSelect';
import { REGION_GROUPS } from '../data/arbitrageCourts';
import { formatTimeInTimezone, getTimezoneMeta } from '../data/timezones';

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

const BITRIX_SYNC_LABELS: Record<string, string> = {
  not_scheduled: 'Не запланировано',
  pending: 'Ожидает отправки',
  processing: 'Отправляется',
  synced: 'Синхронизировано',
  failed: 'Ошибка',
  conflict: 'Изменено в Битрикс24',
};

const REGION_SELECT_GROUPS = REGION_GROUPS.map((group) => ({
  label: group.district,
  options: group.regions.map((region) => ({ value: region.name, label: region.name })),
}));

function PartnerRegionClock({
  region,
  timezone,
  onEdit,
}: {
  region?: string | null;
  timezone?: string | null;
  onEdit: () => void;
}) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  if (!region) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-dashed border-gray-300 bg-white px-4 py-2.5">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gray-100">
          <Clock3 className="h-4 w-4 text-gray-500" aria-hidden="true" />
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-500">
            Время партнёра
          </p>
          <button onClick={onEdit} className="text-sm font-medium text-blue-600 hover:underline">
            Указать регион
          </button>
        </div>
      </div>
    );
  }

  const meta = getTimezoneMeta(timezone);
  return (
    <div className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white px-4 py-2.5 shadow-sm">
      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-50">
        <Clock3 className="h-4 w-4 text-blue-600" aria-hidden="true" />
      </div>
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-500">
          Сейчас у партнёра
        </p>
        <div className="flex items-baseline gap-2">
          <span
            className="text-2xl font-bold tabular-nums leading-none"
            style={{
              backgroundImage: 'linear-gradient(180deg, #1e293b 0%, #475569 48%, #0f172a 100%)',
              WebkitBackgroundClip: 'text',
              backgroundClip: 'text',
              color: 'transparent',
              filter: 'drop-shadow(0 1px 1px rgba(15, 23, 42, 0.18))',
            }}
          >
            {formatTimeInTimezone(timezone, now)}
          </span>
          <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] font-semibold text-gray-600">
            {meta.short}
          </span>
          <span className="text-[11px] text-gray-400">{meta.offset}</span>
        </div>
        <p className="mt-0.5 text-xs text-gray-500">{region}</p>
      </div>
      <button
        onClick={onEdit}
        className="ml-1 rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
        aria-label="Изменить регион"
      >
        <Edit className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </div>
  );
}

function parseFio(full: string) {
  const parts = full.trim().split(/\s+/);
  return { lastName: parts[0] ?? '', firstName: parts[1] ?? '', middleName: parts.slice(2).join(' ') };
}

function formatDateOnly(value?: string | null) {
  if (!value) return '—';
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' }).format(
    new Date(`${value}T00:00:00`),
  );
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
  const [promotionEnabled, setPromotionEnabled] = useState(partner.free_client_limit > 0);
  const [freeClientLimit, setFreeClientLimit] = useState(String(partner.free_client_limit || 10));
  const [promotionStartDate, setPromotionStartDate] = useState(partner.promotion_start_date ?? '');

  const handleSave = () => {
    if (!courtFee || Number(courtFee) <= 0 || !paymentDays || Number(paymentDays) <= 0) {
      toast.error('Проверьте стоимость клиента и срок оплаты');
      return;
    }
    if (promotionEnabled && (!freeClientLimit || Number(freeClientLimit) <= 0)) {
      toast.error('Укажите количество бесплатных клиентов');
      return;
    }

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
      free_client_limit: promotionEnabled ? Number(freeClientLimit) : 0,
      promotion_start_date: promotionEnabled ? promotionStartDate || null : null,
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
                <div className="flex flex-wrap gap-2 mb-2">
                  {[10_000, 15_000, 17_000].map((price) => (
                    <button
                      key={price}
                      type="button"
                      onClick={() => setCourtFee(String(price))}
                      className={`px-3 py-1.5 rounded-lg border text-xs font-medium ${
                        Number(courtFee) === price
                          ? 'border-blue-600 bg-blue-600 text-white'
                          : 'border-gray-300 bg-white text-gray-700'
                      }`}
                    >
                      {price.toLocaleString('ru-RU')} ₽
                    </button>
                  ))}
                </div>
                <input type="number" min="1" className={inputCls} value={courtFee} onChange={(e) => setCourtFee(e.target.value)} />
              </div>
              <div>
                <label className={labelCls}>Срок оплаты (дней)</label>
                <input type="number" min="1" className={inputCls} value={paymentDays} onChange={(e) => setPaymentDays(e.target.value)} />
              </div>
            </div>

            <div className="mt-4 rounded-xl border border-gray-200 p-4">
              <div className="flex items-center gap-2 mb-3">
                <Gift className="w-5 h-5 text-emerald-600" />
                <h5 className="text-sm font-semibold text-gray-900">Льготный месяц</h5>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
                <button
                  type="button"
                  onClick={() => setPromotionEnabled(false)}
                  className={`p-3 rounded-lg border text-left text-sm ${
                    !promotionEnabled ? 'border-blue-600 bg-blue-50 font-medium' : 'border-gray-200'
                  }`}
                >
                  Без льготы
                </button>
                <button
                  type="button"
                  onClick={() => setPromotionEnabled(true)}
                  className={`p-3 rounded-lg border text-left text-sm ${
                    promotionEnabled ? 'border-blue-600 bg-blue-50 font-medium' : 'border-gray-200'
                  }`}
                >
                  Первые клиенты бесплатно
                </button>
              </div>
              {promotionEnabled ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className={labelCls}>Количество бесплатных клиентов</label>
                    <div className="flex gap-2 mb-2">
                      {[5, 10].map((limit) => (
                        <button
                          key={limit}
                          type="button"
                          onClick={() => setFreeClientLimit(String(limit))}
                          className={`px-3 py-1.5 rounded-lg border text-xs font-medium ${
                            Number(freeClientLimit) === limit
                              ? 'border-emerald-600 bg-emerald-600 text-white'
                              : 'border-gray-300 bg-white text-gray-700'
                          }`}
                        >
                          {limit}
                        </button>
                      ))}
                    </div>
                    <input
                      type="number"
                      min="1"
                      className={inputCls}
                      value={freeClientLimit}
                      onChange={(e) => setFreeClientLimit(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className={labelCls}>Начало льготного месяца</label>
                    <input
                      type="date"
                      className={inputCls}
                      value={promotionStartDate}
                      onChange={(e) => setPromotionStartDate(e.target.value)}
                    />
                  </div>
                  <p className="sm:col-span-2 text-xs text-gray-500 flex items-center gap-1.5">
                    <CalendarClock className="w-3.5 h-3.5" />
                    Срок окончания будет рассчитан автоматически: один календарный месяц.
                  </p>
                </div>
              ) : null}
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
  const retryBitrixSync = useRetryPartnerBitrixSync();
  const bindBitrixCollab = useBindPartnerBitrixCollab();
  const [showConfirm, setShowConfirm] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [editingRegion, setEditingRegion] = useState(false);
  const [collabId, setCollabId] = useState('');
  const [chatId, setChatId] = useState('');
  const [rootFolderId, setRootFolderId] = useState('');
  const [clientSearch, setClientSearch] = useState('');
  const [clientPage, setClientPage] = useState(1);
  const deferredClientSearch = useDeferredValue(clientSearch.trim());
  const {
    data: partnerClients,
    isLoading: areClientsLoading,
    isFetching: areClientsFetching,
    isError: areClientsError,
    refetch: refetchClients,
  } = useAdminClients({
    partner_id: id,
    search: deferredClientSearch || undefined,
    page: clientPage,
    page_size: 10,
  });

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

  const handleRegionChange = (region: string) => {
    updatePartner.mutate(
      { id: partner.id, data: { region } },
      {
        onSuccess: () => {
          setEditingRegion(false);
          toast.success('Регион обновлён');
        },
        onError: () => toast.error('Не удалось сохранить регион'),
      },
    );
  };

  const statusStyle = STATUS_STYLES[partner.status] || 'bg-gray-100 text-gray-700';
  const statusLabel = STATUS_LABELS[partner.status] || partner.status;
  const statusIcon = STATUS_ICONS[partner.status] ?? null;

  return (
    <div className="space-y-6">
      {/* Шапка */}
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
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
        <div className="flex flex-wrap items-center gap-3">
          {editingRegion ? (
            <div className="flex w-full max-w-[360px] items-center gap-2">
              <CustomSelect
                value={partner.region ?? ''}
                onChange={handleRegionChange}
                groups={REGION_SELECT_GROUPS}
                placeholder="Выберите регион"
                searchable
                disabled={updatePartner.isPending}
              />
              {updatePartner.isPending ? (
                <Loader2 className="h-4 w-4 flex-shrink-0 animate-spin text-blue-600" />
              ) : (
                <button
                  onClick={() => setEditingRegion(false)}
                  className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
                  aria-label="Отменить изменение региона"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          ) : (
            <PartnerRegionClock
              region={partner.region}
              timezone={partner.timezone}
              onEdit={() => setEditingRegion(true)}
            />
          )}
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

      {/* Финансовая информация */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Финансовая информация</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm text-gray-600">Общая задолженность</p>
                <p className="text-2xl font-semibold text-gray-900 mt-1">
                  {((partner.finance_total_cost ?? 0) / 100).toLocaleString('ru-RU')} ₽
                </p>
              </div>
              <div className="p-3 bg-white rounded-lg border border-gray-200">
                <WalletCards className="w-6 h-6 text-gray-600" />
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm text-amber-700">Текущая задолженность</p>
                <p className="text-2xl font-semibold text-amber-900 mt-1">
                  {((partner.finance_current_debt ?? 0) / 100).toLocaleString('ru-RU')} ₽
                </p>
              </div>
              <div className="p-3 bg-white rounded-lg border border-amber-200">
                <Clock3 className="w-6 h-6 text-amber-600" />
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-red-200 bg-red-50 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm text-red-700">Просроченная задолженность</p>
                <p className="text-2xl font-semibold text-red-900 mt-1">
                  {((partner.finance_overdue_debt ?? 0) / 100).toLocaleString('ru-RU')} ₽
                </p>
              </div>
              <div className="p-3 bg-white rounded-lg border border-red-200">
                <CircleDollarSign className="w-6 h-6 text-red-600" />
              </div>
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
            {partner.free_client_limit > 0 ? (
              <div className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                <div className="flex items-start gap-3">
                  <Gift className="w-5 h-5 text-emerald-700 mt-0.5" />
                  <div>
                    <p className="font-medium text-emerald-900">
                      Первые {partner.free_client_limit} клиентов бесплатно
                    </p>
                    <p className="text-sm text-emerald-800 mt-1">
                      Период: {formatDateOnly(partner.promotion_start_date)} — {formatDateOnly(partner.promotion_end_date)}
                    </p>
                    <p className="text-xs text-emerald-700 mt-2">
                      Льгота завершается по исчерпании лимита или окончании месяца — что наступит раньше.
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <p className="mt-4 text-sm text-gray-500">Льготное предложение не установлено.</p>
            )}
          </div>
        </div>

        {/* Правая колонка */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between gap-3 mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Битрикс24</h2>
              <span className={`text-xs font-medium px-2 py-1 rounded-full ${
                partner.bitrix_sync_status === 'synced'
                  ? 'bg-green-100 text-green-700'
                  : partner.bitrix_sync_status === 'failed' || partner.bitrix_sync_status === 'conflict'
                    ? 'bg-red-100 text-red-700'
                    : 'bg-yellow-100 text-yellow-700'
              }`}>
                {BITRIX_SYNC_LABELS[partner.bitrix_sync_status] ?? partner.bitrix_sync_status}
              </span>
            </div>
            <div className="space-y-2 text-sm">
              <p className="text-gray-600">Карточка партнёра: <span className="text-gray-900">{partner.bitrix_partner_item_id ?? 'ещё не создана'}</span></p>
              <p className="text-gray-600">Чат: <span className="text-gray-900">{partner.bitrix_chat_id ? `привязан (${partner.bitrix_chat_id})` : 'не привязан'}</span></p>
              <p className="text-gray-600">Коллаба: <span className="text-gray-900">{partner.bitrix_collab_id ? 'привязана' : 'не привязана'}</span></p>
              <p className="text-gray-600">Корневая папка: <span className="text-gray-900">{partner.bitrix_root_folder_id ? 'привязана' : 'не привязана'}</span></p>
              {partner.bitrix_sync_error_code && (
                <p className="text-red-600">Код состояния: {partner.bitrix_sync_error_code}</p>
              )}
            </div>

            {partner.status === 'active' && ['not_scheduled', 'failed'].includes(partner.bitrix_sync_status) && (
              <button
                onClick={() => retryBitrixSync.mutate(partner.id, {
                  onSuccess: () => toast.success('Синхронизация поставлена в очередь'),
                  onError: () => toast.error('Не удалось повторить синхронизацию'),
                })}
                disabled={retryBitrixSync.isPending}
                className="mt-4 w-full flex items-center justify-center gap-2 px-3 py-2 text-sm border border-blue-200 text-blue-700 rounded-lg hover:bg-blue-50 disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${retryBitrixSync.isPending ? 'animate-spin' : ''}`} />
                Повторить синхронизацию
              </button>
            )}

            {partner.bitrix_sync_status === 'conflict' && (
              <p className="mt-4 text-sm text-red-700 bg-red-50 rounded-lg p-3">
                Реквизиты изменены в Битрикс24. Данные кабинета не перезаписаны; требуется решение администратора.
              </p>
            )}

            {partner.bitrix_collab_status !== 'linked' && (
              <div className="mt-5 pt-4 border-t border-gray-200 space-y-2">
                <p className="text-sm font-medium text-gray-900">Привязать чат или готовую коллабу</p>
                <p className="text-xs text-gray-500">Чат можно подключить отдельно. ID коллабы и папки добавляются позднее.</p>
                <input value={collabId} onChange={(e) => setCollabId(e.target.value)} placeholder="ID коллабы" className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg" />
                <input value={chatId} onChange={(e) => setChatId(e.target.value)} placeholder="ID чата (можно отдельно)" className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg" />
                <input value={rootFolderId} onChange={(e) => setRootFolderId(e.target.value)} placeholder="ID корневой папки" className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg" />
                <button
                  onClick={() => bindBitrixCollab.mutate({
                    id: partner.id,
                    data: {
                      ...(collabId.trim() ? { collab_id: collabId.trim() } : {}),
                      ...(chatId.trim() ? { chat_id: chatId.trim() } : {}),
                      ...(rootFolderId.trim() ? { root_folder_id: rootFolderId.trim() } : {}),
                    },
                  }, {
                    onSuccess: () => toast.success('Привязка сохранена'),
                    onError: () => toast.error('Не удалось сохранить привязку'),
                  })}
                  disabled={!(collabId.trim() || chatId.trim() || rootFolderId.trim()) || bindBitrixCollab.isPending}
                  className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  <Link2 className="w-4 h-4" />
                  Сохранить привязку
                </button>
              </div>
            )}
          </div>

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

      {/* Клиенты партнёра */}
      <section className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="p-6 border-b border-gray-200">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold text-gray-900">Клиенты партнёра</h2>
              <span className="inline-flex min-w-6 h-6 items-center justify-center rounded-md bg-blue-50 px-2 text-xs font-semibold text-blue-700">
                {partner.clients_count ?? partnerClients?.total ?? 0}
              </span>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <div className="relative sm:w-72">
                <label htmlFor="partner-clients-search" className="sr-only">
                  Поиск по клиентам партнёра
                </label>
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <input
                  id="partner-clients-search"
                  type="search"
                  value={clientSearch}
                  onChange={(event) => {
                    setClientSearch(event.target.value);
                    setClientPage(1);
                  }}
                  placeholder="Поиск по клиентам"
                  className="w-full rounded-lg border border-gray-300 py-2 pl-9 pr-3 text-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />
              </div>
              <Link
                to={`/admin/clients?partner=${partner.id}`}
                className="text-sm font-medium text-blue-600 hover:text-blue-700 hover:underline whitespace-nowrap"
              >
                Все клиенты
              </Link>
            </div>
          </div>
          {deferredClientSearch ? (
            <p className="mt-3 text-xs text-gray-500">
              Найдено: {partnerClients?.total ?? 0}
            </p>
          ) : null}
        </div>

        {areClientsLoading ? (
          <div className="flex items-center justify-center gap-2 px-6 py-12 text-sm text-gray-500">
            <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
            Загрузка клиентов...
          </div>
        ) : areClientsError ? (
          <div className="flex flex-col items-center px-6 py-12 text-center">
            <AlertCircle className="mb-3 h-9 w-9 text-red-400" />
            <p className="text-sm font-medium text-gray-900">Не удалось загрузить клиентов</p>
            <button
              type="button"
              onClick={() => refetchClients()}
              className="mt-3 text-sm font-medium text-blue-600 hover:underline"
            >
              Повторить
            </button>
          </div>
        ) : partnerClients?.items.length ? (
          <>
            <div className={`overflow-x-auto transition-opacity ${areClientsFetching ? 'opacity-60' : ''}`}>
              <table className="w-full min-w-[900px]">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-600">Клиент</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">Телефон</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">Статус</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">Тип</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">Стоимость</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">Дата добавления</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-600">Действия</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {partnerClients.items.map((client) => (
                    <tr key={client.id} className="hover:bg-blue-50/40 transition-colors">
                      <td className="px-6 py-4">
                        <Link
                          to={`/admin/clients/${client.id}`}
                          className="text-sm font-medium text-gray-900 hover:text-blue-700 hover:underline"
                        >
                          {client.full_name}
                        </Link>
                        <p className="mt-0.5 text-xs text-gray-500">
                          <CaseArbitrLink caseNumber={client.case_number} emptyLabel="Дело не указано" />
                        </p>
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-600">{client.phone || '—'}</td>
                      <td className="px-4 py-4">
                        <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${getStatusBadgeClass(client.status)}`}>
                          {getStatusLabel(client.status)}
                        </span>
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-600">
                        {client.type === 'before_court' ? 'До суда' : 'В суде'}
                      </td>
                      <td className="px-4 py-4 text-sm font-medium text-gray-900">
                        {client.court_fee_per_client == null
                          ? '—'
                          : `${(client.court_fee_per_client / 100).toLocaleString('ru-RU')} ₽`}
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-600">
                        {formatDateShort(client.created_at, tz)}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <Link
                          to={`/admin/clients/${client.id}`}
                          className="text-sm font-medium text-blue-600 hover:text-blue-700 hover:underline"
                        >
                          Открыть
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {(partnerClients.pages > 1) ? (
              <div className="flex items-center justify-between gap-4 border-t border-gray-200 px-6 py-4">
                <p className="text-xs text-gray-500">
                  Страница {partnerClients.page} из {partnerClients.pages}
                </p>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setClientPage((page) => Math.max(1, page - 1))}
                    disabled={partnerClients.page <= 1 || areClientsFetching}
                    aria-label="Предыдущая страница клиентов"
                    className="rounded-lg border border-gray-300 p-2 text-gray-600 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setClientPage((page) => Math.min(partnerClients.pages, page + 1))}
                    disabled={partnerClients.page >= partnerClients.pages || areClientsFetching}
                    aria-label="Следующая страница клиентов"
                    className="rounded-lg border border-gray-300 p-2 text-gray-600 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ) : null}
          </>
        ) : (
          <div className="flex flex-col items-center px-6 py-12 text-center">
            <Users className="mb-3 h-10 w-10 text-gray-300" />
            <p className="text-sm font-medium text-gray-900">
              {deferredClientSearch ? 'Клиенты не найдены' : 'У партнёра пока нет клиентов'}
            </p>
            <p className="mt-1 text-xs text-gray-500">
              {deferredClientSearch
                ? 'Попробуйте изменить поисковый запрос.'
                : 'Новые клиенты появятся здесь после добавления.'}
            </p>
          </div>
        )}
      </section>

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
