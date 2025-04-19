import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getProfiles, createProfile, updateProfile, deleteProfile, createChat, getOllamaModels } from '../services/api'
import { Profile, ProfileFormData, ChatFormData, ProviderType, OllamaModel } from '../types'
import ErrorDisplay from './ErrorDisplay'
import { logError } from '../utils/errorHandler'
import { providers, providerOptions, getDefaultUrl, getDefaultModel, getPopularModels } from '../utils/providers'

interface ProfileManagerProps {
  onSelectProfile: (profile: Profile) => void
  selectedProfile: Profile | null
}

const ProfileManager = ({ onSelectProfile, selectedProfile }: ProfileManagerProps) => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  
  const [isCreating, setIsCreating] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [formData, setFormData] = useState<ProfileFormData>({
    name: '',
    provider: 'ollama',
    url: getDefaultUrl('ollama'),
    model_name: getDefaultModel('ollama'),
    token_size: 2048
  })
  
  // Check if the selected provider supports streaming
  const [supportsStreaming, setSupportsStreaming] = useState(true)
  
  // Store installed Ollama models
  const [installedOllamaModels, setInstalledOllamaModels] = useState<OllamaModel[]>([])
  const [isLoadingModels, setIsLoadingModels] = useState(false)
  const [modelError, setModelError] = useState<string | null>(null)
  
  // Update URL and model when provider changes
  useEffect(() => {
    if (formData.provider !== 'custom') {
      // For non-custom providers, use the default URL
      setFormData(prev => ({
        ...prev,
        url: getDefaultUrl(prev.provider),
        // Only set default model if current model is empty or when changing providers
        model_name: prev.model_name === '' ? getDefaultModel(prev.provider) : prev.model_name
      }))
      
      // If Ollama is selected, fetch installed models
      if (formData.provider === 'ollama') {
        fetchOllamaModels(getDefaultUrl('ollama'))
      }
    }
    
    // Update streaming support
    setSupportsStreaming(providers[formData.provider].supportsStreaming)
  }, [formData.provider])
  
  // Function to fetch installed Ollama models
  const fetchOllamaModels = async (baseUrl?: string) => {
    setIsLoadingModels(true)
    setModelError(null)
    
    try {
      const models = await getOllamaModels(baseUrl)
      setInstalledOllamaModels(models)
      console.log('Fetched Ollama models:', models.length > 0 ? 
        `${models.length} Ollama models found` : 
        'No Ollama models found')
    } catch (error) {
      console.error('Error fetching Ollama models:', error)
      setModelError(
        'Could not fetch installed Ollama models. Make sure Ollama is running at ' + 
        (baseUrl || 'http://localhost:11434') + 
        '. You can still select from popular models below.'
      )
      setInstalledOllamaModels([])
    } finally {
      setIsLoadingModels(false)
    }
  }
  
  // Fetch profiles
  const { data: profiles = [], isLoading, error } = useQuery({
    queryKey: ['profiles'],
    queryFn: getProfiles
  })
  
  // Create profile mutation
  const createProfileMutation = useMutation({
    mutationFn: createProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
      resetForm()
    }
  })
  
  // Update profile mutation
  const updateProfileMutation = useMutation({
    mutationFn: ({ id, profile }: { id: number; profile: ProfileFormData }) => 
      updateProfile(id, profile),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
      resetForm()
    }
  })
  
  // Delete profile mutation
  const deleteProfileMutation = useMutation({
    mutationFn: deleteProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
      if (selectedProfile) {
        onSelectProfile(null as unknown as Profile)
      }
    }
  })
  
  // Create chat mutation
  const createChatMutation = useMutation({
    mutationFn: createChat,
    onSuccess: (data) => {
      navigate(`/chat/${data.id}`)
    }
  })
  
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target
    
    if (name === 'provider') {
      // When changing provider, update with default values
      const providerType = value as ProviderType
      setFormData(prev => ({
        ...prev,
        provider: providerType,
        url: providerType === 'custom' ? prev.url : getDefaultUrl(providerType),
        model_name: getDefaultModel(providerType)
      }))
    } else {
      setFormData(prev => ({
        ...prev,
        [name]: name === 'token_size' ? parseInt(value) || 0 : value
      }))
    }
  }
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    if (isEditing && selectedProfile) {
      updateProfileMutation.mutate({ 
        id: selectedProfile.id, 
        profile: formData 
      })
    } else {
      createProfileMutation.mutate(formData)
    }
  }
  
  const handleEdit = (profile: Profile) => {
    setFormData({
      name: profile.name,
      provider: profile.provider || 'custom', // Handle profiles created before provider field was added
      url: profile.url,
      model_name: profile.model_name,
      token_size: profile.token_size
    })
    setIsEditing(true)
    setIsCreating(true)
  }
  
  const handleDelete = (id: number) => {
    if (window.confirm('Are you sure you want to delete this profile?')) {
      deleteProfileMutation.mutate(id)
    }
  }
  
  const handleStartChat = (profile: Profile) => {
    onSelectProfile(profile)
    
    const chatData: ChatFormData = {
      title: `Chat with ${profile.model_name}`,
      profile_id: profile.id
    }
    
    createChatMutation.mutate(chatData)
  }
  
  const resetForm = () => {
    setFormData({
      name: '',
      provider: 'ollama',
      url: getDefaultUrl('ollama'),
      model_name: getDefaultModel('ollama'),
      token_size: 2048
    })
    setIsCreating(false)
    setIsEditing(false)
  }
  
  if (isLoading) {
    return (
      <div className="p-4 flex justify-center items-center h-64">
        <div className="bg-gray-800 rounded-lg p-6 text-center">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-4 text-gray-300">Loading profiles...</p>
        </div>
      </div>
    )
  }
  
  if (error) {
    logError(error, 'Loading profiles')
    return (
      <div className="p-4">
        <ErrorDisplay 
          error={error} 
          retry={() => queryClient.invalidateQueries({ queryKey: ['profiles'] })} 
          className="max-w-2xl mx-auto"
        />
      </div>
    )
  }
  
  return (
    <div className="flex flex-col w-full max-w-4xl mx-auto p-4">
      <h2 className="text-2xl font-bold mb-4">Model Profiles</h2>
      
      {!isCreating ? (
        <button
          onClick={() => setIsCreating(true)}
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded mb-4"
        >
          Create New Profile
        </button>
      ) : (
        <div className="bg-gray-800 p-4 rounded-lg mb-4">
          <h3 className="text-xl font-semibold mb-2">
            {isEditing ? 'Edit Profile' : 'Create New Profile'}
          </h3>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Profile Name</label>
              <input
                type="text"
                name="name"
                value={formData.name}
                onChange={handleInputChange}
                className="w-full p-2 bg-gray-700 rounded border border-gray-600"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Provider</label>
              <select
                name="provider"
                value={formData.provider}
                onChange={handleInputChange}
                className="w-full p-2 bg-gray-700 rounded border border-gray-600"
                required
              >
                {providerOptions.map(option => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              {supportsStreaming && (
                <p className="text-xs text-blue-400 mt-1">
                  ✓ This provider supports streaming responses
                </p>
              )}
            </div>
            
            {formData.provider === 'custom' && (
              <div>
                <label className="block text-sm font-medium mb-1">API URL</label>
                <input
                  type="url"
                  name="url"
                  value={formData.url}
                  onChange={handleInputChange}
                  className="w-full p-2 bg-gray-700 rounded border border-gray-600"
                  placeholder="https://api.example.com/v1/chat/completions"
                  required
                />
              </div>
            )}
            
            <div>
              <label className="block text-sm font-medium mb-1">Model Name</label>
              {formData.provider === 'ollama' ? (
                <div>
                  <div className="flex space-x-2">
                    <select
                      name="model_name"
                      value={formData.model_name}
                      onChange={handleInputChange}
                      className="flex-1 p-2 bg-gray-700 rounded border border-gray-600"
                      required
                    >
                      <option value="" disabled>Select an Ollama model</option>
                      
                      {/* Installed models group */}
                      {installedOllamaModels.length > 0 && (
                        <optgroup label="Installed Models">
                          {installedOllamaModels.map(model => (
                            <option key={model.name} value={model.name}>
                              {model.name} {model.details?.parameter_size ? `(${model.details.parameter_size})` : ''}
                            </option>
                          ))}
                        </optgroup>
                      )}
                      
                      {/* Popular models group */}
                      <optgroup label="Popular Models">
                        {getPopularModels('ollama').map(model => (
                          <option key={model} value={model}>{model}</option>
                        ))}
                      </optgroup>
                    </select>
                    
                    <button 
                      type="button"
                      onClick={() => fetchOllamaModels(formData.url)}
                      className="px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                      title="Refresh installed models"
                      disabled={isLoadingModels}
                    >
                      {isLoadingModels ? '...' : '⟳'}
                    </button>
                  </div>
                  
                  {modelError && (
                    <div className="mt-2 mb-2 p-2 bg-red-900/30 border border-red-700 rounded text-xs">
                      <p className="text-red-400">{modelError}</p>
                      <p className="text-gray-400 mt-1">
                        You can still use the popular models below, or 
                        <button 
                          type="button"
                          onClick={() => fetchOllamaModels(formData.url)}
                          className="ml-1 text-blue-400 hover:underline"
                        >
                          try again
                        </button>
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <div>
                  <div className="flex space-x-2">
                    <input
                      type="text"
                      name="model_name"
                      value={formData.model_name}
                      onChange={handleInputChange}
                      className="flex-1 p-2 bg-gray-700 rounded border border-gray-600"
                      placeholder={getDefaultModel(formData.provider) || "Enter model name"}
                      list={`${formData.provider}-models`}
                      required
                    />
                  </div>
                  
                  {/* Model suggestions datalist */}
                  <datalist id={`${formData.provider}-models`}>
                    {getPopularModels(formData.provider).map(model => (
                      <option key={model} value={model} />
                    ))}
                  </datalist>
                </div>
              )}
              
              <p className="text-xs text-gray-400 mt-1">
                {formData.provider === 'ollama' ? 
                  "Enter the name of your Ollama model (e.g., llama3.2, mistral, codellama)" :
                  formData.provider === 'openai' ?
                  "Enter an OpenAI model (e.g., gpt-3.5-turbo, gpt-4)" :
                  formData.provider === 'anthropic' ?
                  "Enter an Anthropic model (e.g., claude-3-opus, claude-3-sonnet)" :
                  "Enter the model name for your custom provider"}
              </p>
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-1">
                Max Tokens: {formData.token_size}
              </label>
              <input
                type="range"
                name="token_size"
                value={formData.token_size}
                onChange={handleInputChange}
                min="256"
                max="8192"
                step="256"
                className="w-full"
              />
              <p className="text-xs text-gray-400 mt-1">
                Controls the maximum length of the generated response
              </p>
            </div>
            <div className="flex space-x-2">
              <button
                type="submit"
                className="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded"
                disabled={createProfileMutation.isPending || updateProfileMutation.isPending}
              >
                {createProfileMutation.isPending || updateProfileMutation.isPending
                  ? 'Saving...'
                  : isEditing
                  ? 'Update Profile'
                  : 'Create Profile'}
              </button>
              <button
                type="button"
                onClick={resetForm}
                className="bg-gray-600 hover:bg-gray-700 text-white font-bold py-2 px-4 rounded"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}
      
      {/* Error messages */}
      {createProfileMutation.error && (
        <div className="mt-4">
          <ErrorDisplay 
            error={createProfileMutation.error} 
            retry={() => createProfileMutation.reset()}
          />
        </div>
      )}
      
      {updateProfileMutation.error && (
        <div className="mt-4">
          <ErrorDisplay 
            error={updateProfileMutation.error} 
            retry={() => updateProfileMutation.reset()}
          />
        </div>
      )}
      
      {deleteProfileMutation.error && (
        <div className="mt-4">
          <ErrorDisplay 
            error={deleteProfileMutation.error} 
            retry={() => deleteProfileMutation.reset()}
          />
        </div>
      )}
      
      {createChatMutation.error && (
        <div className="mt-4">
          <ErrorDisplay 
            error={createChatMutation.error} 
            retry={() => createChatMutation.reset()}
          />
        </div>
      )}
      
      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        {profiles.length === 0 ? (
          <div className="col-span-full text-center p-4 bg-gray-800 rounded-lg">
            No profiles found. Create your first profile to get started.
          </div>
        ) : (
          profiles.map((profile) => (
            <div
              key={profile.id}
              className={`bg-gray-800 p-4 rounded-lg border-2 ${
                selectedProfile?.id === profile.id
                  ? 'border-blue-500'
                  : 'border-transparent'
              }`}
            >
              <h3 className="text-xl font-semibold">{profile.name}</h3>
              <div className="mt-2 text-gray-300">
                <p>
                  <span className="font-medium">Provider:</span> {profile.provider ? 
                    providers[profile.provider as ProviderType]?.name || profile.provider : 
                    profile.url.includes('ollama') ? 'Ollama' : 'Custom'}
                </p>
                <p><span className="font-medium">Model:</span> {profile.model_name}</p>
                <p><span className="font-medium">Max Tokens:</span> {profile.token_size}</p>
                {(profile.provider === 'ollama' || profile.url.includes('ollama') || profile.url.endsWith('/api/generate')) && (
                  <p className="text-xs text-blue-400 mt-1">✓ Supports streaming</p>
                )}
              </div>
              <div className="mt-4 flex space-x-2">
                <button
                  onClick={() => handleStartChat(profile)}
                  className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
                  disabled={createChatMutation.isPending}
                >
                  {createChatMutation.isPending && selectedProfile?.id === profile.id
                    ? 'Starting...'
                    : 'Start Chat'}
                </button>
                <button
                  onClick={() => handleEdit(profile)}
                  className="bg-yellow-600 hover:bg-yellow-700 text-white font-bold py-2 px-4 rounded"
                >
                  Edit
                </button>
                <button
                  onClick={() => handleDelete(profile.id)}
                  className="bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-4 rounded"
                  disabled={deleteProfileMutation.isPending}
                >
                  {deleteProfileMutation.isPending && selectedProfile?.id === profile.id
                    ? 'Deleting...'
                    : 'Delete'}
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default ProfileManager
