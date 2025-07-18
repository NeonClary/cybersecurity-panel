from typing import Optional
from fastapi import Request
from app.core.session_manager import get_session_manager

session_manager = get_session_manager()

def get_or_create_session_for_request(request: Request, session_id_override: Optional[str] = None) -> str:
    """
    Get or create session for request using multiple strategies:
    1. Explicit session ID
    2. X-Session-ID header
    3. Client IP fallback
    """
    if session_id_override:
        return session_id_override

    session_header = request.headers.get("X-Session-ID")
    if session_header:
        return session_header

    client_ip = request.client.host if request.client else "unknown"
    ip_session_id = f"ip_{client_ip}"
    session = session_manager.get_session(ip_session_id)
    return session.session_id
