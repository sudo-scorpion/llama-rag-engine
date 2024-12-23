import os
import time
from typing import Dict, List
from core.logger.app_logger import logger
from core.query.query_expander import QueryExpander
from core.prompt.prompt_template import PromptTemplate
from core.document.document_processor import DocumentProcessor
from core.retrieval.hybrid_retrieval import HybridRetriever
from core.vector.vector_store import VectorStore
from core.grader.answer_grader import AnswerGrader
from core.ollama.ollama_client import OllamaClient
from termcolor import colored

class RAGEngine:
    def __init__(self, model_name: str = "llama3.2:3b", temperature: float = 0.7, chroma_host: str = 'localhost', chroma_port: int = 8000):
        self.document_processor = DocumentProcessor()
        self.vector_store = VectorStore(host=chroma_host, port=chroma_port)
        self.hybrid_retriever = HybridRetriever(self.vector_store)
        self.query_expander = QueryExpander()
        self.answer_grader = AnswerGrader()
        self.ollama_client = OllamaClient()
        self.model_name = os.getenv("OLLAMA_MODEL_NAME", model_name)
        self.temperature = temperature
        
        # Initialize performance metrics tracking
        self.metrics = {
            'avg_response_time': [],
            'avg_relevance_score': [],
            'temp_adjustments': [],
            'total_documents': 0,
            'failed_queries': 0,
            'successful_queries': 0
        }

    async def initialize(self):
        """Initialize the RAG system components"""
        try:
            await self.vector_store.initialize()
            logger.info("Vector store initialized successfully")
            
            # Warm up the embedding model
            _ = await self.vector_store.search("warmup query", k=1)
            logger.info("Embedding model warmed up")
            
        except Exception as e:
            logger.error(f"Error initializing RAG system: {str(e)}")
            raise

    def _adjust_temperature(self, relevance_score: float):
        """Dynamically adjust temperature based on answer relevance"""
        try:
            if relevance_score < 0.5:
                self.temperature = max(0.1, self.temperature - 0.1)
            elif relevance_score > 0.8:
                self.temperature = min(1.0, self.temperature + 0.1)
            self.metrics['temp_adjustments'].append(self.temperature)
            logger.debug(f"Temperature adjusted to {self.temperature} based on relevance score {relevance_score}")
        except Exception as e:
            logger.error(f"Error adjusting temperature: {str(e)}")

    async def process_document(self, pdf_path: str) -> int:
        """Process and index a PDF document"""
        try:
            # Process the document
            chunks, metadata = await self.document_processor.process_pdf(pdf_path)
            
            if not chunks:
                logger.warning(f"No text extracted from document: {pdf_path}")
                return 0
                
            # Add to vector store
            await self.vector_store.add_embeddings(chunks, metadata)
            
            # Index for hybrid search
            self.hybrid_retriever.index_documents(chunks)
            
            # Update metrics
            self.metrics['total_documents'] += 1
            
            logger.info(f"Successfully processed document with {len(chunks)} chunks")
            return len(chunks)
            
        except Exception as e:
            logger.error(f"Error processing document {pdf_path}: {str(e)}")
            raise

    async def _get_contexts(self, question: str, max_contexts: int = 3) -> List[Dict]:
        """Get relevant contexts for a question using hybrid search"""
        try:
            expanded_queries = await self.query_expander.expand_query(question)
            all_contexts = []

            for query in expanded_queries:
                contexts = await self.hybrid_retriever.hybrid_search(query)
                if contexts:  # Check if contexts is not None
                    all_contexts.extend(contexts)

            # Deduplicate and sort by score
            seen = set()
            unique_contexts = sorted(
                [ctx for ctx in all_contexts if ctx["document"] not in seen and not seen.add(ctx["document"])],
                key=lambda x: x.get("score", 0),
                reverse=True
            )[:max_contexts]
            return unique_contexts
        except Exception as e:
            logger.error(f"Error getting contexts: {str(e)}")
            return []
        
    async def answer_question(self, question: str) -> Dict:
        """Generate an answer for a given question"""
        start_time = time.time()
        try:
            # Get contexts
            contexts = await self._get_contexts(question)

            if not contexts:
                self.metrics['failed_queries'] += 1
                return {
                    'question': question,
                    'answer': "I couldn't find relevant information to answer your question.",
                    'error': "No relevant contexts found",
                    'relevance_score': 0.0,
                    'confidence_score': 0.0,
                    'contexts': []
                }

            # Prepare prompt
            context_prompt = "\n".join([ctx["document"] for ctx in contexts])

            prompt = PromptTemplate.format_prompt(context_prompt, question)

            # Get answer from Ollama using a new client instance
            request = await self.ollama_client.generate(prompt)
            answer = request.get("response", "No answer generated")

            # Grade answer and adjust temperature
            grades = self.answer_grader.grade_answer(question, answer, contexts)
            self._adjust_temperature(grades['relevance_score'])

            # Update metrics
            response_time = time.time() - start_time
            self.metrics['avg_response_time'].append(response_time)
            self.metrics['avg_relevance_score'].append(grades['relevance_score'])
            self.metrics['successful_queries'] += 1

            # Output response in nicely formatted colored text
            print(colored(f"\nQuestion: {question}", 'cyan'))
            print(colored(f"Answer: {answer}\n", 'green'))
            print(colored(f"Relevance Score: {grades['relevance_score']}", 'yellow'))
            print(colored(f"Confidence Score: {grades['confidence_score']}", 'yellow'))
            print(colored(f"Response Time (s): {response_time}", 'magenta'))
        
            return {
                'question': question,
                'answer': answer,
                'relevance_score': grades['relevance_score'],
                'confidence_score': grades['confidence_score'],
                'contexts': contexts,
                'response_time': response_time,
                'error': None
            }

        except Exception as e:
            logger.error(f"Error in answer_question: {str(e)}")
            self.metrics['failed_queries'] += 1
            return {
                'question': question,
                'answer': "Sorry, I encountered an error while processing your question.",
                'error': str(e),
                'relevance_score': None,
                'confidence_score': None,
                'contexts': None
            }
        
    def get_performance_metrics(self) -> Dict:
        """Get comprehensive system performance metrics"""
        try:
            total_queries = self.metrics['successful_queries'] + self.metrics['failed_queries']
            success_rate = (self.metrics['successful_queries'] / total_queries * 100) if total_queries > 0 else 0
            
            return {
                'avg_response_time': sum(self.metrics['avg_response_time']) / len(self.metrics['avg_response_time']) if self.metrics['avg_response_time'] else 0,
                'avg_relevance_score': sum(self.metrics['avg_relevance_score']) / len(self.metrics['avg_relevance_score']) if self.metrics['avg_relevance_score'] else 0,
                'current_temperature': self.temperature,
                'temperature_history': self.metrics['temp_adjustments'],
                'total_documents_processed': self.metrics['total_documents'],
                'total_queries': total_queries,
                'successful_queries': self.metrics['successful_queries'],
                'failed_queries': self.metrics['failed_queries'],
                'success_rate': success_rate
            }
        except Exception as e:
            logger.error(f"Error getting metrics: {str(e)}")
            return {'error': str(e)}

    async def cleanup(self):
        """Cleanup system resources"""
        try:
            await self.http_client.aclose()
            logger.info("RAG system resources cleaned up")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")