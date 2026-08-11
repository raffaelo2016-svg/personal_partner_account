import { useState, useMemo, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router';
import { ArrowLeft, Save, Upload, X, FileText, Check, Loader2, Trash2 } from 'lucide-react';
import { Link } from 'react-router';
import { useCreateClient, useClient, useUpdateClient, useDeleteClient } from '../hooks/useClients';
import { useQueryClient } from '@tanstack/react-query';
import { REGION_GROUPS, getCourtForRegion } from '../data/arbitrageCourts';
import { uploadFile } from '../api/upload';
import { toast } from 'sonner';
import { captureError } from '@/app/sentry';
import { PhoneField } from '@/app/components/PhoneField';
import { normalizePhoneForApi, validatePhoneFieldOptional } from '@/app/utils/phone';
import { clientFormSchema } from '@/app/schemas/client';
import CustomSelect from '../components/ui/CustomSelect';
import DateInput from '../components/ui/DateInput';
import { syntheticChange } from '../utils/form';
import { partitionFiles, formatFileSize, uploadAllSettled, MAX_FILE_SIZE_LABEL } from '../utils/files';

interface UploadedFile {
  file: File;
  comment: string;
}

interface DocumentUploads {
  [key: string]: File[];
}

const EMPTY_FORM = {
  type: 'before_court',
  caseNumber: '',
  fullName: '',
  dateOfBirth: '',
  passportSeries: '',
  passportNumber: '',
  passportIssueDate: '',
  passportIssuedBy: '',
  registrationAddress: '',
  inn: '',
  snils: '',
  region: '',
  arbitrageCourt: '',
  phone: '',
  email: '',
};

function formatSnils(value: string): string {
  const digits = value.replace(/\D/g, '').slice(0, 11);
  const first = digits.slice(0, 3);
  const second = digits.slice(3, 6);
  const third = digits.slice(6, 9);
  const control = digits.slice(9, 11);

  let formatted = first;
  if (second) formatted += `-${second}`;
  if (third) formatted += `-${third}`;
  if (control) formatted += ` ${control}`;
  return formatted;
}

export default function ClientForm() {
  const { id } = useParams<{ id: string }>();
  const isEditMode = !!id;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const createMutation = useCreateClient();
  const updateMutation = useUpdateClient();
  const deleteMutation = useDeleteClient();
  const { data: existingClient, isLoading: isLoadingClient } = useClient(id ?? '');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [formInitialized, setFormInitialized] = useState(false);

  useEffect(() => {
    if (isEditMode && existingClient && !formInitialized) {
      setFormData({
        type: existingClient.type || 'before_court',
        caseNumber: existingClient.case_number || '',
        fullName: existingClient.full_name || '',
        dateOfBirth: existingClient.date_of_birth?.split('T')[0] || '',
        passportSeries: existingClient.passport_series || '',
        passportNumber: existingClient.passport_number || '',
        passportIssueDate: existingClient.passport_issue_date?.split('T')[0] || '',
        passportIssuedBy: existingClient.passport_issued_by || '',
        registrationAddress: existingClient.registration_address || '',
        inn: existingClient.inn || '',
        snils: formatSnils(existingClient.snils || ''),
        region: existingClient.region || '',
        arbitrageCourt: existingClient.arbitrage_court || '',
        phone: existingClient.phone ?? '',
        email: existingClient.email ?? '',
      });
      setFormInitialized(true);
    }
  }, [isEditMode, existingClient, formInitialized]);

  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [uploadError, setUploadError] = useState<string>('');
  const [documentUploads, setDocumentUploads] = useState<DocumentUploads>({});

  const activeMutation = isEditMode ? updateMutation : createMutation;
  const [isUploading, setIsUploading] = useState(false);
  const [phoneError, setPhoneError] = useState('');
  const [emailError, setEmailError] = useState('');
  const [regionError, setRegionError] = useState('');

  const uploadAllFiles = useCallback(async (clientId: string) => {
    const allFiles: { file: File; docType: string }[] = [];

    for (const [docType, files] of Object.entries(documentUploads)) {
      for (const file of files) {
        allFiles.push({ file, docType });
      }
    }
    for (const uf of uploadedFiles) {
      allFiles.push({ file: uf.file, docType: 'other' });
    }

    if (allFiles.length === 0) return { succeeded: [], failed: [] };

    setIsUploading(true);
    try {
      const result = await uploadAllSettled(allFiles, ({ file, docType }) =>
        uploadFile(file, clientId, docType),
      );
      result.failed.forEach(({ item, error }) => {
        captureError(error, { context: 'client_file_upload', fileName: item.file.name });
      });
      return result;
    } finally {
      setIsUploading(false);
    }
  }, [documentUploads, uploadedFiles]);
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPhoneError('');
    setEmailError('');
    setRegionError('');

    if (!formData.region) {
      setRegionError('Выберите регион');
      return;
    }

    const phoneErr = validatePhoneFieldOptional(formData.phone);
    if (phoneErr) {
      setPhoneError(phoneErr);
      return;
    }
    const parsed = clientFormSchema.safeParse({
      fullName: formData.fullName,
      email: formData.email,
    });
    if (!parsed.success) {
      for (const issue of parsed.error.issues) {
        if (issue.path[0] === 'email') setEmailError(issue.message);
      }
      return;
    }
    const emailTrim = parsed.data.email ?? '';

    const payload: Record<string, unknown> = {
      type: formData.type,
      full_name: formData.fullName,
      phone: normalizePhoneForApi(formData.phone),
      email: emailTrim || null,
      case_number: formData.caseNumber || null,
      region: formData.region,
    };

    if (formData.type === 'before_court') {
      payload.date_of_birth = formData.dateOfBirth || null;
      payload.passport_series = formData.passportSeries || null;
      payload.passport_number = formData.passportNumber || null;
      payload.passport_issue_date = formData.passportIssueDate || null;
      payload.passport_issued_by = formData.passportIssuedBy || null;
      payload.registration_address = formData.registrationAddress || null;
      payload.inn = formData.inn || null;
      payload.snils = formData.snils || null;
      payload.arbitrage_court = formData.arbitrageCourt || null;
    }

    if (isEditMode && id) {
      updateMutation.mutate(
        { id, data: payload },
        {
          onSuccess: async () => {
            const result = await uploadAllFiles(id);
            queryClient.invalidateQueries({ queryKey: ['clientFiles', id] });
            if (result && result.failed.length > 0) {
              const names = result.failed.map((f) => f.item.file.name).join(', ');
              toast.warning(`Клиент сохранён. Не загружены файлы: ${names}`);
            } else {
              toast.success('Клиент обновлён');
            }
            navigate(`/dashboard/clients/${id}`);
          },
          onError: (err) => {
            captureError(err, { context: 'client_update' });
            toast.error('Не удалось сохранить изменения');
          },
        },
      );
    } else {
      createMutation.mutate(payload as any, {
        onSuccess: async (data) => {
          const result = await uploadAllFiles(data.id);
          queryClient.invalidateQueries({ queryKey: ['clientFiles', data.id] });
          if (result && result.failed.length > 0) {
            const names = result.failed.map((f) => f.item.file.name).join(', ');
            toast.warning(`Клиент создан. Не загружены файлы: ${names}`);
          } else {
            toast.success('Клиент создан');
          }
          navigate(`/dashboard/clients/${data.id}`);
        },
        onError: (err) => {
          captureError(err, { context: 'client_create' });
          toast.error('Не удалось создать клиента');
        },
      });
    }
  };
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    if (name === 'region') {
      const court = getCourtForRegion(value);
      setRegionError('');
      setFormData({
        ...formData,
        region: value,
        arbitrageCourt: court ? `[${court.code}] ${court.name}` : '',
      });
    } else {
      setFormData({ ...formData, [name]: value });
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      const { valid, invalidFormat, tooLarge } = partitionFiles(files);

      const errors: string[] = [];
      if (invalidFormat.length > 0) {
        errors.push(`Недопустимый формат: ${invalidFormat.join(', ')}. Форматы: JPEG, PNG, PDF, DOC, DOCX`);
      }
      if (tooLarge.length > 0) {
        errors.push(`Превышен размер ${MAX_FILE_SIZE_LABEL}: ${tooLarge.join(', ')}`);
      }
      if (errors.length > 0) {
        setUploadError(errors.join('. '));
        setTimeout(() => setUploadError(''), 5000);
      }

      if (valid.length > 0) {
        setUploadedFiles([...uploadedFiles, ...valid.map((file) => ({ file, comment: '' }))]);
      }
    }
    // Reset input value to allow uploading the same file again
    e.target.value = '';
  };

  const removeFile = (index: number) => {
    setUploadedFiles(uploadedFiles.filter((_, i) => i !== index));
  };

  const updateFileComment = (index: number, comment: string) => {
    const updatedFiles = [...uploadedFiles];
    updatedFiles[index].comment = comment;
    setUploadedFiles(updatedFiles);
  };

  const handleDocumentUpload = (documentType: string, e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      const { valid, invalidFormat, tooLarge } = partitionFiles(files);

      if (invalidFormat.length > 0) {
        toast.error(`Недопустимый формат: ${invalidFormat.join(', ')}. Форматы: JPEG, PNG, PDF, DOC, DOCX`);
      }
      if (tooLarge.length > 0) {
        toast.error(`Превышен размер ${MAX_FILE_SIZE_LABEL}: ${tooLarge.join(', ')}`);
      }

      if (valid.length > 0) {
        setDocumentUploads({
          ...documentUploads,
          [documentType]: [...(documentUploads[documentType] || []), ...valid],
        });
      }
    }
    // Reset input value to allow uploading the same file again
    e.target.value = '';
  };

  const removeDocument = (documentType: string, fileIndex: number) => {
    const updatedFiles = [...(documentUploads[documentType] || [])];
    updatedFiles.splice(fileIndex, 1);
    setDocumentUploads({
      ...documentUploads,
      [documentType]: updatedFiles,
    });
  };

  const requiredDocuments = [
    { id: 'passport', label: 'Паспорт', required: true },
    { id: 'snils', label: 'СНИЛС', required: true },
    { id: 'inn_certificate', label: 'Свидетельство ИНН', required: true },
    { id: 'children_birth_cert', label: 'Свидетельство о рождении детей', required: false },
    { id: 'marriage_cert', label: 'Свидетельство о заключении/расторжении брака', required: false },
    { id: 'employment_history', label: 'Справка о сведениях о трудовой деятельности из информационных ресурсов Пенсионного фонда', required: true },
    { id: 'pension_account', label: 'Справка, содержащая сведения о состоянии индивидуального лицевого счета застрахованного лица', required: true },
    { id: 'tax_registry', label: 'Выписка из Единого государственного реестра налогоплательщиков', required: true },
    { id: 'no_ip_status', label: 'Справка об отсутствии статуса ИП', required: true },
    { id: 'ndfl_2', label: 'Справки 2-НДФЛ (за последние три года)', required: true },
    { id: 'tax_debt', label: 'Справка об исполнении обязанности по уплате налогов, сборов, страховых взносов, пеней, штрафов, процентов', required: true },
    { id: 'credit_debt', label: 'Справка о задолженности по кредитным обязательствам', required: true },
    { id: 'credit_agreements', label: 'Копии кредитных договоров', required: true },
    { id: 'criminal_record', label: 'Справка о наличии (отсутствии) судимости', required: true },
    { id: 'deposit_payment', label: 'Квитанция по оплате 25000 на депозит', required: true },
    { id: 'other', label: 'Прочее', required: false },
  ];
  
  const selectedCourt = useMemo(
    () => (formData.region ? getCourtForRegion(formData.region) : null),
    [formData.region],
  );
  
  if (isEditMode && isLoadingClient) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <Link
          to={isEditMode ? `/dashboard/clients/${id}` : '/dashboard/clients'}
          className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeft className="w-5 h-5" />
          {isEditMode ? 'Назад к карточке' : 'Назад к списку'}
        </Link>
        <h1 className="text-3xl font-semibold text-gray-900 mb-2">
          {isEditMode ? 'Редактирование карточки клиента' : 'Создание карточки клиента'}
        </h1>
        <p className="text-gray-600">
          {isEditMode
            ? 'Измените данные клиента и сохраните изменения'
            : 'Заполните данные для создания новой карточки клиента'}
        </p>
      </div>
      
      <form onSubmit={handleSubmit} className="max-w-3xl">
        {/* Client Type */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Тип клиента
          </h2>
          <div className="space-y-3">
            <label className="flex items-start gap-3 p-4 border-2 border-gray-200 rounded-lg cursor-pointer hover:border-blue-500 has-[:checked]:border-blue-500 has-[:checked]:bg-blue-50">
              <input
                type="radio"
                name="type"
                value="before_court"
                checked={formData.type === 'before_court'}
                onChange={handleChange}
                className="mt-1"
              />
              <div>
                <p className="font-medium text-gray-900">Клиент ДО подачи заявления в суд</p>
                <p className="text-sm text-gray-600 mt-1">
                  Подготовка полного пакета документов и подача заявления через платформу
                </p>
              </div>
            </label>
            <label className="flex items-start gap-3 p-4 border-2 border-gray-200 rounded-lg cursor-pointer hover:border-blue-500 has-[:checked]:border-blue-500 has-[:checked]:bg-blue-50">
              <input
                type="radio"
                name="type"
                value="in_court"
                checked={formData.type === 'in_court'}
                onChange={handleChange}
                className="mt-1"
              />
              <div>
                <p className="font-medium text-gray-900">Клиент в суде</p>
                <p className="text-sm text-gray-600 mt-1">
                  Загрузка судебных документов и передача дела в сопровождение
                </p>
              </div>
            </label>
          </div>
        </div>
        
        {/* Форма для клиента УЖЕ в суде */}
        {formData.type === 'in_court' && (
          <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Информация о судебном деле
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Номер судебного дела <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  name="caseNumber"
                  value={formData.caseNumber}
                  onChange={handleChange}
                  required
                  placeholder="А40-123456/2026"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Регион <span className="text-red-500">*</span>
                </label>
                <CustomSelect
                  value={formData.region}
                  onChange={(val) => handleChange(syntheticChange('region', val))}
                  groups={REGION_GROUPS.map((group) => ({
                    label: group.district,
                    options: group.regions.map((r) => ({ value: r.name, label: r.name })),
                  }))}
                  placeholder="Выберите регион"
                  size="lg"
                  triggerClassName={regionError ? 'border-red-500' : ''}
                />
                {regionError ? <p className="text-sm text-red-500 mt-1">{regionError}</p> : null}
              </div>
              
              <div>
                <label htmlFor="fullName-before-court" className="block text-sm font-medium text-gray-700 mb-1">
                  ФИО клиента <span className="text-red-500">*</span>
                </label>
                <input
                  id="fullName-before-court"
                  type="text"
                  name="fullName"
                  value={formData.fullName}
                  onChange={handleChange}
                  required
                  placeholder="Иванов Иван Иванович"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <PhoneField
                  id="client-phone-in-court"
                  name="phone"
                  label="Телефон"
                  value={formData.phone}
                  onChange={(v) => {
                    setFormData({ ...formData, phone: v });
                    if (phoneError) setPhoneError('');
                  }}
                  error={phoneError}
                  onClearError={() => phoneError && setPhoneError('')}
                  onBlurValidate={() =>
                    setPhoneError(validatePhoneFieldOptional(formData.phone) || '')
                  }
                  hintId="client-phone-hint-in-court"
                  inputClassName="py-2"
                />
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="client-email-in-court">
                    Email
                  </label>
                  <input
                    id="client-email-in-court"
                    type="email"
                    name="email"
                    autoComplete="email"
                    value={formData.email}
                    onChange={(e) => {
                      handleChange(e);
                      if (emailError) setEmailError('');
                    }}
                    placeholder="name@example.com"
                    className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      emailError ? 'border-red-500' : 'border-gray-300'
                    }`}
                  />
                  {emailError ? <p className="text-sm text-red-500 mt-1">{emailError}</p> : null}
                </div>
              </div>
            </div>
          </div>
        )}
        
        {/* Форма для клиента ДО подачи в суд */}
        {formData.type === 'before_court' && (
          <>
            {/* Personal Data */}
            <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Персональные данные
              </h2>
              <div className="space-y-4">
                <div>
                  <label htmlFor="fullName-in-court" className="block text-sm font-medium text-gray-700 mb-1">
                    ФИО <span className="text-red-500">*</span>
                  </label>
                  <input
                    id="fullName-in-court"
                    type="text"
                    name="fullName"
                    value={formData.fullName}
                    onChange={handleChange}
                    required
                    placeholder="Иванов Иван Иванович"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Дата рождения <span className="text-red-500">*</span>
                  </label>
                  <DateInput
                    value={formData.dateOfBirth}
                    onChange={(val) => handleChange(syntheticChange('dateOfBirth', val))}
                    required
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <PhoneField
                    id="client-phone"
                    name="phone"
                    label="Телефон"
                    value={formData.phone}
                    onChange={(v) => {
                      setFormData({ ...formData, phone: v });
                      if (phoneError) setPhoneError('');
                    }}
                    error={phoneError}
                    onClearError={() => phoneError && setPhoneError('')}
                    onBlurValidate={() =>
                      setPhoneError(validatePhoneFieldOptional(formData.phone) || '')
                    }
                    hintId="client-phone-hint"
                    inputClassName="py-2"
                  />
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="client-email">
                      Email
                    </label>
                    <input
                      id="client-email"
                      type="email"
                      name="email"
                      autoComplete="email"
                      value={formData.email}
                      onChange={(e) => {
                        handleChange(e);
                        if (emailError) setEmailError('');
                      }}
                      placeholder="name@example.com"
                      className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                        emailError ? 'border-red-500' : 'border-gray-300'
                      }`}
                    />
                    {emailError ? <p className="text-sm text-red-500 mt-1">{emailError}</p> : null}
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Серия паспорта <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      inputMode="numeric"
                      pattern="\d*"
                      name="passportSeries"
                      value={formData.passportSeries}
                      onChange={(e) => { e.target.value = e.target.value.replace(/\D/g, ''); handleChange(e); }}
                      required
                      placeholder="1234"
                      maxLength={4}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Номер паспорта <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      inputMode="numeric"
                      pattern="\d*"
                      name="passportNumber"
                      value={formData.passportNumber}
                      onChange={(e) => { e.target.value = e.target.value.replace(/\D/g, ''); handleChange(e); }}
                      required
                      placeholder="567890"
                      maxLength={6}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Дата выдачи <span className="text-red-500">*</span>
                    </label>
                    <DateInput
                      value={formData.passportIssueDate}
                      onChange={(val) => handleChange(syntheticChange('passportIssueDate', val))}
                      required
                    />
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Кем выдан <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    name="passportIssuedBy"
                    value={formData.passportIssuedBy}
                    onChange={handleChange}
                    required
                    placeholder="Отделением УФМС России..."
                    rows={2}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Адрес регистрации <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    name="registrationAddress"
                    value={formData.registrationAddress}
                    onChange={handleChange}
                    required
                    placeholder="г. Москва, ул. Примерная, д. 1, кв. 1"
                    rows={2}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      ИНН <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      inputMode="numeric"
                      pattern="\d*"
                      name="inn"
                      value={formData.inn}
                      onChange={(e) => { e.target.value = e.target.value.replace(/\D/g, ''); handleChange(e); }}
                      required
                      placeholder="123456789012"
                      maxLength={12}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      СНИЛС <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      inputMode="numeric"
                      name="snils"
                      value={formData.snils}
                      onChange={(e) => { e.target.value = formatSnils(e.target.value); handleChange(e); }}
                      required
                      placeholder="123-456-789 00"
                      maxLength={14}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>
              </div>
            </div>
            
            {/* Legal Data */}
            <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Юридическая информация
              </h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Регион подачи <span className="text-red-500">*</span>
                  </label>
                  <CustomSelect
                    value={formData.region}
                    onChange={(val) => handleChange(syntheticChange('region', val))}
                    groups={REGION_GROUPS.map((group) => ({
                      label: group.district,
                      options: group.regions.map((r) => ({ value: r.name, label: r.name })),
                    }))}
                    placeholder="Выберите регион"
                    size="lg"
                    triggerClassName={regionError ? 'border-red-500' : ''}
                  />
                  {regionError ? <p className="text-sm text-red-500 mt-1">{regionError}</p> : null}
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Арбитражный суд <span className="text-red-500">*</span>
                  </label>
                  {selectedCourt ? (
                    <div className="w-full px-4 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-900">
                      <span className="font-mono text-blue-600 font-medium">{selectedCourt.code}</span>
                      {' — '}
                      {selectedCourt.name}
                    </div>
                  ) : (
                    <div className="w-full px-4 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-400">
                      Выберите регион для определения суда
                    </div>
                  )}
                  <input type="hidden" name="arbitrageCourt" value={formData.arbitrageCourt} />
                </div>
              </div>
            </div>

            {/* Document Upload for Before Court */}
            <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900">
                  Загрузка документов
                </h2>
                <span className="text-sm text-gray-600">
                  {Object.values(documentUploads).flat().length} файлов загружено
                </span>
              </div>
              <p className="text-sm text-gray-600 mb-6">
                Поддерживаемые форматы: JPEG, PNG, PDF, DOC, DOCX. Максимальный размер файла: 10 МБ
              </p>
              
              <div className="space-y-3">
                {requiredDocuments.map((doc) => (
                  <div key={doc.id} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <label className="text-sm font-medium text-gray-900">
                            {doc.label}
                            {doc.required && <span className="text-red-500 ml-1">*</span>}
                          </label>
                          {documentUploads[doc.id]?.length > 0 && (
                            <div className="flex items-center gap-1 px-2 py-0.5 bg-green-50 text-green-700 rounded-full text-xs font-medium">
                              <Check className="w-3 h-3" />
                              {documentUploads[doc.id].length}
                            </div>
                          )}
                        </div>
                        
                        {/* Uploaded files list */}
                        {documentUploads[doc.id]?.length > 0 && (
                          <div className="space-y-1.5 mb-3">
                            {documentUploads[doc.id].map((file, index) => (
                              <div key={index} className="flex items-center gap-2 text-sm bg-gray-50 px-3 py-2 rounded-lg">
                                <FileText className="w-4 h-4 text-gray-400 flex-shrink-0" />
                                <span className="text-gray-700 flex-1 truncate">{file.name}</span>
                                <span className="text-gray-500 text-xs">{formatFileSize(file.size)}</span>
                                <button
                                  type="button"
                                  onClick={() => removeDocument(doc.id, index)}
                                  className="text-red-500 hover:text-red-700 flex-shrink-0"
                                >
                                  <X className="w-4 h-4" />
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                      
                      {/* Upload button */}
                      <div>
                        <input
                          type="file"
                          multiple
                          onChange={(e) => handleDocumentUpload(doc.id, e)}
                          className="hidden"
                          id={`doc-upload-${doc.id}`}
                          accept=".jpg,.jpeg,.png,.pdf,.doc,.docx"
                        />
                        <label
                          htmlFor={`doc-upload-${doc.id}`}
                          className="flex items-center gap-2 px-4 py-2 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-colors cursor-pointer font-medium text-sm whitespace-nowrap"
                        >
                          <Upload className="w-4 h-4" />
                          Загрузить
                        </label>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
        
        {/* File Upload for "in court" type */}
        {formData.type === 'in_court' && (
          <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Загрузка документов
            </h2>
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <input
                  type="file"
                  multiple
                  onChange={handleFileUpload}
                  className="hidden"
                  id="fileUpload"
                />
                <label
                  htmlFor="fileUpload"
                  className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
                >
                  <Upload className="w-5 h-5" />
                  Загрузить файлы
                </label>
              </div>
              {uploadError && (
                <p className="text-sm text-red-500">{uploadError}</p>
              )}
              <div className="space-y-2">
                {uploadedFiles.map((file, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <FileText className="w-5 h-5 text-gray-500" />
                    <p className="text-sm text-gray-700">{file.file.name}</p>
                    <p className="text-sm text-gray-500">
                      ({formatFileSize(file.file.size)})
                    </p>
                    <input
                      type="text"
                      value={file.comment}
                      onChange={(e) => updateFileComment(index, e.target.value)}
                      placeholder="Комментарий"
                      className="w-32 px-2 py-1 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <button
                      type="button"
                      onClick={() => removeFile(index)}
                      className="text-red-500 hover:text-red-700"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
        
        {/* Error */}
        {activeMutation.isError && (
          <div className="mb-4 p-4 bg-red-50 text-red-700 rounded-lg text-sm">
            {isEditMode
              ? 'Ошибка при сохранении изменений. Попробуйте ещё раз.'
              : 'Ошибка при создании клиента. Попробуйте ещё раз.'}
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={activeMutation.isPending || isUploading}
            className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50"
          >
            {activeMutation.isPending || isUploading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Save className="w-5 h-5" />
            )}
            {isUploading
              ? 'Загрузка файлов...'
              : activeMutation.isPending
                ? 'Сохранение...'
                : isEditMode
                  ? 'Сохранить изменения'
                  : 'Создать карточку клиента'}
          </button>
          <Link
            to={isEditMode ? `/dashboard/clients/${id}` : '/dashboard/clients'}
            className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium"
          >
            Отмена
          </Link>

          {isEditMode && (
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              className="ml-auto flex items-center gap-2 px-6 py-3 border border-red-300 text-red-600 rounded-lg hover:bg-red-50 transition-colors font-medium"
            >
              <Trash2 className="w-5 h-5" />
              Удалить клиента
            </button>
          )}
        </div>

        {showDeleteConfirm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4 shadow-2xl">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Удалить клиента?</h3>
              <p className="text-sm text-gray-600 mb-6">
                Карточка клиента <strong>{formData.fullName}</strong> будет удалена. Это действие нельзя отменить.
              </p>
              <div className="flex items-center gap-3 justify-end">
                <button
                  type="button"
                  onClick={() => setShowDeleteConfirm(false)}
                  className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium"
                >
                  Отмена
                </button>
                <button
                  type="button"
                  disabled={deleteMutation.isPending}
                  onClick={() => {
                    if (id) {
                      deleteMutation.mutate(id, {
                        onSuccess: () => {
                          toast.success('Клиент удалён');
                          navigate('/dashboard/clients');
                        },
                        onError: () => {
                          toast.error('Не удалось удалить клиента');
                        },
                      });
                    }
                  }}
                  className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors font-medium disabled:opacity-50"
                >
                  {deleteMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Trash2 className="w-4 h-4" />
                  )}
                  {deleteMutation.isPending ? 'Удаление...' : 'Удалить'}
                </button>
              </div>
            </div>
          </div>
        )}
      </form>
    </div>
  );
}
