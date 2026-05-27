import os
from pathlib import Path

import chromadb
from chromadb.config import Settings

from app.llm.embedding_client import get_embedding


def _persona_knowledge_path() -> str:
    """Resolve the persona-knowledge ChromaDB path.

    Mirrors ``app.core.rag_manager._default_chroma_path``: when ``DATA_DIR``
    is set (HF Spaces, any bucket-mounted deployment) the embeddings live
    under ``${DATA_DIR}/chroma/persona_knowledge`` so they survive Space
    rebuilds. Local installs keep the historical relative path.
    """
    data_dir = os.environ.get("DATA_DIR", "").strip()
    if data_dir:
        return str(Path(data_dir) / "chroma" / "persona_knowledge")
    return "./chroma_storage"


_path = _persona_knowledge_path()
Path(_path).mkdir(parents=True, exist_ok=True)
client = chromadb.PersistentClient(path=_path)

collection = client.get_or_create_collection("persona_knowledge")

def add_persona_doc(text: str, persona: str, doc_id: str):
    embedding = get_embedding(text)
    collection.add(
        documents=[text],
        embeddings=[embedding],
        metadatas=[{"persona": persona}],
        ids=[doc_id]
    )

def query_persona_knowledge(query: str, persona: str):
    query_embedding = get_embedding(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3,
        where={"persona": persona}
    )
    return results['documents'][0] if results['documents'] else []
