import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Send, User, Bot, Loader2, WifiOff, Paperclip, FileText, X, LifeBuoy } from 'lucide-react';
import { useInfiniteQuery, useMutation, useQueryClient, useQuery } from '@tanstack/react-query';
import {
  fetchChatRooms,
  fetchChatMessages,
  sendChatAttachment,
  sendChatMessage,
  ChatMessageData,
  ChatRoomData,
} from '../api/chat';
import { useWsChat } from '../hooks/useWsChat';
import MessageStatus from '../components/ui/MessageStatus';
import ChatDateSeparator from '../components/ui/ChatDateSeparator';
import { formatTime } from '@/app/utils/formatDate';
import { useTimezone } from '@/app/contexts/TimezoneContext';
import { ALLOWED_FILE_EXTENSIONS, formatFileSize, MAX_FILE_SIZE_LABEL, partitionFiles } from '../utils/files';

const PAGE_SIZE = 20;

const ROOM_TYPE_CONFIG: Record<string, { name: string; description: string; icon: typeof User; color: string }> = {
  admin: { name: 'Администратор', description: 'Рабочие вопросы по сотрудничеству', icon: User, color: 'bg-blue-600' },
  tech_support: { name: 'Техподдержка', description: 'Помощь с работой кабинета', icon: LifeBuoy, color: 'bg-teal-600' },
  arbitration_manager: { name: 'Арбитражный управляющий', description: 'Менеджер дела', icon: User, color: 'bg-slate-400' },
  assistant: { name: 'Помощник АУ', description: 'Петрова Анна Сергеевна', icon: User, color: 'bg-slate-400' },
  ai_assistant: { name: 'Нейропомощник', description: 'Искусственный интеллект', icon: Bot, color: 'bg-slate-400' },
};

function isActiveRoom(room: ChatRoomData): boolean {
  return room.type === 'admin' || room.type === 'tech_support';
}

export default function Chat() {
  const tz = useTimezone();
  const [activeRoomId, setActiveRoomId] = useState<string | null>(null);
  const [inputText, setInputText] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const isInitialLoad = useRef(true);
  const queryClient = useQueryClient();

  const { wsMessages, wsConnected, typingUsers, sendTyping, clearWsMessages } = useWsChat(activeRoomId, {
    roomsQueryKey: ['chatRooms'],
    unreadQueryKey: ['partnerUnreadCount'],
    messagesQueryPrefix: 'chatMessages',
    readerRole: 'partner',
    ownSenderType: 'user',
  });

  const { data: rooms } = useQuery({ queryKey: ['chatRooms'], queryFn: fetchChatRooms });

  const {
    data: messagesData,
    isLoading: messagesLoading,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['chatMessages', activeRoomId],
    queryFn: ({ pageParam }) => fetchChatMessages(activeRoomId!, { limit: PAGE_SIZE, before: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => (lastPage.length < PAGE_SIZE ? undefined : lastPage[0]?.id),
    enabled: !!activeRoomId,
    refetchInterval: 15_000,
  });

  const cachedMessages = useMemo(() => (messagesData?.pages ?? []).flat(), [messagesData]);

  const sendMutation = useMutation({
    mutationFn: ({ roomId, text, file }: { roomId: string; text: string; file?: File | null }) =>
      file ? sendChatAttachment(roomId, text, file) : sendChatMessage(roomId, text),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chatMessages', activeRoomId] });
      queryClient.invalidateQueries({ queryKey: ['chatRooms'] });
    },
  });

  useEffect(() => {
    if (rooms && rooms.length > 0 && !activeRoomId) {
      const adminRoom = rooms.find((r) => r.type === 'admin');
      setActiveRoomId(adminRoom?.id ?? rooms[0].id);
    }
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
      setFileError('Можно прикрепить PDF, JPG, PNG, DOC или DOCX');
      return;
    }
    if (tooLarge.length > 0) {
      setSelectedFile(null);
      setFileError(`Файл должен быть не больше ${MAX_FILE_SIZE_LABEL}`);
      return;
    }
    setSelectedFile(valid[0] ?? null);
  };

  const renderAttachment = (msg: ChatMessageData, isOwn: boolean) => {
    if (!msg.attachment_filename || !msg.attachment_url) return null;
    return (
      <a
        href={msg.attachment_url}
        target="_blank"
        rel="noreferrer"
        className={`mt-2 flex items-center gap-3 rounded-lg border px-3 py-2 transition-colors ${
          isOwn
            ? 'border-blue-400 bg-blue-500 hover:bg-blue-700 text-white'
            : 'border-gray-200 bg-gray-50 hover:bg-gray-100 text-gray-900'
        }`}
      >
        <FileText className="w-5 h-5 flex-shrink-0" />
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium">{msg.attachment_filename}</span>
          {msg.attachment_size ? (
            <span className={`block text-xs ${isOwn ? 'text-blue-100' : 'text-gray-500'}`}>
              {formatFileSize(msg.attachment_size)}
            </span>
          ) : null}
        </span>
      </a>
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
  const activeConfig = activeRoom ? (ROOM_TYPE_CONFIG[activeRoom.type] ?? ROOM_TYPE_CONFIG.admin) : ROOM_TYPE_CONFIG.admin;
  const ActiveIcon = activeConfig.icon;
  const isCurrentRoomActive = activeRoom ? isActiveRoom(activeRoom) : false;

  return (
    <div className="h-[calc(100vh-53px)] flex">
      <div className="w-80 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Чаты</h2>
          <p className="text-sm text-gray-600 mt-1">
            {wsConnected ? 'Подключено' : (
              <span className="flex items-center gap-1 text-orange-600">
                <WifiOff className="w-3 h-3" /> Переподключение...
              </span>
            )}
          </p>
        </div>
        <div className="flex-1 overflow-y-auto">
          {(rooms ?? []).filter(isActiveRoom).map((room) => {
            const cfg = ROOM_TYPE_CONFIG[room.type] ?? ROOM_TYPE_CONFIG.admin;
            const Icon = cfg.icon;
            return (
              <button
                key={room.id}
                onClick={() => { setActiveRoomId(room.id); clearWsMessages(); isInitialLoad.current = true; }}
                className={`w-full p-4 flex items-center gap-3 border-b border-gray-100 transition-colors ${
                  activeRoomId === room.id ? 'bg-blue-50 hover:bg-blue-50' : 'hover:bg-gray-50'
                }`}
              >
                <div className={`w-12 h-12 ${cfg.color} rounded-full flex items-center justify-center flex-shrink-0`}>
                  <Icon className="w-6 h-6 text-white" />
                </div>
                <div className="flex-1 text-left">
                  <div className="flex items-center justify-between">
                    <p className="font-medium text-gray-900">{cfg.name}</p>
                    {room.unread_count > 0 && <span className="bg-blue-600 text-white text-xs rounded-full px-2 py-0.5">{room.unread_count}</span>}
                  </div>
                  <p className="text-sm truncate text-gray-500">{room.last_message ?? cfg.description}</p>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex-1 flex flex-col bg-gray-50">
        <div className="bg-white border-b border-gray-200 p-4 flex items-center gap-3">
          <div className={`w-10 h-10 ${isCurrentRoomActive ? activeConfig.color : 'bg-gray-300'} rounded-full flex items-center justify-center`}>
            <ActiveIcon className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{activeConfig.name}</h3>
            <p className="text-sm text-gray-600">{activeConfig.description}</p>
          </div>
        </div>

        <div ref={scrollContainerRef} onScroll={handleScroll} className="flex-1 overflow-y-auto p-6 space-y-4">
          {isFetchingNextPage && <div className="flex justify-center py-2"><Loader2 className="w-5 h-5 animate-spin text-gray-400" /></div>}
          {messagesLoading && <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-gray-400" /></div>}
          {!messagesLoading && allMessages.length === 0 && isCurrentRoomActive && (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <ActiveIcon className="w-12 h-12 mb-3" /><p className="text-lg font-medium">Начните диалог: {activeConfig.name}</p><p className="text-sm">Напишите ваш первый вопрос</p>
            </div>
          )}
          {allMessages.map((msg, index) => {
            const isUser = msg.sender_type === 'user';
            return (
              <div key={msg.id}>
                <ChatDateSeparator createdAt={msg.created_at} previousCreatedAt={allMessages[index - 1]?.created_at} timezone={tz} />
                <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                  <div className="max-w-md">
                    <div className={`rounded-2xl px-4 py-3 ${isUser ? 'bg-blue-600 text-white' : 'bg-white border border-gray-200 text-gray-900'}`}>
                      {msg.text ? <p>{msg.text}</p> : null}
                      {renderAttachment(msg, isUser)}
                    </div>
                    <div className={`flex items-center gap-0.5 mt-1 ${isUser ? 'justify-end' : 'justify-start'}`}>
                      <span className="text-xs text-gray-500">{formatTime(msg.created_at, tz)}</span>
                      {isUser && <MessageStatus status={msg.delivery_status} />}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
          <div ref={messagesEndRef} />
        </div>

        <div className="bg-white border-t border-gray-200 p-4">
          {activeRoomId && typingUsers[activeRoomId] && (
            <p className="text-xs text-gray-400 mb-2 animate-pulse">Печатает...</p>
          )}
          {selectedFile && (
            <div className="mb-3 flex items-center justify-between gap-3 rounded-lg border border-blue-100 bg-blue-50 px-3 py-2">
              <div className="flex min-w-0 items-center gap-2">
                <FileText className="w-4 h-4 text-blue-600 flex-shrink-0" />
                <span className="truncate text-sm font-medium text-gray-900">{selectedFile.name}</span>
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
            <input type="text" value={inputText} onChange={(e) => { setInputText(e.target.value); sendTyping(); }}
              placeholder="Введите сообщение..." className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
            <button type="submit" disabled={sendMutation.isPending}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2 disabled:opacity-50">
              {sendMutation.isPending ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />} Отправить
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
