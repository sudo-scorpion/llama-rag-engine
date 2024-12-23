import nltk
from nltk.corpus import wordnet, stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from collections import OrderedDict
from typing import List, Dict, Optional
import json
from core.ollama.ollama_client import OllamaClient
from core.logger.app_logger import logger
import httpx

# Download required NLTK data
try:
    nltk.download('punkt_tab', quiet=True)
    nltk.download('punkt', quiet=True)
    nltk.download('averaged_perceptron_tagger_eng', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)
    nltk.download('wordnet', quiet=True)
    nltk.download('stopwords', quiet=True)
except Exception as e:
    logger.warning(f"Error downloading NLTK data: {e}")


class QueryExpander:
    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        max_expansions: int = 5,
        similarity_threshold: float = 0.7
    ):
        try:
            # Initialize NLTK components
            self.lemmatizer = WordNetLemmatizer()
            self.stop_words = set(stopwords.words('english'))
            
            # Load sentence transformer for semantic similarity
            self.embedding_model = SentenceTransformer(embedding_model)
            
            # Configuration
            self.max_expansions = max_expansions
            self.similarity_threshold = similarity_threshold
            self.expansion_cache = OrderedDict()
            self.max_cache_size = 1000
            
            # Templates for LLM prompts
            self.prompt_templates = {
                'semantic_expansion': """Given the search query: "{query}"
                Generate {num_variations} different ways to express the same search intent, maintaining the core meaning while varying the wording and perspective. Consider:
                1. Different ways to phrase the same concept
                2. Related terms and synonyms
                3. More specific or detailed versions
                4. Broader or more general versions
                Format: Return only the queries, one per line.""",

                'query_analysis': """Analyze this search query: "{query}"
                1. What is the core intent?
                2. What are the key concepts?
                3. What context might be missing?
                4. Are there any ambiguities?""",

                'contextual_refinement': """Given the search query "{query}" and this additional context: "{context}"
                Generate {num_variations} refined versions of the query that:
                1. Incorporate relevant context
                2. Maintain the original intent
                3. Add specificity where appropriate
                Format: Return only the refined queries, one per line."""
            }
                        
        except Exception as e:
            logger.error(f"Error initializing QueryExpander: {e}")
            raise

    async def _call_ollama(self, prompt: str) -> str:
        """Make an async call to Ollama API with retry logic"""
        try:            
            request = await OllamaClient().generate(prompt)
            response = request.get('response', '')

            if response and isinstance(response, str):
                logger.info("Query expander is being called")
                logger.info(f"Ollama response: {response}")
                return response
            else:
                logger.warning("Empty response from Ollama")
                return ""
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during Ollama API call: {str(e)}")
            logger.error(f"Response content: {e.response.content if hasattr(e, 'response') else 'No response content'}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error during Ollama API call: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during Ollama API call: {str(e)}")
            raise

    async def generate_semantic_variations(self, query: str, num_variations: int = 5) -> List[str]:
        """Generate semantic variations using LLM"""
        cache_key = f"semantic_{query}_{num_variations}"
        if cache_key in self.expansion_cache:
            return self.expansion_cache[cache_key]
            
        try:
            prompt = self.prompt_templates['semantic_expansion'].format(
                query=query,
                num_variations=num_variations
            )
            
            response = await self._call_ollama(prompt)
            
            if not response:
                logger.warning("Empty response from Ollama")
                return []
                
            variations = [v.strip() for v in response.split('\n') if v.strip()]
            
            # Update cache
            self.expansion_cache[cache_key] = variations
            if len(self.expansion_cache) > self.max_cache_size:
                self.expansion_cache.popitem(last=False)
                
            return variations
            
        except Exception as e:
            logger.warning(f"Semantic variation generation failed: {e}")
            return []

    async def cleanup(self):
        """Cleanup system resources"""
        try:
            await OllamaClient().cleanup()
            logger.info("QueryExpander resources cleaned up")
        except Exception as e:
            logger.error(f"Error during QueryExpander cleanup: {str(e)}")


    async def analyze_query(self, query: str) -> Dict:
        """Analyze query intent and structure using LLM"""
        try:
            prompt = self.prompt_templates['query_analysis'].format(query=query)
            response = await self._call_ollama(prompt)
            
            try:
                analysis = json.loads(response)
                return analysis
            except json.JSONDecodeError:
                logger.warning("Failed to parse query analysis response as JSON")
                return {}
                
        except Exception as e:
            logger.warning(f"Query analysis failed: {e}")
            return {}

    def calculate_similarity(self, query1: str, query2: str) -> float:
        """Calculate semantic similarity between queries using embeddings"""
        try:
            # Generate embeddings
            emb1 = self.embedding_model.encode([query1])[0]
            emb2 = self.embedding_model.encode([query2])[0]
            
            # Calculate cosine similarity
            similarity = cosine_similarity(
                emb1.reshape(1, -1),
                emb2.reshape(1, -1)
            )[0][0]
            
            return float(similarity)
            
        except Exception as e:
            logger.warning(f"Similarity calculation failed: {e}")
            return 0.0

    def filter_similar_queries(self, queries: List[str], threshold: float = None) -> List[str]:
        """Filter out semantically similar queries"""
        if not queries:
            return []
            
        threshold = threshold or self.similarity_threshold
        filtered = [queries[0]]  # Keep the first query
        
        for query in queries[1:]:
            # Check similarity with all accepted queries
            similarities = [
                self.calculate_similarity(query, accepted)
                for accepted in filtered
            ]
            
            # Add if not too similar to any existing query
            if not any(sim > threshold for sim in similarities):
                filtered.append(query)
                
        return filtered

    async def expand_with_context(
        self,
        query: str,
        context: Optional[str] = None,
        num_variations: int = 3
    ) -> List[str]:
        """Generate context-aware query expansions"""
        try:
            if context:
                prompt = self.prompt_templates['contextual_refinement'].format(
                    query=query,
                    context=context,
                    num_variations=num_variations
                )
            else:
                return await self.generate_semantic_variations(query, num_variations)
                
            response = await self._call_ollama(prompt)
            variations = [v.strip() for v in response.split('\n') if v.strip()]
            
            return variations
            
        except Exception as e:
            logger.warning(f"Context-aware expansion failed: {e}")
            return []

    async def expand_query(
        self,
        query: str,
        context: Optional[str] = None,
        num_variations: int = 5
    ) -> Dict:
        """
        Comprehensive query expansion using multiple techniques
        """
        try:
            results = {
                "original_query": query,
                "expansions": [],
                "analysis": {},
                "metadata": {}
            }
            
            # Get query analysis
            analysis = await self.analyze_query(query)
            results["analysis"] = analysis
            
            # Generate variations
            semantic_variations = await self.generate_semantic_variations(
                query,
                num_variations
            )
            
            # Generate context-aware variations if context provided
            if context:
                context_variations = await self.expand_with_context(
                    query,
                    context,
                    num_variations
                )
                all_variations = semantic_variations + context_variations
            else:
                all_variations = semantic_variations
            
            # Filter similar variations
            filtered_variations = self.filter_similar_queries(all_variations)
            
            # Add original query if not present
            if query not in filtered_variations:
                filtered_variations.insert(0, query)
            
            # Limit number of expansions
            results["expansions"] = filtered_variations[:self.max_expansions]
            
            # Add metadata
            results["metadata"] = {
                "total_variations_generated": len(all_variations),
                "variations_after_filtering": len(filtered_variations),
                "similarity_threshold_used": self.similarity_threshold,
                "context_provided": bool(context)
            }
            
            return results
            
        except Exception as e:
            logger.error(f"Query expansion error: {e}")
            return {"original_query": query, "expansions": [query], "error": str(e)}

    def get_stats(self) -> Dict:
        """Get statistics about the query expander"""
        return {
            "model_name": self.model_name,
            "embedding_model": self.embedding_model.get_config_dict()['model_name'],
            "max_expansions": self.max_expansions,
            "similarity_threshold": self.similarity_threshold,
            "cache_size": len(self.expansion_cache),
            "max_cache_size": self.max_cache_size,
            "uses_lemmatization": True,
            "stopwords_loaded": len(self.stop_words) > 0
        }