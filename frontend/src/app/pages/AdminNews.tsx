import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Newspaper, Plus } from 'lucide-react';
import {
  archiveNews, createNews, deleteNewsImage, fetchAdminNews, fetchNewsStats, publishNews, updateNews, uploadNewsImage,
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
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
  const [currentImageUrl, setCurrentImageUrl] = useState<string | null>(null);
  const [removeImage, setRemoveImage] = useState(false);
  const [imageError, setImageError] = useState('');
  const [uploadFailed, setUploadFailed] = useState(false);

  useEffect(() => {
    if (!imageFile) {
      setImagePreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(imageFile);
    setImagePreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [imageFile]);
  const { data, isLoading, isError } = useQuery({ queryKey: ['adminNews'], queryFn: fetchAdminNews });
  const { data: stats } = useQuery({ queryKey: ['newsStats', statsId], queryFn: () => fetchNewsStats(statsId!), enabled: !!statsId });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['adminNews'] });
    queryClient.invalidateQueries({ queryKey: ['newsStats'] });
  };
  const save = useMutation({
    mutationFn: async () => {
      setUploadFailed(false);
      const post = editing ? await updateNews(editing, form) : await createNews(form);
      try {
        if (imageFile) await uploadNewsImage(post.id, imageFile);
        else if (removeImage) await deleteNewsImage(post.id);
      } catch (error) {
        setEditing(post.id); // Reuse the saved draft when retrying a failed upload.
        setUploadFailed(true);
        throw error;
      }
      return post;
    },
    onSuccess: () => {
      refresh();
      setShowForm(false);
      setEditing(null);
      setForm(emptyForm);
      setImageFile(null);
      setCurrentImageUrl(null);
      setRemoveImage(false);
      setImageError('');
    },
  });
  const publish = useMutation({ mutationFn: publishNews, onSuccess: refresh });
  const archive = useMutation({ mutationFn: archiveNews, onSuccess: refresh });

  const startEdit = (post: NewsPost) => {
    setEditing(post.id);
    setForm({ title: post.title, body: post.body, category: post.category, important: post.important, pinned: post.pinned, requires_acknowledgement: post.requires_acknowledgement });
    setCurrentImageUrl(post.image_url);
    setImageFile(null);
    setRemoveImage(false);
    setImageError('');
    setUploadFailed(false);
    setShowForm(true);
  };

  const startCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setCurrentImageUrl(null);
    setImageFile(null);
    setRemoveImage(false);
    setImageError('');
    setUploadFailed(false);
    setShowForm(true);
  };

  const chooseImage = (file: File | undefined) => {
    if (!file) return;
    const extension = file.name.split('.').pop()?.toLowerCase();
    const imageTypes: Record<string, string> = { jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', webp: 'image/webp' };
    const expectedType = imageTypes[extension || ''];
    if (!expectedType || file.type !== expectedType) {
      setImageFile(null);
      setImageError('Выберите изображение JPG, PNG или WebP.');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setImageFile(null);
      setImageError('Размер изображения не должен превышать 5 МБ.');
      return;
    }
    setImageError('');
    setImageFile(file);
    setRemoveImage(false);
  };

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex flex-wrap gap-4 items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-gray-900 flex items-center gap-3"><Newspaper className="w-8 h-8 text-blue-600" /> Новости партнёров</h1>
          <p className="text-gray-600 mt-2">Публикации видны всем партнёрам. Черновики — только администраторам.</p>
        </div>
        <button type="button" onClick={startCreate} className="bg-blue-600 text-white rounded-xl px-5 py-3 flex items-center gap-2 hover:bg-blue-700"><Plus className="w-5 h-5" /> Создать новость</button>
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
          <div className="space-y-2">
            <label htmlFor="news-image" className="block text-sm font-medium text-gray-700">Обложка новости (необязательно)</label>
            <input
              id="news-image"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(event) => { chooseImage(event.target.files?.[0]); event.target.value = ''; }}
              className="block w-full text-sm text-gray-700 file:mr-4 file:rounded-lg file:border-0 file:bg-blue-50 file:px-4 file:py-2 file:text-blue-700 hover:file:bg-blue-100"
            />
            <p className="text-xs text-gray-500">JPG, PNG или WebP, до 5 МБ.</p>
            {imageError && <p role="alert" className="text-sm text-red-600">{imageError}</p>}
            {(imagePreviewUrl || (currentImageUrl && !removeImage)) && (
              <div className="space-y-2">
                <img src={imagePreviewUrl || currentImageUrl || ''} alt="Предпросмотр обложки новости" className="w-full max-w-md aspect-video rounded-xl object-cover border border-gray-200" />
                <button type="button" onClick={() => { setImageFile(null); setRemoveImage(true); }} className="text-sm text-red-700 hover:underline">Убрать обложку</button>
              </div>
            )}
          </div>
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
          {save.isError && <p role="alert" className="text-red-600">{uploadFailed ? 'Текст сохранён, но изображение не загрузилось. Попробуйте ещё раз.' : 'Не удалось сохранить новость.'}</p>}
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
                {post.image_url && <img src={post.image_url} alt="" loading="lazy" className="mb-3 h-20 w-36 rounded-lg object-cover" />}
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
