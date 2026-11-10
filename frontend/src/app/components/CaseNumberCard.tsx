import { useRef, useState } from 'react';
import { FileText, Loader2, Pencil, Plus, Save, X } from 'lucide-react';
import CaseArbitrLink from './CaseArbitrLink';
import { isBlankCaseNumber, normalizeCaseNumber, validateCaseNumber } from '../utils/courtCase';

interface CaseNumberCardProps {
  /** Текущий номер дела клиента. */
  value?: string | null;
  /**
   * Сохраняет номер. `null` очищает поле.
   * Ошибку нужно пробросить — карточка останется в режиме редактирования.
   */
  onSave: (nextValue: string | null) => Promise<void>;
}

/**
 * Карточка «Номер дела» в кабинете администратора: показывает ссылку на КАД
 * Арбитр и позволяет администратору вписать или исправить номер прямо здесь.
 */
export default function CaseNumberCard({ value, onSave }: CaseNumberCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const normalizedValue = normalizeCaseNumber(value);
  const currentValue = isBlankCaseNumber(value) ? '' : normalizedValue;

  const startEditing = () => {
    setDraft(currentValue);
    setError(null);
    setIsEditing(true);
  };

  const cancelEditing = () => {
    setIsEditing(false);
    setDraft('');
    setError(null);
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isSaving) return;

    const validationError = validateCaseNumber(draft);
    if (validationError) {
      setError(validationError);
      inputRef.current?.focus();
      return;
    }

    const nextValue = normalizeCaseNumber(draft) || null;
    if (nextValue === (currentValue || null)) {
      cancelEditing();
      return;
    }

    setIsSaving(true);
    setError(null);
    try {
      await onSave(nextValue);
      setIsEditing(false);
      setDraft('');
    } catch {
      setError('Не удалось сохранить номер дела. Попробуйте ещё раз.');
    } finally {
      setIsSaving(false);
    }
  };

  if (isEditing) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <form onSubmit={handleSubmit} noValidate>
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center flex-shrink-0">
              <FileText className="w-5 h-5 text-green-600" aria-hidden="true" />
            </div>
            <div className="min-w-0 flex-1">
              <label htmlFor="client-case-number" className="block text-sm text-gray-600">
                Номер дела
              </label>
              <input
                ref={inputRef}
                id="client-case-number"
                type="text"
                value={draft}
                onChange={(event) => {
                  setDraft(event.target.value);
                  if (error) setError(null);
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Escape' && !isSaving) {
                    event.preventDefault();
                    cancelEditing();
                  }
                }}
                placeholder="А66-5146/2026"
                autoFocus
                autoComplete="off"
                spellCheck={false}
                aria-invalid={error ? true : undefined}
                aria-describedby={
                  error
                    ? 'client-case-number-hint client-case-number-error'
                    : 'client-case-number-hint'
                }
                className={`mt-1 w-full rounded-lg border px-3 py-2 font-mono text-sm uppercase text-gray-900 placeholder:normal-case placeholder:font-sans focus:outline-none focus:ring-2 ${
                  error
                    ? 'border-red-400 focus:ring-red-500'
                    : 'border-gray-300 focus:ring-blue-500'
                }`}
              />
              <p id="client-case-number-hint" className="mt-1 text-xs text-gray-500">
                Например: А66-5146/2026. Номер откроется в КАД Арбитр.
              </p>
              {error ? (
                <p id="client-case-number-error" role="alert" className="mt-1 text-sm text-red-600">
                  {error}
                </p>
              ) : null}
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <button
                  type="submit"
                  disabled={isSaving}
                  className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSaving ? (
                    <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Save className="w-4 h-4" aria-hidden="true" />
                  )}
                  {isSaving ? 'Сохранение…' : 'Сохранить'}
                </button>
                <button
                  type="button"
                  onClick={cancelEditing}
                  disabled={isSaving}
                  className="inline-flex items-center justify-center gap-2 rounded-lg bg-gray-100 px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <X className="w-4 h-4" aria-hidden="true" />
                  Отменить
                </button>
              </div>
            </div>
          </div>
        </form>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center flex-shrink-0">
          <FileText className="w-5 h-5 text-green-600" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm text-gray-600">Номер дела</p>
          {currentValue ? (
            <div className="mt-0.5 flex items-center gap-2">
              <span className="min-w-0 truncate font-mono font-semibold text-gray-900">
                <CaseArbitrLink caseNumber={currentValue} />
              </span>
              <button
                type="button"
                onClick={startEditing}
                aria-label="Изменить номер дела"
                title="Изменить номер дела"
                className="flex-shrink-0 rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              >
                <Pencil className="w-4 h-4" aria-hidden="true" />
              </button>
            </div>
          ) : (
            <div className="mt-0.5 flex flex-wrap items-center gap-2">
              <span className="font-semibold text-gray-900">—</span>
              <button
                type="button"
                onClick={startEditing}
                className="inline-flex items-center gap-1 rounded text-sm font-medium text-blue-600 transition-colors hover:text-blue-700 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              >
                <Plus className="w-3.5 h-3.5" aria-hidden="true" />
                Добавить номер
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
