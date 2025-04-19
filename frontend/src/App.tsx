import { useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import ProfileManager from './components/ProfileManager'
import Chat from './components/Chat'
import ChatList from './components/ChatList'
import { Profile } from './types'

const App = () => {
  const [selectedProfile, setSelectedProfile] = useState<Profile | null>(null)

  return (
    <div className="flex flex-col h-screen bg-gray-900 text-white">
      <header className="bg-gray-800 p-4 shadow-md">
        <h1 className="text-2xl font-bold">LocalChat</h1>
      </header>
      
      <main className="flex flex-1 overflow-hidden">
        <Routes>
          <Route 
            path="/" 
            element={
              <ProfileManager 
                onSelectProfile={setSelectedProfile}
                selectedProfile={selectedProfile}
              />
            } 
          />
          <Route 
            path="/chats" 
            element={
              <ChatList 
                selectedProfile={selectedProfile}
                onSelectProfile={setSelectedProfile}
              />
            } 
          />
          <Route 
            path="/chat/:chatId" 
            element={
              selectedProfile ? (
                <Chat profile={selectedProfile} />
              ) : (
                <Navigate to="/" replace />
              )
            } 
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      
      <footer className="bg-gray-800 p-2 text-center text-sm text-gray-400">
        LocalChat - Chat with AI Models
      </footer>
    </div>
  )
}

export default App
