import os
from fastapi import APIRouter, Body, HTTPException, Header, UploadFile, File, Request
from fastapi import Query
from typing import Optional, List
import httpx
from app.llm.llm_client import LLMClient
from app.llm.improved_gemini_client import ImprovedGeminiClient
from app.llm.improved_ollama_client import ImprovedOllamaClient
from app.models.persona import Persona
from app.core.improved_orchestrator import ImprovedChatOrchestrator
from app.core.session_manager import get_session_manager
from app.core.rag_manager import get_rag_manager
from app.models.default_personas import get_default_personas
from app.utils.document_extractor import extract_text_from_file
from app.utils.file_limits import is_within_upload_limit
from pydantic import BaseModel

from fastapi.responses import StreamingResponse
from fastapi import Query
from app.utils.file_export import export_chat_as_file

import hashlib
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Provider management (same as before)
current_provider = "gemini"
available_providers = ["ollama", "gemini"]

def create_llm_client(provider: str = None) -> LLMClient:
    """Create LLM client based on provider"""
    if provider is None:
        provider = current_provider
        
    if provider == "gemini":
        try:
            return ImprovedGeminiClient(model_name=os.getenv("GEMINI_MODEL"))
        except ValueError as e:
            logger.warning(f"Gemini API key not found, falling back to Ollama: {e}")
            return ImprovedOllamaClient(model_name="llama3.2:1b")
    elif provider == "ollama":
        return ImprovedOllamaClient(model_name="llama3.2:1b")
    else:
        raise ValueError(f"Unknown provider: {provider}")

# Initialize with default provider
llm = create_llm_client()
chat_orchestrator = ImprovedChatOrchestrator()
session_manager = get_session_manager()

# Initialize personas
DEFAULT_PERSONAS = get_default_personas(llm)
for persona in DEFAULT_PERSONAS:
    chat_orchestrator.register_persona(persona)

# Keep all the same data models as before
class UserInput(BaseModel):
    user_input: str

class PersonaInput(BaseModel):
    id: str
    name: str
    system_prompt: str

class ChatMessage(BaseModel):
    user_input: str
    session_id: Optional[str] = None
    response_length: Optional[str] = "medium"

class ReplyToAdvisor(BaseModel):
    user_input: str
    advisor_id: str
    original_message_id: Optional[str] = None

class ProviderSwitch(BaseModel):
    provider: str

# ==============================================================
# SESSION MANAGEMENT COMPATIBILITY LAYER
# ==============================================================

def get_or_create_session_for_request(request: Request, 
                                    session_id_override: Optional[str] = None) -> str:
    """
    Get or create session for request using multiple strategies:
    1. Use provided session_id if given
    2. Use X-Session-ID header if present  
    3. Use client IP as fallback for backward compatibility
    4. Create new session if nothing available
    
    This allows the old stateless API to work with session management
    """
    # Strategy 1: Explicit session ID (for new clients)
    if session_id_override:
        return session_id_override
    
    # Strategy 2: Check for session header (optional for frontend)
    session_header = request.headers.get("X-Session-ID")
    if session_header:
        return session_header
    
    # Strategy 3: Use client IP for backward compatibility
    # This gives each client IP their own persistent session
    client_ip = request.client.host if request.client else "unknown"
    ip_session_id = f"ip_{client_ip}"
    
    # Get or create session for this IP
    session = session_manager.get_session(ip_session_id)
    return session.session_id



# Helper functions (same as before)
def _is_valid_response(response: str, persona_id: str) -> bool:
    """Validate response quality"""
    if len(response) < 2 or len(response) > 5000:
        return False
    
    confusion_indicators = [
        f"Thank you, Dr. {persona_id.title()}",
        "Assistant:",
        f"Dr. {persona_id.title()}",
        "Assistant:",
        f"Dr. {persona_id.title()} Advisor:",
        "excellent discussion, Assistant"
    ]
    
    return not any(indicator in response for indicator in confusion_indicators)

def _get_persona_fallback(persona_id: str) -> str:
    """Get persona-specific fallback responses"""
    fallbacks = {
        "methodist": "Focus on ensuring your methodology aligns with your research question. What specific method are you considering?",
        "theorist": "Consider the theoretical framework underlying your approach. What assumptions guide your thinking?",
        "pragmatist": "Let's break this down into actionable steps. What's the most important thing you need to decide today?"
    }
    return fallbacks.get(persona_id, "I'd be happy to help. Could you provide more details?")

# Provider management endpoints (EXACTLY THE SAME)
@router.get("/current-provider")
async def get_current_provider():
    return {
        "current_provider": current_provider,
        "available_providers": available_providers,
        "model_info": {
            "name": llm.model_name if hasattr(llm, 'model_name') else "gemini-2.0-flash",
            "provider": current_provider
        }
    }

@router.post("/switch-provider")
async def switch_provider(provider_data: ProviderSwitch):
    global current_provider, llm
    
    if provider_data.provider not in available_providers:
        raise HTTPException(
            status_code=400, 
            detail=f"Unknown provider: {provider_data.provider}. Available: {available_providers}"
        )
    
    try:
        current_provider = provider_data.provider
        new_llm = create_llm_client(current_provider)
        llm = new_llm
        
        new_personas = get_default_personas(new_llm)
        chat_orchestrator.personas.clear()
        for persona in new_personas:
            chat_orchestrator.register_persona(persona)
        
        return {
            "message": f"Successfully switched to {current_provider}",
            "current_provider": current_provider,
            "model_info": {
                "name": new_llm.model_name if hasattr(new_llm, 'model_name') else "gemini-2.0-flash",
                "provider": current_provider
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to switch to {provider_data.provider}: {str(e)}"
        )

# Main chat endpoint (SAME INTERFACE, improved backend)
@router.post("/chat-sequential")
async def chat_sequential(message: ChatMessage, request: Request):
    """Generate advisor responses - ENHANCED with RAG"""
    try:
        session_id = get_or_create_session_for_request(request, message.session_id)
        
        # Process message through improved orchestrator (now with RAG)
        result = await chat_orchestrator.process_message(
            user_input=message.user_input,
            session_id=session_id,
            response_length=message.response_length or "medium"
        )
        
        # Add RAG information to response
        if result["type"] == "persona_responses":
            # Count how many personas used documents
            personas_with_docs = sum(1 for r in result["responses"] if r.get("used_documents", False))
            total_chunks_used = sum(r.get("document_chunks_used", 0) for r in result["responses"])
            
            result["rag_info"] = {
                "personas_using_documents": personas_with_docs,
                "total_document_chunks_used": total_chunks_used,
                "rag_enabled": True
            }
        
        return result
        
    except Exception as e:
        logger.error(f"Error in chat-sequential: {str(e)}")
        return {
            "type": "error",
            "message": "I encountered an error processing your request. Please try again.",
            "error": str(e),
            "rag_enabled": False
        }

# Individual advisor endpoint (SAME INTERFACE)
@router.post("/chat/{persona_id}")
async def chat_with_specific_advisor(persona_id: str, input: UserInput, request: Request):
    """Chat with a specific advisor - SAME INTERFACE"""
    try:
        if persona_id not in chat_orchestrator.personas:
            raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found")

        # Get session using compatibility layer
        session_id = get_or_create_session_for_request(request)
        
        # Use new orchestrator
        result = await chat_orchestrator.chat_with_persona(
            user_input=input.user_input,
            persona_id=persona_id,
            session_id=session_id
        )
        
        if result["type"] == "single_persona_response":
            persona_data = result["persona"]
            return {
                "persona": persona_data["persona_name"],
                "persona_id": persona_data["persona_id"],
                "response": persona_data["response"]
            }
        else:
            return {
                "persona": "System",
                "response": result.get("message", "I'm having trouble generating a response right now. Please try again.")
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat_with_specific_advisor: {e}")
        return {
            "persona": "System",
            "response": "I'm having trouble generating a response right now. Please try again."
        }

# Reply to advisor endpoint (SAME INTERFACE)
@router.post("/reply-to-advisor")
async def reply_to_advisor(reply: ReplyToAdvisor, request: Request):
    """Reply to a specific advisor - SAME INTERFACE"""
    try:
        if reply.advisor_id not in chat_orchestrator.personas:
            raise HTTPException(status_code=404, detail=f"Advisor '{reply.advisor_id}' not found")

        # Get session using compatibility layer
        session_id = get_or_create_session_for_request(request)
        
        # Use new orchestrator
        result = await chat_orchestrator.chat_with_persona(
            user_input=reply.user_input,
            persona_id=reply.advisor_id,
            session_id=session_id
        )
        
        if result["type"] == "single_persona_response":
            persona_data = result["persona"]
            return {
                "type": "advisor_reply",
                "persona": persona_data["persona_name"],
                "persona_id": persona_data["persona_id"],
                "response": persona_data["response"],
                "original_message_id": reply.original_message_id
            }
        else:
            return {
                "type": "error",
                "persona": "System",
                "response": result.get("message", "I'm having trouble generating a reply right now. Please try again.")
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in reply_to_advisor: {e}")
        return {
            "type": "error",
            "persona": "System",
            "response": "I'm having trouble generating a reply right now. Please try again."
        }

@router.post("/upload-document")
async def upload_document(file: UploadFile = File(...), request: Request = None):
    """
    Upload document with RAG integration - ENHANCED VERSION
    
    Now documents are:
    1. Chunked intelligently 
    2. Embedded and stored in ChromaDB
    3. Available for semantic retrieval
    4. NOT stored in session context (saves memory)
    """
    # Validate file type
    if file.content_type not in [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
        "text/plain"
    ]:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    try:
        # Get session using compatibility layer
        session_id = get_or_create_session_for_request(request)
        session = session_manager.get_session(session_id)
        
        file_bytes = await file.read()

        # Simple size check
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="Upload exceeds file size limit (10 MB).")

        # Extract text content
        content = extract_text_from_file(file_bytes, file.content_type)
        if not content.strip():
            raise HTTPException(status_code=400, detail="Document is empty or unreadable.")

        # Get RAG manager
        rag_manager = get_rag_manager()
        
        # Determine file type for metadata
        file_type_map = {
            "application/pdf": "pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
            "text/plain": "txt"
        }
        file_type = file_type_map.get(file.content_type, "unknown")
        
        # Add document to vector database instead of session context
        rag_result = rag_manager.add_document(
            content=content,
            filename=file.filename,
            session_id=session_id,
            file_type=file_type
        )
        
        if not rag_result["success"]:
            raise HTTPException(status_code=500, detail=f"Failed to process document: {rag_result.get('error', 'Unknown error')}")
        
        # Add just the filename to session for tracking (not the full content)
        session.uploaded_files.append(file.filename)
        session.total_upload_size += len(file_bytes)
        
        # Add a brief document reference to session messages (not full content)
        session.append_message("system", f"Document uploaded: {file.filename} ({rag_result['chunks_created']} chunks, {rag_result['total_tokens']} tokens)")

        return {
            "message": "Document uploaded and processed successfully.",
            "filename": file.filename,
            "chunks_created": rag_result["chunks_created"],
            "total_tokens": rag_result["total_tokens"],
            "processing_method": "RAG_vector_storage"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")


@router.get("/export-chat")
async def export_chat(request: Request, format: str = Query(..., regex="^(txt|pdf|docx)$")):
    """
    Export the current chat context as a downloadable file in txt, pdf, or docx format.
    """
    try:
        session_id = get_or_create_session_for_request(request)
        session = session_manager.get_session(session_id)

        if not session.messages:
            return {"error": "No messages to export in current session."}

        # Generate the file using utility
        file_stream, filename, media_type = export_chat_as_file(session.messages, format)

        return StreamingResponse(
            file_stream,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        logger.error(f"Error exporting chat: {str(e)}")
        return {"error": "Failed to export chat.", "detail": str(e)}


# Add new endpoint to get document statistics
@router.get("/document-stats")
async def get_document_stats(request: Request):
    """Get statistics about uploaded documents in vector database"""
    try:
        session_id = get_or_create_session_for_request(request)
        rag_manager = get_rag_manager()
        
        stats = rag_manager.get_document_stats(session_id)
        return stats
        
    except Exception as e:
        logger.error(f"Error getting document stats: {str(e)}")
        return {"total_chunks": 0, "total_documents": 0, "documents": []}

# Get uploaded files (SAME INTERFACE)
@router.get("/uploaded-files")
async def get_uploaded_filenames(request: Request):
    """Get uploaded files - SAME INTERFACE"""
    try:
        session_id = get_or_create_session_for_request(request)
        session = session_manager.get_session(session_id)
        return {"files": session.uploaded_files}
    except Exception as e:
        logger.error(f"Error getting uploaded files: {str(e)}")
        return {"files": []}

# Context endpoint (SAME INTERFACE)
@router.get("/context")
async def get_context(request: Request):
    """Get context - ENHANCED with RAG information"""
    try:
        session_id = get_or_create_session_for_request(request)
        session = session_manager.get_session(session_id)

        # Get RAG statistics
        rag_stats = session.get_rag_stats()
        
        return {
            "messages": session.messages,
            "rag_info": {
                "total_documents": rag_stats.get("total_documents", 0),
                "total_chunks": rag_stats.get("total_chunks", 0),
                "documents": rag_stats.get("documents", [])
            }
        }
    except Exception as e:
        logger.error(f"Error getting context: {str(e)}")
        return {"messages": [], "rag_info": {"total_documents": 0, "total_chunks": 0}}

@router.post("/reset-session")
async def reset_session(request: Request):
    """Reset session - ENHANCED with RAG cleanup"""
    try:
        session_id = get_or_create_session_for_request(request)
        
        # Use the enhanced reset that clears both conversation and vector DB
        success = session_manager.reset_session_completely(session_id)
        
        if success:
            return {"status": "reset", "message": "Session and all documents reset successfully"}
        else:
            return {"status": "error", "message": "Failed to reset session"}
    except Exception as e:
        logger.error(f"Error resetting session: {e}")
        return {"status": "error", "message": "Failed to reset session"}


# Legacy model endpoints (SAME INTERFACE)
@router.post("/switch-model")
async def switch_model(model_name: str = Body(...)):
    """Legacy model switching - SAME INTERFACE"""
    if "gemini" in model_name.lower():
        return await switch_provider(ProviderSwitch(provider="gemini"))
    else:
        return await switch_provider(ProviderSwitch(provider="ollama"))

@router.get("/current-model")
async def get_current_model():
    """Legacy model info - SAME INTERFACE"""
    model_name = llm.model_name if hasattr(llm, 'model_name') else "gemini-2.0-flash"
    return {
        "model": model_name,
        "provider": current_provider
    }

@router.post("/search-documents")
async def search_documents(request: Request, query: str = Body(..., embed=True), persona: str = Body("", embed=True)):
    """
    Search uploaded documents using RAG
    
    This endpoint allows direct document search for debugging/testing
    """
    try:
        session_id = get_or_create_session_for_request(request)
        rag_manager = get_rag_manager()
        
        # Get persona context for search enhancement
        persona_contexts = {
            "methodist": "methodology research design analysis",
            "theorist": "theory theoretical framework conceptual",
            "pragmatist": "practical application implementation"
        }
        persona_context = persona_contexts.get(persona, "")
        
        # Search documents
        results = rag_manager.search_documents(
            query=query,
            session_id=session_id,
            persona_context=persona_context,
            n_results=5
        )
        
        return {
            "query": query,
            "persona_filter": persona,
            "results_count": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error searching documents: {str(e)}")
        return {"query": query, "results_count": 0, "results": [], "error": str(e)}

@router.get("/session-stats")
async def get_session_stats(request: Request):
    """Get comprehensive session statistics including RAG data"""
    try:
        session_id = get_or_create_session_for_request(request)
        stats = session_manager.get_session_stats(session_id)
        return stats
    except Exception as e:
        logger.error(f"Error getting session stats: {str(e)}")
        return {"error": str(e)}


@router.get("/debug/personas")
async def debug_personas(request: Request):
    """Debug personas - ENHANCED with RAG information"""
    try:
        session_id = get_or_create_session_for_request(request)
        session = session_manager.get_session(session_id)
        
        # Get RAG statistics
        rag_manager = get_rag_manager()
        rag_stats = rag_manager.get_document_stats(session_id)
        
        return {
            "personas": {
                pid: {
                    "name": persona.name,
                    "prompt": persona.system_prompt[:100] + "...",
                    "retrieval_keywords": chat_orchestrator._get_persona_context_keywords(pid)
                } for pid, persona in chat_orchestrator.personas.items()
            },
            "session_info": {
                "context_length": len(session.messages),
                "uploaded_files": session.uploaded_files,
                "rag_stats": rag_stats
            },
            "current_provider": current_provider,
            "rag_enabled": True
        }
    except Exception as e:
        logger.error(f"Error in debug endpoint: {str(e)}")
        return {
            "personas": {},
            "session_info": {"context_length": 0},
            "current_provider": current_provider,
            "rag_enabled": False,
            "error": str(e)
        }

@router.get("/debug/ranked-personas")
async def get_ranked_personas(request: Request, k: int = Query(3, ge=1, le=10)):
    """
    Debug endpoint: Get top-k ranked personas based on current session context.
    Uses LLM to rank based on latest conversation messages.
    """
    try:
        session_id = get_or_create_session_for_request(request)
        
        # Call the ranking method
        top_personas = await chat_orchestrator.get_top_personas(session_id=session_id, k=k)
        
        # Include some metadata for debug purposes
        return {
            "ranked_personas": top_personas,
            "available_personas": list(chat_orchestrator.personas.keys()),
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Error in /debug/ranked-personas: {e}")
        return {
            "ranked_personas": [],
            "error": str(e)
        }


@router.post("/chat/{persona_id}")
async def chat_with_specific_persona(persona_id: str, message: ChatMessage, request: Request):
    """
    Chat with a specific persona - Enhanced with RAG debugging
    
    This endpoint helps debug RAG integration by testing individual personas
    """
    try:
        session_id = get_or_create_session_for_request(request, message.session_id)
        
        # Validate persona exists
        if persona_id not in chat_orchestrator.personas:
            available_personas = list(chat_orchestrator.personas.keys())
            raise HTTPException(
                status_code=400, 
                detail=f"Persona '{persona_id}' not found. Available: {available_personas}"
            )
        
        # Use the enhanced orchestrator method
        result = await chat_orchestrator.chat_with_persona(
            user_input=message.user_input,
            persona_id=persona_id,
            session_id=session_id,
            response_length=message.response_length or "medium"
        )
        
        # Fix: Handle the response structure properly
        if result.get("type") == "single_persona_response" and "persona" in result:
            persona_data = result["persona"]
            
            # Add debugging information
            result["debug_info"] = {
                "persona_id": persona_id,
                "session_id": session_id,
                "query_length": len(message.user_input),
                "rag_manager_available": True,
                "used_documents": persona_data.get("used_documents", False),
                "chunks_used": persona_data.get("document_chunks_used", 0)
            }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in individual persona chat: {str(e)}")
        return {
            "type": "error",
            "message": f"Error chatting with {persona_id}: {str(e)}",
            "persona_id": persona_id
        }

# Also add a debug endpoint to check RAG status:

@router.get("/debug/rag-status")
async def debug_rag_status(request: Request):
    """
    Debug endpoint to check RAG system status
    """
    try:
        session_id = get_or_create_session_for_request(request)
        
        # Get RAG manager
        rag_manager = get_rag_manager()
        
        # Get session stats
        session_stats = session_manager.get_session_stats(session_id)
        
        # Test a simple search
        test_search = rag_manager.search_documents(
            query="test methodology research",
            session_id=session_id,
            persona_context="",
            n_results=3
        )
        
        return {
            "rag_manager_healthy": True,
            "session_id": session_id,
            "session_stats": session_stats.get("rag_stats", {}),
            "test_search_results": len(test_search),
            "test_search_details": [
                {
                    "relevance": chunk.get("relevance_score", 0),
                    "distance": chunk.get("distance", "unknown"),
                    "text_length": len(chunk.get("text", "")),
                    "filename": chunk.get("metadata", {}).get("filename", "unknown")
                }
                for chunk in test_search[:3]
            ],
            "persona_keywords": {
                pid: chat_orchestrator._get_persona_context_keywords(pid)
                for pid in chat_orchestrator.personas.keys()
            }
        }
        
    except Exception as e:
        logger.error(f"Error in RAG debug: {str(e)}")
        return {
            "rag_manager_healthy": False,
            "error": str(e),
            "session_id": session_id if 'session_id' in locals() else "unknown"
        }

# Ask endpoint (SAME INTERFACE)
class PersonaQuery(BaseModel):
    question: str
    persona: str

@router.post("/ask/")
async def ask_question(query: PersonaQuery, request: Request):
    """Ask question - SAME INTERFACE"""
    try:
        session_id = get_or_create_session_for_request(request)
        
        # Use the new orchestrator
        result = await chat_orchestrator.chat_with_persona(
            user_input=query.question,
            persona_id=query.persona,
            session_id=session_id
        )
        
        if result["type"] == "single_persona_response":
            response_text = result["persona"]["response"]
        else:
            response_text = result.get("message", "I'm having trouble responding right now.")
        
        return {"response": response_text}
        
    except Exception as e:
        logger.error(f"Error in ask endpoint: {str(e)}")
        return {"response": "I encountered an error. Please try again."}
    


# Root endpoint (SAME INTERFACE)
@router.get("/")
def root():
    """Root endpoint - SAME INTERFACE with updated info"""
    return {
        "message": "Multi-LLM PhD Advisor Backend is up and running",
        "version": "1.0.0",  # Updated version 
        "features": [
            "Improved Session Management",
            "Unified Context Handling", 
            "Ollama Support", 
            "Gemini API Support", 
            "Provider Switching"
        ]
    }