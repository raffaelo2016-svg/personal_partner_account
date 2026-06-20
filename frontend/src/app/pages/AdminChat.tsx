import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Send, Search, User, Loader2, WifiOff, MessageSquare } from 'lucide-react';
import { useInfiniteQuery, useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchAdminChatRooms,
  fetchAdminChatMessages,
  sendAdminChatMessage,
  ChatMessageData,
} from '../api/chat';
import { useWsChat } from '../hooks/useWsChat';
import MessageStatus from '../components/ui/MessageStatus';
import { formatTime } from '@/app/utils/formatDate';
import { useTimezone } from '@/app/contexts/TimezoneContext';

const PAGE_SIZE = 20;

export default function AdminChat() {
  const tz = useTimezone();
  const [activeRoomId, setActiveRoomId] = useState<string | null>(null);
  const [inputText, setInputText] = useState('');
  const [searchText, setSearchText] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isInitialLoad = useRef(true);
  const queryClient = useQueryClient();

  const { wsMessages, wsConnected, typingUsers, sendTyping, clearWsMessages } = useWsChat(activeRoomId, {
    roomsQueryKey: ['adminChatRooms'],
    unreadQueryKey: ['adminUnreadCount'],
    messagesQueryPrefix: 'adminChatMessages',
    readerRole: 'admin',
    ownSenderType: 'admin',
  });

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchText), 300);
    return () => clearTimeout(timer);
  }, [searchText]);

  const { data: rooms, isLoading: roomsLoading } = useQuery({
    queryKey: ['adminChatRooms', debouncedSearch],
    queryFn: () => fetchAdminChatRooms(debouncedSearch || undefined),
  });

  const {
    data: messagesData,
    isLoading: messagesLoading,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['adminChatMessages', activeRoomId],
    queryFn: ({ pageParam }) => fetchAdminChatMessages(activeRoomId!, { limit: PAGE_SIZE, before: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => (lastPage.length < PAGE_SIZE ? undefined : lastPage[0]?.id),
    enabled: !!activeRoomId,
  });

  const cachedMessages = useMemo(() => (messagesData?.pages ?? []).flat(), [messagesData]);

  const sendMutation = useMutation({
    mutationFn: ({ roomId, text }: { roomId: string; text: string }) => sendAdminChatMessage(roomId, text),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminChatMessages', activeRoomId] });
      queryClient.invalidateQueries({ queryKey: ['adminChatRooms'] });
      queryClient.invalidateQueries({ queryKey: ['adminUnreadCount'] });
    },
  });

  useEffect(() => {
    if (rooms && rooms.length > 0 && !activeRoomId) setActiveRoomId(rooms[0].id);
  }, [rooms, activeRoomId]);

  useEffect(() => { isInitialLoad.current = true; }, [activeRoomId]);

  useEffect(() => {
    if (isInitialLoad.current && cachedMessages.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'instant' });
      isInitialLoad.current = false;
    }
  }, [cachedMessages]);

  useEffect(() => {
    if (wsMessages.length > 0) messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [wsMessages]);

  const handleScroll = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el || isFetchingNextPage || !hasNextPage) return;
    if (el.scrollTop < 100) {
      const prevHeight = el.scrollHeight;
      fetchNextPage().then(() => {
        requestAnimationFrame(() => { el.scrollTop = el.scrollHeight - prevHeight; });
      });
    }
  }, [fetchNextPage, hasNextPage, isFetchingNextPage]);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
  }, []);

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || !activeRoomId) return;
    sendMutation.mutate({ roomId: activeRoomId, text: inputText }, { onSuccess: scrollToBottom });
    setInputText('');
    scrollToBottom();
  };

  const allMessages = useMemo(() => {
    const combined = [
      ...cachedMessages,
      ...wsMessages.filter((wm) => wm.room_id === activeRoomId && !cachedMessages.some((m) => m.id === wm.id)),
    ];
    combined.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
    return combined;
  }, [cachedMessages, wsMessages, activeRoomId]);

  const activeRoom = rooms?.find((r) => r.id === activeRoomId);

  return (
    <div className="h-[calc(100vh-53px)] -m-4 lg:-m-8 flex">
      <div className="w-96 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-5 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900 mb-1">Чаты с партнёрами</h2>
          <p className="text-sm text-gray-500 mb-3">
            {wsConnected ? 'Подключено' : (
              <span className="flex items-center gap-1 text-orange-600"><WifiOff className="w-3 h-3" /> Переподключение...</span>
            )}
          </p>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input type="text" value={searchText} onChange={(e) => setSearchText(e.target.value)}
              placeholder="Поиск по партнёру..."
              className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {roomsLoading && <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-gray-400" /></div>}
          {!roomsLoading && (rooms ?? []).length === 0 && (
            <div className="text-center text-gray-400 py-12"><MessageSquare className="w-10 h-10 mx-auto mb-2" /><p>Нет чатов</p></div>
          )}
          {(rooms ?? []).map((room) => (
            <button key={room.id}
              onClick={() => { setActiveRoomId(room.id); clearWsMessages(); isInitialLoad.current = true; }}
              className={`w-full p-4 flex items-center gap-3 border-b border-gray-100 hover:bg-gray-50 transition-colors ${activeRoomId === room.id ? 'bg-blue-50' : ''}`}>
              <div className="w-11 h-11 bg-blue-600 rounded-full flex items-center justify-center flex-shrink-0">
                <span className="text-white font-semibold text-sm">{(room.partner_name ?? 'П').slice(0, 2).toUpperCase()}</span>
              </div>
              <div className="flex-1 text-left min-w-0">
                <div className="flex items-center justify-between">
                  <p className="font-medium text-gray-900 truncate">{room.partner_name ?? 'Партнёр'}</p>
                  {room.unread_count > 0 && <span className="bg-red-500 text-white text-xs rounded-full px-2 py-0.5 ml-2 flex-shrink-0">{room.unread_count}</span>}
                </div>
                <p className="text-sm text-gray-500 truncate">{room.last_message ?? 'Нет сообщений'}</p>
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 flex flex-col bg-gray-50">
        {activeRoom ? (
          <>
            <div className="bg-white border-b border-gray-200 p-4 flex items-center gap-3">
              <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center">
                <span className="text-white font-semibold text-sm">{(activeRoom.partner_name ?? 'П').slice(0, 2).toUpperCase()}</span>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">{activeRoom.partner_name ?? 'Партнёр'}</h3>
                <p className="text-sm text-gray-500">Чат с партнёром</p>
              </div>
            </div>

            <div ref={scrollContainerRef} onScroll={handleScroll} className="flex-1 overflow-y-auto p-6 space-y-4">
              {isFetchingNextPage && <div className="flex justify-center py-2"><Loader2 className="w-5 h-5 animate-spin text-gray-400" /></div>}
              {messagesLoading && <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-gray-400" /></div>}
              {!messagesLoading && allMessages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full text-gray-400">
                  <MessageSquare className="w-12 h-12 mb-3" /><p className="text-lg font-medium">Нет сообщений</p><p className="text-sm">Напишите первое сообщение партнёру</p>
                </div>
              )}
              {allMessages.map((msg) => {
                const isAdmin = msg.sender_type === 'admin';
                return (
                  <div key={msg.id} className={`flex ${isAdmin ? 'justify-end' : 'justify-start'}`}>
                    <div className="max-w-md">
                      {!isAdmin && (
                        <div className="flex items-center gap-2 mb-1">
                          <div className="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center"><User className="w-3.5 h-3.5 text-blue-600" /></div>
                          <span className="text-xs text-gray-500">Партнёр</span>
                        </div>
                      )}
                      <div className={`rounded-2xl px-4 py-3 ${isAdmin ? 'bg-slate-700 text-white' : 'bg-white border border-gray-200 text-gray-900'}`}>
                        <p>{msg.text}</p>
                      </div>
                      <div className={`flex items-center gap-0.5 mt-1 ${isAdmin ? 'justify-end' : 'justify-start'}`}>
                        <span className="text-xs text-gray-500">{formatTime(msg.created_at, tz)}</span>
                        {isAdmin && <MessageStatus status={msg.delivery_status} />}
                      </div>
                    </div>
                  </div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>

            <div className="bg-white border-t border-gray-200 p-4">
              {activeRoomId && typingUsers[activeRoomId] && (
                <p className="text-xs text-gray-400 mb-2 animate-pulse">Партнёр печатает...</p>
              )}
              <form onSubmit={handleSend} className="flex items-center gap-3">
                <input type="text" value={inputText} onChange={(e) => { setInputText(e.target.value); sendTyping(); }}
                  placeholder="Введите сообщение..."
                  className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
                <button type="submit" disabled={sendMutation.isPending}
                  className="px-6 py-3 bg-slate-700 text-white rounded-lg hover:bg-slate-800 transition-colors flex items-center gap-2 disabled:opacity-50">
                  {sendMutation.isPending ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />} Отправить
                </button>
              </form>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-400">
            <div className="text-center"><MessageSquare className="w-16 h-16 mx-auto mb-4" /><p className="text-xl font-medium">Выберите чат</p><p className="text-sm mt-1">Выберите партнёра из списка слева</p></div>
          </div>
        )}
      </div>
    </div>
  );
}
