import numpy as np
from typing import List, Dict
from core.logger.app_logger import logger
from rank_bm25 import BM25Okapi
from transformers import AutoTokenizer

class HybridRetriever:
    def __init__(self, vector_store):
        self.vector_store = vector_store
        self.tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
        self.bm25 = None
        self.documents = []
        
    def index_documents(self, documents: List[str]):
        self.documents = documents
        tokenized_docs = [
            self.tokenizer.tokenize(doc.lower()) 
            for doc in documents
        ]
        self.bm25 = BM25Okapi(tokenized_docs)
    
    def _safe_normalize_scores(self, scores: List[float], max_score: float, weight: float) -> List[float]:
        """Safely normalize scores to prevent division issues"""
        if not scores:
            return []
            
        # Ensure max_score is positive to prevent division by zero
        max_score = max(max_score, 1e-10)
        
        # Convert to numpy array for vectorized operations
        scores_array = np.array(scores, dtype=np.float32)
        
        # Normalize and apply weight
        normalized_scores = np.clip(scores_array / max_score, 0, 1) * weight
        
        return normalized_scores.tolist()
    
    async def hybrid_search(self, query: str, k: int = 5) -> List[Dict]:
        """Perform hybrid search with safe score normalization"""
        try:
            # Get dense retrieval results
            dense_results = await self.vector_store.search(query, k=k)
            
            # Get sparse retrieval results
            tokenized_query = self.tokenizer.tokenize(query.lower())
            bm25_scores = self.bm25.get_scores(tokenized_query)
            top_sparse_indices = np.argsort(bm25_scores)[-k:][::-1]
            sparse_results = [
                {
                    "document": self.documents[i], 
                    "score": float(bm25_scores[i])
                }
                for i in top_sparse_indices
            ]
            
            # Extract scores and documents
            dense_scores = [result["score"] for result in dense_results]
            sparse_scores = [result["score"] for result in sparse_results]
            
            # Find maximum scores safely
            max_dense = max(dense_scores) if dense_scores else 1.0
            max_sparse = max(sparse_scores) if sparse_scores else 1.0
            
            # Weight parameters
            dense_weight = 0.7
            sparse_weight = 0.3
            
            # Normalize scores safely
            normalized_dense_scores = self._safe_normalize_scores(
                dense_scores, max_dense, dense_weight
            )
            normalized_sparse_scores = self._safe_normalize_scores(
                sparse_scores, max_sparse, sparse_weight
            )
            
            # Combine results
            combined_results = {}
            
            # Add dense results
            for result, norm_score in zip(dense_results, normalized_dense_scores):
                doc = result["document"]
                combined_results[doc] = combined_results.get(doc, 0) + norm_score
            
            # Add sparse results
            for result, norm_score in zip(sparse_results, normalized_sparse_scores):
                doc = result["document"]
                combined_results[doc] = combined_results.get(doc, 0) + norm_score
            
            # Sort and format results
            sorted_results = [
                {
                    "document": doc,
                    "score": float(score)  # Ensure score is float
                }
                for doc, score in sorted(
                    combined_results.items(),
                    key=lambda x: x[1],
                    reverse=True
                )
            ][:k]
            
            return sorted_results
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {str(e)}")
            return []
    
    def get_retrieval_stats(self) -> Dict:
        """Get statistics about the retriever"""
        return {
            "total_documents": len(self.documents),
            "has_bm25_index": self.bm25 is not None,
            "vector_store_stats": self.vector_store.get_stats()
        }