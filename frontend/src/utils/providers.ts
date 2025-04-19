import { ProviderInfo, ProviderType } from '../types';

// Provider information with default configurations
export const providers: Record<ProviderType, ProviderInfo> = {
  ollama: {
    id: 'ollama',
    name: 'Ollama',
    defaultUrl: 'http://localhost:11434/api/generate',
    defaultModel: 'llama3.2',
    supportsStreaming: true,
    popularModels: [
      'llama3.2',
      'llama3',
      'llama2',
      'mistral',
      'gemma',
      'codellama',
      'phi',
      'mixtral',
      'vicuna',
      'orca-mini'
    ]
  },
  openai: {
    id: 'openai',
    name: 'OpenAI',
    defaultUrl: 'https://api.openai.com/v1/chat/completions',
    defaultModel: 'gpt-3.5-turbo',
    supportsStreaming: false,
    popularModels: [
      'gpt-3.5-turbo',
      'gpt-4',
      'gpt-4-turbo',
      'gpt-4o'
    ]
  },
  anthropic: {
    id: 'anthropic',
    name: 'Anthropic',
    defaultUrl: 'https://api.anthropic.com/v1/messages',
    defaultModel: 'claude-3-opus-20240229',
    supportsStreaming: false,
    popularModels: [
      'claude-3-opus-20240229',
      'claude-3-sonnet-20240229',
      'claude-3-haiku-20240307',
      'claude-2.1'
    ]
  },
  custom: {
    id: 'custom',
    name: 'Custom Provider',
    defaultUrl: '',
    defaultModel: '',
    supportsStreaming: false,
    popularModels: []
  }
};

// Get a list of providers for dropdown options
export const providerOptions = Object.values(providers).map(provider => ({
  value: provider.id,
  label: provider.name
}));

// Helper function to check if a provider supports streaming
export const supportsStreaming = (provider: ProviderType, url: string): boolean => {
  if (provider === 'ollama') {
    return true;
  }
  
  // Check if URL contains known streaming providers
  if (url.includes('ollama') || url.endsWith('/api/generate')) {
    return true;
  }
  
  return false;
};

// Helper function to get the default URL for a provider
export const getDefaultUrl = (provider: ProviderType): string => {
  return providers[provider]?.defaultUrl || '';
};

// Helper function to get the default model for a provider
export const getDefaultModel = (provider: ProviderType): string => {
  return providers[provider]?.defaultModel || '';
};

// Helper function to get popular models for a provider
export const getPopularModels = (provider: ProviderType): string[] => {
  return providers[provider]?.popularModels || [];
};
