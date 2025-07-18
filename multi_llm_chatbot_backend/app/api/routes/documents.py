from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Body
from fastapi import Query
from app.utils.document_extractor import extract_text_from_file
from app.core.session_manager import get_session_manager
from app.core.rag_manager import get_rag_manager
from app.api.utils import get_or_create_session_for_request
from fastapi.responses import StreamingResponse
from app.utils.chat_summary import generate_summary_from_messages, parse_summary_to_blocks, format_summary_for_text_export
from app.utils.file_export import prepare_export_response, generate_pdf_file_from_blocks
from app.core.session_manager import get_session_manager
from app.api.utils import get_or_create_session_for_request
from app.core.bootstrap import chat_orchestrator
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

session_manager = get_session_manager()
get_rag_manager = get_rag_manager  # avoid circular import issues


@router.post("/upload-document")
async def upload_document(file: UploadFile = File(...), request: Request = None):
    try:
        session_id = get_or_create_session_for_request(request)
        session = session_manager.get_session(session_id)

        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        if file.size and file.size > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File size exceeds 10MB limit")

        file_bytes = await file.read()
        content = extract_text_from_file(file_bytes, file.content_type)
        if not content.strip():
            raise HTTPException(status_code=400, detail="Document is empty or unreadable.")

        rag_manager = get_rag_manager()
        file_type_map = {
            "application/pdf": "pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx", 
            "text/plain": "txt"
        }
        file_type = file_type_map.get(file.content_type, "unknown")

        rag_result = rag_manager.add_document(
            content=content,
            filename=file.filename,
            session_id=session_id,
            file_type=file_type
        )

        if not rag_result["success"]:
            raise HTTPException(status_code=500, detail=f"Failed to process document: {rag_result.get('error', 'Unknown error')}")

        session.uploaded_files.append(file.filename)
        session.total_upload_size += len(file_bytes)

        doc_metadata = rag_result.get("document_metadata", {})
        doc_title = doc_metadata.get("title", file.filename)

        session.append_message(
            "system", 
            f"Document uploaded: '{doc_title}' ({file.filename}) - {rag_result['chunks_created']} sections processed, ~{rag_result['total_tokens']} tokens analyzed. You can now ask questions about this document by referencing it by name."
        )

        return {
            "message": f"Document '{file.filename}' uploaded and processed successfully.",
            "filename": file.filename,
            "document_title": doc_title,
            "chunks_created": rag_result['chunks_created'],
            "total_tokens": rag_result['total_tokens'],
            "file_type": file_type,
            "can_reference_by_name": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing document upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")


@router.post("/search-documents")
async def search_documents(request: Request, query: str = Body(..., embed=True), persona: str = Body("", embed=True)):
    try:
        session_id = get_or_create_session_for_request(request)
        rag_manager = get_rag_manager()

        persona_contexts = {
            "methodologist": "methodology research design analysis",
            "theorist": "theory theoretical framework conceptual",
            "pragmatist": "practical application implementation"
        }
        persona_context = persona_contexts.get(persona, "")

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


@router.get("/document-stats")
async def get_document_stats(request: Request):
    try:
        session_id = get_or_create_session_for_request(request)
        rag_manager = get_rag_manager()
        return rag_manager.get_document_stats(session_id)
    except Exception as e:
        logger.error(f"Error getting document stats: {str(e)}")
        return {"total_chunks": 0, "total_documents": 0, "documents": []}


@router.get("/uploaded-files")
async def get_uploaded_filenames(request: Request):
    try:
        session_id = get_or_create_session_for_request(request)
        session = session_manager.get_session(session_id)
        return {"files": session.uploaded_files}
    except Exception as e:
        logger.error(f"Error getting uploaded files: {str(e)}")
        return {"files": []}


@router.get("/document-insights/{filename}")
async def get_document_insights(filename: str, request: Request):
    try:
        session_id = get_or_create_session_for_request(request)
        rag_manager = get_rag_manager()
        stats = rag_manager.get_document_stats(session_id)
        document_info = next((doc for doc in stats.get("documents", []) if doc["filename"] == filename), None)

        if not document_info:
            raise HTTPException(status_code=404, detail=f"Document {filename} not found")

        results = rag_manager.collection.get(
            where={"session_id": session_id, "filename": filename},
            limit=3,
            include=["documents", "metadatas"]
        )

        sample_sections = []
        if results["documents"]:
            for doc, metadata in zip(results["documents"], results["metadatas"]):
                sample_sections.append({
                    "section": metadata.get("document_section", "unknown"),
                    "content_preview": doc[:200] + "..." if len(doc) > 200 else doc,
                    "keywords": metadata.get("keywords", "")
                })

        return {
            "filename": filename,
            "document_title": document_info.get("title", filename),
            "file_type": document_info.get("file_type", "unknown"),
            "statistics": {
                "total_chunks": document_info["chunks"],
                "estimated_tokens": document_info["estimated_tokens"],
                "sections_identified": document_info["sections"]
            },
            "content_analysis": {
                "has_methodology": document_info.get("has_methodology", False),
                "has_theory": document_info.get("has_theory", False),
                "has_references": document_info.get("has_references", False)
            },
            "sample_sections": sample_sections
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document insights: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing document: {str(e)}")
    
@router.get("/export-chat")
async def export_chat(request: Request, format: str = Query(..., regex="^(txt|pdf|docx)$")):
    try:
        session_id = get_or_create_session_for_request(request)
        session = session_manager.get_session(session_id)

        if not session.messages:
            return {"error": "No messages in this session."}

        return prepare_export_response(session.messages, format)

    except Exception as e:
        logger.error(f"Error exporting chat: {str(e)}")
        return {"error": "Failed to export chat.", "detail": str(e)}

@router.get("/chat-summary")
async def chat_summary(
    request: Request,
    format: str = Query("text", regex="^(txt|pdf|docx)$")
):
    """
    Generate and return a summary of the current session chat.
    Can return as plain txt, PDF, or DOCX.
    """
    try:
        session_id = get_or_create_session_for_request(request)
        session = session_manager.get_session(session_id)

        if not session.messages:
            return {"error": "No messages in this session."}

        llm = next(iter(chat_orchestrator.personas.values())).llm
        summary_text = await generate_summary_from_messages(session.messages, llm)

        if format == "txt":
            # Use improved formatting for text export
            formatted_summary = format_summary_for_text_export(summary_text)
            return prepare_export_response(formatted_summary, "txt", filename_prefix="chat_summary")

        elif format == "docx":
            # Use improved formatting for DOCX export
            formatted_summary = format_summary_for_text_export(summary_text)
            return prepare_export_response(formatted_summary, "docx", filename_prefix="chat_summary")

        elif format == "pdf":
            # Parse and render using block formatting
            blocks = [{"type": "heading", "text": "Chat Summary"}] + parse_summary_to_blocks(summary_text)

            file_stream = generate_pdf_file_from_blocks(blocks)
            return StreamingResponse(
                file_stream,
                media_type="application/pdf",
                headers={"Content-Disposition": "attachment; filename=chat_summary.pdf"}
            )

    except Exception as e:
        logger.error(f"Error in chat-summary endpoint: {str(e)}")
        return {"error": "Summary generation failed", "detail": str(e)}

