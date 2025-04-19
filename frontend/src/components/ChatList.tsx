import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getChats, getProfiles } from '../services/api'
import { Profile } from '../types'
import ErrorDisplay from './ErrorDisplay'
import { logError } from '../utils/errorHandler'
import { format } from 'date-fns'

interface ChatListProps {
  selectedProfile: Profile | null
  onSelectProfile: (profile: Profile) => void
}

const ChatList = ({ selectedProfile, onSelectProfile }: ChatListProps) => {
  const navigate = useNavigate()
  const location = useLocation()
  const [profileId, setProfileId] = useState<number | null>(null)
  
  // Parse profile ID from query parameters
  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const profileParam = params.get('profile')
    if (profileParam) {
      const id = parseInt(profileParam)
      if (!isNaN(id)) {
        setProfileId(id)
      }
    }
  }, [location.search])
  
  // Fetch profiles
  const { 
    data: profiles = [], 
    isLoading: profilesLoading, 
    error: profilesError 
  } = useQuery({
    queryKey: ['profiles'],
    queryFn: getProfiles
  })
  
  // Set the selected profile if it's not already set
  useEffect(() => {
    if (profileId && profiles.length > 0 && !selectedProfile) {
      const profile = profiles.find(p => p.id === profileId)
      if (profile) {
        onSelectProfile(profile)
      }
    }
  }, [profileId, profiles, selectedProfile, onSelectProfile])
  
  // Fetch chats for the selected profile
  const { 
    data: chats = [], 
    isLoading: chatsLoading, 
    error: chatsError,
    refetch: refetchChats
  } = useQuery({
    queryKey: ['chats', profileId],
    queryFn: () => getChats(profileId || undefined),
    enabled: !!profileId
  })
  
  const handleSelectChat = (chatId: number) => {
    navigate(`/chat/${chatId}`)
  }
  
  const handleChangeProfile = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = parseInt(e.target.value)
    if (!isNaN(id)) {
      const profile = profiles.find(p => p.id === id)
      if (profile) {
        onSelectProfile(profile)
        setProfileId(id)
        navigate(`/chats?profile=${id}`)
      }
    }
  }
  
  const handleBackToProfiles = () => {
    navigate('/')
  }
  
  if (profilesLoading) {
    return (
      <div className="p-4 flex justify-center items-center h-64">
        <div className="bg-gray-800 rounded-lg p-6 text-center">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-4 text-gray-300">Loading profiles...</p>
        </div>
      </div>
    )
  }
  
  if (profilesError) {
    logError(profilesError, 'Loading profiles')
    return (
      <div className="p-4">
        <ErrorDisplay 
          error={profilesError} 
          retry={() => navigate(0)} 
          className="max-w-2xl mx-auto"
        />
      </div>
    )
  }
  
  return (
    <div className="flex flex-col w-full max-w-4xl mx-auto p-4">
      <div className="flex items-center mb-6">
        <button
          onClick={handleBackToProfiles}
          className="mr-4 bg-gray-700 hover:bg-gray-600 text-white font-bold py-2 px-4 rounded"
        >
          ← Back to Profiles
        </button>
        <h2 className="text-2xl font-bold">Chat History</h2>
      </div>
      
      <div className="bg-gray-800 p-4 rounded-lg mb-6">
        <label className="block text-sm font-medium mb-2">Select Profile</label>
        <select
          value={profileId || ''}
          onChange={handleChangeProfile}
          className="w-full p-2 bg-gray-700 rounded border border-gray-600"
        >
          <option value="" disabled>Select a profile</option>
          {profiles.map(profile => (
            <option key={profile.id} value={profile.id}>
              {profile.name} ({profile.model_name})
            </option>
          ))}
        </select>
      </div>
      
      {chatsLoading && (
        <div className="p-4 flex justify-center items-center h-32">
          <div className="bg-gray-800 rounded-lg p-6 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
            <p className="mt-2 text-gray-300">Loading chats...</p>
          </div>
        </div>
      )}
      
      {chatsError && (
        <div className="mt-4">
          <ErrorDisplay 
            error={chatsError} 
            retry={() => refetchChats()} 
            className="max-w-2xl mx-auto"
          />
        </div>
      )}
      
      {!chatsLoading && chats.length === 0 && profileId && (
        <div className="bg-gray-800 p-6 rounded-lg text-center">
          <p className="text-gray-300 mb-4">No chats found for this profile.</p>
          <button
            onClick={() => navigate(`/`)}
            className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
          >
            Create New Chat
          </button>
        </div>
      )}
      
      {chats.length > 0 && (
        <div className="grid grid-cols-1 gap-4">
          {chats.map(chat => (
            <div
              key={chat.id}
              className="bg-gray-800 p-4 rounded-lg border border-gray-700 hover:border-blue-500 cursor-pointer transition-colors"
              onClick={() => handleSelectChat(chat.id)}
            >
              <div className="flex justify-between items-center">
                <h3 className="text-xl font-semibold">{chat.title}</h3>
                <span className="text-sm text-gray-400">
                  {format(new Date(chat.created_at), 'MMM d, yyyy h:mm a')}
                </span>
              </div>
              <div className="mt-2 text-gray-300">
                <p>
                  <span className="text-gray-400">{chat.messages?.length || 0} messages</span>
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default ChatList
