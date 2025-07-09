import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import nltk
import tiktoken
from typing import List, Dict, Any, Optional
import uuid
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    try:
        nltk.download('punkt')
    except Exception as e:
        logger.warning(f"Could not download NLTK punkt: {e}")

class DocumentChunker:
    """Intelligent document chunking with overlaps and semantic boundaries"""
    
    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4 encoding
        except Exception as e:
            logger.warning(f"Could not load tiktoken encoding: {e}")
            self.encoding = None
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        if self.encoding:
            return len(self.encoding.encode(text))
        else:
            # Fallback: approximate 4 chars per token
            return len(text) // 4
    
    def _encode_text(self, text: str) -> List[int]:
        """Encode text to tokens"""
        if self.encoding:
            return self.encoding.encode(text)
        else:
            # Fallback: return character indices
            return list(range(len(text)))
    
    def _decode_tokens(self, tokens: List[int]) -> str:
        """Decode tokens back to text"""
        if self.encoding:
            return self.encoding.decode(tokens)
        else:
            # Fallback: can't properly decode without tiktoken
            return ""
    
    def chunk_text(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk text intelligently with semantic boundaries
        """
        # Clean and normalize text
        text = self._clean_text(text)
        
        # Simple sentence splitting fallback if NLTK isn't available
        try:
            sentences = nltk.sent_tokenize(text)
        except Exception:
            # Fallback sentence splitting
            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if s.strip()]
        
        chunks = []
        current_chunk = ""
        current_tokens = 0
        chunk_index = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            sentence_tokens = self._count_tokens(sentence)
            
            # If adding this sentence would exceed chunk size, save current chunk
            if current_tokens + sentence_tokens > self.chunk_size and current_chunk:
                chunk_data = self._create_chunk_metadata(
                    current_chunk.strip(), 
                    metadata, 
                    chunk_index
                )
                chunks.append(chunk_data)
                
                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk)
                current_chunk = overlap_text + " " + sentence
                current_tokens = self._count_tokens(current_chunk)
                chunk_index += 1
            else:
                current_chunk += " " + sentence
                current_tokens += sentence_tokens
        
        # Add final chunk if it has content
        if current_chunk.strip():
            chunk_data = self._create_chunk_metadata(
                current_chunk.strip(), 
                metadata, 
                chunk_index
            )
            chunks.append(chunk_data)
        
        logger.info(f"Created {len(chunks)} chunks from document: {metadata.get('filename', 'unknown')}")
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Remove excessive whitespace and newlines
        text = re.sub(r'\n+', '\n', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _get_overlap_text(self, text: str) -> str:
        """Get the last N tokens for overlap"""
        if self.encoding:
            tokens = self._encode_text(text)
            if len(tokens) <= self.overlap:
                return text
            
            overlap_tokens = tokens[-self.overlap:]
            return self._decode_tokens(overlap_tokens)
        else:
            # Fallback: use character-based overlap
            words = text.split()
            overlap_words = words[-self.overlap:] if len(words) > self.overlap else words
            return " ".join(overlap_words)
    
    def _create_chunk_metadata(self, chunk_text: str, base_metadata: Dict[str, Any], chunk_index: int) -> Dict[str, Any]:
        """Create comprehensive metadata for a chunk"""
        return {
            "text": chunk_text,
            "chunk_id": str(uuid.uuid4()),
            "chunk_index": chunk_index,
            "token_count": self._count_tokens(chunk_text),
            "filename": base_metadata.get("filename", "unknown"),
            "file_type": base_metadata.get("file_type", "unknown"),
            "session_id": base_metadata.get("session_id"),
            "upload_timestamp": base_metadata.get("upload_timestamp"),
            "file_size": base_metadata.get("file_size", 0)
        }

class SimpleEmbeddingFunction:
    """Simple embedding function wrapper for ChromaDB - FIXED for new interface"""
    
    def __init__(self, model):
        self.model = model
    
    def __call__(self, input):
        """Generate embeddings for input texts - Updated signature for ChromaDB 0.4.16+"""
        try:
            # Handle both single string and list of strings
            if isinstance(input, str):
                input = [input]
            
            embeddings = self.model.encode(input, convert_to_tensor=False)
            return embeddings.tolist() if hasattr(embeddings, 'tolist') else embeddings
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            # Return dummy embeddings as fallback
            return [[0.0] * 384 for _ in input]  # 384 is dimension for all-MiniLM-L6-v2

class RAGManager:
    """
    Retrieval-Augmented Generation Manager - FIXED VERSION
    
    Handles document storage, embedding, and retrieval using ChromaDB
    """
    
    def __init__(self, embedding_model: str = "all-MiniLM-L6-v2", persist_directory: str = "./chroma_db"):
        self.embedding_model_name = embedding_model
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(exist_ok=True)
        
        # Initialize embedding model
        logger.info(f"Loading embedding model: {embedding_model}")
        try:
            self.embedding_model = SentenceTransformer(embedding_model)
            logger.info("Embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
        
        # Initialize ChromaDB client
        try:
            self.client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            logger.info("ChromaDB client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client: {e}")
            raise
        
        # Initialize collection
        self.collection_name = "phd_advisor_documents"
        self.collection = self._get_or_create_collection()
        
        # Initialize chunker
        self.chunker = DocumentChunker()
    
    def _get_or_create_collection(self):
        """Get or create the ChromaDB collection"""
        try:
            # First, try to get existing collection
            try:
                collection = self.client.get_collection(
                    name=self.collection_name
                )
                logger.info(f"Found existing collection: {self.collection_name}")
                return collection
            except ValueError:
                # Collection doesn't exist, create it
                logger.info(f"Creating new collection: {self.collection_name}")
                collection = self.client.create_collection(
                    name=self.collection_name,
                    embedding_function=SimpleEmbeddingFunction(self.embedding_model),
                    metadata={"description": "PhD Advisor document storage"}
                )
                logger.info(f"Created collection: {self.collection_name}")
                return collection
                
        except Exception as e:
            logger.error(f"Error with collection management: {e}")
            # Try to reset and recreate
            try:
                logger.info("Attempting to reset and recreate collection...")
                self.client.reset()
                collection = self.client.create_collection(
                    name=self.collection_name,
                    embedding_function=SimpleEmbeddingFunction(self.embedding_model),
                    metadata={"description": "PhD Advisor document storage"}
                )
                logger.info("Successfully recreated collection")
                return collection
            except Exception as e2:
                logger.error(f"Failed to recreate collection: {e2}")
                raise
    
    def add_document(self, content: str, filename: str, session_id: str, file_type: str = "unknown") -> Dict[str, Any]:
        """
        Add a document to the vector database
        """
        try:
            # Create base metadata
            base_metadata = {
                "filename": filename,
                "file_type": file_type,
                "session_id": session_id,
                "upload_timestamp": str(uuid.uuid4()),  # Using UUID as timestamp for simplicity
                "file_size": len(content)
            }
            
            # Chunk the document
            chunks = self.chunker.chunk_text(content, base_metadata)
            
            if not chunks:
                raise ValueError("No chunks created from document")
            
            # Prepare data for ChromaDB
            chunk_ids = [chunk["chunk_id"] for chunk in chunks]
            chunk_texts = [chunk["text"] for chunk in chunks]
            chunk_metadatas = [
                {k: v for k, v in chunk.items() if k != "text" and k != "chunk_id"}
                for chunk in chunks
            ]
            
            # Add to ChromaDB with error handling
            try:
                self.collection.add(
                    ids=chunk_ids,
                    documents=chunk_texts,
                    metadatas=chunk_metadatas
                )
                logger.info(f"Successfully added {len(chunks)} chunks for document: {filename}")
            except Exception as e:
                logger.error(f"Error adding chunks to ChromaDB: {e}")
                # Try to recreate collection and try again
                self.collection = self._get_or_create_collection()
                self.collection.add(
                    ids=chunk_ids,
                    documents=chunk_texts,
                    metadatas=chunk_metadatas
                )
                logger.info(f"Successfully added {len(chunks)} chunks after collection reset")
            
            return {
                "success": True,
                "filename": filename,
                "chunks_created": len(chunks),
                "total_tokens": sum(chunk["token_count"] for chunk in chunks),
                "chunk_ids": chunk_ids
            }
            
        except Exception as e:
            logger.error(f"Error adding document {filename}: {str(e)}")
            return {
                "success": False,
                "filename": filename,
                "error": str(e)
            }
    
    def search_documents(self, query: str, session_id: str, persona_context: str = "", n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search for relevant document chunks
        """
        try:
            # Enhance query with persona context for better retrieval
            enhanced_query = f"{query} {persona_context}".strip()
            
            # Search the collection
            results = self.collection.query(
                query_texts=[enhanced_query],
                n_results=n_results,
                where={"session_id": session_id}  # Filter by session
            )
            
            # Format results
            retrieved_chunks = []
            if results['documents'] and results['documents'][0]:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                )):
                    # ChromaDB returns squared euclidean distance, convert to similarity
                    # For better similarity scores, we'll use: similarity = 1 / (1 + distance)
                    similarity_score = 1 / (1 + abs(distance)) if distance is not None else 0.5
                    
                    chunk_data = {
                        "text": doc,
                        "metadata": metadata,
                        "relevance_score": similarity_score,
                        "distance": distance,  # Keep original for debugging
                        "rank": i + 1
                    }
                    retrieved_chunks.append(chunk_data)
            
            logger.info(f"Retrieved {len(retrieved_chunks)} chunks for query: {query[:50]}...")
            return retrieved_chunks
            
        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            return []
    
    def get_document_stats(self, session_id: str) -> Dict[str, Any]:
        """Get statistics about documents in a session"""
        try:
            # Get all chunks for this session
            results = self.collection.get(
                where={"session_id": session_id}
            )
            
            if not results or not results.get('metadatas'):
                return {
                    "total_chunks": 0,
                    "total_documents": 0,
                    "documents": []
                }
            
            # Analyze metadata
            metadatas = results['metadatas']
            documents = {}
            
            for metadata in metadatas:
                filename = metadata.get('filename', 'unknown')
                if filename not in documents:
                    documents[filename] = {
                        "filename": filename,
                        "file_type": metadata.get('file_type', 'unknown'),
                        "chunk_count": 0,
                        "total_tokens": 0
                    }
                
                documents[filename]["chunk_count"] += 1
                documents[filename]["total_tokens"] += metadata.get('token_count', 0)
            
            return {
                "total_chunks": len(metadatas),
                "total_documents": len(documents),
                "documents": list(documents.values())
            }
            
        except Exception as e:
            logger.error(f"Error getting document stats: {str(e)}")
            return {"total_chunks": 0, "total_documents": 0, "documents": []}
    
    def delete_session_documents(self, session_id: str) -> bool:
        """Delete all documents for a session"""
        try:
            # Get all document IDs for this session
            results = self.collection.get(
                where={"session_id": session_id}
            )
            
            if results and results.get('ids'):
                chunk_ids = results['ids']
                self.collection.delete(ids=chunk_ids)
                logger.info(f"Deleted {len(chunk_ids)} chunks for session: {session_id}")
                return True
            
            return True  # No documents to delete is also success
            
        except Exception as e:
            logger.error(f"Error deleting session documents: {str(e)}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Check if RAG system is working properly"""
        try:
            # Test basic operations
            test_doc = "This is a test document for health checking."
            test_session = "health_check_session"
            
            # Try adding a test document
            result = self.add_document(test_doc, "test.txt", test_session, "txt")
            if not result["success"]:
                return {"status": "error", "message": "Failed to add test document"}
            
            # Try searching
            search_results = self.search_documents("test", test_session)
            
            # Try getting stats
            stats = self.get_document_stats(test_session)
            
            # Cleanup
            self.delete_session_documents(test_session)
            
            return {
                "status": "healthy",
                "embedding_model": self.embedding_model_name,
                "collection_name": self.collection_name,
                "test_results": {
                    "add_document": result["success"],
                    "search_documents": len(search_results) > 0,
                    "get_stats": stats["total_chunks"] > 0
                }
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}

# Global RAG manager instance
_rag_manager = None

def get_rag_manager() -> RAGManager:
    """Get the global RAG manager instance"""
    global _rag_manager
    if _rag_manager is None:
        try:
            _rag_manager = RAGManager()
            logger.info("RAG Manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize RAG Manager: {e}")
            raise
    return _rag_manager