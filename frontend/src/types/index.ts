export interface Profile {
  id: number;
  name: string;
  provider: ProviderType;
  url: string;
  model_name: string;
  token_size: number;
  created_at: string;
}

export interface Chat {
  id: number;
  title: string;
  profile_id: number;
  created_at: string;
  messages: Message[];
}

export interface Message {
  id: number;
  chat_id: number;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

export type ProviderType = 'ollama' | 'openai' | 'anthropic' | 'custom';

export interface ProviderInfo {
  id: ProviderType;
  name: string;
  defaultUrl: string;
  defaultModel: string;
  supportsStreaming: boolean;
  popularModels: string[];
}

// Ollama model information
export interface OllamaModel {
  name: string;
  model: string;
  modified_at: string;
  size: number;
  digest: string;
  details?: {
    format: string;
    family: string;
    families?: string[];
    parameter_size?: string;
    quantization_level?: string;
  };
}

export interface ProfileFormData {
  name: string;
  provider: ProviderType;
  url: string;
  model_name: string;
  token_size: number;
}

export interface ChatFormData {
  title: string;
  profile_id: number;
}

export interface MessageFormData {
  role: 'user';
  content: string;
}

export interface ApiError {
  status: number;
  message: string;
}

export interface StreamingOptions {
  streaming: boolean;
  onChunk?: (chunk: MessageEvent) => void;
  onComplete?: () => void;
  onError?: (error: any) => void;
}
