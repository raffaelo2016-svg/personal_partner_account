import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Newspaper, Plus } from 'lucide-react';
import {
  archiveNews, createNews, fetchAdminNews, fetchNewsStats, publishNews, updateNews,
  type NewsInput, type NewsPost,
} from '../api/news';

const emptyForm: NewsInput = {
  title: '', body: '', category: 'announcement', important: false, pinned: false, requires_acknowledgement: false,
};

const statusLabel = { draft: 'Черновик', published: 'Опубликовано', archived: 'В архиве' };

export default function AdminNews() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState<NewsInput>(emptyForm);
  const [showForm, setShowForm] = useState(false);
  const [statsId, setStatsId] = useState<string | null>(null);
  const { data, isLoading, isError } = useQuery({ queryKey: ['adminNews'], queryFn: fetchAdminNews });
  const { data: stats } = useQuery({ queryKey: ['newsStats', statsId], queryFn: () => fetchNewsStats(statsId!), enabled: !!statsId });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['adminNews'] });
    queryClient.invalidateQueries({ queryKey: ['newsStats'] });
  };
  const save = useMutation({
    mutationFn: () => editing ? updateNews(editing, form) : createNews(form),
    onSuccess: () => { refresh(); setShowForm(false); setEditing(null); setForm(emptyForm); },
  });
  const publish = useMutation({ mutationFn: publishNews, onSuccess: refresh });
  const archive = useMutation({ mutationFn: archiveNews, onSuccess: refresh });

  const startEdit = (post: NewsPost) => {
    setEditing(post.id);
    setForm({ title: post.title, body: post.body, category: post.category, important: post.important, pinned: post.pinned, requires_acknowledgement: post.requires_acknowledgement });
    setShowForm(true);
  };

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex flex-wrap gap-4 items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-gray-900 flex items-center gap-3"><Newspaper className="w-8 h-8 text-blue-600" /> Новости партнёров</h1>
          <p className="text-gray-600 mt-2">Публикации видны всем партнёрам. Черновики — только администраторам.</p>
        </div>
        <button type="button" onClick={() => { setEditing(null); setForm(emptyForm); setShowForm(true); }} className="bg-blue-600 text-white rounded-xl px-5 py-3 flex items-center gap-2 hover:bg-blue-700"><Plus className="w-5 h-5" /> Создать новость</button>
      </div>

      {showForm && (
        <form onSubmit={(event) => { event.preventDefault(); save.mutate(); }} className="bg-white border border-gray-200 rounded-2xl p-6 space-y-5">
          <h2 className="text-xl font-semibold text-gray-900">{editing ? 'Редактировать новость' : 'Новый черновик'}</h2>
          <label className="block text-sm font-medium text-gray-700">Заголовок
            <input required minLength={3} maxLength={255} value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} className="block mt-2 w-full border border-gray-300 rounded-xl px-4 py-3" />
          </label>
          <label className="block text-sm font-medium text-gray-700">Текст
            <textarea required maxLength={20000} rows={8} value={form.body} onChange={(event) => setForm({ ...form, body: event.target.value })} className="block mt-2 w-full border border-gray-300 rounded-xl px-4 py-3" />
          </label>
          <label className="block text-sm font-medium text-gray-700">Категория
            <select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value as NewsInput['category'] })} className="block mt-2 w-full border border-gray-300 rounded-xl px-4 py-3">
              <option value="announcement">Объявление</option><option value="update">Обновление</option><option value="instruction">Инструкция</option>
            </select>
          </label>
          <div className="flex flex-wrap gap-5 text-sm text-gray-700">
            <label className="flex items-center gap-2"><input type="checkbox" checked={form.important} onChange={(event) => setForm({ ...form, important: event.target.checked })} /> Важное</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={form.pinned} onChange={(event) => setForm({ ...form, pinned: event.target.checked })} /> Закрепить</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={form.requires_acknowledgement} onChange={(event) => setForm({ ...form, requires_acknowledgement: event.target.checked })} /> Требовать подтверждение</label>
          </div>
          {save.isError && <p role="alert" className="text-red-600">Не удалось сохранить новость.</p>}
          <div className="flex gap-3">
            <button type="submit" disabled={save.isPending} className="bg-blue-600 text-white rounded-xl px-5 py-2.5 disabled:opacity-50">Сохранить</button>
            <button type="button" onClick={() => setShowForm(false)} className="border border-gray-300 rounded-xl px-5 py-2.5">Отмена</button>
          </div>
        </form>
      )}

      {isLoading && <p className="text-gray-500">Загружаем новости…</p>}
      {isError && <p role="alert" className="text-red-600">Не удалось загрузить новости.</p>}
      {data?.items.length === 0 && <div className="bg-white border border-gray-200 rounded-2xl p-10 text-center text-gray-500">Пока публикаций нет. Создайте первый черновик.</div>}
      <div className="space-y-4">
        {data?.items.map((post) => (
          <article key={post.id} className="bg-white border border-gray-200 rounded-2xl p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm text-gray-500">{statusLabel[post.status]} · {post.published_at ? new Date(post.published_at).toLocaleDateString('ru-RU') : 'Не опубликовано'}</p>
                <h2 className="text-xl font-semibold text-gray-900 mt-1">{post.title}</h2>
                <p className="text-gray-600 mt-2 line-clamp-2 whitespace-pre-line">{post.body}</p>
              </div>
              <div className="flex flex-wrap gap-2 text-sm">
                {post.status !== 'archived' && <button type="button" onClick={() => startEdit(post)} className="border border-gray-300 rounded-lg px-3 py-2 hover:bg-gray-50">Изменить</button>}
                {post.status === 'draft' && <button type="button" disabled={publish.isPending} onClick={() => { if (window.confirm('Опубликовать новость для всех партнёров?')) publish.mutate(post.id); }} className="bg-blue-600 text-white rounded-lg px-3 py-2 disabled:opacity-50">Опубликовать</button>}
                {post.status === 'published' && <button type="button" onClick={() => setStatsId(statsId === post.id ? null : post.id)} className="border border-gray-300 rounded-lg px-3 py-2 hover:bg-gray-50">Статистика</button>}
                {post.status !== 'archived' && <button type="button" disabled={archive.isPending} onClick={() => { if (window.confirm('Убрать новость из ленты партнёров?')) archive.mutate(post.id); }} className="border border-red-200 text-red-700 rounded-lg px-3 py-2 disabled:opacity-50">В архив</button>}
              </div>
            </div>
            {statsId === post.id && stats && <p className="mt-4 pt-4 border-t border-gray-100 text-sm text-gray-600">Партнёров: {stats.total} · Прочитали: {stats.read} · Подтвердили: {stats.acknowledged}</p>}
          </article>
        ))}
      </div>
    </div>
  );
}
