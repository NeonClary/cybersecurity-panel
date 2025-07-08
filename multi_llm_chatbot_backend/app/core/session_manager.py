from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import uuid
from dataclasses import dataclass, field
import asyncio
from threading import Lock

@dataclass
class ConversationContext:
    """Individual conversation context for a session"""
    session_id: str
    messages: List[dict] = field(default_factory=list)
    uploaded_files: List[str] = field(default_factory=list)
    total_upload_size: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    
    def append_message(self, role: str, content: str):
        """Add a message to the conversation"""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        self.last_accessed = datetime.now()
    
    def get_recent_messages(self, limit: int = 20) -> List[dict]:
        """Get recent messages with limit"""
        return self.messages[-limit:] if len(self.messages) > limit else self.messages
    
    def get_messages_by_role(self, role: str) -> List[dict]:
        """Get all messages from a specific role"""
        return [msg for msg in self.messages if msg['role'] == role]
    
    def clear_messages(self):
        """Clear all messages but preserve metadata"""
        self.messages = []
        self.last_accessed = datetime.now()
    
    def add_uploaded_file(self, filename: str, content: str, file_size: int):
        """Add uploaded file content to context"""
        self.uploaded_files.append(filename)
        self.total_upload_size += file_size
        self.append_message("document", f"[Uploaded: {filename}]\n{content}")
    
    def get_context_size(self) -> int:
        """Calculate total context size in characters"""
        return sum(len(msg['content']) for msg in self.messages)

class SessionManager:
    """Thread-safe session manager for handling multiple user conversations"""
    
    def __init__(self, session_timeout_hours: int = 24, cleanup_interval_minutes: int = 60):
        self.sessions: Dict[str, ConversationContext] = {}
        self.session_timeout = timedelta(hours=session_timeout_hours)
        self.cleanup_interval = timedelta(minutes=cleanup_interval_minutes)
        self.lock = Lock()
        self.last_cleanup = datetime.now()
    
    def create_session(self) -> str:
        """Create a new session and return session ID"""
        session_id = str(uuid.uuid4())
        with self.lock:
            self.sessions[session_id] = ConversationContext(session_id=session_id)
        return session_id
    
    def get_session(self, session_id: Optional[str] = None) -> ConversationContext:
        """Get existing session or create new one"""
        if not session_id:
            session_id = self.create_session()
        
        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = ConversationContext(session_id=session_id)
            
            session = self.sessions[session_id]
            session.last_accessed = datetime.now()
            
            # Trigger cleanup if needed
            self._cleanup_expired_sessions()
            
            return session
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a specific session"""
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                return True
            return False
    
    def get_active_session_count(self) -> int:
        """Get number of active sessions"""
        with self.lock:
            return len(self.sessions)
    
    def _cleanup_expired_sessions(self):
        """Remove expired sessions (called periodically)"""
        now = datetime.now()
        
        # Only run cleanup periodically to avoid overhead
        if now - self.last_cleanup < self.cleanup_interval:
            return
        
        expired_sessions = []
        for session_id, session in self.sessions.items():
            if now - session.last_accessed > self.session_timeout:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
        
        self.last_cleanup = now
        
        if expired_sessions:
            print(f"Cleaned up {len(expired_sessions)} expired sessions")

# Global session manager instance
session_manager = SessionManager()

def get_session_manager() -> SessionManager:
    """Get the global session manager instance"""
    return session_manager