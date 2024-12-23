import numpy as np
from transformers import AutoModel, AutoTokenizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict
import pandas as pd
from sqlite3 import connect

class AnswerGrader:
    def __init__(self):
        self.db_conn = connect('./db/answer_grades.db')
        self.model = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
        self.tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
        self.create_tables()

    def create_tables(self):
        cursor = self.db_conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS answer_grades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT,
                answer TEXT,
                relevance_score FLOAT,
                confidence_score FLOAT,
                feedback TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.db_conn.commit()

    def _get_embeddings(self, text: str) -> np.ndarray:
        inputs = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True)
        outputs = self.model(**inputs)
        return outputs.last_hidden_state.mean(dim=1).detach().numpy()

    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        emb1 = self._get_embeddings(text1)
        emb2 = self._get_embeddings(text2)
        return cosine_similarity(emb1, emb2)[0][0]

    def grade_answer(self, question: str, answer: str, context: List[Dict]) -> Dict:
        # Calculate semantic relevance
        context_text = ' '.join(ctx["document"] for ctx in context)
        relevance_score = self._calculate_semantic_similarity(answer, context_text)
        
        # Calculate confidence score
        confidence_score = self._calculate_confidence(answer)
        
        # Store the grades
        cursor = self.db_conn.cursor()
        cursor.execute(
            'INSERT INTO answer_grades (question, answer, relevance_score, confidence_score) VALUES (?, ?, ?, ?)',
            (question, answer, relevance_score, confidence_score)
        )
        self.db_conn.commit()
        
        return {
            'relevance_score': float(relevance_score),
            'confidence_score': confidence_score
        }

    def _calculate_confidence(self, answer: str) -> float:
        # Enhanced confidence scoring based on multiple factors
        factors = {
            'length': min(1.0, len(answer.split()) / 100),
            'specificity': len(set(answer.split())) / len(answer.split()) if answer.split() else 0,
            'structure': 0.8 if any(marker in answer.lower() for marker in ['because', 'therefore', 'however']) else 0.5
        }
        return sum(factors.values()) / len(factors)

    def update_grade_with_feedback(self, answer_id: int, feedback: str):
        cursor = self.db_conn.cursor()
        cursor.execute(
            'UPDATE answer_grades SET feedback = ? WHERE id = ?',
            (feedback, answer_id)
        )
        self.db_conn.commit()

    def get_historical_grades(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM answer_grades", self.db_conn)