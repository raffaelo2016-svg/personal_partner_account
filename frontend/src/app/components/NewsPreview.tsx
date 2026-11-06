import { Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Newspaper, Pin } from 'lucide-react';
import { fetchNews } from '../api/news';

export default function NewsPreview() {
  const { data, isError } = useQuery({ queryKey: ['news', 3], queryFn: () => fetchNews(3) });
  if (isError || !data?.items.length) return null;

  return (
    <section className="bg-white rounded-2xl border border-gray-200 overflow-hidden" aria-labelledby="news-preview-title">
      <div className="px-6 py-4 flex items-center justify-between border-b border-gray-100">
        <h2 id="news-preview-title" className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Newspaper className="w-5 h-5 text-blue-600" /> Новости для партнёров
        </h2>
        <Link to="/dashboard/news" className="text-sm text-blue-600 hover:underline flex items-center gap-1">
          Все новости <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
      <div className="divide-y divide-gray-100">
        {data.items.map((post) => (
          <Link key={post.id} to={`/dashboard/news/${post.id}`} className="block px-6 py-4 hover:bg-blue-50/40">
            <span className="flex items-center gap-2 font-medium text-gray-900">
              {post.pinned && <Pin className="w-4 h-4 text-blue-500" aria-label="Закреплено" />}
              {post.title}
              {!post.read_at && <span className="w-2 h-2 rounded-full bg-blue-600" aria-label="Не прочитано" />}
            </span>
            <span className="block text-sm text-gray-500 mt-1 line-clamp-1">{post.body}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
