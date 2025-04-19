import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getChat, getMessages, sendMessage, cancelStreamingResponse } from '../services/api'
import { Profile, Message as MessageType, MessageFormData, StreamingOptions } from '../types'
import MessageInput from './MessageInput.tsx'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import remarkGfm from 'remark-gfm'
import { FiArrowLeft, FiRefreshCw, FiZap, FiZapOff, FiList } from 'react-icons/fi'
import ErrorDisplay, { ModelApiErrorDisplay } from './ErrorDisplay'
import { logError, isModelApiError } from '../utils/errorHandler'
import ChatHistory from './ChatHistory'

// Helper function to sanitize markdown content
const sanitizeMarkdown = (content: string): string => {
  if (!content) return ''
  
  try {
    // Fix common markdown issues that could cause parsing errors
    
    // 1. Fix incomplete table syntax
    // Look for table-like structures that might be incomplete
    const hasTableStart = content.includes('|') && content.includes('---')
    
    if (hasTableStart) {
      // Make sure tables have proper formatting
      const lines = content.split('\n')
      let inTable = false
      let tableStartIndex = -1
      let hasHeader = false
      let hasDivider = false
      
      // Find potential table starts
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim()
        
        if (line.startsWith('|') && line.endsWith('|')) {
          if (!inTable) {
            inTable = true
            tableStartIndex = i
          }
          
          if (inTable && i === tableStartIndex) {
            hasHeader = true
          }
          
          // Check for divider row
          if (inTable && i === tableStartIndex + 1 && line.replace(/[^\-|]/g, '') === line) {
            hasDivider = true
          }
        } else if (inTable && line === '') {
          // End of table
          inTable = false
          
          // Fix incomplete tables
          if (hasHeader && !hasDivider) {
            // Add missing divider
            const headerCells = lines[tableStartIndex].split('|').length - 2
            const divider = '|' + ' --- |'.repeat(headerCells > 0 ? headerCells : 1)
            lines.splice(tableStartIndex + 1, 0, divider)
            i++
          }
          
          hasHeader = false
          hasDivider = false
        }
      }
      
      // Handle case where table is at the end of content
      if (inTable && hasHeader && !hasDivider) {
        const headerCells = lines[tableStartIndex].split('|').length - 2
        const divider = '|' + ' --- |'.repeat(headerCells > 0 ? headerCells : 1)
        lines.splice(tableStartIndex + 1, 0, divider)
      }
      
      content = lines.join('\n')
    }
    
    // 2. Fix code blocks that might be incomplete
    const codeBlockRegex = /```([^\n]*)(\n[\s\S]*?)?(```)?/g
    content = content.replace(codeBlockRegex, (match, lang, code, end) => {
      if (!end) {
        return `\`\`\`${lang || ''}${code || ''}\`\`\``
      }
      return match
    })
    
    return content
  } catch (error) {
    console.error('Error sanitizing markdown:', error)
    return content // Return original content if sanitization fails
  }
}

interface ChatProps {
  profile: Profile
}

const Chat = ({ profile }: ChatProps) => {
  const { chatId } = useParams<{ chatId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [input, setInput] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const [streamingEnabled, setStreamingEnabled] = useState(true)
  const [streamingMessage, setStreamingMessage] = useState('')
  const [showChatHistory, setShowChatHistory] = useState(false)
  const [showTooltip, setShowTooltip] = useState<string | null>(null)
  const [markdownEnabled, setMarkdownEnabled] = useState(true)
  
  // Fetch chat data
  const { data: chat, isLoading: chatLoading, error: chatError } = useQuery({
    queryKey: ['chat', chatId],
    queryFn: () => getChat(Number(chatId)),
    enabled: !!chatId
  })
  
  // Fetch messages
  const { 
    data: messages = [], 
    isLoading: messagesLoading, 
    error: messagesError,
    refetch: refetchMessages
  } = useQuery({
    queryKey: ['messages', chatId],
    queryFn: () => getMessages(Number(chatId)),
    enabled: !!chatId,
    refetchInterval: isTyping ? 3000 : false, // Auto-refresh during streaming
    staleTime: 1000 // Consider data stale after 1 second
  })
  
  // Local state for optimistic updates
  const [localMessages, setLocalMessages] = useState<MessageType[]>([])
  
  // Update local messages when server messages change
  useEffect(() => {
    if (messages && messages.length > 0) {
      setLocalMessages(messages)
      
      // Log message details for debugging
      console.log(`Loaded ${messages.length} messages from server:`, 
        messages.map(m => ({ id: m.id, role: m.role, contentLength: m.content.length }))
      )
    }
  }, [messages])
  
  // Periodically refresh messages to ensure we have the latest data
  useEffect(() => {
    if (!chatId) return
    
    // Set up a timer to refresh messages every 5 seconds during streaming
    // This ensures we get the saved AI responses from the database
    const intervalId = setInterval(() => {
      if (isTyping) {
        refetchMessages()
      }
    }, 5000)
    
    return () => clearInterval(intervalId)
  }, [chatId, isTyping, refetchMessages])
  
  // Send message mutation
  const sendMessageMutation = useMutation({
    mutationFn: (message: MessageFormData) => {
      // Check if we should use streaming for Ollama
      const isOllamaApi = profile.url.toLowerCase().includes('ollama') || 
                         profile.url.endsWith('/api/generate')
      
      // Immediately add the user message to local messages for display
      const userMessage: MessageType = {
        id: Date.now(), // Temporary ID
        chat_id: Number(chatId),
        role: 'user',
        content: message.content,
        created_at: new Date().toISOString()
      }
      
      setLocalMessages(prev => [...prev, userMessage])
      
      if (streamingEnabled && isOllamaApi) {
        // Clear any previous streaming message
        setStreamingMessage('')
        
        // Set up streaming options
        const streamingOptions: StreamingOptions = {
          streaming: true,
          onChunk: (event: MessageEvent) => {
            const data = event.data
            
            if (data === '[DONE]') {
              setIsTyping(false)
              refetchMessages()
              return
            }
            
            try {
              // Parse the JSON-encoded chunk
              const parsedData = JSON.parse(data)
              setStreamingMessage(prev => prev + parsedData)
            } catch (error) {
              // Fallback to using raw data if JSON parsing fails
              setStreamingMessage(prev => prev + data)
            }
          },
          onComplete: () => {
            // Save the final streaming message before setting isTyping to false
            const finalMessage = streamingMessage
            
            // Add the AI response to local messages
            if (finalMessage && finalMessage.trim() !== '') {
              // Sanitize the markdown content before saving
              const sanitizedContent = sanitizeMarkdown(finalMessage)
              
              const aiMessage: MessageType = {
                id: Date.now() + 1, // Another temporary ID
                chat_id: Number(chatId),
                role: 'assistant',
                content: sanitizedContent,
                created_at: new Date().toISOString()
              }
              
              setLocalMessages(prev => [...prev, aiMessage])
            }
            
            setIsTyping(false)
            refetchMessages()
          },
          onError: (error) => {
            console.error('Error in streaming response:', error)
            setIsTyping(false)
            refetchMessages()
          }
        }
        
        return sendMessage(Number(chatId), message, streamingOptions)
      } else {
        // Use regular non-streaming API
        return sendMessage(Number(chatId), message)
      }
    },
    onMutate: () => {
      setIsTyping(true)
    },
    onSuccess: () => {
      // For non-streaming responses, we need to refresh the messages
      if (!streamingEnabled) {
        queryClient.invalidateQueries({ queryKey: ['messages', chatId] })
      }
      setInput('')
      if (!streamingEnabled) {
        setIsTyping(false)
      }
    },
    onError: (error) => {
      logError(error, 'Sending message')
      setIsTyping(false)
    }
  })
  
  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])
  
  // Add keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Only handle keyboard shortcuts when not typing in the input field
      const isTypingInInput = document.activeElement?.tagName === 'INPUT' || 
                             document.activeElement?.tagName === 'TEXTAREA';
      
      if (isTypingInInput) return;
      
      // Keyboard shortcuts
      switch (e.key) {
        case 'h': // Toggle chat history
          setShowChatHistory(prev => !prev);
          break;
        case 's': // Toggle streaming
          setStreamingEnabled(prev => !prev);
          break;
        case 'm': // Toggle markdown formatting
          setMarkdownEnabled(prev => !prev);
          break;
        case 'r': // Refresh messages
          refetchMessages();
          break;
        case 'Escape': // Close chat history if open
          if (showChatHistory) {
            setShowChatHistory(false);
          }
          break;
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [refetchMessages, showChatHistory])
  
  const handleSendMessage = (e: React.FormEvent): void => {
    e.preventDefault()
    if (!input.trim()) return
    
    let messageContent = input.trim()
    
    // Add Markdown formatting hint for LLMs if markdown is enabled
    if (markdownEnabled) {
      const isGemma = profile.model_name.toLowerCase().includes('gemma')
      const isLlama = profile.model_name.toLowerCase().includes('llama')
      const isCodeModel = profile.model_name.toLowerCase().includes('code') ||
                         profile.model_name.toLowerCase().includes('starcoder')
      
      // Only add the hint if the user hasn't already specified a format
      if (!messageContent.toLowerCase().includes('markdown') && 
          !messageContent.toLowerCase().includes('format')) {
        
        // Add a model-specific hint
        if (isCodeModel) {
          messageContent += '\n\nPlease format your response using Markdown with proper code blocks including language identifiers for syntax highlighting.'
        } else if (isGemma || isLlama) {
          messageContent += '\n\nPlease format your response using Markdown with proper headings, lists, and code blocks with syntax highlighting where appropriate.'
        } else {
          messageContent += '\n\nPlease use Markdown formatting in your response.'
        }
      }
    }
    
    const message: MessageFormData = {
      role: 'user',
      content: messageContent
    }
    
    sendMessageMutation.mutate(message)
  }
  
  // Handle stopping the streaming response
  const handleStopStreaming = (): void => {
    // Save the current streaming message before cancelling
    const finalMessage = streamingMessage
    
    // Cancel the streaming request
    cancelStreamingResponse()
    
    // Update UI state
    setIsTyping(false)
    
    // Add the partial AI response to local messages if it exists
    if (finalMessage && finalMessage.trim() !== '') {
      // Sanitize the markdown content before saving
      const sanitizedContent = sanitizeMarkdown(finalMessage)
      
      const aiMessage: MessageType = {
        id: Date.now(), // Temporary ID
        chat_id: Number(chatId),
        role: 'assistant',
        content: sanitizedContent,
        created_at: new Date().toISOString()
      }
      
      setLocalMessages(prev => [...prev, aiMessage])
    }
    
    // Refresh messages multiple times to ensure we get the latest data
    // The backend might take some time to save the message
    const refreshInterval = setInterval(() => {
      refetchMessages()
    }, 1000) // Try every second
    
    // Stop refreshing after 5 seconds
    setTimeout(() => {
      clearInterval(refreshInterval)
    }, 5000)
  }
  
  const handleBackToProfiles = () => {
    navigate('/')
  }
  
  const handleSelectChat = (selectedChatId: number) => {
    navigate(`/chat/${selectedChatId}`)
    // Don't automatically close the sidebar to allow for quick chat switching
  }
  
  if (chatLoading || messagesLoading) {
    return (
      <div className="flex-1 p-4 flex items-center justify-center">
        <div className="bg-gray-800 rounded-lg p-6 text-center">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-4 text-gray-300">Loading chat...</p>
        </div>
      </div>
    )
  }
  
  if (chatError) {
    logError(chatError, 'Loading chat')
    return (
      <div className="flex-1 p-4">
        <ErrorDisplay 
          error={chatError} 
          retry={() => navigate('/')} 
          className="max-w-2xl mx-auto"
        />
      </div>
    )
  }
  
  if (messagesError) {
    logError(messagesError, 'Loading messages')
    return (
      <div className="flex-1 p-4">
        <ErrorDisplay 
          error={messagesError} 
          retry={() => refetchMessages()} 
          className="max-w-2xl mx-auto"
        />
      </div>
    )
  }
  
  if (!chat) {
    return <div className="flex-1 p-4 text-red-500">Chat not found</div>
  }
  
  return (
    <div className="flex h-full w-full">
      {/* Chat History Sidebar */}
      {showChatHistory && (
        <ChatHistory 
          profileId={profile.id}
          currentChatId={Number(chatId)}
          onSelectChat={handleSelectChat}
          onClose={() => setShowChatHistory(false)}
        />
      )}
      
      {/* Main Chat Area */}
      <div className="flex flex-col flex-1 h-full">
        <div className="bg-gray-800 p-4 flex items-center justify-between">
          <div className="flex items-center">
            <button
              onClick={handleBackToProfiles}
              className="mr-4 p-2 rounded-full hover:bg-gray-700"
              aria-label="Back to profiles"
              title="Back to profiles"
            >
              <FiArrowLeft />
            </button>
            <div>
              <h2 className="text-xl font-bold">{chat.title}</h2>
              <p className="text-sm text-gray-400">
                Using {profile.name} ({profile.model_name})
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            {/* Chat History Button */}
            <div className="relative">
              <button
                onClick={() => setShowChatHistory(!showChatHistory)}
                className={`p-2 rounded-full hover:bg-gray-700 ${showChatHistory ? 'bg-gray-700' : ''}`}
                aria-label="Toggle chat history"
                title="Toggle chat history"
                onMouseEnter={() => setShowTooltip('history')}
                onMouseLeave={() => setShowTooltip(null)}
              >
                <FiList />
              </button>
              {showTooltip === 'history' && (
                <div className="absolute right-0 top-full mt-2 bg-gray-800 text-white text-xs p-2 rounded shadow-lg whitespace-nowrap z-10">
                  View chat history <span className="text-gray-400 ml-1">(H)</span>
                </div>
              )}
            </div>
            
            {/* Streaming Toggle Button */}
            <div className="relative">
              <button
                onClick={() => setStreamingEnabled(!streamingEnabled)}
                className={`p-2 rounded-full hover:bg-gray-700 ${streamingEnabled ? 'text-yellow-400' : 'text-gray-400'}`}
                aria-label={streamingEnabled ? 'Disable streaming' : 'Enable streaming'}
                onMouseEnter={() => setShowTooltip('streaming')}
                onMouseLeave={() => setShowTooltip(null)}
              >
                {streamingEnabled ? <FiZap /> : <FiZapOff />}
              </button>
              {showTooltip === 'streaming' && (
                <div className="absolute right-0 top-full mt-2 bg-gray-800 text-white text-xs p-2 rounded shadow-lg whitespace-nowrap z-10">
                  {streamingEnabled ? 
                    "Streaming enabled: See responses as they're generated" : 
                    "Streaming disabled: Wait for complete responses"}
                  <span className="text-gray-400 ml-1">(S)</span>
                </div>
              )}
            </div>
            
            {/* Markdown Toggle Button */}
            <div className="relative">
              <button
                onClick={() => setMarkdownEnabled(!markdownEnabled)}
                className={`p-2 rounded-full hover:bg-gray-700 ${markdownEnabled ? 'text-green-400' : 'text-gray-400'}`}
                aria-label={markdownEnabled ? 'Disable Markdown formatting' : 'Enable Markdown formatting'}
                onMouseEnter={() => setShowTooltip('markdown')}
                onMouseLeave={() => setShowTooltip(null)}
              >
                <span className="font-mono text-sm font-bold">MD</span>
              </button>
              {showTooltip === 'markdown' && (
                <div className="absolute right-0 top-full mt-2 bg-gray-800 text-white text-xs p-2 rounded shadow-lg whitespace-nowrap z-10">
                  {markdownEnabled ? 
                    "Markdown formatting enabled: Responses will be formatted with headings, lists, and code blocks" : 
                    "Markdown formatting disabled: Plain text responses"}
                  <span className="text-gray-400 ml-1">(M)</span>
                </div>
              )}
            </div>
            
            {/* Refresh Button */}
            <div className="relative">
              <button
                onClick={() => refetchMessages()}
                className="p-2 rounded-full hover:bg-gray-700"
                aria-label="Refresh messages"
                onMouseEnter={() => setShowTooltip('refresh')}
                onMouseLeave={() => setShowTooltip(null)}
              >
                <FiRefreshCw />
              </button>
              {showTooltip === 'refresh' && (
                <div className="absolute right-0 top-full mt-2 bg-gray-800 text-white text-xs p-2 rounded shadow-lg whitespace-nowrap z-10">
                  Refresh messages <span className="text-gray-400 ml-1">(R)</span>
                </div>
              )}
            </div>
          </div>
        </div>
      
        <div className="flex-1 overflow-y-auto p-4 bg-gray-900">
          {/* Error message from sending a message */}
          {sendMessageMutation.error && (
          <div className="mb-4">
            {isModelApiError(sendMessageMutation.error) ? (
              <ModelApiErrorDisplay 
                error={sendMessageMutation.error} 
                retry={() => sendMessageMutation.reset()}
              />
            ) : (
              <ErrorDisplay 
                error={sendMessageMutation.error} 
                retry={() => sendMessageMutation.reset()}
              />
            )}
          </div>
        )}
        
        {localMessages.length === 0 ? (
          <div className="text-center text-gray-500 mt-8 max-w-2xl mx-auto p-6 bg-gray-800/50 rounded-lg border border-gray-700">
            <h3 className="text-xl font-semibold mb-4">Welcome to a new chat!</h3>
            <p className="mb-3">You're now chatting with <span className="text-blue-400">{profile.model_name}</span> using the <span className="text-blue-400">{profile.name}</span> profile.</p>
            
            <div className="bg-gray-800 p-4 rounded-lg mb-4 text-left">
              <h4 className="text-sm font-semibold mb-2 text-gray-400">Tips:</h4>
              <ul className="list-disc list-inside space-y-2 text-sm">
                <li>Ask questions, request code examples, or discuss any topic</li>
                <li>Use the <FiZap className="inline text-yellow-400" /> toggle to enable/disable streaming responses <span className="text-gray-500">(press S)</span></li>
                <li>Toggle <span className="font-mono font-bold">MD</span> to enable/disable Markdown formatting <span className="text-gray-500">(press M)</span></li>
                <li>View your chat history with the <FiList className="inline" /> button <span className="text-gray-500">(press H)</span></li>
                <li>Refresh messages with the <FiRefreshCw className="inline" /> button if needed <span className="text-gray-500">(press R)</span></li>
                <li>Press <span className="bg-gray-700 px-1 rounded">Esc</span> to close the chat history sidebar</li>
              </ul>
            </div>
            
            <p className="text-sm">Start the conversation by sending a message below</p>
          </div>
        ) : (
          localMessages.map((message: MessageType) => (
            <div
              key={message.id}
              className={`mb-4 p-4 rounded-lg max-w-3xl ${
                message.role === 'user'
                  ? 'ml-auto bg-blue-600'
                  : 'mr-auto bg-gray-700'
              }`}
            >
              <div className="text-sm font-bold mb-1">
                {message.role === 'user' ? 'You' : 'AI'}
              </div>
              <div className="prose prose-invert max-w-none">
                {(() => {
                  try {
                    return (
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          code({node, inline, className, children, ...props}) {
                            const match = /language-(\w+)/.exec(className || '')
                            return !inline && match ? (
                              <SyntaxHighlighter
                                style={vscDarkPlus as any}
                                language={match[1]}
                                PreTag="div"
                                {...props}
                              >
                                {String(children).replace(/\n$/, '')}
                              </SyntaxHighlighter>
                            ) : (
                              <code className={className} {...props}>
                                {children}
                              </code>
                            )
                          }
                        }}
                      >
                        {sanitizeMarkdown(message.content)}
                      </ReactMarkdown>
                    )
                  } catch (error) {
                    console.error('Error rendering markdown:', error)
                    return <div className="whitespace-pre-wrap">{message.content}</div>
                  }
                })()}
              </div>
            </div>
          ))
        )}
        {isTyping && (
          <div className="mb-4 p-4 rounded-lg max-w-3xl mr-auto bg-gray-700">
            <div className="text-sm font-bold mb-1 flex items-center">
              <span className="mr-2">AI</span>
              {streamingEnabled && (
                <span className="text-xs px-2 py-0.5 bg-yellow-500/20 text-yellow-400 rounded-full flex items-center">
                  <FiZap className="mr-1" size={10} />
                  Streaming
                </span>
              )}
            </div>
            {streamingEnabled && streamingMessage ? (
              <div className="prose prose-invert max-w-none">
                {(() => {
                  try {
                    return (
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          code({node, inline, className, children, ...props}) {
                            const match = /language-(\w+)/.exec(className || '')
                            return !inline && match ? (
                              <SyntaxHighlighter
                                style={vscDarkPlus as any}
                                language={match[1]}
                                PreTag="div"
                                {...props}
                              >
                                {String(children).replace(/\n$/, '')}
                              </SyntaxHighlighter>
                            ) : (
                              <code className={className} {...props}>
                                {children}
                              </code>
                            )
                          }
                        }}
                      >
                        {sanitizeMarkdown(streamingMessage)}
                      </ReactMarkdown>
                    )
                  } catch (error) {
                    console.error('Error rendering markdown:', error)
                    return <div className="whitespace-pre-wrap">{streamingMessage}</div>
                  }
                })()}
                <div className="inline-block animate-pulse">▌</div>
              </div>
            ) : (
              <div className="flex space-x-2">
                <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" />
                <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '0.2s' }} />
                <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '0.4s' }} />
              </div>
            )}
          </div>
        )}
          <div ref={messagesEndRef} />
        </div>
        
        <MessageInput
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onSubmit={handleSendMessage}
          onStopStreaming={handleStopStreaming}
          disabled={isTyping || sendMessageMutation.isPending}
          isLoading={sendMessageMutation.isPending}
          isStreaming={isTyping}
        />
      </div>
    </div>
  )
}

export default Chat
