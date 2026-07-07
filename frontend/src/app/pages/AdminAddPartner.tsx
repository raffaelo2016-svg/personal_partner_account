import { ArrowLeft, Eye, EyeOff, Check, CircleDollarSign, CalendarDays } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';
import { createPartner } from '@/app/api/partners';
import { toast } from 'sonner';
import { PhoneField } from '@/app/components/PhoneField';
import { normalizePhoneForApi, validatePhoneField } from '@/app/utils/phone';
import {
  sanitizeInnDigits,
  sanitizeKppDigits,
  validateInnForPartnerType,
  validateKpp,
} from '@/app/utils/innKpp';

export default function AdminAddPartner() {
  const [partnerType, setPartnerType] = useState<'individual' | 'legal' | 'entrepreneur'>('individual');
  const [showPassword, setShowPassword] = useState(false);
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [apiError, setApiError] = useState('');
  const [phoneError, setPhoneError] = useState('');
  const [innError, setInnError] = useState('');
  const [kppError, setKppError] = useState('');
  const [success, setSuccess] = useState(false);
  
  // Common fields
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');

  // Individual fields
  const [lastName, setLastName] = useState('');
  const [firstName, setFirstName] = useState('');
  const [middleName, setMiddleName] = useState('');

  // Financial fields
  const [courtFee, setCourtFee] = useState('');
  const [paymentTermDays, setPaymentTermDays] = useState('');
  const [courtFeeError, setCourtFeeError] = useState('');
  const [paymentTermError, setPaymentTermError] = useState('');

  // Legal entity fields
  const [fullName, setFullName] = useState('');
  const [shortName, setShortName] = useState('');
  const [postalAddress, setPostalAddress] = useState('');
  const [inn, setInn] = useState('');
  const [legalAddress, setLegalAddress] = useState('');
  const [kpp, setKpp] = useState('');

  const calculatePasswordStrength = (pass: string) => {
    if (!pass) return 0;
    let strength = 0;
    if (pass.length >= 8) strength += 25;
    if (pass.match(/[a-z]/)) strength += 25;
    if (pass.match(/[A-Z]/)) strength += 25;
    if (pass.match(/[0-9]/)) strength += 25;
    return strength;
  };

  const passwordStrength = calculatePasswordStrength(password);

  const getStrengthLabel = (strength: number) => {
    if (strength === 0) return '';
    if (strength <= 25) return 'Слабый';
    if (strength <= 50) return 'Средний';
    if (strength <= 75) return 'Хороший';
    return 'Отличный';
  };

  const getStrengthColor = (strength: number) => {
    if (strength === 0) return 'bg-gray-200';
    if (strength <= 25) return 'bg-red-500';
    if (strength <= 50) return 'bg-yellow-500';
    if (strength <= 75) return 'bg-blue-500';
    return 'bg-green-500';
  };

  const changePartnerType = (v: 'individual' | 'legal' | 'entrepreneur') => {
    setPartnerType(v);
    setInnError('');
    setKppError('');
    setInn('');
    setKpp('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setApiError('');
    setInnError('');
    setKppError('');
    setCourtFeeError('');
    setPaymentTermError('');

    const fio = `${lastName} ${firstName} ${middleName}`.trim();
    const directorName =
      partnerType === 'legal' ? (fullName || shortName).trim() : fio;

    if (!email || !password || !directorName) {
      setApiError('Заполните обязательные поля');
      return;
    }

    if (!courtFee) {
      setCourtFeeError('Обязательное поле');
      return;
    }
    if (Number(courtFee) <= 0) {
      setCourtFeeError('Сумма должна быть больше 0');
      return;
    }
    if (!paymentTermDays) {
      setPaymentTermError('Обязательное поле');
      return;
    }
    if (Number(paymentTermDays) <= 0) {
      setPaymentTermError('Срок должен быть больше 0');
      return;
    }

    const phoneErr = validatePhoneField(phone);
    if (phoneErr) {
      setPhoneError(phoneErr);
      return;
    }
    const phoneE164 = normalizePhoneForApi(phone);
    if (!phoneE164) {
      setPhoneError('Проверьте номер телефона');
      return;
    }

    if (partnerType === 'legal') {
      const ie = validateInnForPartnerType(inn, 'legal');
      const ke = validateKpp(kpp);
      if (ie) {
        setInnError(ie);
        return;
      }
      if (ke) {
        setKppError(ke);
        return;
      }
    }
    if (partnerType === 'entrepreneur') {
      const ie = validateInnForPartnerType(inn, 'entrepreneur');
      if (ie) {
        setInnError(ie);
        return;
      }
    }

    setIsSubmitting(true);
    try {
      await createPartner({
        email,
        password,
        partner_type: partnerType,
        company_name: partnerType === 'legal' ? (shortName || fullName) : directorName,
        director_name: directorName,
        inn,
        phone: phoneE164,
        short_name: shortName || undefined,
        full_legal_name: fullName || undefined,
        legal_address: legalAddress || undefined,
        postal_address: postalAddress || undefined,
        kpp: partnerType === 'legal' ? kpp : undefined,
        court_fee_per_client: Math.round(Number(courtFee) * 100),
        payment_term_days: Number(paymentTermDays),
      });
      setSuccess(true);
      toast.success('Партнёр добавлен');
    } catch (err) {
      const axiosErr = err as import('axios').AxiosError<{ code?: string; detail?: unknown }>;
      const data = axiosErr.response?.data;
      const detail = data?.detail;
      const detailObj = detail && typeof detail === 'object' && !Array.isArray(detail)
        ? (detail as Record<string, unknown>)
        : null;

      if (detailObj?.code === 'DUPLICATE_EMAIL') {
        setApiError('Пользователь с таким email уже зарегистрирован.');
      } else if (data?.code === 'VALIDATION_ERROR' && Array.isArray(detail)) {
        const fieldLabels: Record<string, string> = {
          email: 'Email',
          password: 'Пароль',
          phone: 'Телефон',
          inn: 'ИНН',
          kpp: 'КПП',
          company_name: 'Компания',
          director_name: 'ФИО',
          court_fee_per_client: 'Сумма судебных расходов',
          payment_term_days: 'Срок оплаты',
        };
        const generalMessages: string[] = [];
        for (const item of detail as Array<{ loc?: unknown; msg?: unknown }>) {
          const loc = Array.isArray(item.loc) ? (item.loc as unknown[]) : [];
          const msg = typeof item.msg === 'string' ? item.msg : 'Ошибка валидации';
          if (loc.includes('phone')) setPhoneError(msg);
          else if (loc.includes('inn')) setInnError(msg);
          else if (loc.includes('kpp')) setKppError(msg);
          else if (loc.includes('court_fee_per_client')) setCourtFeeError(msg);
          else if (loc.includes('payment_term_days')) setPaymentTermError(msg);
          else {
            const fieldKey = loc.find(
              (part): part is string => typeof part === 'string' && part in fieldLabels,
            );
            const label = fieldKey ? fieldLabels[fieldKey] : null;
            generalMessages.push(label ? `${label}: ${msg}` : msg);
          }
        }
        if (generalMessages.length > 0) {
          setApiError(generalMessages.join('; '));
        } else {
          setApiError('Проверьте корректность заполненных полей.');
        }
      } else {
        setApiError('Ошибка при регистрации. Попробуйте ещё раз.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (success) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="bg-white rounded-2xl shadow-xl p-8 max-w-md w-full text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Check className="w-8 h-8 text-green-600" />
          </div>
          <h2 className="text-2xl font-semibold text-gray-900 mb-2">Партнёр добавлен</h2>
          <p className="text-gray-600 mb-6">
            Данные партнёра сохранены. Сумма судебных расходов и срок оплаты установлены администратором.
          </p>
          <Link
            to="/admin/partners"
            className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            Вернуться к партнёрам
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          to="/admin/partners"
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5 text-gray-600" />
        </Link>
        <h1 className="text-3xl font-semibold text-gray-900">Добавление партнёра</h1>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        {/* Partner Type Selection */}
        <div className="mb-8">
          <div className="flex gap-6">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="partnerType"
                value="individual"
                checked={partnerType === 'individual'}
                onChange={() => changePartnerType('individual')}
                className="w-4 h-4 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm font-medium text-gray-900">Физическое лицо</span>
            </label>
            
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="partnerType"
                value="legal"
                checked={partnerType === 'legal'}
                onChange={() => changePartnerType('legal')}
                className="w-4 h-4 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm font-medium text-gray-900">Юридическое лицо</span>
            </label>
            
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="partnerType"
                value="entrepreneur"
                checked={partnerType === 'entrepreneur'}
                onChange={() => changePartnerType('entrepreneur')}
                className="w-4 h-4 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm font-medium text-gray-900">ИП</span>
            </label>
          </div>
        </div>

        {/* Email, Phone Row */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              E-mail
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="test@email.com"
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <PhoneField
            id="register-phone"
            name="phone"
            label={
              <>
                Телефон <span className="text-red-500">*</span>
              </>
            }
            value={phone}
            onChange={setPhone}
            error={phoneError}
            onClearError={() => phoneError && setPhoneError('')}
            onBlurValidate={() => setPhoneError(validatePhoneField(phone) || '')}
            required
            hintId="register-phone-hint"
            inputClassName="py-2.5"
          />
        </div>

        {/* Conditional Fields Based on Partner Type */}
        {partnerType === 'individual' && (
          <>
            {/* Name Fields Row */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Фамилия
                </label>
                <input
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Имя
                </label>
                <input
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Отчество
                </label>
                <input
                  type="text"
                  value={middleName}
                  onChange={(e) => setMiddleName(e.target.value)}
                  placeholder=""
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          </>
        )}

        {partnerType === 'legal' && (
          <>
            {/* Legal Entity Name Fields */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Полное наименование
                </label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Сокращенное наименование
                </label>
                <input
                  type="text"
                  value={shortName}
                  onChange={(e) => setShortName(e.target.value)}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50"
                />
              </div>
            </div>

            {/* Address and INN Fields */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Почтовый адрес
                </label>
                <input
                  type="text"
                  value={postalAddress}
                  onChange={(e) => setPostalAddress(e.target.value)}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  ИНН <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  inputMode="numeric"
                  autoComplete="off"
                  value={inn}
                  onChange={(e) => {
                    setInn(sanitizeInnDigits(e.target.value, 10));
                    if (innError) setInnError('');
                  }}
                  placeholder="7736050003"
                  maxLength={10}
                  aria-invalid={!!innError}
                  className={`w-full px-4 py-2.5 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50 ${
                    innError ? 'border-red-500' : 'border-gray-300'
                  }`}
                />
                <p className="text-xs text-gray-500 mt-1">
                  10 цифр — как в выписке ЕГРЮЛ.
                </p>
                {innError && <p className="text-sm text-red-500 mt-1">{innError}</p>}
              </div>
            </div>

            {/* Legal Address and KPP Fields */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Юридический адрес
                </label>
                <input
                  type="text"
                  value={legalAddress}
                  onChange={(e) => setLegalAddress(e.target.value)}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  КПП <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  inputMode="numeric"
                  autoComplete="off"
                  value={kpp}
                  onChange={(e) => {
                    setKpp(sanitizeKppDigits(e.target.value));
                    if (kppError) setKppError('');
                  }}
                  placeholder="770401001"
                  maxLength={9}
                  aria-invalid={!!kppError}
                  className={`w-full px-4 py-2.5 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50 ${
                    kppError ? 'border-red-500' : 'border-gray-300'
                  }`}
                />
                <p className="text-xs text-gray-500 mt-1">9 цифр; позиции 5–6 — код причины постановки на учёт (01–99).</p>
                {kppError && <p className="text-sm text-red-500 mt-1">{kppError}</p>}
              </div>
            </div>
          </>
        )}

        {partnerType === 'entrepreneur' && (
          <>
            {/* Entrepreneur Name Fields */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Фамилия
                </label>
                <input
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Имя
                </label>
                <input
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Отчество
                </label>
                <input
                  type="text"
                  value={middleName}
                  onChange={(e) => setMiddleName(e.target.value)}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50"
                />
              </div>
            </div>

            {/* INN Field */}
            <div className="mb-6 max-w-md">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                ИНН <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                inputMode="numeric"
                autoComplete="off"
                value={inn}
                onChange={(e) => {
                  setInn(sanitizeInnDigits(e.target.value, 12));
                  if (innError) setInnError('');
                }}
                placeholder="500100732259"
                maxLength={12}
                aria-invalid={!!innError}
                className={`w-full px-4 py-2.5 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50 ${
                  innError ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              <p className="text-xs text-gray-500 mt-1">
                12 цифр — как в свидетельстве ИП.
              </p>
              {innError && <p className="text-sm text-red-500 mt-1">{innError}</p>}
            </div>
          </>
        )}

        {/* Password Field */}
        <div className="mb-6 max-w-md">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Пароль
          </label>
          <div className="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••"
              className="w-full px-4 py-2.5 pr-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>

          {/* Password Strength Indicator */}
          {password && (
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-gray-500">Стойкость пароля</span>
                <span className={`font-medium ${
                  passwordStrength <= 25 ? 'text-red-600' :
                  passwordStrength <= 50 ? 'text-yellow-600' :
                  passwordStrength <= 75 ? 'text-blue-600' : 'text-green-600'
                }`}>
                  {getStrengthLabel(passwordStrength)}
                </span>
              </div>
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-300 ${getStrengthColor(passwordStrength)}`}
                  style={{ width: `${passwordStrength}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Financial Parameters */}
        <div className="space-y-5 mb-6">
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-5">
            <div className="flex items-start gap-3 mb-3">
              <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
                <CircleDollarSign className="w-5 h-5 text-white" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-gray-900">
                  Сумма судебных расходов
                </h3>
                <p className="text-sm text-gray-600 mt-0.5">
                  Укажите сумму судебных расходов для данного партнёра. Эта сумма будет автоматически умножена на количество должников.
                </p>
              </div>
            </div>
            <input
              type="number"
              value={courtFee}
              onChange={(e) => {
                setCourtFee(e.target.value);
                if (courtFeeError) setCourtFeeError('');
              }}
              placeholder="Введите сумму в рублях"
              min="1"
              className={`w-full max-w-sm px-4 py-3 border rounded-lg bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                courtFeeError ? 'border-red-500' : 'border-gray-300'
              }`}
            />
            {courtFeeError ? (
              <p className="text-sm text-red-500 mt-2">{courtFeeError}</p>
            ) : (
              <p className="text-sm text-orange-600 mt-2 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-orange-500 inline-block flex-shrink-0" />
                Обязательное поле для расчета платежей
              </p>
            )}
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-xl p-5">
            <div className="flex items-start gap-3 mb-3">
              <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
                <CalendarDays className="w-5 h-5 text-white" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-gray-900">
                  Срок оплаты
                </h3>
                <p className="text-sm text-gray-600 mt-0.5">
                  Укажите срок оплаты (в днях) с даты вынесения судом определения о назначении процедуры банкротства.
                </p>
              </div>
            </div>
            <input
              type="number"
              value={paymentTermDays}
              onChange={(e) => {
                setPaymentTermDays(e.target.value);
                if (paymentTermError) setPaymentTermError('');
              }}
              placeholder="Введите количество дней"
              min="1"
              className={`w-full max-w-sm px-4 py-3 border rounded-lg bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                paymentTermError ? 'border-red-500' : 'border-gray-300'
              }`}
            />
            {paymentTermError ? (
              <p className="text-sm text-red-500 mt-2">{paymentTermError}</p>
            ) : (
              <p className="text-sm text-orange-600 mt-2 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-orange-500 inline-block flex-shrink-0" />
                Обязательное поле для расчета платежей
              </p>
            )}
          </div>
        </div>

        {/* Error */}
        {apiError && (
          <div className="mb-4 p-4 bg-red-50 text-red-700 rounded-lg text-sm">
            {apiError}
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-3 pt-4">
          <button
            type="submit"
            disabled={isSubmitting}
            className="px-8 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? 'Сохранение...' : 'Добавить партнера'}
          </button>
          <Link
            to="/admin/partners"
            className="px-8 py-3 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
          >
            Отменить
          </Link>
        </div>
      </form>
    </div>
  );
}
