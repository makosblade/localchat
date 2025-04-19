import axios from 'axios';
import { 
  Profile, 
  ProfileFormData, 
  Chat, 
  ChatFormData, 
  Message, 
  MessageFormData,
  StreamingOptions,
  OllamaModel
} from '../types';

const API_URL = '/api';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Profile API
export const getProfiles = async (): Promise<Profile[]> => {
  const response = await api.get('/profiles/');
  return response.data;
};

export const getProfile = async (id: number): Promise<Profile> => {
  const response = await api.get(`/profiles/${id}`);
  return response.data;
};

export const createProfile = async (profile: ProfileFormData): Promise<Profile> => {
  const response = await api.post('/profiles/', profile);
  return response.data;
};

export const updateProfile = async (id: number, profile: ProfileFormData): Promise<Profile> => {
  const response = await api.put(`/profiles/${id}`, profile);
  return response.data;
};

export const deleteProfile = async (id: number): Promise<void> => {
  await api.delete(`/profiles/${id}`);
};

// Chat API
export const getChats = async (profileId?: number): Promise<Chat[]> => {
  const params = profileId ? { profile_id: profileId } : {};
  const response = await api.get('/chats/', { params });
  return response.data;
};

export const getChat = async (id: number): Promise<Chat> => {
  const response = await api.get(`/chats/${id}`);
  return response.data;
};

export const createChat = async (chat: ChatFormData): Promise<Chat> => {
  const response = await api.post('/chats/', chat);
  return response.data;
};

export const deleteChat = async (id: number): Promise<void> => {
  await api.delete(`/chats/${id}`);
};

// Message API
export const getMessages = async (chatId: number): Promise<Message[]> => {
  const response = await api.get(`/chats/${chatId}/messages/`);
  return response.data;
};

export const deleteMessage = async (messageId: number): Promise<void> => {
  await api.delete(`/messages/${messageId}`);
}

// Provider-specific endpoints
export const getOllamaModels = async (baseUrl?: string): Promise<OllamaModel[]> => {
  const params = baseUrl ? { base_url: baseUrl } : {};
  const response = await api.get('/providers/ollama/models', { params });
  return response.data;
}

export const sendMessage = async (
  chatId: number, 
  message: MessageFormData,
  options?: StreamingOptions
): Promise<Message> => {
  // Default to non-streaming behavior
  if (!options?.streaming) {
    const response = await api.post(`/chats/${chatId}/messages/`, message);
    return response.data;
  }
  
  // For streaming, we need to return a placeholder message that will be updated
  // as the streaming response comes in
  const placeholderMessage: Message = {
    id: -1, // Temporary ID
    chat_id: chatId,
    role: 'assistant',
    content: '',
    created_at: new Date().toISOString()
  };
  
  // Set up event source for streaming
  const params = new URLSearchParams({ stream: 'true' });
  const url = `${API_URL}/chats/${chatId}/messages/?${params}`;
  
  // Make the request using fetch to support streaming
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(message)
  });
  
  if (!response.ok) {
    throw new Error(`Server error: ${response.status}`);
  }
  
  if (!response.body) {
    throw new Error('No response body received');
  }
  
  // Set up the reader for the stream
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  
  // Start reading the stream
  const readStream = async () => {
    try {
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) {
          break;
        }
        
        // Decode the chunk
        const chunk = decoder.decode(value, { stream: true });
        
        // Process each line (each SSE event)
        const lines = chunk.split('\n\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.substring(6); // Remove 'data: ' prefix
            // Call the callback with the new chunk
            if (options?.onChunk && data) {
              options.onChunk(data);
            }
          }
        }
      }
    } catch (error) {
      console.error('Error reading stream:', error);
      if (options?.onError) {
        options.onError(error);
      }
    } finally {
      if (options?.onComplete) {
        options.onComplete();
      }
    }
  };
  
  // Start reading the stream in the background
  readStream();
  
  // Return the placeholder message
  return placeholderMessage;
};

export default api;
