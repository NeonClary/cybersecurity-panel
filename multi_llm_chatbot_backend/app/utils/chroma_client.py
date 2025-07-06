import chromadb
from chromadb.config import Settings
from app.llm.embedding_client import get_embedding

client = chromadb.PersistentClient(path="./chroma_storage")

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
