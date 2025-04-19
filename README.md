# LocalChat

A ChatGPT-like interface for interacting with AI models hosted at user-configured endpoints, with special support for Ollama streaming responses.

## Features

- Create and manage profiles for different AI model endpoints
- Configure model URL, name, and token size for each profile
- Chat with selected models through a familiar interface
- Real-time streaming responses when using Ollama models
- Persistent chat history
- Detailed error handling and logging

## Tech Stack

- **Frontend**: React, TypeScript, Vite, Tailwind CSS
- **Backend**: Python, FastAPI, SQLAlchemy
- **Database**: SQLite

## Setup

### Backend

1. Navigate to the backend directory:
   ```
   cd backend
   ```

2. Install dependencies with Poetry:
   ```
   poetry install
   ```

3. Start the backend server:
   ```
   poetry run uvicorn localchat.main:app --reload
   ```

### Frontend

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Install dependencies with PNPM:
   ```
   pnpm install
   ```

3. Start the development server:
   ```
   pnpm dev
   ```

4. Open your browser and navigate to http://localhost:5173

## Usage

1. Create a profile with your model endpoint details
   - For Ollama, use the URL format: `http://localhost:11434/api/generate`
   - The app will automatically detect Ollama endpoints and enable streaming
2. Select the profile to start a chat session
3. Start chatting with the AI model!
4. Toggle streaming on/off using the lightning bolt icon in the chat interface

## Ollama Integration

LocalChat has special support for [Ollama](https://ollama.ai/), a tool for running large language models locally:

- **Streaming Responses**: See the model's response in real-time as it's being generated
- **Automatic URL Detection**: The app will automatically detect Ollama endpoints and configure them correctly
- **Model Suggestions**: When creating an Ollama profile, you'll get suggestions for popular models

### Setting up Ollama

1. Install Ollama from [ollama.ai](https://ollama.ai/)
2. Pull a model: `ollama pull llama3.2`
3. Start Ollama
4. In LocalChat, create a profile with:
   - URL: `http://localhost:11434/api/generate`
   - Model name: `llama3.2` (or any other model you've pulled)

## License

MIT
