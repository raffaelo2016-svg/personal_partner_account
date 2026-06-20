import { useState, useCallback, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router';
import { Search, Filter, Plus, ChevronRight, ChevronDown, X, Loader2 } from 'lucide-react';
import { useInfiniteClients } from '../hooks/useClients';
import { useIntersectionObserver } from '../hooks/useIntersectionObserver';
import CustomSelect from '../components/ui/CustomSelect';
import {
  STATUS_OPTIONS,
  getCategoryLabel,
  getStatusBadgeClass,
  getStatusDotClass,
  getStatusLabel,
} from '../data/clientStatuses';

type FilterCategory = 'all' | 'before_court' | 'in_court' | 'completed';
const VALID_CATEGORIES: FilterCategory[] = ['all', 'before_court', 'in_court', 'completed'];

export default function ClientsList() {
  const [searchParams, setSearchParams] = useSearchParams();

  const searchQuery = searchParams.get('q') ?? '';
  const filterCategoryRaw = searchParams.get('category') ?? 'all';
  const filterCategory: FilterCategory = VALID_CATEGORIES.includes(filterCategoryRaw as FilterCategory)
    ? (filterCategoryRaw as FilterCategory)
    : 'all';
  const statusFilter = searchParams.get('status') ?? 'all';
  const [isStatusDropdownOpen, setIsStatusDropdownOpen] = useState(false);

  const updateParam = useCallback(
    (key: string, value: string, defaultValue = 'all') => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (!value || value === defaultValue) next.delete(key);
          else next.set(key, value);
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const setSearchQuery = (v: string) => updateParam('q', v, '');
  const setFilterCategory = (v: FilterCategory) => updateParam('category', v);
  const setStatusFilter = (v: string) => updateParam('status', v);

  const filters = {
    search: searchQuery || undefined,
    category: filterCategory !== 'all' ? filterCategory : undefined,
    status: statusFilter !== 'all' ? statusFilter : undefined,
  };

  const { data: pages, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteClients(filters);

  const loadMore = useCallback(() => { if (hasNextPage) fetchNextPage(); }, [hasNextPage, fetchNextPage]);
  const sentinelRef = useIntersectionObserver(loadMore, !!hasNextPage && !isFetchingNextPage);

  const total = pages?.pages[0]?.total ?? 0;
  
  const clients = useMemo(() => pages?.pages.flatMap((p) => p.items) ?? [], [pages]);
  
  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-gray-900 mb-2">
            Клиенты
          </h1>
          <p className="text-gray-600">
            Управление клиентами и их карточками{total ? ` (${total})` : ''}
          </p>
        </div>
        <Link
          to="/dashboard/clients/new"
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-5 h-5" />
          Добавить клиента
        </Link>
      </div>
      
      {/* Filters */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
        <div className="flex flex-col sm:flex-row gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Поиск по имени, телефону или региону..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          {/* Type Filter */}
          <div className="flex items-center gap-2">
            <Filter className="w-5 h-5 text-gray-400" />
            <CustomSelect
              value={filterCategory}
              onChange={(val) => setFilterCategory(val as FilterCategory)}
              options={[
                { value: 'all', label: 'Все клиенты' },
                { value: 'before_court', label: 'ДО подачи в суд' },
                { value: 'in_court', label: 'В суде' },
                { value: 'completed', label: 'Завершено' },
              ]}
            />
          </div>
          
          {/* Status Filter */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setIsStatusDropdownOpen(!isStatusDropdownOpen)}
              className="flex items-center gap-3 px-4 py-2.5 bg-gradient-to-br from-gray-50 to-gray-100 border border-gray-200 rounded-lg hover:shadow-md hover:border-gray-300 transition-all min-w-[240px] group"
            >
              <div className="flex items-center gap-2 flex-1">
                <div className="p-1.5 bg-white rounded-lg shadow-sm">
                  <Filter className="w-4 h-4 text-gray-600" />
                </div>
                <div className="flex items-center gap-2 flex-1">
                  {statusFilter !== 'all' && (
                    <span className={`w-2 h-2 rounded-full ${getStatusDotClass(statusFilter)}`} />
                  )}
                  <span className="text-sm font-medium text-gray-700 truncate">
                    {statusFilter === 'all' ? 'Все статусы' : getStatusLabel(statusFilter)}
                  </span>
                </div>
              </div>
              <ChevronDown 
                className={`w-4 h-4 text-gray-500 transition-transform ${
                  isStatusDropdownOpen ? 'rotate-180' : ''
                }`} 
              />
            </button>
            
            {isStatusDropdownOpen && (
              <>
                {/* Backdrop */}
                <div 
                  className="fixed inset-0 z-10" 
                  onClick={() => setIsStatusDropdownOpen(false)}
                />
                
                {/* Dropdown */}
                <div className="absolute right-0 mt-2 w-80 bg-white rounded-xl shadow-2xl border border-gray-200 z-20 overflow-hidden">
                  {/* Header */}
                  <div className="sticky top-0 bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-3 flex items-center justify-between">
                    <span className="text-white font-semibold text-sm">Фильтр по статусу</span>
                    <button
                      type="button"
                      onClick={() => setIsStatusDropdownOpen(false)}
                      className="text-white hover:bg-white/20 rounded-lg p-1 transition-colors"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                  
                  {/* Content */}
                  <div className="max-h-[500px] overflow-y-auto">
                    {/* All statuses option */}
                    <button
                      type="button"
                      onClick={() => {
                        setStatusFilter('all');
                        setIsStatusDropdownOpen(false);
                      }}
                      className={`w-full px-4 py-3 flex items-center gap-3 hover:bg-gray-50 transition-colors border-b border-gray-100 ${
                        statusFilter === 'all' ? 'bg-blue-50' : ''
                      }`}
                    >
                      <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-gray-100 to-gray-200 flex items-center justify-center">
                        <Filter className="w-4 h-4 text-gray-600" />
                      </div>
                      <span className="text-sm font-medium text-gray-900">Все статусы</span>
                      {statusFilter === 'all' && (
                        <div className="ml-auto w-2 h-2 rounded-full bg-blue-600" />
                      )}
                    </button>
                    
                    {/* Status list */}
                    <div className="py-1">
                      {STATUS_OPTIONS.map((opt) => {
                        const OptIcon = opt.icon;
                        return (
                          <button
                            key={opt.value}
                            type="button"
                            onClick={() => {
                              setStatusFilter(opt.value);
                              setIsStatusDropdownOpen(false);
                            }}
                            className={`w-full px-4 py-2.5 flex items-center gap-3 hover:bg-gray-50 transition-colors ${
                              statusFilter === opt.value ? 'bg-blue-50' : ''
                            }`}
                          >
                            <OptIcon className={`w-4 h-4 ${opt.color}`} />
                            <span className="text-sm text-gray-700 flex-1 text-left">{opt.label}</span>
                            {statusFilter === opt.value && (
                              <div className="w-1.5 h-1.5 rounded-full bg-blue-600" />
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
      
      {/* Clients List */}
      <div className="bg-white rounded-xl border border-gray-200">
        {isLoading ? (
          <div className="px-6 py-12 text-center flex items-center justify-center gap-2">
            <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
            <span className="text-gray-500">Загрузка...</span>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {clients.length === 0 ? (
              <div className="px-6 py-12 text-center">
                <p className="text-gray-500">Клиенты не найдены</p>
              </div>
            ) : (
              clients.map((client) => (
                <Link
                  key={client.id}
                  to={`/dashboard/clients/${client.id}`}
                  className="px-6 py-4 hover:bg-gray-50 transition-colors flex items-center justify-between group"
                >
                  <div className="flex items-center gap-4 flex-1">
                    <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center">
                      <span className="text-lg font-medium text-blue-700">
                        {client.full_name.split(' ').map(n => n[0]).join('').slice(0, 2)}
                      </span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-900 group-hover:text-blue-600 mb-1">
                        {client.full_name}
                      </p>
                      <div className="flex items-center gap-3 text-sm text-gray-500">
                        <span>{client.phone ?? '—'}</span>
                        <span>•</span>
                        <span>{client.region ?? '—'}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <p className="text-sm text-gray-600 mb-1">
                        {getCategoryLabel(client.status)}
                      </p>
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusBadgeClass(client.status)}`}>
                        {getStatusLabel(client.status)}
                      </span>
                    </div>
                    <ChevronRight className="w-5 h-5 text-gray-400 group-hover:text-gray-600" />
                  </div>
                </Link>
              ))
            )}
          </div>
        )}

        {(hasNextPage || isFetchingNextPage) && (
          <div ref={sentinelRef} className="flex justify-center py-4 border-t border-gray-200">
            <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
          </div>
        )}
      </div>
    </div>
  );
}