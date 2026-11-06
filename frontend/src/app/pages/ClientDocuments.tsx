import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router';
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Building2,
  Check,
  Download,
  FileArchive,
  FileText,
  ListChecks,
  Loader2,
  Plus,
  Save,
  Trash2,
  UserRound,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  downloadGeneratedDocument,
  type DocumentGenerationData,
  type GeneratedDocumentKind,
} from '../api/clients';
import { useClient, useUpdateClient } from '../hooks/useClients';

type FormItem = Record<string, string>;

interface GenerationForm {
  general: FormItem;
  creditors: FormItem[];
  debtors: FormItem[];
  real_estate: FormItem[];
  vehicles: FormItem[];
  bank_accounts: FormItem[];
  company_interests: FormItem[];
  securities: FormItem[];
  other_assets: FormItem[];
}

type CollectionKey = Exclude<keyof GenerationForm, 'general'>;

interface FieldDefinition {
  key: string;
  label: string;
  placeholder?: string;
  type?: 'text' | 'number' | 'date' | 'textarea' | 'select';
  options?: Array<{ value: string; label: string }>;
  wide?: boolean;
}

const today = new Date().toISOString().slice(0, 10);

const EMPTY_FORM: GenerationForm = {
  general: {
    birth_place: '',
    actual_address: '',
    subdivision_code: '',
    document_date: today,
    monthly_income: '',
    employment_status: '',
    marital_status: '',
    dependants: '',
    cash_amount: '',
    previous_names: '',
    credit_purpose: '',
    claims_present: '',
    enforcement_present: '',
    other_obligations: '',
    transactions_present: '',
    bankruptcy_last_five_years: '',
    criminal_economic_record: '',
  },
  creditors: [],
  debtors: [],
  real_estate: [],
  vehicles: [],
  bank_accounts: [],
  company_interests: [],
  securities: [],
  other_assets: [],
};

const STEPS = [
  { id: 0, label: 'Заявление', icon: FileText },
  { id: 1, label: 'Кредиторы', icon: ListChecks },
  { id: 2, label: 'Имущество', icon: FileArchive },
  { id: 3, label: 'Проверка и скачивание', icon: Download },
];

const PARTY_FIELDS: FieldDefinition[] = [
  { key: 'obligation', label: 'Содержание обязательства', placeholder: 'Кредит, заём, расписка' },
  { key: 'name', label: 'Наименование / ФИО', placeholder: 'Банк или физическое лицо' },
  { key: 'address', label: 'Адрес', wide: true },
  { key: 'basis', label: 'Основание', placeholder: 'Кредитный договор' },
  { key: 'contract_number', label: 'Номер договора' },
  { key: 'contract_date', label: 'Дата договора', type: 'date' },
  { key: 'total_amount', label: 'Общая сумма, руб.', type: 'number' },
  { key: 'overdue_amount', label: 'Просрочено, руб.', type: 'number' },
  { key: 'penalties', label: 'Пени и штрафы, руб.', type: 'number' },
];

const REAL_ESTATE_FIELDS: FieldDefinition[] = [
  {
    key: 'category',
    label: 'Вид',
    type: 'select',
    options: [
      { value: 'land', label: 'Земельный участок' },
      { value: 'house', label: 'Дом / дача' },
      { value: 'apartment', label: 'Квартира' },
      { value: 'garage', label: 'Гараж' },
      { value: 'other', label: 'Иное' },
    ],
  },
  { key: 'name', label: 'Наименование' },
  { key: 'ownership', label: 'Вид собственности' },
  { key: 'address', label: 'Адрес', wide: true },
  { key: 'area', label: 'Площадь, м²' },
  { key: 'basis_value', label: 'Основание и стоимость', wide: true },
  { key: 'pledge', label: 'Залог / залогодержатель', wide: true },
];

const VEHICLE_FIELDS: FieldDefinition[] = [
  {
    key: 'category',
    label: 'Вид',
    type: 'select',
    options: [
      { value: 'car', label: 'Легковой автомобиль' },
      { value: 'truck', label: 'Грузовой автомобиль' },
      { value: 'motorcycle', label: 'Мототранспорт' },
      { value: 'agriculture', label: 'Сельхозтехника' },
      { value: 'water', label: 'Водный транспорт' },
      { value: 'air', label: 'Воздушный транспорт' },
      { value: 'other', label: 'Иное' },
    ],
  },
  { key: 'name', label: 'Марка и модель' },
  { key: 'identifier', label: 'VIN / идентификатор' },
  { key: 'ownership', label: 'Вид собственности' },
  { key: 'address', label: 'Место хранения', wide: true },
  { key: 'value', label: 'Стоимость, руб.', type: 'number' },
  { key: 'pledge', label: 'Залог / залогодержатель', wide: true },
];

const ACCOUNT_FIELDS: FieldDefinition[] = [
  { key: 'bank', label: 'Банк' },
  { key: 'account_type', label: 'Вид счёта' },
  { key: 'currency', label: 'Валюта', placeholder: 'RUB' },
  { key: 'opened_at', label: 'Дата открытия', type: 'date' },
  { key: 'balance', label: 'Остаток', type: 'number' },
];

const INTEREST_FIELDS: FieldDefinition[] = [
  { key: 'name', label: 'Организация' },
  { key: 'address', label: 'Адрес', wide: true },
  { key: 'capital', label: 'Уставный капитал' },
  { key: 'share', label: 'Доля' },
  { key: 'basis', label: 'Основание участия', wide: true },
];

const SECURITY_FIELDS: FieldDefinition[] = [
  { key: 'type', label: 'Вид ценной бумаги' },
  { key: 'issuer', label: 'Эмитент' },
  { key: 'nominal', label: 'Номинал', type: 'number' },
  { key: 'quantity', label: 'Количество', type: 'number' },
  { key: 'total', label: 'Общая стоимость', type: 'number' },
];

const OTHER_ASSET_FIELDS: FieldDefinition[] = [
  {
    key: 'category',
    label: 'Категория',
    type: 'select',
    options: [
      { value: 'cash', label: 'Наличные' },
      { value: 'jewelry', label: 'Драгоценности' },
      { value: 'art', label: 'Предметы искусства' },
      { value: 'professional', label: 'Профессиональное имущество' },
      { value: 'other', label: 'Иное' },
    ],
  },
  { key: 'name', label: 'Наименование' },
  { key: 'value', label: 'Стоимость, руб.', type: 'number' },
  { key: 'address', label: 'Место нахождения', wide: true },
  { key: 'pledge', label: 'Залог / залогодержатель', wide: true },
];

function mergeStoredData(value: DocumentGenerationData | undefined): GenerationForm {
  const source = value ?? {};
  const general = typeof source.general === 'object' && source.general ? (source.general as FormItem) : {};
  const collection = (key: CollectionKey) => (
    Array.isArray(source[key])
      ? (source[key] as FormItem[]).map((item) => ({ ...item, _rowId: item._rowId || crypto.randomUUID() }))
      : []
  );
  return {
    general: { ...EMPTY_FORM.general, ...general },
    creditors: collection('creditors'),
    debtors: collection('debtors'),
    real_estate: collection('real_estate'),
    vehicles: collection('vehicles'),
    bank_accounts: collection('bank_accounts'),
    company_interests: collection('company_interests'),
    securities: collection('securities'),
    other_assets: collection('other_assets'),
  };
}

function inputClass() {
  return 'mt-1.5 w-full rounded-xl border border-gray-200 bg-white px-3.5 py-2.5 text-sm text-gray-900 outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100';
}

function serializeForm(form: GenerationForm): DocumentGenerationData {
  const cleanItems = (items: FormItem[]) => items.map((item) => (
    Object.fromEntries(Object.entries(item).filter(([key]) => key !== '_rowId'))
  ));
  return {
    general: form.general,
    creditors: cleanItems(form.creditors),
    debtors: cleanItems(form.debtors),
    real_estate: cleanItems(form.real_estate),
    vehicles: cleanItems(form.vehicles),
    bank_accounts: cleanItems(form.bank_accounts),
    company_interests: cleanItems(form.company_interests),
    securities: cleanItems(form.securities),
    other_assets: cleanItems(form.other_assets),
  };
}

function CollectionEditor({
  title,
  description,
  addLabel,
  items,
  fields,
  onAdd,
  onChange,
  onRemove,
}: {
  title: string;
  description: string;
  addLabel: string;
  items: FormItem[];
  fields: FieldDefinition[];
  onAdd: () => void;
  onChange: (index: number, key: string, value: string) => void;
  onRemove: (index: number) => void;
}) {
  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="font-semibold text-gray-950">{title}</h3>
          <p className="mt-1 text-sm text-gray-500">{description}</p>
        </div>
        <button
          type="button"
          onClick={onAdd}
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-3.5 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100"
        >
          <Plus className="h-4 w-4" /> {addLabel}
        </button>
      </div>

      {items.length === 0 ? (
        <div className="mt-4 rounded-xl border border-dashed border-gray-300 px-4 py-6 text-center text-sm text-gray-500">
          Сведения не добавлены. Если объектов нет, оставьте раздел пустым.
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          {items.map((item, index) => (
            <div key={item._rowId || String(index)} className="rounded-xl border border-gray-200 bg-gray-50/70 p-4">
              <div className="mb-3 flex items-center justify-between">
                <span className="text-sm font-semibold text-gray-700">Запись {index + 1}</span>
                <button
                  type="button"
                  onClick={() => onRemove(index)}
                  aria-label={`Удалить запись ${index + 1}`}
                  className="rounded-lg p-2 text-gray-400 hover:bg-red-50 hover:text-red-600"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {fields.map((field) => (
                  <label key={field.key} className={`text-sm font-medium text-gray-700 ${field.wide ? 'sm:col-span-2 lg:col-span-3' : ''}`}>
                    {field.label}
                    {field.type === 'select' ? (
                      <select
                        value={item[field.key] ?? ''}
                        onChange={(event) => onChange(index, field.key, event.target.value)}
                        className={inputClass()}
                      >
                        <option value="">Выберите</option>
                        {field.options?.map((option) => (
                          <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                      </select>
                    ) : field.type === 'textarea' ? (
                      <textarea
                        value={item[field.key] ?? ''}
                        onChange={(event) => onChange(index, field.key, event.target.value)}
                        placeholder={field.placeholder}
                        rows={3}
                        className={inputClass()}
                      />
                    ) : (
                      <input
                        type={field.type ?? 'text'}
                        value={item[field.key] ?? ''}
                        onChange={(event) => onChange(index, field.key, event.target.value)}
                        placeholder={field.placeholder}
                        min={field.type === 'number' ? '0' : undefined}
                        className={inputClass()}
                      />
                    )}
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export default function ClientDocuments() {
  const { id = '' } = useParams<{ id: string }>();
  const { data: client, isLoading } = useClient(id);
  const updateClient = useUpdateClient();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<GenerationForm>(EMPTY_FORM);
  const [initialized, setInitialized] = useState(false);
  const [downloading, setDownloading] = useState<GeneratedDocumentKind | null>(null);

  useEffect(() => {
    if (client && !initialized) {
      setForm(mergeStoredData(client.document_generation_data));
      setInitialized(true);
    }
  }, [client, initialized]);

  const missingProfile = useMemo(() => {
    if (!client) return [];
    return [
      ['Дата рождения', client.date_of_birth],
      ['Паспорт', client.passport_series && client.passport_number],
      ['Дата выдачи паспорта', client.passport_issue_date],
      ['Кем выдан паспорт', client.passport_issued_by],
      ['Адрес регистрации', client.registration_address],
      ['ИНН', client.inn],
      ['СНИЛС', client.snils],
      ['Арбитражный суд', client.arbitrage_court],
    ].filter(([, value]) => !value).map(([label]) => label as string);
  }, [client]);

  const generalCompleted = Object.values(form.general).filter((value) => value.trim()).length;
  const readiness = Math.round(((8 - missingProfile.length + Math.min(generalCompleted, 8)) / 16) * 100);

  const setGeneral = (key: string, value: string) => {
    setForm((current) => ({ ...current, general: { ...current.general, [key]: value } }));
  };

  const addItem = (key: CollectionKey, defaults: FormItem = {}) => {
    setForm((current) => ({ ...current, [key]: [...current[key], { ...defaults, _rowId: crypto.randomUUID() }] }));
  };

  const updateItem = (key: CollectionKey, index: number, field: string, value: string) => {
    setForm((current) => ({
      ...current,
      [key]: current[key].map((item, itemIndex) => itemIndex === index ? { ...item, [field]: value } : item),
    }));
  };

  const removeItem = (key: CollectionKey, index: number) => {
    setForm((current) => ({ ...current, [key]: current[key].filter((_, itemIndex) => itemIndex !== index) }));
  };

  const save = async (showToast = true) => {
    if (!id) return;
    await updateClient.mutateAsync({ id, data: { document_generation_data: serializeForm(form) } });
    if (showToast) toast.success('Анкета сохранена');
  };

  const handleDownload = async (kind: GeneratedDocumentKind) => {
    setDownloading(kind);
    try {
      await save(false);
      await downloadGeneratedDocument(id, kind);
      toast.success('Документ сформирован и скачан');
    } catch {
      toast.error('Не удалось сформировать документ');
    } finally {
      setDownloading(null);
    }
  };

  if (isLoading || !client) {
    return <div className="flex min-h-[420px] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-blue-600" /></div>;
  }

  return (
    <div className="mx-auto max-w-7xl pb-10">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <Link to={`/dashboard/clients/${id}`} className="inline-flex items-center gap-2 text-sm font-medium text-gray-500 hover:text-blue-700">
            <ArrowLeft className="h-4 w-4" /> Назад в карточку клиента
          </Link>
          <div className="mt-4 flex items-center gap-3">
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-100 text-violet-700">
              <FileText className="h-6 w-6" />
            </span>
            <div>
              <h1 className="text-2xl font-bold text-gray-950">Документы до суда</h1>
              <p className="mt-1 text-sm text-gray-500">{client.full_name}</p>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to={`/dashboard/clients/${id}#client-files`}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <FileArchive className="h-4 w-4" /> Загрузить исходные документы
          </Link>
          <button
            type="button"
            onClick={() => void save()}
            disabled={updateClient.isPending}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {updateClient.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Сохранить анкету
          </button>
        </div>
      </div>

      <div className="mb-6 rounded-2xl border border-blue-100 bg-gradient-to-r from-blue-50 to-violet-50 p-5">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-start gap-3">
            <Building2 className="mt-0.5 h-5 w-5 text-blue-700" />
            <div>
              <p className="font-semibold text-gray-950">Самостоятельная подготовка партнёром</p>
              <p className="mt-1 text-sm text-gray-600">Данные сохраняются в карточке клиента и используются сразу в трёх шаблонах.</p>
            </div>
          </div>
          <div className="min-w-52">
            <div className="flex items-center justify-between text-xs font-medium text-gray-600">
              <span>Готовность данных</span><span>{readiness}%</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/80">
              <div className="h-full rounded-full bg-blue-600" style={{ width: `${readiness}%` }} />
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="h-fit rounded-2xl border border-gray-200 bg-white p-3 shadow-sm xl:sticky xl:top-6">
          {STEPS.map(({ id: stepId, label, icon: Icon }) => (
            <button
              key={stepId}
              type="button"
              onClick={() => setStep(stepId)}
              className={`mb-1 flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm font-medium transition ${
                step === stepId ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${step === stepId ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-500'}`}>
                <Icon className="h-4 w-4" />
              </span>
              {label}
            </button>
          ))}
        </aside>

        <main className="space-y-5">
          {step === 0 && (
            <>
              <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex items-center gap-3">
                  <UserRound className="h-5 w-5 text-blue-700" />
                  <div>
                    <h2 className="text-lg font-semibold text-gray-950">Сведения для заявления</h2>
                    <p className="text-sm text-gray-500">Паспортные данные уже берутся из карточки клиента.</p>
                  </div>
                </div>
                <div className="mt-5 grid gap-4 sm:grid-cols-2">
                  {[
                    ['birth_place', 'Место рождения'],
                    ['actual_address', 'Фактический адрес'],
                    ['subdivision_code', 'Код подразделения'],
                    ['document_date', 'Дата документа', 'date'],
                    ['monthly_income', 'Среднемесячный доход, руб.', 'number'],
                    ['cash_amount', 'Наличные денежные средства, руб.', 'number'],
                    ['employment_status', 'Занятость'],
                    ['marital_status', 'Семейное положение'],
                    ['dependants', 'Лица на иждивении'],
                    ['previous_names', 'Прежние ФИО'],
                  ].map(([key, label, type]) => (
                    <label key={key} className="text-sm font-medium text-gray-700">
                      {label}
                      <input type={type ?? 'text'} value={form.general[key] ?? ''} onChange={(event) => setGeneral(key, event.target.value)} className={inputClass()} />
                    </label>
                  ))}
                </div>
              </section>
              <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <h2 className="text-lg font-semibold text-gray-950">Обстоятельства дела</h2>
                <p className="mt-1 text-sm text-gray-500">Опишите факты своими словами. Эти ответы заменят утверждения, заранее записанные в шаблоне.</p>
                <div className="mt-5 grid gap-4">
                  {[
                    ['credit_purpose', 'Цели возникновения обязательств'],
                    ['claims_present', 'Исковые требования кредиторов'],
                    ['enforcement_present', 'Судебные решения и исполнительные производства'],
                    ['other_obligations', 'Долговые расписки и иные требования'],
                    ['transactions_present', 'Сделки за последние три года'],
                    ['bankruptcy_last_five_years', 'Банкротство за последние пять лет'],
                    ['criminal_economic_record', 'Сведения об ответственности за экономические правонарушения'],
                  ].map(([key, label]) => (
                    <label key={key} className="text-sm font-medium text-gray-700">
                      {label}
                      <textarea value={form.general[key] ?? ''} onChange={(event) => setGeneral(key, event.target.value)} rows={3} className={inputClass()} />
                    </label>
                  ))}
                </div>
              </section>
            </>
          )}

          {step === 1 && (
            <>
              <CollectionEditor
                title="Кредиторы гражданина"
                description="Добавьте каждого кредитора и актуальную сумму обязательства."
                addLabel="Добавить кредитора"
                items={form.creditors}
                fields={PARTY_FIELDS}
                onAdd={() => addItem('creditors', { number: String(form.creditors.length + 1) })}
                onChange={(index, key, value) => updateItem('creditors', index, key, value)}
                onRemove={(index) => removeItem('creditors', index)}
              />
              <CollectionEditor
                title="Должники гражданина"
                description="Заполните, если другие лица должны деньги клиенту."
                addLabel="Добавить должника"
                items={form.debtors}
                fields={PARTY_FIELDS}
                onAdd={() => addItem('debtors')}
                onChange={(index, key, value) => updateItem('debtors', index, key, value)}
                onRemove={(index) => removeItem('debtors', index)}
              />
            </>
          )}

          {step === 2 && (
            <>
              <CollectionEditor title="Недвижимость" description="Земля, дома, квартиры, гаражи и иные объекты." addLabel="Добавить объект" items={form.real_estate} fields={REAL_ESTATE_FIELDS} onAdd={() => addItem('real_estate')} onChange={(index, key, value) => updateItem('real_estate', index, key, value)} onRemove={(index) => removeItem('real_estate', index)} />
              <CollectionEditor title="Транспорт" description="Автомобили и другие зарегистрированные транспортные средства." addLabel="Добавить транспорт" items={form.vehicles} fields={VEHICLE_FIELDS} onAdd={() => addItem('vehicles')} onChange={(index, key, value) => updateItem('vehicles', index, key, value)} onRemove={(index) => removeItem('vehicles', index)} />
              <CollectionEditor title="Банковские счета" description="Счета и остатки на дату подготовки документов." addLabel="Добавить счёт" items={form.bank_accounts} fields={ACCOUNT_FIELDS} onAdd={() => addItem('bank_accounts')} onChange={(index, key, value) => updateItem('bank_accounts', index, key, value)} onRemove={(index) => removeItem('bank_accounts', index)} />
              <CollectionEditor title="Доли в организациях" description="Участие в обществах и иных юридических лицах." addLabel="Добавить долю" items={form.company_interests} fields={INTEREST_FIELDS} onAdd={() => addItem('company_interests')} onChange={(index, key, value) => updateItem('company_interests', index, key, value)} onRemove={(index) => removeItem('company_interests', index)} />
              <CollectionEditor title="Ценные бумаги" description="Акции, облигации и другие ценные бумаги." addLabel="Добавить бумагу" items={form.securities} fields={SECURITY_FIELDS} onAdd={() => addItem('securities')} onChange={(index, key, value) => updateItem('securities', index, key, value)} onRemove={(index) => removeItem('securities', index)} />
              <CollectionEditor title="Иное имущество" description="Наличные, драгоценности, предметы искусства и другие ценности." addLabel="Добавить имущество" items={form.other_assets} fields={OTHER_ASSET_FIELDS} onAdd={() => addItem('other_assets')} onChange={(index, key, value) => updateItem('other_assets', index, key, value)} onRemove={(index) => removeItem('other_assets', index)} />
            </>
          )}

          {step === 3 && (
            <>
              {missingProfile.length > 0 && (
                <div className="flex gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-5 text-amber-900">
                  <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
                  <div>
                    <p className="font-semibold">В карточке клиента не хватает данных</p>
                    <p className="mt-1 text-sm">{missingProfile.join(', ')}. Документы сформируются с пометкой «не указано».</p>
                    <Link to={`/dashboard/clients/${id}/edit`} className="mt-3 inline-flex items-center gap-1 text-sm font-semibold underline">Дополнить карточку <ArrowRight className="h-4 w-4" /></Link>
                  </div>
                </div>
              )}
              <div className="grid gap-4 lg:grid-cols-3">
                {[
                  { kind: 'application' as const, title: 'Заявление в суд', description: 'Данные клиента, обстоятельства и требования.', icon: FileText },
                  { kind: 'creditors' as const, title: 'Список кредиторов и должников', description: `${form.creditors.length} кредиторов, ${form.debtors.length} должников.`, icon: ListChecks },
                  { kind: 'inventory' as const, title: 'Опись имущества', description: 'Недвижимость, транспорт, счета и иные активы.', icon: FileArchive },
                ].map(({ kind, title, description, icon: Icon }) => (
                  <article key={kind} className="flex flex-col rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
                    <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-violet-100 text-violet-700"><Icon className="h-5 w-5" /></span>
                    <h3 className="mt-4 font-semibold text-gray-950">{title}</h3>
                    <p className="mt-2 flex-1 text-sm leading-5 text-gray-500">{description}</p>
                    <div className="mt-4 flex items-center gap-2 text-xs text-green-700"><Check className="h-4 w-4" /> Формат DOCX</div>
                    <button type="button" onClick={() => void handleDownload(kind)} disabled={downloading !== null} className="mt-4 inline-flex items-center justify-center gap-2 rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-violet-700 disabled:opacity-60">
                      {downloading === kind ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                      Сформировать и скачать
                    </button>
                  </article>
                ))}
              </div>
              <div className="flex gap-3 rounded-2xl border border-gray-200 bg-gray-50 p-5">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-gray-500" />
                <p className="text-sm leading-6 text-gray-600">
                  Сформированные файлы являются проектами документов. Перед подачей в суд проверьте фактические сведения, приложения и актуальность правовых формулировок.
                </p>
              </div>
            </>
          )}

          <div className="flex items-center justify-between pt-1">
            <button type="button" onClick={() => setStep((current) => Math.max(0, current - 1))} disabled={step === 0} className="rounded-xl border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 disabled:opacity-40">Назад</button>
            {step < 3 && (
              <button type="button" onClick={() => setStep((current) => Math.min(3, current + 1))} className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700">Продолжить <ArrowRight className="h-4 w-4" /></button>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
