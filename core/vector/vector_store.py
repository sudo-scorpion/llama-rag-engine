import os
import json
from typing import List, Dict
import time
from sentence_transformers import SentenceTransformer
import chromadb
from redis import Redis
from core.logger.app_logger import logger

class VectorStore:
    def __init__(self, host: str = 'localhost', port: int = 8000):
        self.host = host
        self.port = port
        self.embedding_model = SentenceTransformer(os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2'))
        self.chroma_client = None
        self.collection = None
        self.redis_client = Redis(host='localhost', port=6379, db=0)

    async def initialize(self):
        try:
            self.chroma_client = await chromadb.AsyncHttpClient(host=self.host, port=self.port)
            collections = await self.chroma_client.list_collections()
            collection_names = [col.name for col in collections]
            if "pdf_embeddings" not in collection_names:
                self.collection = await self.chroma_client.create_collection("pdf_embeddings")
            else:
                self.collection = await self.chroma_client.get_collection("pdf_embeddings")
        except Exception as e:
            logger.error(f"Error initializing vector store: {str(e)}")
            raise

    async def add_embeddings(self, texts: List[str], metadata: List[Dict] = None):
        try:
            if not texts:
                logger.warning("No texts provided to add_embeddings")
                return

            # Ensure metadata is provided for each text
            if metadata is None:
                metadata = [{
                    "chunk_index": i,
                    "timestamp": str(import_time.time()),
                    "text_length": len(text)
                } for i, text in enumerate(texts)]

            # Ensure metadata length matches texts length
            if len(metadata) != len(texts):
                metadata = metadata[:len(texts)] if len(metadata) > len(texts) else metadata + [{"chunk_index": i} for i in range(len(metadata), len(texts))]

            # Generate embeddings
            embeddings = self.embedding_model.encode(texts, convert_to_tensor=True).cpu().numpy()

            # Generate IDs
            ids = [f"doc_{i}_{int(time.time())}" for i in range(len(texts))]

            # Cache embeddings in Redis
            for i, (text, embedding) in enumerate(zip(texts, embeddings)):
                cache_key = f"embedding_{ids[i]}"
                self.redis_client.setex(
                    cache_key,
                    300,  # Cache for 5 minutes
                    json.dumps({
                        "text": text,
                        "embedding": embedding.tolist(),
                        "metadata": metadata[i]
                    })
                )

            # Add to ChromaDB
            await self.collection.add(
                embeddings=embeddings.tolist(),
                documents=texts,
                metadatas=metadata,
                ids=ids
            )

            logger.info(f"Successfully added {len(texts)} documents to vector store")

        except Exception as e:
            logger.error(f"Error adding embeddings: {str(e)}")
            raise

    async def search(self, query: str, k: int = 5) -> List[Dict]:
        try:
            # Check cache first
            cache_key = f"query_{query}"
            cached_results = self.redis_client.get(cache_key)
            
            if cached_results:
                return json.loads(cached_results)

            # Generate query embedding
            query_embedding = self.embedding_model.encode([query], convert_to_tensor=True).cpu().numpy()
            
            # Search in ChromaDB
            results = await self.collection.query(
                query_embeddings=query_embedding.tolist(),
                n_results=k
            )
            
            # Process results
            documents = results.get("documents", [[]])[0]  # Get first list of documents
            metadatas = results.get("metadatas", [[]])[0]  # Get first list of metadata
            distances = results.get("distances", [[]])[0]  # Get first list of distances
            
            search_results = [
                {
                    "document": doc,
                    "metadata": meta,
                    "score": float(1 - dist) if isinstance(dist, (int, float)) else 0.0
                }
                for doc, meta, dist in zip(documents, metadatas, distances)
            ]
            
            # Cache results
            self.redis_client.setex(
                cache_key,
                300,  # Cache for 5 minutes
                json.dumps(search_results)
            )
            
            return search_results
            
        except Exception as e:
            logger.error(f"Error in search: {str(e)}")
            return []

    def get_stats(self) -> Dict:
        """Get statistics about the vector store"""
        try:
            return {
                "total_documents": self.collection.count() if self.collection else 0,
                "embedding_model": str(self.embedding_model),
                "has_redis_cache": bool(self.redis_client)
            }
        except Exception as e:
            logger.error(f"Error getting vector store stats: {str(e)}")
            return {
                "error": str(e)
            }