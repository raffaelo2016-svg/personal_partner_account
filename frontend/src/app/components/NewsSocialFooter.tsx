import SocialLinks from './SocialLinks';

export default function NewsSocialFooter() {
  return (
    <footer className="mt-10 border-t border-gray-100 pt-8">
      <div className="rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50 to-sky-50 p-6 sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-widest text-blue-600">Каналы ЮРИТЕХ для партнёров</p>
        <h2 className="mt-2 text-xl font-semibold text-gray-900">Будем на связи</h2>
        <p className="mb-5 mt-2 text-sm leading-relaxed text-gray-600">Новости, специальные предложения и полезные материалы для вашей работы. Присоединяйтесь!</p>
        <SocialLinks variant="footer" />
      </div>
    </footer>
  );
}
