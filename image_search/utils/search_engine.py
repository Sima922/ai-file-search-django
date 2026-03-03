import os 
import logging
import numpy as np
import shutil
import time
import uuid
import re
from typing import Dict, List, Optional, Union, Any
from threading import Lock
from datetime import datetime
from PIL import Image
import chromadb
from chromadb.utils.embedding_functions import OpenCLIPEmbeddingFunction
from django.conf import settings
from django.http import JsonResponse, HttpResponseBadRequest
from rank_bm25 import BM25Okapi

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(settings.BASE_DIR, "search_engine.log")),
    ],
)
logger = logging.getLogger(__name__)

class EnhancedMultimodalSearchEngine:
    """
    Advanced multimodal search engine with hybrid semantic-keyword search,
    query expansion, and result diversification.
    """
    _instance = None
    _lock = Lock()

    def __new__(cls):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        try:
            self.db_path = os.path.join(settings.BASE_DIR, "chroma_db")
            os.makedirs(self.db_path, exist_ok=True)

            self.temp_dir = os.path.join(settings.BASE_DIR, "temp_image_processing")
            os.makedirs(self.temp_dir, exist_ok=True)

            self.client = chromadb.PersistentClient(path=self.db_path)
            self.embedding_function = OpenCLIPEmbeddingFunction()
            self._ensure_collections()

            logger.info("Search engine initialized successfully.")
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            raise

    def _ensure_collections(self):
        try:
            self.image_collection = self.client.get_or_create_collection(
                name="student_images", 
                embedding_function=self.embedding_function
            )
            self.document_collection = self.client.get_or_create_collection(
                name="student_documents", 
                embedding_function=self.embedding_function
            )
            logger.info("Collections initialized successfully.")
        except Exception as e:
            logger.error(f"Collection initialization error: {e}")
            raise

    def _tokenize(self, text: str) -> List[str]:
        """Advanced tokenization with stopword removal"""
        tokens = re.findall(r'\b\w[\w.-]*\b', text.lower())
        return [t for t in tokens if t not in getattr(settings, 'SEARCH_STOPWORDS', set())]

    def _expand_query(self, query: str) -> str:
        """Query expansion using synonyms and key terms"""
        synonyms = getattr(settings, 'QUERY_SYNONYMS', {})
        expansions = [query]
        
        # Add synonyms for full query
        if query.lower() in synonyms:
            expansions.extend(synonyms[query.lower()])
        
        # Add synonyms for individual terms
        for term in self._tokenize(query):
            if term in synonyms:
                expansions.extend(synonyms[term])
        
        return ' '.join(list(set(expansions)))

    def _calculate_freshness_boost(self, upload_date: str) -> float:
        """Calculate boost based on document freshness"""
        try:
            upload_time = datetime.fromisoformat(upload_date)
            days_old = (datetime.now() - upload_time).days
            return 1 / (1 + days_old)  # Recent items get higher boost
        except:
            return 1.0

    def _hybrid_rerank(self, query: str, documents: List[str], 
                      metadatas: List[Dict], distances: List[float]) -> List[Dict]:
        """Advanced hybrid ranking with dynamic weighting"""
        if not documents:
            return []

        # Calculate semantic scores with freshness boost
        semantic_scores = []
        for i, d in enumerate(distances):
            base_score = 1 / (1 + d)
            if metadatas[i].get('uploaded_at'):
                base_score *= (1 + 0.2 * self._calculate_freshness_boost(metadatas[i]['uploaded_at']))
            semantic_scores.append(base_score)

        # Calculate BM25 scores with safe normalization
        tokenized_corpus = [self._tokenize(doc) for doc in documents]
        bm25 = BM25Okapi(tokenized_corpus)
        tokenized_query = self._tokenize(query)
        bm25_scores = bm25.get_scores(tokenized_query)
        
        max_bm25 = max(bm25_scores) or 1e-9
        bm25_normalized = [(s + 1e-9) / (max_bm25 + 1e-9) for s in bm25_scores]

        # Dynamic weighting based on query type
        query_length = len(tokenized_query)
        is_keyword_query = (query_length <= 3 or 
                           any(t in getattr(settings, 'SEARCH_KEYWORDS', set()) 
                               for t in tokenized_query))
        
        semantic_weight = 0.7 if is_keyword_query else 0.85
        combined_scores = [
            (semantic_weight * s) + ((1 - semantic_weight) * b)
            for s, b in zip(semantic_scores, bm25_normalized)
        ]

        # Sort by combined score
        sorted_indices = np.argsort(combined_scores)[::-1]
        
        return [
            {
                "text": documents[i],
                "metadata": metadatas[i],
                "score": combined_scores[i]
            }
            for i in sorted_indices
        ]

    def _diversify_results(self, results: List[Dict], lambda_param: float = 0.7) -> List[Dict]:
        """Maximal Marginal Relevance diversification"""
        if len(results) <= 1:
            return results
        
        diversified = [results[0]]
        remaining = results[1:]
        
        while remaining:
            next_idx = max(
                enumerate(remaining),
                key=lambda x: (
                    lambda_param * x[1].get('score', 0) - 
                    (1 - lambda_param) * max(
                        self._similarity(x[1], d) 
                        for d in diversified
                    )
                )
            )[0]
            diversified.append(remaining.pop(next_idx))
        
        return diversified

    def _similarity(self, a: Dict, b: Dict) -> float:
        """Calculate similarity between two results"""
        # Simple text similarity for demonstration
        text_a = a.get('text', '')
        text_b = b.get('text', '')
        tokens_a = set(self._tokenize(text_a))
        tokens_b = set(self._tokenize(text_b))
        return len(tokens_a & tokens_b) / (len(tokens_a | tokens_b) + 1e-9)

    def _filter_duplicates(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter duplicate results based on filename"""
        seen_filenames = set()
        unique_results = []
        
        for result in results:
            metadata = result.get("metadata", {})
            filename = metadata.get("filename")
            
            if filename and filename not in seen_filenames:
                seen_filenames.add(filename)
                unique_results.append(result)
        
        return self._diversify_results(unique_results)

    def _generate_unique_id(self, prefix: str = '') -> str:
        return f"{prefix}_{uuid.uuid4()}" if prefix else str(uuid.uuid4())

    def _copy_image_safely(self, original_path: str) -> str:
        try:
            unique_filename = f"{int(time.time())}_{os.path.basename(original_path)}"
            temp_path = os.path.join(self.temp_dir, unique_filename)
            shutil.copy2(original_path, temp_path)
            return temp_path
        except Exception as e:
            logger.error(f"Image copy error: {e}")
            raise

    def add_image(self, image_path: str, metadata: Dict[str, Any]) -> bool:
        try:
            safe_image_path = self._copy_image_safely(image_path)
            with Image.open(safe_image_path) as img:
                if img.mode != "RGB":
                    img = img.convert("RGB")
                
                img_id = self._generate_unique_id('img')
                metadata.update({
                    "original_path": image_path,
                    "image_id": img_id,
                    "uploaded_at": datetime.now().isoformat()
                })

                embeddings = self.embedding_function([np.array(img)])
                self.image_collection.add(
                    ids=[img_id],
                    embeddings=embeddings,
                    metadatas=[metadata]
                )
                
                logger.info(f"Added image: {metadata.get('filename', 'unknown')}")
                return True
        except Exception as e:
            logger.error(f"Image addition failed: {e}")
            return False
        finally:
            if os.path.exists(safe_image_path):
                os.remove(safe_image_path)

    def add_document(self, processed_document: Dict[str, Any]) -> bool:
        try:
            text_chunks = processed_document.get("text_chunks", [])
            if not text_chunks:
                logger.warning("No text chunks in document")
                return False

            doc_id = self._generate_unique_id('doc')
            metadata = processed_document.get("metadata", {})
            metadata.update({
                "document_id": doc_id,
                "uploaded_at": datetime.now().isoformat()
            })

            texts = [chunk["text"] for chunk in text_chunks]
            embeddings = self.embedding_function(texts)
            chunk_ids = [f"{doc_id}_chunk{i}" for i in range(len(text_chunks))]

            chunk_metadatas = []
            for idx, (chunk_id, chunk) in enumerate(zip(chunk_ids, text_chunks)):
                chunk_meta = metadata.copy()
                chunk_meta.update({
                    "chunk_id": chunk_id,
                    "chunk_index": idx,
                    "length": len(chunk["text"])
                })
                chunk_metadatas.append(chunk_meta)

            self.document_collection.add(
                ids=chunk_ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=chunk_metadatas
            )

            logger.info(f"Added document: {metadata.get('filename', 'unknown')} with {len(text_chunks)} chunks")
            return True
        except Exception as e:
            logger.error(f"Document addition failed: {e}")
            return False

    def search(self, query: str, n_results: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        try:
            expanded_query = self._expand_query(query)
            query_embeddings = self.embedding_function([expanded_query])

            # Image search (semantic only)
            image_results = self.image_collection.query(
                query_embeddings=query_embeddings,
                n_results=n_results * 2,
                include=["distances", "metadatas"]
            )

            # Document search (hybrid)
            doc_results = self.document_collection.query(
                query_embeddings=query_embeddings,
                n_results=n_results * 3,
                include=["distances", "metadatas", "documents"]
            )

            # Process images
            image_results_processed = [
                {
                    "type": "image",
                    "metadata": meta,
                    "score": 1 / (1 + dist)
                }
                for dist, meta in zip(image_results["distances"][0], image_results["metadatas"][0])
            ]

            # Process documents with hybrid reranking
            reranked_docs = self._hybrid_rerank(
                query=expanded_query,
                documents=doc_results["documents"][0],
                metadatas=doc_results["metadatas"][0],
                distances=doc_results["distances"][0]
            )

            doc_results_processed = [
                {
                    "type": "document",
                    "text": doc["text"],
                    "metadata": doc["metadata"],
                    "score": doc["score"]
                }
                for doc in reranked_docs
            ]

            # Apply final filtering and limiting
            final_images = self._filter_duplicates(image_results_processed)[:n_results]
            final_docs = self._filter_duplicates(doc_results_processed)[:n_results]

            return {
                "images": sorted(final_images, key=lambda x: x["score"], reverse=True),
                "documents": sorted(final_docs, key=lambda x: x["score"], reverse=True)
            }

        except Exception as e:
            logger.error(f"Search failed for '{query}': {e}")
            return {"images": [], "documents": []}

    def process_and_add_files(self, files: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        results = {"success": [], "failure": []}
        
        for file_data in files:
            try:
                file_type = file_data.get("type")
                metadata = file_data.get("metadata", {})
                filename = metadata.get("filename", "unknown")
                
                if file_type == "image":
                    if self.add_image(file_data.get("path"), metadata):
                        results["success"].append(filename)
                    else:
                        results["failure"].append(filename)
                
                elif file_type == "document":
                    if self.add_document(file_data.get("processed_document", {})):
                        results["success"].append(filename)
                    else:
                        results["failure"].append(filename)
                
                else:
                    logger.warning(f"Unsupported file type: {file_type}")
                    results["failure"].append(filename)
            
            except Exception as e:
                logger.error(f"File processing error: {e}")
                results["failure"].append(filename)
        
        return results

# Initialize singleton instance
_search_engine = EnhancedMultimodalSearchEngine()

def search_view(request):
    """Django view for handling search requests"""
    query = request.GET.get("query", "").strip()
    n_results = min(int(request.GET.get("n_results", 5)), 20)  # Limit to 20 results
    
    if not query:
        return HttpResponseBadRequest("Query parameter is required")
    
    try:
        results = _search_engine.search(query, n_results)
        return JsonResponse(results)
    except Exception as e:
        logger.error(f"Search view error: {e}")
        return JsonResponse({"error": "Search failed"}, status=500)