const channels = [
  { name: 'Telegram', url: import.meta.env.VITE_TELEGRAM_URL || 'https://t.me/yuritechpart', color: 'text-sky-500' },
  { name: 'YouTube', url: import.meta.env.VITE_YOUTUBE_URL || 'https://www.youtube.com/@uritech.partner', color: 'text-red-600' },
];

export default function SocialLinks({ variant = 'header' }: { variant?: 'header' | 'footer' }) {
  const isFooter = variant === 'footer';
  return (
    <nav aria-label="Социальные сети ЮРИТЕХ" className="flex shrink-0 flex-wrap items-center gap-2 sm:gap-3">
      {channels.map(({ name, url, color }) => {
        const href = typeof url === 'string' && /^https:\/\//.test(url) ? url : undefined;
        const content = (
          <>
            <svg viewBox="0 0 24 24" className={`h-5 w-5 shrink-0 ${color}`} aria-hidden="true">
              {name === 'Telegram' ? (
                <path fill="currentColor" d="M21.4 3.3 18.1 20c-.2 1.2-.9 1.5-1.9.9l-5-3.7-2.4 2.3c-.3.3-.5.5-1 .5l.4-5.1L17.5 6.5c.4-.4-.1-.6-.6-.3L5.4 13.4.5 11.9c-1.1-.3-1.1-1.1.2-1.6L20 2.9c.9-.3 1.6.2 1.4.4Z" />
              ) : (
                <>
                  <rect x="1" y="4" width="22" height="16" rx="5" fill="currentColor" />
                  <path d="m10 8 6 4-6 4Z" fill="white" />
                </>
              )}
            </svg>
            <span className={isFooter ? '' : 'hidden sm:inline'}>{name}</span>
          </>
        );
        const className = isFooter
          ? 'inline-flex min-h-12 items-center justify-center gap-3 rounded-xl border border-blue-100 bg-white px-5 py-3 text-sm font-semibold text-gray-900 shadow-sm transition-colors'
          : 'inline-flex h-10 w-10 items-center justify-center gap-2 rounded-xl border border-gray-200 bg-white text-sm font-medium text-gray-700 transition-colors sm:w-auto sm:px-3';
        return href ? (
          <a key={name} href={href} target="_blank" rel="noopener noreferrer" aria-label={`${name} ЮРИТЕХ — откроется в новой вкладке`} title={name} className={`${className} hover:border-gray-300 hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2`}>
            {content}
          </a>
        ) : (
          <button key={name} type="button" disabled aria-label={name} title="Ссылка на канал пока не настроена" className={`${className} cursor-default`}>
            {content}
          </button>
        );
      })}
    </nav>
  );
}
