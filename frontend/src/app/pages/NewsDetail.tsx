import { useEffect, useRef } from 'react';
import { Link, useParams } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, CheckCircle2 } from 'lucide-react';
import { acknowledgeNews, fetchNewsPost, readNews } from '../api/news';

export default function NewsDetail() {
  const { id = '' } = useParams();
  const queryClient = useQueryClient();
  const readAttempted = useRef<string | null>(null);
  const { data: post, isLoading, isError } = useQuery({ queryKey: ['newsPost', id], queryFn: () => fetchNewsPost(id), enabled: !!id });
  const markRead = useMutation({
    mutationFn: readNews,
    onSuccess: (updated) => {
      queryClient.setQueryData(['newsPost', id], updated);
      queryClient.invalidateQueries({ queryKey: ['news'] });
      queryClient.invalidateQueries({ queryKey: ['newsUnreadCount'] });
    },
  });
  const acknowledge = useMutation({
    mutationFn: acknowledgeNews,
    onSuccess: (updated) => queryClient.setQueryData(['newsPost', id], updated),
  });

  useEffect(() => {
    if (post && !post.read_at && readAttempted.current !== post.id) {
      readAttempted.current = post.id;
      markRead.mutate(post.id);
    }
  }, [post?.id, post?.read_at]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="p-4 lg:p-8 max-w-4xl mx-auto">
      <Link to="/dashboard/news" className="inline-flex items-center gap-2 text-blue-600 hover:underline mb-6"><ArrowLeft className="w-4 h-4" /> Все новости</Link>
      {isLoading && <p className="text-gray-500">Загружаем новость…</p>}
      {isError && <p role="alert" className="text-red-600">Новость не найдена или недоступна.</p>}
      {post && (
        <article className="bg-white rounded-2xl border border-gray-200 p-6 lg:p-10">
          <div className="flex flex-wrap gap-2 text-xs font-medium mb-4">
            {post.important && <span className="bg-amber-50 text-amber-700 rounded-full px-3 py-1">Важное</span>}
            {post.pinned && <span className="bg-blue-50 text-blue-700 rounded-full px-3 py-1">Закреплено</span>}
          </div>
          <h1 className="text-3xl font-semibold text-gray-900">{post.title}</h1>
          <p className="text-sm text-gray-500 mt-3">{post.published_at ? new Date(post.published_at).toLocaleDateString('ru-RU') : ''}</p>
          {post.image_url && (
            <img src={post.image_url} alt={`Обложка новости «${post.title}»`} className="mt-6 w-full aspect-video rounded-xl object-cover" />
          )}
          <div className="mt-8 text-gray-700 leading-relaxed whitespace-pre-wrap break-words">{post.body}</div>
          {post.requires_acknowledgement && (
            <div className="mt-10 pt-6 border-t border-gray-100">
              {post.acknowledged_at ? (
                <p className="text-green-700 flex items-center gap-2"><CheckCircle2 className="w-5 h-5" /> Вы подтвердили ознакомление</p>
              ) : (
                <button type="button" disabled={acknowledge.isPending} onClick={() => acknowledge.mutate(post.id)} className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-xl px-5 py-3 font-medium">Подтвердить ознакомление</button>
              )}
              {acknowledge.isError && <p role="alert" className="text-red-600 mt-2">Не удалось сохранить подтверждение.</p>}
            </div>
          )}
        </article>
      )}
    </div>
  );
}
