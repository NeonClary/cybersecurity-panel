# utils/file_limits.py
from app.core.context import GlobalSessionContext

MAX_SESSION_UPLOAD_SIZE_MB = 10


MAX_TOTAL_UPLOAD_MB = 10

def is_within_upload_limit(session_id: str, new_file_bytes: bytes, session_context: GlobalSessionContext) -> bool:
    size_mb = (session_context.total_upload_size + len(new_file_bytes)) / (1024 * 1024)
    return size_mb <= MAX_TOTAL_UPLOAD_MB
