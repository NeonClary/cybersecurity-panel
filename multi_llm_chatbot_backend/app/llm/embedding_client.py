from sentence_transformers import SentenceTransformer
import os

API_KEY = os.getenv("GEMINI_API_KEY")

# Using a compact, fast model good for semantic search
model = SentenceTransformer("all-MiniLM-L6-v2")

def get_embedding(text: str) -> list[float]:
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()
