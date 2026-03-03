import os
import base64
import logging
import uuid
import hashlib
import tempfile
from typing import Dict, List, Any, Optional, Generator
from datetime import datetime
from dataclasses import dataclass
import filetype
import io
from unstructured.partition.auto import partition
from unstructured.documents.elements import Element, Text, Image as UnstructuredImage
from PIL import Image
from django.conf import settings

# Configure logging
logging.basicConfig(
    level=getattr(settings, 'LOG_LEVEL', logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class Chunk:
    text: str
    chunk_id: str
    metadata: Dict[str, Any]
    start_char: int
    end_char: int

@dataclass
class ImageResult:
    id: str
    base64_image: str
    path: str
    metadata: Dict[str, Any]

class EnhancedDocumentProcessor:
    def __init__(
        self,
        max_text_chunk_size: int = 1500,
        text_overlap: int = 200,
        max_image_dimension: int = 2048
    ):
        self.max_text_chunk_size = max_text_chunk_size
        self.text_overlap = text_overlap
        self.max_image_dimension = max_image_dimension
        self.supported_extensions = ['.pdf', '.docx', '.doc', '.pptx', '.txt', '.jpg', '.jpeg', '.png']

    def _validate_file(self, file_path: str) -> None:
        """Validate file type and size"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        if not any(file_path.lower().endswith(ext) for ext in self.supported_extensions):
            raise ValueError(f"Unsupported file format: {os.path.basename(file_path)}")

    def _generate_metadata(self, file_path: str) -> Dict[str, Any]:
        """Generate comprehensive metadata"""
        file_stats = os.stat(file_path)
        return {
            'document_id': str(uuid.uuid4()),
            'file_name': os.path.basename(file_path),
            'file_size': file_stats.st_size,
            'file_hash': self._calculate_file_hash(file_path),
            'uploaded_at': datetime.now().isoformat(),
            'content_type': self._detect_content_type(file_path),
            'processing_date': datetime.now().isoformat()
        }

    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 file hash"""
        sha_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(4096):
                sha_hash.update(chunk)
        return sha_hash.hexdigest()

    def _detect_content_type(self, file_path: str) -> str:
        """Detect file content type"""
        kind = filetype.guess(file_path)
        return kind.mime if kind else 'application/octet-stream'

    def _chunk_text(self, text: str, metadata: Dict[str, Any]) -> Generator[Chunk, None, None]:
        """Improved text chunking with sentence boundary awareness"""
        current_chunk = []
        current_length = 0
        start_idx = 0

        # Simple sentence splitting (consider using NLTK for better results)
        sentences = text.split('. ')
        
        for sentence in sentences:
            sentence += '. '
            sentence_length = len(sentence)
            
            if current_length + sentence_length > self.max_text_chunk_size:
                chunk_text = ' '.join(current_chunk)
                yield Chunk(
                    text=chunk_text,
                    chunk_id=str(uuid.uuid4()),
                    metadata=metadata,
                    start_char=start_idx,
                    end_char=start_idx + len(chunk_text)
                )
                
                # Keep overlap
                current_chunk = current_chunk[-self.text_overlap // 20 :] + [sentence]
                current_length = sum(len(s) for s in current_chunk)
                start_idx += len(chunk_text) - self.text_overlap
            else:
                current_chunk.append(sentence)
                current_length += sentence_length

        if current_chunk:
            yield Chunk(
                text=' '.join(current_chunk),
                chunk_id=str(uuid.uuid4()),
                metadata=metadata,
                start_char=start_idx,
                end_char=start_idx + len(' '.join(current_chunk))
            )

    def _process_image(self, image_data: bytes, metadata: Dict[str, Any]) -> Optional[ImageResult]:
        """Process and optimize image with retries"""
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Convert and resize image
                temp_path = os.path.join(temp_dir, f"temp_{metadata['document_id']}.png")
                
                with Image.open(io.BytesIO(image_data)) as img:
                    # Convert to RGB if needed
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Resize if necessary
                    if max(img.size) > self.max_image_dimension:
                        img.thumbnail((self.max_image_dimension, self.max_image_dimension))
                    
                    img.save(temp_path, format='PNG', optimize=True)
                
                # Convert to base64
                with open(temp_path, 'rb') as img_file:
                    base64_image = base64.b64encode(img_file.read()).decode('utf-8')
                
                return ImageResult(
                    id=str(uuid.uuid4()),
                    base64_image=base64_image,
                    path=temp_path,
                    metadata={
                        **metadata,
                        'dimensions': img.size,
                        'mode': img.mode,
                        'file_type': 'image/png'
                    }
                )
            except Exception as e:
                logger.error(f"Image processing failed: {str(e)}")
                return None

    def process_document(self, file_path: str) -> Dict[str, Any]:
        """Main document processing method"""
        try:
            self._validate_file(file_path)
            metadata = self._generate_metadata(file_path)
            logger.info(f"Processing document: {metadata['file_name']}")

            elements = partition(file_path)
            text_content = []
            extracted_images = []
            page_counter = 1

            for element in elements:
                if isinstance(element, Text):
                    # Add page context metadata
                    element_metadata = {
                        **metadata,
                        'page_number': page_counter,
                        'element_type': 'text'
                    }
                    text_content.append((element.text, element_metadata))
                    if 'PAGE_BREAK' in element.text:
                        page_counter += 1

                elif isinstance(element, UnstructuredImage):
                    img_metadata = {
                        **metadata,
                        'page_number': page_counter,
                        'element_type': 'image'
                    }
                    image_result = self._process_image(element.to_dict()['data'], img_metadata)
                    if image_result:
                        extracted_images.append(image_result)

            # Process text chunks with context-aware chunking
            text_chunks = []
            current_page = 1
            full_text = ' '.join([t[0] for t in text_content])
            
            for chunk in self._chunk_text(full_text, metadata):
                chunk_metadata = {
                    **metadata,
                    'chunk_length': len(chunk.text),
                    'contains_page_numbers': any(str(p) in chunk.text for p in range(1, page_counter+1))
                }
                text_chunks.append({
                    'chunk_id': chunk.chunk_id,
                    'text': chunk.text,
                    'metadata': chunk_metadata,
                    'start_char': chunk.start_char,
                    'end_char': chunk.end_char
                })

            return {
                'metadata': metadata,
                'text_chunks': text_chunks,
                'images': [img.__dict__ for img in extracted_images],
                'processing_summary': {
                    'total_chunks': len(text_chunks),
                    'total_images': len(extracted_images),
                    'pages_processed': page_counter
                }
            }

        except Exception as e:
            logger.error(f"Document processing failed: {str(e)}")
            return {
                'metadata': self._generate_metadata(file_path) if os.path.exists(file_path) else {},
                'text_chunks': [],
                'images': [],
                'error': str(e)
            }

# Example Usage
if __name__ == "__main__":
    processor = EnhancedDocumentProcessor()
    test_file = "path/to/document.pdf"
    
    if os.path.exists(test_file):
        result = processor.process_document(test_file)
        print(f"Processed {result['metadata']['file_name']}")
        print(f"Text chunks: {len(result['text_chunks'])}")
        print(f"Images extracted: {len(result['images'])}")
    else:
        print("Test file not found")