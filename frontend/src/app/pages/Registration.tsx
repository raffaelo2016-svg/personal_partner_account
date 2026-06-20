import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import { ArrowRight, Check, Loader2, CircleDollarSign, CalendarDays } from 'lucide-react';
import logo from '@/assets/logo-color.svg';
import { PhoneField } from '@/app/components/PhoneField';
import { registerApi } from '../api/auth';
import { normalizePhoneForApi, validatePhoneField } from '../utils/phone';
import {
  flattenZodErrors,
  registrationStep1Schema,
  registrationStep2Schema,
} from '../schemas/registration';

// Yandex SmartCaptcha глобальный объект, который подгружает <script> в index.html.
declare global {
  interface Window {
    smartCaptcha?: {
      render: (
        container: HTMLElement | string,
        options: { sitekey: string; callback?: (token: string) => void; hl?: string },
      ) => number;
      reset: (widgetId?: number) => void;
      destroy: (widgetId: number) => void;
    };
  }
}

const CAPTCHA_SITEKEY = import.meta.env.VITE_YANDEX_CAPTCHA_CLIENT_KEY as string | undefined;
const CAPTCHA_ENABLED = Boolean(CAPTCHA_SITEKEY);

export default function Registration() {
  const [step, setStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [apiError, setApiError] = useState('');
  const [captchaToken, setCaptchaToken] = useState('');
  const captchaContainerRef = useRef<HTMLDivElement | null>(null);
  const captchaWidgetIdRef = useRef<number | null>(null);
  const [formData, setFormData] = useState({
    // Данные компании
    companyName: '',
    inn: '',
    ogrn: '',
    legalAddress: '',
    
    // Финансовые параметры
    courtFee: '',
    paymentTermDays: '',
    
    // Контактное лицо
    contactName: '',
    contactPhone: '',
    contactEmail: '',
    
    // Учетные данные
    password: '',
    confirmPassword: '',
    
    // Согласия
    agreeTerms: false,
    agreePersonalData: false,
  });
  
  const [errors, setErrors] = useState<Record<string, string>>({});
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value, type } = e.target;
    const checked = (e.target as HTMLInputElement).checked;
    
    setFormData({
      ...formData,
      [name]: type === 'checkbox' ? checked : value,
    });
    
    // Очистить ошибку при изменении поля
    if (errors[name]) {
      setErrors({ ...errors, [name]: '' });
    }
  };
  
  const validateStep1 = () => {
    const result = registrationStep1Schema.safeParse({
      companyName: formData.companyName,
      inn: formData.inn,
      ogrn: formData.ogrn,
      legalAddress: formData.legalAddress,
      courtFee: formData.courtFee,
      paymentTermDays: formData.paymentTermDays,
    });
    const newErrors = flattenZodErrors(result);
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validateStep2 = () => {
    const result = registrationStep2Schema.safeParse({
      contactName: formData.contactName,
      contactEmail: formData.contactEmail,
      password: formData.password,
      confirmPassword: formData.confirmPassword,
      agreeTerms: formData.agreeTerms,
      agreePersonalData: formData.agreePersonalData,
    });
    const newErrors = flattenZodErrors(result);
    const phoneErr = validatePhoneField(formData.contactPhone);
    if (phoneErr) newErrors.contactPhone = phoneErr;
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };
  
  const handleNextStep = () => {
    if (step === 1 && validateStep1()) {
      setStep(2);
    }
  };

  // Рендер капчи после появления step 2 в DOM. Скрипт может ещё не загрузиться —
  // тогда поллим window.smartCaptcha раз в 200 мс.
  useEffect(() => {
    if (step !== 2 || !CAPTCHA_ENABLED || captchaWidgetIdRef.current !== null) return;
    let cancelled = false;
    const tryRender = () => {
      if (cancelled) return;
      if (!captchaContainerRef.current || !window.smartCaptcha) {
        setTimeout(tryRender, 200);
        return;
      }
      const id = window.smartCaptcha.render(captchaContainerRef.current, {
        sitekey: CAPTCHA_SITEKEY!,
        hl: 'ru',
        callback: (token: string) => setCaptchaToken(token),
      });
      captchaWidgetIdRef.current = id;
    };
    tryRender();
    return () => {
      cancelled = true;
    };
  }, [step]);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateStep2()) return;

    const phoneE164 = normalizePhoneForApi(formData.contactPhone);
    if (!phoneE164) {
      setErrors((prev) => ({ ...prev, contactPhone: 'Проверьте номер телефона' }));
      return;
    }

    if (CAPTCHA_ENABLED && !captchaToken) {
      setApiError('Подтвердите, что вы не робот.');
      return;
    }

    setIsSubmitting(true);
    setApiError('');
    try {
      await registerApi({
        email: formData.contactEmail,
        password: formData.password,
        company_name: formData.companyName,
        director_name: formData.contactName,
        inn: formData.inn,
        phone: phoneE164,
        court_fee_per_client: Math.round(Number(formData.courtFee) * 100),
        payment_term_days: Number(formData.paymentTermDays),
        captcha_token: CAPTCHA_ENABLED ? captchaToken : undefined,
      });
      setStep(3);
    } catch (err) {
      const axiosErr = err as import('axios').AxiosError<{ code?: string; detail?: unknown }>;
      const data = axiosErr.response?.data;
      const detail = data?.detail as { code?: string; loc?: unknown; msg?: string } | unknown;
      const detailObj = detail && typeof detail === 'object' ? (detail as Record<string, unknown>) : null;
      if (detailObj?.code === 'DUPLICATE_EMAIL') {
        setApiError('Пользователь с таким email уже зарегистрирован.');
      } else if (detailObj?.code === 'CAPTCHA_REQUIRED' || detailObj?.code === 'CAPTCHA_INVALID') {
        setApiError('Подтвердите, что вы не робот, и повторите отправку.');
        setCaptchaToken('');
        if (captchaWidgetIdRef.current !== null) {
          window.smartCaptcha?.reset(captchaWidgetIdRef.current);
        }
      } else if (data?.code === 'VALIDATION_ERROR' && Array.isArray(detail)) {
        const fieldErrors: Record<string, string> = {};
        for (const item of detail) {
          const loc = Array.isArray(item.loc) ? item.loc : [];
          const msg = typeof item.msg === 'string' ? item.msg : 'Ошибка валидации';
          if (loc.includes('phone')) fieldErrors.contactPhone = msg;
          else if (loc.includes('email')) fieldErrors.contactEmail = msg;
          else if (loc.includes('director_name')) fieldErrors.contactName = msg;
          else if (loc.includes('company_name')) fieldErrors.companyName = msg;
          else if (loc.includes('inn')) fieldErrors.inn = msg;
          else if (loc.includes('password')) fieldErrors.password = msg;
        }
        const mapped = Object.keys(fieldErrors).length;
        setErrors((prev) => ({ ...prev, ...fieldErrors }));
        setApiError(
          mapped === 0
            ? (typeof detail[0]?.msg === 'string' ? detail[0].msg : 'Ошибка валидации')
            : mapped < detail.length
              ? 'Проверьте корректность заполненных полей.'
              : '',
        );
      } else {
        setApiError('Ошибка при регистрации. Попробуйте ещё раз.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };
  
  if (step === 3) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-xl p-8 max-w-md w-full text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Check className="w-8 h-8 text-green-600" />
          </div>
          <h2 className="text-2xl font-semibold text-gray-900 mb-2">
            Заявка отправлена!
          </h2>
          <p className="text-gray-600 mb-6">
            Ваша заявка на регистрацию успешно отправлена. Мы свяжемся с вами в течение 24 часов для подтверждения.
          </p>
          <Link
            to="/"
            className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Вернуться на главную
          </Link>
        </div>
      </div>
    );
  }
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <Link to="/" className="flex items-center">
              <img src={logo} alt="ЮРИТЕХ" className="h-10 w-auto" />
            </Link>
            <Link to="/login" className="text-sm text-gray-600 hover:text-gray-900">
              Уже есть аккаунт? <span className="text-blue-600 font-medium">Войти</span>
            </Link>
          </div>
        </div>
      </div>
      
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Progress */}
        <div className="mb-8">
          <div className="flex items-center justify-center gap-4 mb-4">
            <div className="flex items-center">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center font-medium ${
                step >= 1 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'
              }`}>
                1
              </div>
              <span className={`ml-2 text-sm font-medium ${
                step >= 1 ? 'text-gray-900' : 'text-gray-500'
              }`}>
                Данные компании
              </span>
            </div>
            <div className={`w-20 h-1 ${step >= 2 ? 'bg-blue-600' : 'bg-gray-200'}`} />
            <div className="flex items-center">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center font-medium ${
                step >= 2 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'
              }`}>
                2
              </div>
              <span className={`ml-2 text-sm font-medium ${
                step >= 2 ? 'text-gray-900' : 'text-gray-500'
              }`}>
                Контактные данные
              </span>
            </div>
          </div>
        </div>
        
        <div className="bg-white rounded-2xl shadow-xl p-8">
          {step === 1 && (
            <div>
              <h2 className="text-2xl font-semibold text-gray-900 mb-2">
                Регистрация партнера
              </h2>
              <p className="text-gray-600 mb-8">
                Заполните информацию о вашей юридической компании
              </p>
              
              <div className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Название компании <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    name="companyName"
                    value={formData.companyName}
                    onChange={handleChange}
                    placeholder='ООО "Юридическая компания"'
                    className={`w-full px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      errors.companyName ? 'border-red-500' : 'border-gray-300'
                    }`}
                  />
                  {errors.companyName && (
                    <p className="text-sm text-red-500 mt-1">{errors.companyName}</p>
                  )}
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
                      placeholder="1234567890"
                      maxLength={10}
                      className={`w-full px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                        errors.inn ? 'border-red-500' : 'border-gray-300'
                      }`}
                    />
                    {errors.inn && (
                      <p className="text-sm text-red-500 mt-1">{errors.inn}</p>
                    )}
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      ОГРН <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      name="ogrn"
                      value={formData.ogrn}
                      onChange={handleChange}
                      placeholder="1234567890123"
                      maxLength={13}
                      className={`w-full px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                        errors.ogrn ? 'border-red-500' : 'border-gray-300'
                      }`}
                    />
                    {errors.ogrn && (
                      <p className="text-sm text-red-500 mt-1">{errors.ogrn}</p>
                    )}
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Юридический адрес <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    name="legalAddress"
                    value={formData.legalAddress}
                    onChange={handleChange}
                    placeholder="г. Москва, ул. Примерная, д. 1, офис 100"
                    rows={3}
                    className={`w-full px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      errors.legalAddress ? 'border-red-500' : 'border-gray-300'
                    }`}
                  />
                  {errors.legalAddress && (
                    <p className="text-sm text-red-500 mt-1">{errors.legalAddress}</p>
                  )}
                </div>
              </div>

              {/* Финансовые параметры */}
              <div className="space-y-5 mt-6">
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
                    name="courtFee"
                    value={formData.courtFee}
                    onChange={handleChange}
                    placeholder="Введите сумму в рублях"
                    min="1"
                    className={`w-full max-w-sm px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      errors.courtFee ? 'border-red-500' : 'border-gray-300'
                    }`}
                  />
                  {errors.courtFee ? (
                    <p className="text-sm text-red-500 mt-2">{errors.courtFee}</p>
                  ) : (
                    <p className="text-sm text-blue-600 mt-2 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-600 inline-block" />
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
                    name="paymentTermDays"
                    value={formData.paymentTermDays}
                    onChange={handleChange}
                    placeholder="Введите количество дней"
                    min="1"
                    className={`w-full max-w-sm px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      errors.paymentTermDays ? 'border-red-500' : 'border-gray-300'
                    }`}
                  />
                  {errors.paymentTermDays ? (
                    <p className="text-sm text-red-500 mt-2">{errors.paymentTermDays}</p>
                  ) : (
                    <p className="text-sm text-blue-600 mt-2 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-600 inline-block" />
                      Обязательное поле для расчета платежей
                    </p>
                  )}
                </div>
              </div>
              
              <div className="mt-8 flex justify-between">
                <Link
                  to="/"
                  className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium"
                >
                  Отмена
                </Link>
                <button
                  type="button"
                  onClick={handleNextStep}
                  className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
                >
                  Продолжить
                  <ArrowRight className="w-5 h-5" />
                </button>
              </div>
            </div>
          )}
          
          {step === 2 && (
            <form onSubmit={handleSubmit}>
              <h2 className="text-2xl font-semibold text-gray-900 mb-2">
                Контактные данные
              </h2>
              <p className="text-gray-600 mb-8">
                Укажите данные контактного лица и создайте учетную запись
              </p>
              
              <div className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    ФИО контактного лица <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    name="contactName"
                    value={formData.contactName}
                    onChange={handleChange}
                    placeholder="Иванов Иван Иванович"
                    className={`w-full px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      errors.contactName ? 'border-red-500' : 'border-gray-300'
                    }`}
                  />
                  {errors.contactName && (
                    <p className="text-sm text-red-500 mt-1">{errors.contactName}</p>
                  )}
                </div>
                
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="sm:col-span-2">
                    <PhoneField
                      id="contactPhone"
                      name="contactPhone"
                      label={
                        <>
                          Телефон <span className="text-red-500">*</span>
                        </>
                      }
                      value={formData.contactPhone}
                      onChange={(v) => setFormData({ ...formData, contactPhone: v })}
                      error={errors.contactPhone}
                      onClearError={() =>
                        errors.contactPhone && setErrors({ ...errors, contactPhone: '' })
                      }
                      onBlurValidate={() =>
                        setErrors((prev) => ({
                          ...prev,
                          contactPhone: validatePhoneField(formData.contactPhone) || '',
                        }))
                      }
                      required
                      hintId="contactPhone-hint"
                      inputClassName="py-3"
                    />
                  </div>

                  <div className="sm:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Email <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="email"
                      name="contactEmail"
                      value={formData.contactEmail}
                      onChange={handleChange}
                      placeholder="partner@example.com"
                      className={`w-full px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                        errors.contactEmail ? 'border-red-500' : 'border-gray-300'
                      }`}
                    />
                    {errors.contactEmail && (
                      <p className="text-sm text-red-500 mt-1">{errors.contactEmail}</p>
                    )}
                  </div>
                </div>
                
                <div className="border-t border-gray-200 pt-6 mt-6">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">
                    Создание учетной записи
                  </h3>
                  
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Пароль <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="password"
                        name="password"
                        value={formData.password}
                        onChange={handleChange}
                        placeholder="Минимум 8 символов"
                        className={`w-full px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                          errors.password ? 'border-red-500' : 'border-gray-300'
                        }`}
                      />
                      {errors.password && (
                        <p className="text-sm text-red-500 mt-1">{errors.password}</p>
                      )}
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Подтверждение пароля <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="password"
                        name="confirmPassword"
                        value={formData.confirmPassword}
                        onChange={handleChange}
                        placeholder="Повторите пароль"
                        className={`w-full px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                          errors.confirmPassword ? 'border-red-500' : 'border-gray-300'
                        }`}
                      />
                      {errors.confirmPassword && (
                        <p className="text-sm text-red-500 mt-1">{errors.confirmPassword}</p>
                      )}
                    </div>
                  </div>
                </div>
                
                <div className="border-t border-gray-200 pt-6 space-y-3">
                  <label className="flex items-start gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      name="agreeTerms"
                      checked={formData.agreeTerms}
                      onChange={handleChange}
                      className="mt-1"
                    />
                    <span className="text-sm text-gray-700">
                      Я согласен с{' '}
                      <a href="#" className="text-blue-600 hover:underline">
                        условиями использования
                      </a>{' '}
                      и{' '}
                      <a href="#" className="text-blue-600 hover:underline">
                        политикой конфиденциальности
                      </a>
                      <span className="text-red-500">*</span>
                    </span>
                  </label>
                  {errors.agreeTerms && (
                    <p className="text-sm text-red-500">{errors.agreeTerms}</p>
                  )}
                  
                  <label className="flex items-start gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      name="agreePersonalData"
                      checked={formData.agreePersonalData}
                      onChange={handleChange}
                      className="mt-1"
                    />
                    <span className="text-sm text-gray-700">
                      Я даю согласие на обработку персональных данных
                      <span className="text-red-500">*</span>
                    </span>
                  </label>
                  {errors.agreePersonalData && (
                    <p className="text-sm text-red-500">{errors.agreePersonalData}</p>
                  )}
                </div>
              </div>
              
              {CAPTCHA_ENABLED && (
                <div className="mt-6 flex justify-center">
                  <div ref={captchaContainerRef} />
                </div>
              )}

              {apiError && (
                <div className="mt-4 p-4 bg-red-50 text-red-700 rounded-lg text-sm">
                  {apiError}
                </div>
              )}

              <div className="mt-8 flex justify-between">
                <button
                  type="button"
                  onClick={() => setStep(1)}
                  className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium"
                >
                  Назад
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || (CAPTCHA_ENABLED && !captchaToken)}
                  className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSubmitting && <Loader2 className="w-5 h-5 animate-spin" />}
                  {isSubmitting ? 'Отправка...' : 'Зарегистрироваться'}
                </button>
              </div>
            </form>
          )}
        </div>
        
        <p className="text-center text-sm text-gray-600 mt-6">
          Нужна помощь?{' '}
          <a href="#" className="text-blue-600 hover:underline font-medium">
            Свяжитесь с нами
          </a>
        </p>
      </div>
    </div>
  );
}