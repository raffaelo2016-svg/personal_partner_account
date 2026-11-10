import { useState } from 'react';
import { Check, Copy, Download, FileText, Image as ImageIcon, Loader2 } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { getAgentMe } from '@/app/api/agent';

const BANNERS = [
  {
    file: '/materials/banner-square.svg',
    name: 'Квадратный баннер',
    size: '1080 × 1080',
    hint: 'Для соцсетей и мессенджеров',
  },
  {
    file: '/materials/banner-wide.svg',
    name: 'Широкий баннер',
    size: '1920 × 1080',
    hint: 'Для сайта, презентаций и писем',
  },
];

export default function AgentMaterials() {
  const { data: me, isLoading } = useQuery({ queryKey: ['agent', 'me'], queryFn: getAgentMe });
  const [copied, setCopied] = useState<string | null>(null);

  const link = me?.profile.referral_link ?? '';
  const code = me?.profile.code ?? '';

  const templates = [
    {
      id: 'short',
      title: 'Короткое сообщение',
      hint: 'Мессенджеры и соцсети',
      text: `Привет! Запустили агентскую программу ЮРИТЕХ: 1 000 ₽ за каждого клиента, дошедшего до процедуры банкротства. Если ты юрист или у тебя юридическая компания — регистрируйся по моей ссылке: ${link}`,
    },
    {
      id: 'letter',
      title: 'Письмо партнёру',
      hint: 'Почта',
      text: `Здравствуйте!

ЮРИТЕХ запустил агентскую программу: за каждого клиента, дошедшего до введения в процедуру, начисляем 1 000 ₽. Срок программы не ограничен.

Если вы юрист или юридическая компания и хотите передавать клиентов на арбитражное сопровождение — зарегистрируйтесь по моей ссылке:
${link}

Мой код агента: ${code}

После регистрации партнёр закрепляется за мной, а вы сможете видеть клиентов и начисления в своём кабинете.`,
    },
    {
      id: 'post',
      title: 'Пост для соцсетей',
      hint: 'Публикации',
      text: `ЮРИТЕХ — агентская программа для юристов и юридических компаний.

Что получает партнёр:
— кабинет для клиентов, документов и задач;
— сопровождение дел в ЮРИТЕХ;
— прозрачные статусы и финансы.

Моё вознаграждение как агента — 1 000 ₽ за каждого клиента, дошедшего до процедуры. Срок программы не ограничен.

Регистрация партнёра по ссылке:
${link}`,
    },
  ];

  const copy = async (value: string, key: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(key);
      setTimeout(() => setCopied(null), 2500);
    } catch {
      setCopied(null);
    }
  };

  if (isLoading) {
    return (
      <div className="py-20 flex justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-emerald-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Материалы</h1>
        <p className="text-sm text-gray-500 mt-1">
          Презентация, баннеры и готовые тексты — чтобы приглашать партнёров было проще.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-white border border-gray-200 rounded-xl p-5 lg:col-span-1">
          <div className="w-11 h-11 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
            <FileText className="w-5 h-5" />
          </div>
          <h2 className="mt-3 text-base font-semibold text-gray-900">Презентация программы</h2>
          <p className="mt-1 text-sm text-gray-500">
            4 страницы: как работает программа, сколько платим и что делать дальше.
          </p>
          <a
            href="/materials/agent-program.pdf"
            download
            className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
          >
            <Download className="w-4 h-4" />
            Скачать PDF
          </a>
        </div>

        {BANNERS.map((banner) => (
          <div key={banner.file} className="bg-white border border-gray-200 rounded-xl p-5">
            <div className="w-11 h-11 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <ImageIcon className="w-5 h-5" />
            </div>
            <h2 className="mt-3 text-base font-semibold text-gray-900">{banner.name}</h2>
            <p className="mt-1 text-sm text-gray-500">
              {banner.size} · {banner.hint}
            </p>
            <img
              src={banner.file}
              alt={banner.name}
              className="mt-3 h-28 w-full rounded-lg border border-gray-100 bg-slate-50 object-contain"
            />
            <div className="mt-4 flex flex-wrap gap-2">
              <a
                href={banner.file}
                download
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-700 hover:border-emerald-300 hover:text-emerald-700"
              >
                <Download className="w-4 h-4" />
                Скачать
              </a>
              <button
                onClick={() => copy(`${window.location.origin}${banner.file}`, banner.file)}
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-700 hover:border-emerald-300 hover:text-emerald-700"
              >
                {copied === banner.file ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                {copied === banner.file ? 'Скопировано' : 'Ссылка'}
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-white border border-gray-200 rounded-xl p-5">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-gray-900">Ваша ссылка для партнёров</h2>
            <p className="text-sm text-gray-500">
              Уже подставлена во все тексты ниже. Код агента: <span className="font-mono">{code || '—'}</span>
            </p>
          </div>
          <button
            onClick={() => copy(link, 'link')}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-700 hover:border-emerald-300 hover:text-emerald-700"
          >
            {copied === 'link' ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
            {copied === 'link' ? 'Скопировано' : 'Скопировать'}
          </button>
        </div>
        <div className="mt-3 rounded-lg bg-gray-50 border border-gray-200 px-3 py-2.5 font-mono text-xs text-gray-600 break-all">
          {link || '—'}
        </div>
      </div>

      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Готовые тексты</h2>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {templates.map((template) => (
            <div key={template.id} className="bg-white border border-gray-200 rounded-xl p-5 flex flex-col">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-gray-900">{template.title}</h3>
                  <p className="text-xs text-gray-500">{template.hint}</p>
                </div>
                <button
                  onClick={() => copy(template.text, template.id)}
                  className="inline-flex shrink-0 items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-gray-200 text-xs text-gray-600 hover:border-emerald-300 hover:text-emerald-700"
                >
                  {copied === template.id ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  {copied === template.id ? 'Готово' : 'Копировать'}
                </button>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-gray-600 whitespace-pre-line line-clamp-6">
                {template.text}
              </p>
            </div>
          ))}
        </div>
      </div>

      <p className="text-xs text-gray-400">
        Тексты можно менять под себя. Важно не обещать сроки и результат дела — программа платит только
        за клиентов, дошедших до процедуры.
      </p>
    </div>
  );
}
