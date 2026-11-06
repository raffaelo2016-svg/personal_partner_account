import SroDetailsCard from '../components/SroDetailsCard';

export default function SroDetails() {
  return (
    <div className="space-y-8 p-4 sm:p-8">
      <div>
        <h1 className="mb-2 text-3xl font-semibold text-gray-900">Реквизиты СРО</h1>
        <p className="text-gray-600">Скопируйте реквизиты одним абзацем и вставьте в заявление в суд.</p>
      </div>
      <SroDetailsCard showStatement />
    </div>
  );
}
