import { Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { Newspaper, Pin } from 'lucide-react';
import { fetchNews } from '../api/news';

const categoryLabel = { announcement: 'Объявление', update: 'Обновление', instruction: 'Инструкция' };

export default function News() {
  const { data, isLoading, isError } = useQuery({ queryKey: ['news', 100], queryFn: () => fetchNews(100) });

  return (
    <div className="p-4 lg:p-8 max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-gray-900 flex items-center gap-3"><Newspaper className="w-8 h-8 text-blue-600" /> Новости</h1>
        <p className="text-gray-600 mt-2">Объявления, обновления и инструкции для партнёров ЮРИТЕХ</p>
      </div>
      {isLoading && <p className="text-gray-500">Загружаем новости…</p>}
      {isError && <p role="alert" className="text-red-600">Не удалось загрузить новости. Попробуйте обновить страницу.</p>}
      {data?.items.length === 0 && <div className="bg-white border border-gray-200 rounded-2xl p-10 text-center text-gray-500">Пока новостей нет.</div>}
      <div className="space-y-4">
        {data?.items.map((post) => (
          <Link key={post.id} to={`/dashboard/news/${post.id}`} className={`block rounded-2xl border bg-white p-6 hover:shadow-md transition-shadow ${post.important ? 'border-amber-300' : 'border-gray-200'}`}>
            <div className="flex items-start justify-between gap-4">
              <div className="flex flex-wrap items-center gap-2 text-xs font-medium">
                <span className="bg-blue-50 text-blue-700 rounded-full px-3 py-1">{categoryLabel[post.category]}</span>
                {post.important && <span className="bg-amber-50 text-amber-700 rounded-full px-3 py-1">Важное</span>}
                {post.pinned && <span className="text-gray-500 flex items-center gap-1"><Pin className="w-3 h-3" /> Закреплено</span>}
              </div>
              {!post.read_at && <span className="text-xs text-blue-600 font-medium whitespace-nowrap">Не прочитано</span>}
            </div>
            {post.image_url && (
              <img src={post.image_url} alt="" loading="lazy" className="mt-4 w-full aspect-[16/7] rounded-xl object-cover" />
            )}
            <h2 className="text-xl font-semibold text-gray-900 mt-3">{post.title}</h2>
            <p className="text-gray-600 mt-2 line-clamp-2 whitespace-pre-line">{post.body}</p>
            <p className="text-xs text-gray-400 mt-4">{post.published_at ? new Date(post.published_at).toLocaleDateString('ru-RU') : ''}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
