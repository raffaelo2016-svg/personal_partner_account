import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Settings as SettingsIcon, Bell, Lock, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import {
  fetchTimezone,
  updateTimezone,
  fetchPartnerNotificationPreferences,
  updatePartnerNotificationPreferences,
  changePartnerPassword,
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

  if (isLoading || tzLoading) {
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
          ].map((item, idx) => (
            <label key={item.key} className={`flex items-center justify-between py-3 cursor-pointer ${idx < 2 ? 'border-b border-gray-200' : ''}`}>
              <div>
                <p className="font-medium text-gray-900">{item.label}</p>
                <p className="text-sm text-gray-600">{item.desc}</p>
              </div>
              <input
                type="checkbox"
                checked={notifPrefs?.[item.key as keyof typeof notifPrefs] as boolean ?? true}
                onChange={(e) => handleNotifToggle(item.key, e.target.checked)}
                className="w-5 h-5 text-blue-600 rounded"
              />
            </label>
          ))}
        </div>
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
