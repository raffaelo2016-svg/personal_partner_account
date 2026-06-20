import { PHONE_HINT_RU, PHONE_INPUT_MAX, processPhoneInputForDisplay } from '@/app/utils/phone';

type PhoneFieldProps = {
  id: string;
  name?: string;
  label: React.ReactNode;
  value: string;
  onChange: (value: string) => void;
  /** Сообщение об ошибке (после submit или blur) */
  error?: string;
  /** Очистить ошибку при вводе */
  onClearError?: () => void;
  /** Валидация при уходе с поля (например, phoneErrorAfterBlur из utils/phone) */
  onBlurValidate?: () => void;
  required?: boolean;
  hintId: string;
  className?: string;
  inputClassName?: string;
};

/** Единое поле телефона: санитизация, подсказка, a11y. */
export function PhoneField({
  id,
  name,
  label,
  value,
  onChange,
  error,
  onClearError,
  onBlurValidate,
  required = false,
  hintId,
  className = '',
  inputClassName = '',
}: PhoneFieldProps) {
  return (
    <div className={className}>
      <label className="block text-sm font-medium text-gray-700 mb-2" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        type="tel"
        name={name}
        inputMode="tel"
        autoComplete="tel"
        enterKeyHint="done"
        spellCheck={false}
        value={value}
        onChange={(e) => {
          onChange(processPhoneInputForDisplay(e.target.value));
          onClearError?.();
        }}
        onBlur={() => onBlurValidate?.()}
        placeholder="+7 (900) 123-45-67"
        maxLength={PHONE_INPUT_MAX}
        aria-invalid={!!error}
        aria-describedby={hintId}
        aria-required={required || undefined}
        className={`w-full px-4 py-2.5 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
          error ? 'border-red-500' : 'border-gray-300'
        } ${inputClassName}`}
      />
      <p id={hintId} className="text-xs text-gray-500 mt-1">
        {PHONE_HINT_RU}
      </p>
      {error ? <p className="text-sm text-red-500 mt-1">{error}</p> : null}
    </div>
  );
}
