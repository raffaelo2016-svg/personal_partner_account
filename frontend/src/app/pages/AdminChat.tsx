import { decodeChatText } from '@/app/utils/chatText';
import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Send, Search, User, Loader2, WifiOff, MessageSquare, Paperclip, FileText, Inbox, X, History, Trash2 } from 'lucide-react';
import { Link } from 'react-router';
import { useInfiniteQuery, useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchAdminChatRooms,
  fetchAdminChatMessages,
  fetchAdminChatMessageEvents,
  sendAdminChatAttachment,
  sendAdminChatMessage,
  deleteAdminChatMessage,
  ChatMessageData,
} from '../api/chat';
import { useWsChat } from '../hooks/useWsChat';
import MessageStatus from '../components/ui/MessageStatus';
import ChatDateSeparator from '../components/ui/ChatDateSeparator';
import { formatTime } from '@/app/utils/formatDate';
import { useTimezone } from '@/app/contexts/TimezoneContext';
import { ALLOWED_FILE_EXTENSIONS, formatFileSize, FILE_SIZE_LIMITS_LABEL, partitionFiles } from '../utils/files';

const PAGE_SIZE = 20;

export default function AdminChat() {
  const tz = useTimezone();
  const [activeRoomId, setActiveRoomId] = useState<string | null>(null);
  const [inputText, setInputText] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState('');
  const [searchText, setSearchText] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [showJournal, setShowJournal] = useState(false);
  const [roomType, setRoomType] = useState<'admin' | 'tech_support'>('admin');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
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
    queryKey: ['adminChatRooms', roomType, debouncedSearch],
    queryFn: () => fetchAdminChatRooms(debouncedSearch || undefined, roomType),
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
    refetchInterval: 15_000,
  });

  const cachedMessages = useMemo(() => (messagesData?.pages ?? []).flat(), [messagesData]);

  const { data: messageEvents = [], isLoading: eventsLoading } = useQuery({
    queryKey: ['adminChatMessageEvents', activeRoomId],
    queryFn: () => fetchAdminChatMessageEvents(activeRoomId!),
    enabled: !!activeRoomId && showJournal && roomType === 'admin',
    refetchInterval: showJournal && roomType === 'admin' ? 15_000 : false,
  });

  const sendMutation = useMutation({
    mutationFn: ({ roomId, text, file }: { roomId: string; text: string; file?: File | null }) =>
      file ? sendAdminChatAttachment(roomId, text, file) : sendAdminChatMessage(roomId, text),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminChatMessages', activeRoomId] });
      queryClient.invalidateQueries({ queryKey: ['adminChatRooms'] });
      queryClient.invalidateQueries({ queryKey: ['adminUnreadCount'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: ({ roomId, messageId }: { roomId: string; messageId: string }) =>
      deleteAdminChatMessage(roomId, messageId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminChatMessages', activeRoomId] });
      queryClient.invalidateQueries({ queryKey: ['adminChatRooms'] });
      queryClient.invalidateQueries({ queryKey: ['adminUnreadCount'] });
    },
  });

  const handleDeleteMessage = (messageId: string) => {
    if (!activeRoomId || deleteMutation.isPending) return;
    if (!window.confirm('Удалить сообщение? Оно исчезнет у всех участников чата.')) return;
    deleteMutation.mutate({ roomId: activeRoomId, messageId });
  };

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
    if ((!inputText.trim() && !selectedFile) || !activeRoomId) return;
    sendMutation.mutate(
      { roomId: activeRoomId, text: inputText, file: selectedFile },
      {
        onSuccess: () => {
          setSelectedFile(null);
          setFileError('');
          if (fileInputRef.current) fileInputRef.current.value = '';
          scrollToBottom();
        },
      },
    );
    setInputText('');
    scrollToBottom();
  };

  const handleFileSelect = (files: FileList | null) => {
    setFileError('');
    if (!files || files.length === 0) return;
    const { valid, invalidFormat, tooLarge } = partitionFiles(files);
    if (invalidFormat.length > 0) {
      setSelectedFile(null);
      setFileError('Можно прикрепить PDF, JPG, PNG, DOC, DOCX, ZIP или MP3');
      return;
    }
    if (tooLarge.length > 0) {
      setSelectedFile(null);
      setFileError(`Превышен допустимый размер файла. ${FILE_SIZE_LIMITS_LABEL}.`);
      return;
    }
    setSelectedFile(valid[0] ?? null);
  };

  const renderAttachment = (msg: ChatMessageData, isOwn: boolean) => {
    if (!msg.attachment_filename || !msg.attachment_url) return null;
    return (
      <div className="mt-2 space-y-1.5">
        <a
          href={msg.attachment_url}
          target="_blank"
          rel="noreferrer"
          translate="no"
          className={`flex items-center gap-3 rounded-lg border px-3 py-2 transition-colors ${
            isOwn
              ? 'border-slate-500 bg-slate-600 hover:bg-slate-800 text-white'
              : 'border-gray-200 bg-gray-50 hover:bg-gray-100 text-gray-900'
          }`}
        >
          <FileText className="w-5 h-5 flex-shrink-0" />
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium">{msg.attachment_filename}</span>
            {msg.attachment_size ? (
              <span className={`block text-xs ${isOwn ? 'text-slate-200' : 'text-gray-500'}`}>
                {formatFileSize(msg.attachment_size)}
              </span>
            ) : null}
          </span>
        </a>
        {!isOwn && (
          <Link
            to={`/admin/documents-inbox?message=${msg.id}`}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-600 hover:text-blue-700"
          >
            <Inbox className="h-3.5 w-3.5" />
            Прикрепить к клиенту
          </Link>
        )}
      </div>
    );
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
          <div className="mb-3 flex gap-1 rounded-lg bg-gray-100 p-1" role="tablist" aria-label="Тип чата">
            {([
              ['admin', 'Рабочие вопросы'],
              ['tech_support', 'Техподдержка'],
            ] as const).map(([type, label]) => (
              <button key={type} type="button" role="tab" aria-selected={roomType === type}
                onClick={() => { setRoomType(type); setActiveRoomId(null); setShowJournal(false); clearWsMessages(); }}
                className={`flex-1 rounded-md px-2 py-2 text-sm font-medium ${roomType === type ? 'bg-white text-blue-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}>
                {label}
              </button>
            ))}
          </div>
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
              translate="no"
              onClick={() => { setActiveRoomId(room.id); clearWsMessages(); isInitialLoad.current = true; }}
              className={`w-full p-4 flex items-center gap-3 border-b border-gray-100 hover:bg-gray-50 transition-colors ${activeRoomId === room.id ? 'bg-blue-50' : ''}`}>
              <div className={`w-11 h-11 ${roomType === 'tech_support' ? 'bg-teal-600' : 'bg-blue-600'} rounded-full flex items-center justify-center flex-shrink-0`}>
                <span className="text-white font-semibold text-sm">{(room.partner_name ?? 'П').slice(0, 2).toUpperCase()}</span>
              </div>
              <div className="flex-1 text-left min-w-0">
                <div className="flex items-center justify-between">
                  <p className="font-medium text-gray-900 truncate">{room.partner_name ?? 'Партнёр'}</p>
                  {room.unread_count > 0 && <span className="bg-red-500 text-white text-xs rounded-full px-2 py-0.5 ml-2 flex-shrink-0">{room.unread_count}</span>}
                </div>
                <p className="text-sm text-gray-500 truncate">{decodeChatText(room.last_message ?? 'Нет сообщений')}</p>
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 flex flex-col bg-gray-50">
        {activeRoom ? (
          <>
            <div className="bg-white border-b border-gray-200 p-4 flex items-center gap-3">
              <div className={`w-10 h-10 ${roomType === 'tech_support' ? 'bg-teal-600' : 'bg-blue-600'} rounded-full flex items-center justify-center`}>
                <span className="text-white font-semibold text-sm">{(activeRoom.partner_name ?? 'П').slice(0, 2).toUpperCase()}</span>
              </div>
              <div translate="no">
                <h3 className="font-semibold text-gray-900">{activeRoom.partner_name ?? 'Партнёр'}</h3>
                <p className="text-sm text-gray-500">{roomType === 'tech_support' ? 'Техническая поддержка' : 'Чат с партнёром'}</p>
              </div>
              {roomType === 'admin' && <button
                type="button"
                onClick={() => setShowJournal((value) => !value)}
                className="ml-auto inline-flex items-center gap-2 rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
              >
                <History className="h-4 w-4" />
                История изменений
              </button>}
            </div>

            {showJournal && (
              <div className="border-b border-gray-200 bg-amber-50 px-6 py-3">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-900">
                  Изменения и удаления в Битрикс24
                </p>
                {eventsLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin text-amber-700" />
                ) : messageEvents.length === 0 ? (
                  <p className="text-sm text-amber-800">Изменений и удалений не зафиксировано.</p>
                ) : (
                  <div className="max-h-32 space-y-1 overflow-y-auto">
                    {messageEvents.map((event) => (
                      <p key={event.id} className="text-sm text-amber-900">
                        {event.event_type === 'updated' ? 'Сообщение изменено' : 'Сообщение удалено'} в Битрикс24
                        {' · '}{formatTime(event.event_at, tz)}
                        {' · '}ID {event.bitrix_message_id}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div ref={scrollContainerRef} onScroll={handleScroll} className="flex-1 overflow-y-auto p-6 space-y-4">
              {isFetchingNextPage && <div className="flex justify-center py-2"><Loader2 className="w-5 h-5 animate-spin text-gray-400" /></div>}
              {messagesLoading && <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-gray-400" /></div>}
              {!messagesLoading && allMessages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full text-gray-400">
                  <MessageSquare className="w-12 h-12 mb-3" /><p className="text-lg font-medium">Нет сообщений</p><p className="text-sm">Напишите первое сообщение партнёру</p>
                </div>
              )}
              {allMessages.map((msg, index) => {
                const isAdmin = msg.sender_type === 'admin';
                return (
                  <div key={msg.id}>
                    <ChatDateSeparator createdAt={msg.created_at} previousCreatedAt={allMessages[index - 1]?.created_at} timezone={tz} />
                    <div className={`flex ${isAdmin ? 'justify-end' : 'justify-start'}`}>
                      <div className="relative max-w-md group">
                        {!isAdmin && (
                          <div className="flex items-center gap-2 mb-1">
                            <div className="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center"><User className="w-3.5 h-3.5 text-blue-600" /></div>
                            <span className="text-xs text-gray-500">Партнёр</span>
                          </div>
                        )}
                        <div translate="no" className={`rounded-2xl px-4 py-3 ${isAdmin ? 'bg-slate-700 text-white' : 'bg-white border border-gray-200 text-gray-900'}`}>
                          {msg.text ? <p>{decodeChatText(msg.text)}</p> : null}
                          {renderAttachment(msg, isAdmin)}
                        </div>
                        <div className={`flex items-center gap-0.5 mt-1 ${isAdmin ? 'justify-end' : 'justify-start'}`}>
                          <span className="text-xs text-gray-500">{formatTime(msg.created_at, tz)}</span>
                          {isAdmin && <MessageStatus status={msg.delivery_status} />}
                        </div>
                        <button
                          type="button"
                          onClick={() => handleDeleteMessage(msg.id)}
                          disabled={deleteMutation.isPending}
                          aria-label="Удалить сообщение"
                          title="Удалить сообщение"
                          className="absolute -top-2 -right-2 z-10 rounded-full border border-gray-200 bg-white p-1 text-gray-400 opacity-0 shadow-sm transition-opacity hover:border-red-200 hover:text-red-600 group-hover:opacity-100 disabled:cursor-not-allowed"
                        >
                          {deleteMutation.isPending ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="h-3.5 w-3.5" />
                          )}
                        </button>
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
              {selectedFile && (
                <div className="mb-3 flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <FileText className="w-4 h-4 text-slate-600 flex-shrink-0" />
                    <span translate="no" className="truncate text-sm font-medium text-gray-900">{selectedFile.name}</span>
                    <span className="text-xs text-gray-500 flex-shrink-0">{formatFileSize(selectedFile.size)}</span>
                  </div>
                  <button
                    type="button"
                    className="rounded-md p-1 text-gray-500 hover:bg-white hover:text-gray-700"
                    onClick={() => {
                      setSelectedFile(null);
                      if (fileInputRef.current) fileInputRef.current.value = '';
                    }}
                    aria-label="Убрать файл"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              )}
              {fileError && <p className="mb-2 text-xs text-red-600">{fileError}</p>}
              <form onSubmit={handleSend} className="flex items-center gap-3">
                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  accept={ALLOWED_FILE_EXTENSIONS.join(',')}
                  onChange={(e) => handleFileSelect(e.target.files)}
                />
                <button
                  type="button"
                  className="p-3 border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
                  onClick={() => fileInputRef.current?.click()}
                  aria-label="Прикрепить файл"
                >
                  <Paperclip className="w-5 h-5" />
                </button>
                <input type="text" translate="no" value={inputText} onChange={(e) => { setInputText(e.target.value); sendTyping(); }}
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
