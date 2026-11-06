import { useState, useRef, useEffect } from 'react';
import { Bell, Check, CheckCheck, X } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import {
  fetchUnreadCount,
  fetchNotifications,
  markNotificationRead,
  markAllNotificationsRead,
} from '../api/notifications';
import { formatDateTime } from '@/app/utils/formatDate';
import { useTimezone } from '@/app/contexts/TimezoneContext';

const TYPE_ICONS: Record<string, string> = {
  status_change: '🔄',
  new_task: '📋',
  new_client: '👤',
  overdue_payment: '⚠️',
  new_partner: '🤝',
  news: '📰',
};

export default function NotificationBell() {
  const tz = useTimezone();
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const { data: unreadCount = 0 } = useQuery({
    queryKey: ['unreadCount'],
    queryFn: fetchUnreadCount,
    refetchInterval: 30000,
  });

  const { data: notificationsData } = useQuery({
    queryKey: ['notifications', { is_read: false }],
    queryFn: () => fetchNotifications({ is_read: false, page: 1 }),
    enabled: open,
  });

  const markReadMutation = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['unreadCount'] });
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });

  const markAllMutation = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['unreadCount'] });
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleClick = (notif: { id: string; link?: string | null }) => {
    markReadMutation.mutate(notif.id);
    if (notif.link) {
      navigate(notif.link);
      setOpen(false);
    }
  };

  const notifications = notificationsData?.items ?? [];

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        aria-label={
          unreadCount > 0
            ? `Уведомления, непрочитанных: ${unreadCount}`
            : 'Уведомления'
        }
        aria-expanded={open}
        aria-haspopup="true"
        onClick={() => setOpen(!open)}
        className="relative p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
      >
        <Bell className="w-5 h-5" aria-hidden="true" />
        {unreadCount > 0 && (
          <span
            aria-hidden="true"
            className="absolute -top-0.5 -right-0.5 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center font-medium"
          >
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-96 bg-white rounded-xl shadow-lg border border-gray-200 z-50 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <h3 className="font-semibold text-gray-900">Уведомления</h3>
            <div className="flex items-center gap-2">
              {unreadCount > 0 && (
                <button
                  onClick={() => markAllMutation.mutate()}
                  className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1"
                >
                  <CheckCheck className="w-3.5 h-3.5" />
                  Прочитать все
                </button>
              )}
              <button
                type="button"
                aria-label="Закрыть уведомления"
                onClick={() => setOpen(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-4 h-4" aria-hidden="true" />
              </button>
            </div>
          </div>

          <div className="max-h-96 overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="px-4 py-8 text-center text-gray-500 text-sm">
                Нет новых уведомлений
              </div>
            ) : (
              notifications.map((notif) => (
                <button
                  key={notif.id}
                  onClick={() => handleClick(notif)}
                  className="w-full px-4 py-3 flex items-start gap-3 hover:bg-gray-50 transition-colors text-left border-b border-gray-50 last:border-0"
                >
                  <span className="text-lg flex-shrink-0 mt-0.5">
                    {TYPE_ICONS[notif.type] ?? '📌'}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900">{notif.title}</p>
                    <p className="text-xs text-gray-500 mt-0.5 truncate">{notif.message}</p>
                    <p className="text-xs text-gray-400 mt-1">
                      {formatDateTime(notif.created_at, tz)}
                    </p>
                  </div>
                  {!notif.is_read && (
                    <span className="w-2 h-2 bg-blue-500 rounded-full flex-shrink-0 mt-2" />
                  )}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
