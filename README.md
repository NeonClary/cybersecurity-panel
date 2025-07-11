# PhD Advisory Panel

An AI-powered academic guidance system that provides personalized advice through specialized advisor personas. Get diverse perspectives on your PhD journey from multiple AI advisors, each bringing unique expertise in methodology, theory, and practical guidance.

## Features

- **Multiple AI Advisor Personas**: Chat with specialized advisors including Methodologist (methodology expert), Theorist (conceptual frameworks), and Pragmatist (action-focused guidance)
- **Document Upload Support**: Upload PDFs, Word documents, and text files to provide context for your questions
- **Multi-LLM Backend**: Supports both Gemini API and Ollama models with seamless provider switching
- **Real-time Chat Interface**: Modern, responsive chat interface with advisor-specific styling
- **Context-Aware Responses**: Maintains conversation history and document context across the session
- **Sequential Advisor Responses**: Get input from all advisors in a structured sequence
- **Individual Advisor Chat**: Have focused conversations with specific advisors

## Architecture

### Frontend (React)
- **Technology**: React 18 with modern hooks and functional components
- **Styling**: CSS custom properties with dark/light theme support
- **Components**: Modular component architecture with reusable UI elements
- **State Management**: React hooks for local state management
- **Icons**: Lucide React for consistent iconography

### Backend (FastAPI)
- **Framework**: FastAPI with automatic API documentation
- **LLM Integration**: Support for multiple providers (Gemini, Ollama)
- **Document Processing**: PDF, DOCX, and text file extraction
- **Session Management**: Global session context with file upload tracking
- **CORS Support**: Configured for React development server

## Quick Start

### Prerequisites
- Node.js 16+ and npm
- Python 3.8+
- (Optional) Gemini API key for Google's models
- (Optional) Ollama installation for local models

### Backend Setup

1. **Clone and navigate to backend directory**
```bash
cd multi_llm_chatbot_backend
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up environment variables**
Create a `.env` file:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash
```

4. **Start the backend server**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000` with interactive docs at `http://localhost:8000/docs`

### Frontend Setup

1. **Navigate to frontend directory**
```bash
cd phd-advisor-frontend
```

2. **Install dependencies**
```bash
npm install
```

3. **Start the development server**
```bash
npm start
```

The application will open at `http://localhost:3000`

## Advisor Personas

### Methodologist - Research Methodology Expert
- **Focus**: Research design, validity, sampling, methodological rigor
- **Style**: Precise, analytical, methodology-focused
- **Best for**: Research design questions, data collection methods, validity concerns

### Theorist - Conceptual Frameworks Expert  
- **Focus**: Theoretical positioning, epistemological assumptions, conceptual clarity
- **Style**: Thoughtful, intellectually rigorous, theory-oriented
- **Best for**: Literature review, theoretical frameworks, conceptual development

### Pragmatist - Action-Focused Advisor
- **Focus**: Practical next steps, immediate actions, progress over perfection
- **Style**: Warm, motivational, results-oriented
- **Best for**: Getting unstuck, prioritizing tasks, actionable advice

## API Endpoints

### Core Chat Endpoints
- `POST /chat-sequential` - Get responses from all advisors in sequence
- `POST /chat/{persona_id}` - Chat with a specific advisor
- `POST /reply-to-advisor` - Reply to a specific advisor's message

### Document Management
- `POST /upload-document` - Upload documents (PDF, DOCX, TXT)
- `GET /uploaded-files` - List uploaded filenames
- `GET /context` - View current session context

### Provider Management
- `GET /current-provider` - Get current LLM provider info
- `POST /switch-provider` - Switch between Gemini and Ollama

### System
- `GET /debug/personas` - Debug persona configurations
- `GET /` - API health check

## Configuration

### Supported LLM Providers

**Gemini (Default)**
- Requires GEMINI_API_KEY environment variable
- Uses gemini-2.0-flash model by default
- Cloud-based, requires internet connection

**Ollama (Local)**
- Requires Ollama installation
- Uses llama3.2:1b model by default
- Runs locally, no internet required

### File Upload Limits
- Maximum file size: 10MB per file
- Total session limit: 50MB
- Supported formats: PDF, DOCX, TXT

### Environment Variables
```env
# Required for Gemini
GEMINI_API_KEY=your_api_key

# Optional configurations
GEMINI_MODEL=gemini-2.0-flash
OLLAMA_BASE_URL=http://localhost:11434
```

## Development

### Project Structure
```
phd-advisor-frontend/
├── public/
├── src/
│   ├── components/     # Reusable UI components
│   ├── data/          # Advisor configurations
│   ├── pages/         # Main page components
│   ├── styles/        # CSS stylesheets
│   └── utils/         # Helper functions

multi_llm_chatbot_backend/
├── app/
│   ├── api/           # API routes
│   ├── core/          # Business logic
│   ├── llm/           # LLM client implementations
│   ├── models/        # Data models
│   ├── tests/         # Test files
│   └── utils/         # Utility functions
```

### Adding New Advisors
1. Create persona in `app/api/routes.py` with system prompt
2. Add advisor configuration in frontend `src/data/advisors.js`
3. Update advisor styling in `src/styles/`

### Testing Document Upload
Use the test script:
```bash
cd multi_llm_chatbot_backend/app/tests
python test_document_upload.py
```

## Usage Examples

### Starting a Conversation
1. Navigate to the home page
2. Click "Start Conversation"
3. Type your PhD-related question
4. Receive responses from all three advisors

### Uploading Documents
1. In the chat interface, click the upload button
2. Select your PDF, DOCX, or TXT file
3. The document content will be added to the conversation context
4. Ask questions about your uploaded documents

### Switching LLM Providers
```bash
curl -X POST "http://localhost:8000/switch-provider" \
  -H "Content-Type: application/json" \
  -d '{"provider": "ollama"}'
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request


## Support

- Check the API documentation at `http://localhost:8000/docs`
- Review the debug endpoints for troubleshooting
- Ensure all environment variables are properly configured
- Verify that your LLM provider (Gemini/Ollama) is accessible