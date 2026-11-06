import { useEffect, useId, useRef, useState } from 'react';
import { Copy, FileText } from 'lucide-react';
import { toast } from 'sonner';
import { SRO, SRO_STATEMENT } from '../data/sro';

export default function SroDetailsCard({ showStatement = false }: { showStatement?: boolean }) {
  const titleId = useId();
  const statementId = useId();
  const statementRef = useRef<HTMLTextAreaElement>(null);
  const [copying, setCopying] = useState(false);
  const [manualCopy, setManualCopy] = useState(false);

  useEffect(() => {
    if (manualCopy) {
      statementRef.current?.focus();
      statementRef.current?.select();
    }
  }, [manualCopy]);

  async function copyStatement() {
    setCopying(true);
    try {
      await navigator.clipboard.writeText(SRO_STATEMENT);
      setManualCopy(false);
      toast.success('Реквизиты скопированы. Вставьте их в заявление');
    } catch {
      setManualCopy(true);
      statementRef.current?.focus();
      statementRef.current?.select();
    } finally {
      setCopying(false);
    }
  }

  return (
    <section aria-labelledby={titleId} className="rounded-2xl border border-blue-200 bg-blue-50 p-5 sm:p-6">
      <div className="flex flex-col gap-6 xl:flex-row xl:items-center">
        <div className="flex min-w-0 flex-1 items-start gap-4">
          <div className="hidden h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-blue-100 text-blue-600 sm:flex">
            <FileText className="h-7 w-7" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <h2 id={titleId} className="text-xl font-semibold text-blue-800 sm:text-2xl">
              СРО для заявления в суд
            </h2>
            <p className="mt-3 font-semibold leading-relaxed text-gray-900">{SRO.name}</p>
            <dl className="mt-3 space-y-1 text-sm leading-relaxed text-gray-600">
              <div><dt className="inline font-medium">Адрес: </dt><dd className="inline">{SRO.address}</dd></div>
              <div><dt className="inline font-medium">ОГРН: </dt><dd className="inline">{SRO.ogrn}</dd></div>
              <div><dt className="inline font-medium">ИНН: </dt><dd className="inline">{SRO.inn}</dd></div>
            </dl>
          </div>
        </div>
        <div className="shrink-0 xl:w-72">
          <button
            type="button"
            onClick={copyStatement}
            disabled={copying}
            className="inline-flex w-full items-center justify-center gap-3 rounded-xl bg-blue-600 px-4 py-4 text-sm font-semibold text-white transition-colors hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 disabled:opacity-60"
          >
            <Copy className="h-5 w-5 shrink-0" aria-hidden="true" />
            {copying ? 'Копирование…' : 'Скопировать для заявления'}
          </button>
          <p className="mt-2 text-center text-xs text-gray-600">Все реквизиты одним нажатием</p>
        </div>
      </div>
      {(showStatement || manualCopy) && (
        <div className="mt-6 border-t border-blue-200 pt-5">
          <label htmlFor={statementId} className="block text-sm font-medium text-gray-900">
            Текст для вставки в заявление
          </label>
          {manualCopy && (
            <p role="status" className="mt-2 text-sm text-gray-700">
              Не удалось скопировать автоматически. Скопируйте выделенный текст вручную.
            </p>
          )}
          <textarea
            id={statementId}
            ref={statementRef}
            readOnly
            value={SRO_STATEMENT}
            onFocus={(event) => event.currentTarget.select()}
            className="mt-2 min-h-48 w-full resize-y rounded-xl border border-blue-200 bg-white p-4 text-sm leading-relaxed text-gray-800 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200 sm:min-h-32"
          />
        </div>
      )}
    </section>
  );
}
