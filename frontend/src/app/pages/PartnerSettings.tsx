import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Settings as SettingsIcon, Bell, Lock, Loader2, Send, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';
import {
  fetchTimezone,
  updateTimezone,
  fetchPartnerNotificationPreferences,
  updatePartnerNotificationPreferences,
  changePartnerPassword,
  fetchTelegramConnection,
  createTelegramConnectLink,
  disconnectTelegram,
} from '../api/partnerSettings';
import TimezoneSelect from '../components/ui/TimezoneSelect';

export default function PartnerSettings() {
  const queryClient = useQueryClient();

  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [currentPwd, setCurrentPwd] = useState('');
  const [newPwd, setNewPwd] = useState('');

  const { data: tzData, isLoading: tzLoading } = useQuery({
    queryKey: ['partnerTimezone'],
    queryFn: fetchTimezone,
  });

  const updateTzMutation = useMutation({
    mutationFn: (tz: string) => updateTimezone(tz),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['partnerTimezone'] });
      queryClient.invalidateQueries({ queryKey: ['appTimezone'] });
      toast.success('Часовой пояс обновлён');
    },
    onError: () => toast.error('Ошибка при обновлении'),
  });

  const { data: notifPrefs, isLoading } = useQuery({
    queryKey: ['partnerNotifPrefs'],
    queryFn: fetchPartnerNotificationPreferences,
  });

  const { data: telegram, isLoading: telegramLoading, refetch: refetchTelegram } = useQuery({
    queryKey: ['partnerTelegram'],
    queryFn: fetchTelegramConnection,
    refetchOnWindowFocus: true,
  });

  const connectTelegramMutation = useMutation({
    mutationFn: createTelegramConnectLink,
    onSuccess: ({ url }) => {
      window.open(url, '_blank', 'noopener,noreferrer');
      toast.info('В Telegram нажмите «Запустить», затем вернитесь в кабинет');
    },
    onError: () => toast.error('Telegram пока не настроен'),
  });

  const disconnectTelegramMutation = useMutation({
    mutationFn: disconnectTelegram,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['partnerTelegram'] });
      toast.success('Telegram отключён');
    },
    onError: () => toast.error('Не удалось отключить Telegram'),
  });

  const updateNotifMutation = useMutation({
    mutationFn: (prefs: Record<string, boolean>) => updatePartnerNotificationPreferences(prefs),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['partnerNotifPrefs'] });
      toast.success('Настройки уведомлений обновлены');
    },
    onError: () => toast.error('Ошибка при обновлении'),
  });

  const changePwdMutation = useMutation({
    mutationFn: () => changePartnerPassword(currentPwd, newPwd),
    onSuccess: () => {
      setShowPasswordForm(false);
      setCurrentPwd('');
      setNewPwd('');
      toast.success('Пароль успешно изменён');
    },
    onError: () => toast.error('Ошибка при смене пароля'),
  });

  function handleNotifToggle(field: string, value: boolean) {
    updateNotifMutation.mutate({ [field]: value });
  }

  if (isLoading || tzLoading || telegramLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-gray-900">Настройки</h1>
        <p className="text-gray-600 mt-2">Управление уведомлениями и безопасностью</p>
      </div>

      {/* General Settings */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center">
            <SettingsIcon className="w-5 h-5 text-slate-600" />
          </div>
          <h2 className="text-xl font-semibold text-gray-900">Общие настройки</h2>
        </div>
        <div className="py-3">
          <p className="font-medium text-gray-900 mb-2">Часовой пояс</p>
          <div className="max-w-sm">
            <TimezoneSelect
              value={tzData?.timezone ?? 'Europe/Moscow'}
              onChange={(tz) => updateTzMutation.mutate(tz)}
            />
            {tzData?.region && (
              <p className="mt-2 text-xs text-gray-500">
                Регион: {tzData.region}. Часовой пояс подставляется автоматически, но его можно изменить.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Notifications */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
            <Bell className="w-5 h-5 text-blue-600" />
          </div>
          <h2 className="text-xl font-semibold text-gray-900">Уведомления</h2>
        </div>
        <div className="space-y-4">
          {[
            { key: 'email_notifications', label: 'Email уведомления', desc: 'Получать уведомления на email' },
            { key: 'new_partner_notifications', label: 'Уведомления о новых событиях', desc: 'Оповещение о важных событиях' },
            { key: 'critical_events', label: 'Критические события', desc: 'Уведомления о критических событиях' },
            { key: 'telegram_notifications', label: 'Telegram уведомления', desc: 'Новости и события в подключённый Telegram' },
          ].map((item, idx) => (
            <label key={item.key} className={`flex items-center justify-between py-3 cursor-pointer ${idx < 3 ? 'border-b border-gray-200' : ''}`}>
              <div>
                <p className="font-medium text-gray-900">{item.label}</p>
                <p className="text-sm text-gray-600">{item.desc}</p>
              </div>
              <input
                type="checkbox"
                checked={notifPrefs?.[item.key as keyof typeof notifPrefs] as boolean ?? true}
                onChange={(e) => handleNotifToggle(item.key, e.target.checked)}
                disabled={item.key === 'telegram_notifications' && !telegram?.connected}
                className="w-5 h-5 text-blue-600 rounded"
              />
            </label>
          ))}
        </div>
      </div>

      {/* Telegram */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 bg-sky-100 rounded-lg flex items-center justify-center shrink-0">
              <Send className="w-5 h-5 text-sky-600" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-xl font-semibold text-gray-900">Telegram</h2>
                {telegram?.connected && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Подключён
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-600 mt-1">Новости и важные уведомления из кабинета прямо в Telegram.</p>
              {telegram?.connected && telegram.username && (
                <p className="text-sm font-medium text-gray-800 mt-2">@{telegram.username}</p>
              )}
            </div>
          </div>
          {telegram?.connected ? (
            <button
              type="button"
              onClick={() => disconnectTelegramMutation.mutate()}
              disabled={disconnectTelegramMutation.isPending}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              {disconnectTelegramMutation.isPending ? 'Отключение…' : 'Отключить'}
            </button>
          ) : (
            <div className="flex flex-col gap-2 sm:items-end">
              <button
                type="button"
                onClick={() => connectTelegramMutation.mutate()}
                disabled={!telegram?.available || connectTelegramMutation.isPending}
                className="rounded-lg bg-[#229ED9] px-4 py-2 text-sm font-medium text-white hover:bg-[#1b8fc5] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {connectTelegramMutation.isPending ? 'Открываем Telegram…' : 'Подключить Telegram'}
              </button>
              {telegram?.available && (
                <button type="button" onClick={() => refetchTelegram()} className="text-sm text-blue-600 hover:underline">
                  Проверить подключение
                </button>
              )}
            </div>
          )}
        </div>
        {!telegram?.available && (
          <p className="mt-4 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Telegram-уведомления скоро будут доступны.
          </p>
        )}
      </div>

      {/* Security */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
            <Lock className="w-5 h-5 text-red-600" />
          </div>
          <h2 className="text-xl font-semibold text-gray-900">Безопасность</h2>
        </div>
        <div className="space-y-4">
          <div className="flex items-center justify-between py-3 border-b border-gray-200">
            <div>
              <p className="font-medium text-gray-900">Сменить пароль</p>
              <p className="text-sm text-gray-600">Обновите пароль для безопасности</p>
            </div>
            <button
              className="text-sm text-blue-600 hover:underline"
              onClick={() => setShowPasswordForm(!showPasswordForm)}
            >
              {showPasswordForm ? 'Отмена' : 'Изменить'}
            </button>
          </div>

          {showPasswordForm && (
            <div className="bg-gray-50 rounded-lg p-4 space-y-3">
              <input
                type="password"
                placeholder="Текущий пароль"
                value={currentPwd}
                onChange={(e) => setCurrentPwd(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 text-sm"
              />
              <input
                type="password"
                placeholder="Новый пароль (мин. 8 символов)"
                value={newPwd}
                onChange={(e) => setNewPwd(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 text-sm"
              />
              <button
                onClick={() => changePwdMutation.mutate()}
                disabled={changePwdMutation.isPending || newPwd.length < 8}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm disabled:opacity-50"
              >
                {changePwdMutation.isPending ? 'Сохранение...' : 'Сохранить'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
