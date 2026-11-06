import { Link } from 'react-router';
import {
  ArrowRight,
  Building2,
  Check,
  Circle,
  FileArchive,
  FileText,
  ListChecks,
  Loader2,
  PackageCheck,
  WandSparkles,
} from 'lucide-react';
import { toast } from 'sonner';
import type { ClientData } from '../api/clients';
import type { UploadedFileResponse } from '../api/upload';
import { useChangeClientStatus } from '../hooks/useClients';

interface Props {
  client: ClientData;
  files: UploadedFileResponse[];
}

const REQUIRED_PROFILE_FIELDS: Array<{ key: keyof ClientData; label: string }> = [
  { key: 'date_of_birth', label: 'Дата рождения' },
  { key: 'passport_series', label: 'Серия паспорта' },
  { key: 'passport_number', label: 'Номер паспорта' },
  { key: 'passport_issue_date', label: 'Дата выдачи паспорта' },
  { key: 'passport_issued_by', label: 'Кем выдан паспорт' },
  { key: 'registration_address', label: 'Адрес регистрации' },
  { key: 'inn', label: 'ИНН' },
  { key: 'snils', label: 'СНИЛС' },
  { key: 'arbitrage_court', label: 'Арбитражный суд' },
];

const BASE_FILES = [
  { types: ['passport'], label: 'Копия паспорта' },
  { types: ['snils'], label: 'СНИЛС' },
  { types: ['inn_certificate'], label: 'Документ с ИНН' },
] as const;

const GENERATED_DOCUMENTS = [
  {
    title: 'Заявление в суд',
    description: 'Персональные данные, обстоятельства, доходы, семейное положение и сведения для суда.',
    icon: FileText,
  },
  {
    title: 'Список кредиторов и должников',
    description: 'Кредиторы, суммы обязательств, договоры, адреса и сведения о должниках гражданина.',
    icon: ListChecks,
  },
  {
    title: 'Опись имущества',
    description: 'Недвижимость, транспорт, счета, доли, ценные бумаги и иное имущество.',
    icon: FileArchive,
  },
] as const;

function hasValue(value: ClientData[keyof ClientData]) {
  return value !== null && value !== undefined && String(value).trim().length > 0;
}

export default function ClientDocumentPreparation({ client, files }: Props) {
  const changeStatus = useChangeClientStatus();
  const mode = client.document_preparation_mode ?? 'uritech';
  const completedFields = REQUIRED_PROFILE_FIELDS.filter(({ key }) => hasValue(client[key])).length;
  const completedFiles = BASE_FILES.filter(({ types }) =>
    files.some((file) => (types as readonly string[]).includes(file.document_type)),
  ).length;
  const totalChecks = REQUIRED_PROFILE_FIELDS.length + BASE_FILES.length;
  const completedChecks = completedFields + completedFiles;
  const readiness = Math.round((completedChecks / totalChecks) * 100);
  const canTransfer = client.status === 'documents_collection';

  const handleTransfer = () => {
    if (!canTransfer) return;
    changeStatus.mutate(
      {
        clientId: client.id,
        status: 'documents_formation',
        comment: 'Партнёр передал базовый комплект документов на подготовку ЮРИТЕХ',
      },
      {
        onSuccess: () => toast.success('Карточка передана ЮРИТЕХ на подготовку документов'),
        onError: () => toast.error('Не удалось передать карточку. Попробуйте ещё раз.'),
      },
    );
  };

  return (
    <section id="court-documents" className="mb-6 overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
      <div className="flex flex-col gap-4 border-b border-gray-200 bg-gradient-to-r from-slate-50 to-blue-50 px-6 py-5 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium text-blue-700">
            {mode === 'uritech' ? (
              <Building2 className="h-4 w-4" aria-hidden="true" />
            ) : (
              <WandSparkles className="h-4 w-4" aria-hidden="true" />
            )}
            {mode === 'uritech' ? 'Подготовка командой ЮРИТЕХ' : 'Самостоятельная подготовка партнёром'}
          </div>
          <h2 className="mt-1 text-xl font-semibold text-gray-950">Документы для подачи в суд</h2>
          <p className="mt-1 max-w-3xl text-sm text-gray-600">
            {mode === 'uritech'
              ? 'Загрузите базовые документы клиента и передайте карточку команде ЮРИТЕХ.'
              : 'Проверьте данные клиента, затем заполните сведения для каждого из трёх документов.'}
          </p>
        </div>
        <Link
          to={`/dashboard/clients/${client.id}/edit#document-preparation`}
          className="inline-flex items-center justify-center gap-2 self-start rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Изменить способ
        </Link>
      </div>

      <div className="p-6">
        <div className="mb-6 grid gap-4 sm:grid-cols-[1fr_auto] sm:items-center">
          <div>
            <div className="mb-2 flex items-center justify-between text-sm">
              <span className="font-medium text-gray-800">Готовность исходных данных</span>
              <span className="font-semibold text-blue-700">{readiness}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-gray-100">
              <div
                className="h-full rounded-full bg-blue-600 transition-[width]"
                style={{ width: `${readiness}%` }}
                aria-hidden="true"
              />
            </div>
            <p className="mt-2 text-xs text-gray-500">
              Заполнено и загружено {completedChecks} из {totalChecks} базовых пунктов. Полный состав зависит от ситуации клиента.
            </p>
          </div>
          <Link
            to={`/dashboard/clients/${client.id}/edit#client-files`}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-2.5 text-sm font-medium text-blue-700 hover:bg-blue-100"
          >
            Дополнить данные
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </div>

        {mode === 'uritech' ? (
          <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
            <div>
              <h3 className="font-semibold text-gray-900">Базовый комплект</h3>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {BASE_FILES.map((item) => {
                  const complete = files.some((file) =>
                    (item.types as readonly string[]).includes(file.document_type),
                  );
                  return (
                    <div key={item.label} className="flex items-center gap-3 rounded-lg border border-gray-200 px-4 py-3">
                      {complete ? (
                        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-green-100 text-green-700">
                          <Check className="h-4 w-4" aria-hidden="true" />
                        </span>
                      ) : (
                        <Circle className="h-6 w-6 text-gray-300" aria-hidden="true" />
                      )}
                      <span className="text-sm text-gray-800">{item.label}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="rounded-xl border border-blue-200 bg-blue-50 p-5">
              <PackageCheck className="h-8 w-8 text-blue-700" aria-hidden="true" />
              <h3 className="mt-3 font-semibold text-gray-950">
                {canTransfer ? 'Передайте карточку в работу' : 'Карточка уже передана в работу'}
              </h3>
              <p className="mt-1 text-sm leading-5 text-gray-600">
                {canTransfer
                  ? 'После передачи статус изменится на «Формирование документов». Недостающие сведения можно будет добавить позднее.'
                  : 'Текущий этап отражается в шкале выше. Дополнительные файлы можно загружать в карточку клиента.'}
              </p>
              <button
                type="button"
                onClick={handleTransfer}
                disabled={!canTransfer || changeStatus.isPending}
                className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {changeStatus.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
                {canTransfer ? 'Передать ЮРИТЕХ' : 'Передано ЮРИТЕХ'}
              </button>
            </div>
          </div>
        ) : (
          <div>
            <div className="grid gap-4 lg:grid-cols-3">
              {GENERATED_DOCUMENTS.map((document, index) => {
                const Icon = document.icon;
                return (
                  <article key={document.title} className="flex flex-col rounded-xl border border-gray-200 p-5">
                    <div className="flex items-start justify-between gap-3">
                      <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-violet-100 text-violet-700">
                        <Icon className="h-5 w-5" aria-hidden="true" />
                      </span>
                      <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600">
                        Шаг {index + 1}
                      </span>
                    </div>
                    <h3 className="mt-4 font-semibold text-gray-950">{document.title}</h3>
                    <p className="mt-2 flex-1 text-sm leading-5 text-gray-600">{document.description}</p>
                    <Link
                      to={`/dashboard/clients/${client.id}/documents`}
                      className="mt-5 inline-flex items-center justify-center gap-2 rounded-lg border border-violet-200 bg-violet-50 px-4 py-2.5 text-sm font-medium text-violet-700 hover:bg-violet-100"
                    >
                      Открыть анкету
                      <ArrowRight className="h-4 w-4" aria-hidden="true" />
                    </Link>
                  </article>
                );
              })}
            </div>
            <p className="mt-4 text-sm text-gray-500">
              Анкета сохраняется в карточке. Каждый документ можно повторно сформировать и скачать в DOCX.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
