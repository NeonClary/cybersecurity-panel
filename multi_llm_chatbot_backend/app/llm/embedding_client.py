from sentence_transformers import SentenceTransformer
import os
import httpx
import hashlib

API_KEY = os.getenv("GEMINI_API_KEY")

# Using a compact, fast model good for semantic search
model = SentenceTransformer("all-MiniLM-L6-v2")

def get_embedding(text: str) -> list[float]:
    # Use deterministic hash → convert to float vector
    hashed = hashlib.sha256(text.encode()).hexdigest()
    return [int(hashed[i:i+4], 16) / 65536.0 for i in range(0, len(hashed), 4)]
