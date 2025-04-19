import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getChats, deleteChat } from '../services/api'
import { Chat } from '../types'
import { FiTrash2, FiMessageSquare, FiX } from 'react-icons/fi'
// Note: We need to install date-fns package with: pnpm add date-fns
// For now, let's create a simple date formatter function
const formatDistanceToNow = (date: Date): string => {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);
  
  if (diffDay > 0) {
    return `${diffDay} day${diffDay > 1 ? 's' : ''} ago`;
  } else if (diffHour > 0) {
    return `${diffHour} hour${diffHour > 1 ? 's' : ''} ago`;
  } else if (diffMin > 0) {
    return `${diffMin} minute${diffMin > 1 ? 's' : ''} ago`;
  } else {
    return 'just now';
  }
}

interface ChatHistoryProps {
  profileId: number
  currentChatId?: number
  onSelectChat: (chatId: number) => void
  onClose: () => void
}

const ChatHistory = ({ profileId, currentChatId, onSelectChat, onClose }: ChatHistoryProps) => {
  const navigate = useNavigate()
  
  // Fetch chats for the current profile
  const { 
    data: chats = [], 
    isLoading, 
    error,
    refetch: refetchChats
  } = useQuery({
    queryKey: ['chats', profileId],
    queryFn: () => getChats(profileId),
    enabled: !!profileId
  })
  
  const handleDeleteChat = async (chatId: number, e: React.MouseEvent) => {
    e.stopPropagation() // Prevent triggering the chat selection
    
    if (window.confirm('Are you sure you want to delete this chat?')) {
      try {
        await deleteChat(chatId)
        
        // If we're deleting the current chat, navigate back to profiles
        if (currentChatId === chatId) {
          navigate('/')
        } else {
          // Otherwise just refetch the chat list
          refetchChats()
        }
      } catch (error) {
        console.error('Error deleting chat:', error)
        alert('Failed to delete chat')
      }
    }
  }
  
  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString)
      return formatDistanceToNow(date)
    } catch (e) {
      return 'Unknown date'
    }
  }
  
  return (
    <div className="w-64 h-full bg-gray-800 border-r border-gray-700 flex flex-col">
      <div className="p-3 border-b border-gray-700 flex justify-between items-center">
        <h2 className="text-lg font-semibold">Chat History</h2>
        <button 
          onClick={onClose}
          className="p-1 rounded-full hover:bg-gray-700 text-gray-400"
          aria-label="Close chat history"
          title="Close chat history"
        >
          <FiX />
        </button>
      </div>
      
      {isLoading ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
        </div>
      ) : error ? (
        <div className="p-4 text-red-400 text-center">
          <p>Failed to load chats</p>
          <button 
            onClick={() => refetchChats()}
            className="mt-2 text-blue-400 hover:underline"
          >
            Try again
          </button>
        </div>
      ) : chats.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-gray-500 text-center p-4">
          <div>
            <FiMessageSquare className="mx-auto mb-2 text-2xl" />
            <p>No chat history yet</p>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto">
          {chats.map((chat: Chat) => (
            <div 
              key={chat.id}
              onClick={() => onSelectChat(chat.id)}
              className={`p-3 border-b border-gray-700 hover:bg-gray-700 cursor-pointer flex justify-between items-start ${
                currentChatId === chat.id ? 'bg-gray-700' : ''
              }`}
            >
              <div className="overflow-hidden">
                <h3 className="font-medium truncate">{chat.title}</h3>
                <p className="text-xs text-gray-400">{formatDate(chat.created_at)}</p>
              </div>
              <button
                onClick={(e) => handleDeleteChat(chat.id, e)}
                className="p-1 text-gray-400 hover:text-red-400 rounded"
                aria-label="Delete chat"
                title="Delete chat"
              >
                <FiTrash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default ChatHistory
