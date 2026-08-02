interface MessageStatusProps {
  status: 'sent' | 'delivered' | 'read' | 'failed';
  className?: string;
}

export default function MessageStatus({ status, className = '' }: MessageStatusProps) {
  if (status === 'failed') {
    return (
      <span
        className={`inline-flex items-center gap-1 ml-1 text-[10px] font-medium text-red-600 ${className}`}
        title="Сообщение сохранено в кабинете, но не доставлено в Битрикс24"
      >
        <span aria-hidden="true">!</span>
        Ошибка
      </span>
    );
  }

  if (status === 'read') {
    // Две синие галочки
    return (
      <svg aria-label="Прочитано" viewBox="0 0 16 11" width="16" height="11" className={`inline-block ml-1 text-blue-500 ${className}`} fill="none">
        <path d="M11.071 0.653a.457.457 0 0 1 .637 0c.176.173.176.454 0 .627L6.16 6.873a.457.457 0 0 1-.637 0L3.292 4.66a.44.44 0 0 1 0-.627.457.457 0 0 1 .637 0l1.912 1.884 5.23-5.264z" fill="currentColor" />
        <path d="M14.071 0.653a.457.457 0 0 1 .637 0c.176.173.176.454 0 .627L9.16 6.873a.457.457 0 0 1-.637 0L6.292 4.66a.44.44 0 0 1 0-.627.457.457 0 0 1 .637 0l1.912 1.884 5.23-5.264z" fill="currentColor" />
      </svg>
    );
  }

  if (status === 'delivered') {
    // Две серые галочки
    return (
      <svg aria-label="Доставлено" viewBox="0 0 16 11" width="16" height="11" className={`inline-block ml-1 text-gray-400 ${className}`} fill="none">
        <path d="M11.071 0.653a.457.457 0 0 1 .637 0c.176.173.176.454 0 .627L6.16 6.873a.457.457 0 0 1-.637 0L3.292 4.66a.44.44 0 0 1 0-.627.457.457 0 0 1 .637 0l1.912 1.884 5.23-5.264z" fill="currentColor" />
        <path d="M14.071 0.653a.457.457 0 0 1 .637 0c.176.173.176.454 0 .627L9.16 6.873a.457.457 0 0 1-.637 0L6.292 4.66a.44.44 0 0 1 0-.627.457.457 0 0 1 .637 0l1.912 1.884 5.23-5.264z" fill="currentColor" />
      </svg>
    );
  }

  // sent — одна серая галочка
  return (
    <span className={`inline-flex items-center gap-1 ml-1 text-[10px] text-gray-400 ${className}`} title="Отправляется в Битрикс24">
      <svg aria-hidden="true" viewBox="0 0 12 11" width="12" height="11" fill="none">
      <path d="M9.071 0.653a.457.457 0 0 1 .637 0c.176.173.176.454 0 .627L4.16 6.873a.457.457 0 0 1-.637 0L1.292 4.66a.44.44 0 0 1 0-.627.457.457 0 0 1 .637 0l1.912 1.884 5.23-5.264z" fill="currentColor" />
      </svg>
      Отправляется
    </span>
  );
}
