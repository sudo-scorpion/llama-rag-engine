# core/document_processor/pdf_processor.py
import camelot
import pdfplumber
from typing import Dict, List, Optional
from pathlib import Path
import hashlib

class PDFProcessor:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def analyze_document(self, file_path: str) -> Dict:
        """Analyze PDF for tables and content structure."""
        try:
            # Try detecting tables using camelot
            tables_lattice = camelot.read_pdf(file_path, flavor='lattice', pages='all')
            tables_stream = camelot.read_pdf(file_path, flavor='stream', pages='all')

            # Use pdfplumber for additional verification
            with pdfplumber.open(file_path) as pdf:
                pages_info = []
                for page_num, page in enumerate(pdf.pages, 1):
                    plumber_tables = page.find_tables()
                    pages_info.append({
                        'page': page_num,
                        'has_tables': len(plumber_tables) > 0,
                        'table_count': len(plumber_tables)
                    })

            return {
                'has_tables': len(tables_lattice) > 0 or len(tables_stream) > 0,
                'table_count': len(tables_lattice) + len(tables_stream),
                'pages': pages_info,
                'tables_by_type': {
                    'lattice': len(tables_lattice),
                    'stream': len(tables_stream)
                }
            }
        except Exception as e:
            raise Exception(f"Error analyzing document: {str(e)}")

    def process_document(self, file_path: str) -> List[Dict]:
        """Process PDF document and extract both text and tables."""
        chunks = []
        
        # Process tables first
        tables_info = self.analyze_document(file_path)
        if tables_info['has_tables']:
            tables = camelot.read_pdf(file_path, pages='all')
            for table_idx, table in enumerate(tables):
                table_data = table.df.to_dict('records')
                chunk_id = self._generate_chunk_id(str(table_data), table.page, table_idx, 'table')
                chunks.append({
                    'id': chunk_id,
                    'content': table_data,
                    'metadata': {
                        'source': str(file_path),
                        'page': table.page,
                        'type': 'table',
                        'accuracy': table.accuracy,
                        'position': table_idx
                    }
                })

        # Process text content
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text:
                    text_chunks = self._create_chunks(text)
                    for chunk_idx, chunk in enumerate(text_chunks):
                        chunk_id = self._generate_chunk_id(chunk, page_num, chunk_idx, 'text')
                        chunks.append({
                            'id': chunk_id,
                            'content': chunk,
                            'metadata': {
                                'source': str(file_path),
                                'page': page_num,
                                'type': 'text',
                                'position': chunk_idx
                            }
                        })

        return chunks

    def _create_chunks(self, text: str) -> List[str]:
        """Create overlapping chunks from text."""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                last_period = text.rfind('.', start, end)
                if last_period != -1:
                    end = last_period + 1
            
            chunk = text[start:end].strip()
            if chunk:  # Only add non-empty chunks
                chunks.append(chunk)
            
            start = end - self.chunk_overlap

        return chunks

    def _generate_chunk_id(self, content: str, page: int, position: int, chunk_type: str) -> str:
        """Generate a unique ID for a chunk."""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        return f"{chunk_type}_{page}_{position}_{content_hash[:8]}"

# Example usage
if __name__ == "__main__":
    processor = PDFProcessor()
    pdf_path = "path/to/your/document.pdf"
    
    # Analyze document
    analysis = processor.analyze_document(pdf_path)
    print(f"Document analysis: {analysis}")
    
    # Process document
    chunks = processor.process_document(pdf_path)
    print(f"Processed {len(chunks)} chunks")