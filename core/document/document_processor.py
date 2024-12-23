from typing import List, Dict, Tuple, Set
import tiktoken
import re
from langchain.text_splitter import RecursiveCharacterTextSplitter
import pymupdf
from pathlib import Path
from datetime import datetime
import numpy as np
from PIL import Image
from pdfminer.high_level import extract_text
from pytesseract import pytesseract
from pdf2image import convert_from_path
from core.logger.app_logger import logger


class DocumentProcessor:
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 80,
        min_chunk_size: int = 64,
        max_input_length: int = 2048,
    ):
        """
        Initialize document processor optimized for Ollama 3.2 3B model.
        """
        self.encoding = tiktoken.get_encoding("cl100k_base")
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=self._token_length,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""],
            keep_separator=True,
        )
        
        self.min_chunk_size = min_chunk_size
        self.max_input_length = max_input_length
        self.model_name = "ollama-3.2-3b"

    def _token_length(self, text: str) -> int:
        """Calculate token length using tiktoken."""
        return len(self.encoding.encode(text))

    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text."""
        try:
            if not isinstance(text, str):
                text = str(text)
                
            # Remove unicode characters
            text = text.encode('ascii', 'ignore').decode()
            
            # Basic cleaning
            text = re.sub(r'\s+', ' ', text)
            text = re.sub(r'\n\s*\n', '\n\n', text)
            
            # Remove PDF artifacts
            text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
            text = re.sub(r'(?i)page \d+ of \d+', '', text)
            text = re.sub(r'(?i)confidential|draft|internal use only', '', text)
            
            # Simplify punctuation
            text = re.sub(r'\.{2,}', '.', text)
            text = re.sub(r'[\(\{\[\]\}\)]', '', text)
            
            # Additional cleaning
            text = re.sub(r'\x0c', '', text)  # Remove form feed
            text = re.sub(r'(?<=\S)-(?=\S)', '- ', text)  # Fix hyphenation
            
            return text.strip()
            
        except Exception as e:
            logger.error(f"Error cleaning text: {str(e)}")
            return text if isinstance(text, str) else str(text)

    def _extract_text_with_pymupdf(self, pdf_path: str) -> List[Dict]:
        """Extract text using PyMuPDF with defensive programming"""
        try:
            doc = pymupdf.Document(pdf_path)
            pages = []
            
            for page_num in range(len(doc)):
                try:
                    page = doc[page_num]
                    page_content = ""
                    
                    # Method 1: Try simple text extraction first
                    try:
                        simple_text = page.get_text("text")
                        if simple_text and simple_text.strip():
                            page_content = simple_text
                    except Exception as e:
                        logger.debug(f"Simple text extraction failed for page {page_num + 1}: {e}")
                    
                    # Method 2: Try dict-based extraction if simple method yields no content
                    if not page_content:
                        try:
                            # Get raw dictionary
                            raw_dict = page.get_text("rawdict")
                            
                            # Extract text from blocks
                            text_parts = []
                            
                            if isinstance(raw_dict, dict) and "blocks" in raw_dict:
                                for block in raw_dict["blocks"]:
                                    if not isinstance(block, dict):
                                        continue
                                        
                                    # Handle text blocks
                                    if block.get("type") == 0:  # text block
                                        for line in block.get("lines", []):
                                            if isinstance(line, dict) and "spans" in line:
                                                for span in line["spans"]:
                                                    if isinstance(span, dict) and "text" in span:
                                                        text = span["text"].strip()
                                                        if text:
                                                            text_parts.append(text)
                            
                            if text_parts:
                                page_content = " ".join(text_parts)
                                
                        except Exception as e:
                            logger.debug(f"Dict-based extraction failed for page {page_num + 1}: {e}")
                    
                    # Method 3: Try HTML extraction as last resort
                    if not page_content:
                        try:
                            html_text = page.get_text("html")
                            # Remove HTML tags
                            html_text = re.sub('<[^<]+?>', '', html_text)
                            if html_text and html_text.strip():
                                page_content = html_text
                        except Exception as e:
                            logger.debug(f"HTML extraction failed for page {page_num + 1}: {e}")
                    
                    # If we got any content, clean and add it
                    if page_content and page_content.strip():
                        cleaned_text = self._clean_text(page_content)
                        if cleaned_text:
                            pages.append({
                                "content": cleaned_text,
                                "page_num": page_num + 1,
                                "type": "pymupdf"
                            })
                            logger.debug(f"Successfully extracted text from page {page_num + 1}")
                    else:
                        logger.debug(f"No content extracted from page {page_num + 1}")
                    
                except Exception as page_error:
                    logger.warning(f"Error processing page {page_num + 1}: {str(page_error)}")
                    continue
            
            # Close the document
            doc.close()
            
            # Check if we got any pages
            if pages:
                logger.info(f"Successfully extracted text from {len(pages)} pages using PyMuPDF")
                return pages
            else:
                logger.warning("No text extracted from any pages using PyMuPDF")
                return []
                
        except Exception as e:
            logger.error(f"PyMuPDF extraction failed: {str(e)}")
            return []

    def _extract_text_with_pdfminer(self, pdf_path: str) -> List[Dict]:
        """Fallback text extraction using PDFMiner."""
        try:
            text = extract_text(pdf_path)
            if text.strip():
                return [{
                    "content": self._clean_text(text),
                    "page_num": 1
                }]
        except Exception as e:
            logger.error(f"PDFMiner extraction failed: {str(e)}")
        return []

    def _perform_ocr(self, pdf_path: str) -> List[Dict]:
        """OCR fallback using Tesseract."""
        try:
            images = convert_from_path(pdf_path)
            pages = []

            for i, image in enumerate(images):
                img_gray = Image.fromarray(np.array(image)).convert('L')
                custom_config = r'--oem 3 --psm 6'
                text = pytesseract.image_to_string(img_gray, config=custom_config)
                
                if text.strip():
                    pages.append({
                        "content": self._clean_text(text),
                        "page_num": i + 1
                    })

            return pages
        except Exception as e:
            logger.error(f"OCR extraction failed: {str(e)}")
            return []

    async def process_pdf(self, pdf_path: str) -> Tuple[List[str], List[Dict]]:
        """Process PDF document with fallback mechanisms."""
        if not Path(pdf_path).exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        pages = []
        extraction_method = "pymupdf"

        try:
            # Extraction pipeline with better error handling
            pages = self._extract_text_with_pymupdf(pdf_path)
            
            if not pages:
                logger.info("Attempting PDFMiner extraction...")
                extraction_method = "pdfminer"
                pages = self._extract_text_with_pdfminer(pdf_path)
            
            if not pages:
                logger.info("Attempting OCR extraction...")
                extraction_method = "ocr"
                pages = self._perform_ocr(pdf_path)

            if not pages:
                raise Exception("No text could be extracted from the PDF")

            # Process text
            all_text = "\n\n".join(page["content"] for page in pages)
            chunks = self.text_splitter.split_text(all_text)
            
            # Validate chunks
            valid_chunks = []
            for chunk in chunks:
                token_length = self._token_length(chunk)
                if token_length >= self.min_chunk_size and token_length <= self.max_input_length:
                    valid_chunks.append(chunk)
            
            if not valid_chunks:
                logger.warning("No valid chunks were generated after filtering")
            
            metadata = [{
                "type": extraction_method,
                "page": page["page_num"],
                "source": pdf_path,
                "total_pages": len(pages),
                "token_count": self._token_length(page["content"]),
                "processing_timestamp": datetime.now().isoformat()
            } for page in pages]

            return valid_chunks, metadata

        except Exception as e:
            logger.error(f"PDF processing failed: {str(e)}")
            raise




# class DocumentProcessor:
#     def __init__(self):
#         self.text_splitter = RecursiveCharacterTextSplitter(
#             chunk_size=1000,
#             chunk_overlap=20,
#             separators=["\n\n", "\n", " ", ""]
#         )

#     async def process_pdf(self, pdf_path: str) -> Tuple[List[str], List[Dict]]:
#         """
#         Process PDF document with PDFPlumber and OCR fallback
#         """
#         try:
#             # Try PDFPlumber first (better for text-based PDFs)
#             loader = PDFPlumberLoader(pdf_path)
#             documents = loader.load()
            
#             pages = []
#             metadata = []
            
#             for doc in documents:
#                 if doc.page_content.strip():  # Only include non-empty pages
#                     pages.append(doc.page_content)
#                     meta = {
#                         "type": "text",
#                         "page": doc.metadata.get("page", 0) + 1,
#                         "source": pdf_path,
#                         "total_pages": len(documents)
#                     }
#                     metadata.append(meta)
            
#             # If no text was extracted, try PyPDF
#             if not pages:
#                 logger.info("No text found with PDFPlumber, trying PyPDF...")
#                 loader = PyPDFLoader(pdf_path)
#                 documents = loader.load()
                
#                 for doc in documents:
#                     if doc.page_content.strip():
#                         pages.append(doc.page_content)
#                         meta = {
#                             "type": "pypdf",
#                             "page": doc.metadata.get("page", 0) + 1,
#                             "source": pdf_path,
#                             "total_pages": len(documents)
#                         }
#                         metadata.append(meta)
            
#             # If still no text, fall back to OCR
#             if not pages:
#                 raise Exception("No text found with PDF loaders")
                
#             chunks = self.text_splitter.split_text('\n\n'.join(pages))
#             return chunks, metadata

#         except Exception as e:
#             logger.warning(f"Falling back to OCR due to error: {str(e)}")
#             try:
#                 images = convert_from_path(pdf_path)
#                 ocr_texts = []
#                 ocr_metadata = []
                
#                 for i, image in enumerate(images):
#                     text = image_to_string(image)
#                     if text.strip():  # Only include non-empty text
#                         ocr_texts.append(text)
#                         ocr_metadata.append({
#                             "type": "ocr",
#                             "page": i + 1,
#                             "source": pdf_path,
#                             "processing_method": "tesseract"
#                         })
                
#                 chunks = self.text_splitter.split_text('\n\n'.join(ocr_texts))
#                 return chunks, ocr_metadata
                
#             except Exception as ocr_error:
#                 logger.error(f"OCR fallback failed: {str(ocr_error)}")
#                 raise

#     def get_status(self) -> Dict:
#         """Return processor status and configuration"""
#         return {
#             "chunk_size": self.text_splitter.chunk_size,
#             "chunk_overlap": self.text_splitter.chunk_overlap,
#             "supported_formats": ["pdf"],
#             "processors": {
#                 "primary": "pdfplumber",
#                 "secondary": "pypdf",
#                 "fallback": "tesseract-ocr"
#             }
#         }
