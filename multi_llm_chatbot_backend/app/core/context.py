# Global context storage
class GlobalSessionContext:
    def __init__(self):
        self.full_log: list[dict] = []
        self.uploaded_files: list[str] = []
        self.total_upload_size: int = 0

    def append(self, role: str, content: str):
        self.full_log.append({"role": role, "content": content})

    def filter_by_persona(self, persona_id: str):
        return self.full_log

    def clear(self):
        self.full_log = []
        self.uploaded_files = []
        self.total_upload_size = 0