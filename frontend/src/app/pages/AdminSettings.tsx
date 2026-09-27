import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Settings as SettingsIcon, Bell, Lock, Loader2, Check, X } from 'lucide-react';
import { toast } from 'sonner';
import {
  fetchSystemSettings,
  updateSystemSettings,
  fetchNotificationPreferences,
  updateNotificationPreferences,
  changeAdminPassword,
} from '../api/adminSettings';
import type { SystemSettingData } from '../api/adminSettings';

const SETTING_LABELS: Record<string, { label: string; description: string }> = {
  system_name: { label: 'Название системы', description: '' },
  language: { label: 'Язык интерфейса', description: '' },
  timezone: { label: 'Часовой пояс', description: '' },
};

export default function AdminSettings() {
  const queryClient = useQueryClient();
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');

  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [currentPwd, setCurrentPwd] = useState('');
  const [newPwd, setNewPwd] = useState('');

  const { data: settings = [], isLoading: settingsLoading } = useQuery({
    queryKey: ['adminSettings'],
    queryFn: fetchSystemSettings,
  });

  const { data: notifPrefs } = useQuery({
    queryKey: ['adminNotifPrefs'],
    queryFn: fetchNotificationPreferences,
  });


  const updateSettingsMutation = useMutation({
    mutationFn: (updates: Record<string, string>) => updateSystemSettings(updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminSettings'] });
      setEditingKey(null);
      toast.success('Настройка обновлена');
    },
    onError: () => toast.error('Ошибка при обновлении настройки'),
  });

  const updateNotifMutation = useMutation({
    mutationFn: (prefs: Record<string, boolean>) => updateNotificationPreferences(prefs),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminNotifPrefs'] });
      toast.success('Настройки уведомлений обновлены');
    },
  });

  const changePwdMutation = useMutation({
    mutationFn: () => changeAdminPassword(currentPwd, newPwd),
    onSuccess: () => {
      setShowPasswordForm(false);
      setCurrentPwd('');
      setNewPwd('');
      toast.success('Пароль успешно изменён');
    },
    onError: () => toast.error('Ошибка при смене пароля'),
  });


  function startEdit(setting: SystemSettingData) {
    setEditingKey(setting.key);
    setEditValue(setting.value);
  }

  function saveEdit() {
    if (editingKey) {
      updateSettingsMutation.mutate({ [editingKey]: editValue });
    }
  }

  function handleNotifToggle(field: string, value: boolean) {
    updateNotifMutation.mutate({ [field]: value });
  }

  const settingsMap = Object.fromEntries(settings.map((s) => [s.key, s]));

  if (settingsLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-gray-900">Настройки системы</h1>
        <p className="text-gray-600 mt-2">Управление конфигурацией и параметрами системы</p>
      </div>

      {/* General Settings */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center">
            <SettingsIcon className="w-5 h-5 text-slate-600" />
          </div>
          <h2 className="text-xl font-semibold text-gray-900">Общие настройки</h2>
        </div>
        <div className="space-y-4">
          {['system_name', 'language'].map((key) => {
            const setting = settingsMap[key];
            const meta = SETTING_LABELS[key] || { label: key, description: '' };
            const isEditing = editingKey === key;
            return (
              <div key={key} className="flex items-center justify-between py-3 border-b border-gray-200">
                <div>
                  <p className="font-medium text-gray-900">{meta.label}</p>
                  {isEditing ? (
                    <div className="flex items-center gap-2 mt-1">
                      <input
                        type="text"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        className="border rounded-lg px-3 py-1 text-sm"
                        autoFocus
                      />
                      <button onClick={saveEdit} className="text-green-600 hover:text-green-700">
                        <Check className="w-4 h-4" />
                      </button>
                      <button onClick={() => setEditingKey(null)} className="text-gray-400 hover:text-gray-600">
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ) : (
                    <p className="text-sm text-gray-600">{setting?.value || '—'}</p>
                  )}
                </div>
                {!isEditing && (
                  <button
                    className="text-sm text-blue-600 hover:underline"
                    onClick={() => setting && startEdit(setting)}
                  >
                    Изменить
                  </button>
                )}
              </div>
            );
          })}
          <div className="py-3">
            <p className="font-medium text-gray-900 mb-2">Часовой пояс</p>
            <p className="text-sm font-medium text-gray-900">Москва (МСК, UTC+3)</p>
            <p className="mt-1 text-xs text-gray-500">Единый часовой пояс для всех пользователей кабинета</p>
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
            { key: 'new_partner_notifications', label: 'Уведомления о новых партнерах', desc: 'Оповещение при регистрации новых партнеров' },
            { key: 'critical_events', label: 'Критические события', desc: 'Уведомления о критических событиях системы' },
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
                className="px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-800 text-sm disabled:opacity-50"
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
