import React from 'react'
import { FiSend, FiSquare } from 'react-icons/fi'

interface MessageInputProps {
  value: string
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void
  onSubmit: (e: React.FormEvent) => void
  onStopStreaming?: () => void
  disabled?: boolean
  isLoading?: boolean
  isStreaming?: boolean
}

const MessageInput: React.FC<MessageInputProps> = ({
  value,
  onChange,
  onSubmit,
  onStopStreaming,
  disabled = false,
  isLoading = false,
  isStreaming = false,
}) => {
  // Auto-resize textarea based on content
  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const textarea = e.target
    
    // Reset height to auto to get the correct scrollHeight
    textarea.style.height = 'auto'
    
    // Set the height to the scrollHeight
    textarea.style.height = `${textarea.scrollHeight}px`
    
    // Call the onChange handler
    onChange(e)
  }
  
  // Handle keyboard shortcuts (Ctrl+Enter or Cmd+Enter to submit)
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault()
      if (!disabled && value.trim()) {
        onSubmit(e as unknown as React.FormEvent)
      }
    }
  }
  
  return (
    <div className="border-t border-gray-700 bg-gray-800 p-4">
      <form onSubmit={onSubmit} className="flex items-end space-x-2">
        <div className="flex-1 relative">
          <textarea
            value={value}
            onChange={handleTextareaChange}
            onKeyDown={handleKeyDown}
            placeholder="Type your message..."
            className="w-full p-3 pr-10 bg-gray-700 rounded-lg border border-gray-600 resize-none min-h-[50px] max-h-[200px] overflow-y-auto"
            disabled={disabled}
            rows={1}
          />
          {value.length > 0 && (
            <span className="absolute right-2 bottom-2 text-xs text-gray-400">
              {isLoading ? 'Sending...' : 'Ctrl+Enter to send'}
            </span>
          )}
        </div>
        {isStreaming ? (
          <button
            type="button"
            onClick={onStopStreaming}
            className="p-3 rounded-lg bg-red-600 hover:bg-red-700 transition-colors"
            title="Stop streaming response"
          >
            <FiSquare className="text-white" />
          </button>
        ) : (
          <button
            type="submit"
            className={`p-3 rounded-lg ${
              disabled || !value.trim()
                ? 'bg-gray-600 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-700'
            }`}
            disabled={disabled || !value.trim()}
          >
            <FiSend className="text-white" />
          </button>
        )}
      </form>
    </div>
  )
}

export default MessageInput
