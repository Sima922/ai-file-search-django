from django.shortcuts import render, redirect  
from django.contrib import messages
from django.http import FileResponse
from django.urls import reverse
from tqdm import tqdm
from PIL import Image
import os
import uuid
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required

from .models import StudentImage, TextChunk, ImageMetadata
from .utils import setup_logging
from .utils.document_processor import EnhancedDocumentProcessor
from .utils.search_engine import EnhancedMultimodalSearchEngine

# Configure logging
logger = logging.getLogger(__name__)

class FileProcessor:
    def __init__(self):
        try:
            self.search_engine = EnhancedMultimodalSearchEngine()
            self.doc_processor = EnhancedDocumentProcessor()
        except Exception as e:
            logger.error(f"Initialization error: {str(e)}")
            self.search_engine = None
            self.doc_processor = None

    def process_file(self, request, file):
        """Unified file processing method"""
        unique_file_id = str(uuid.uuid4())
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', unique_file_id)
        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, file.name)
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        file_ext = file.name.lower()
        try:
            if file_ext.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                return self._process_image(request, file, file_path, unique_file_id)
            elif file_ext.endswith(('.pdf', '.docx', '.txt', '.pptx')):
                return self._process_document(request, file, file_path, unique_file_id)
            else:
                logger.warning(f"Unsupported file type: {file.name}")
                return False
        except Exception as e:
            logger.error(f"Error processing {file.name}: {str(e)}")
            return False

    def _process_image(self, request, file, file_path, unique_file_id):
        try:
            student_image = StudentImage.objects.create(
                unique_id=unique_file_id,
                image=file,
                uploader=request.user if request.user.is_authenticated else None,
                file_type='image'
            )

            metadata = {
                'unique_id': unique_file_id,
                'filename': file.name,
                'uploaded_at': student_image.uploaded_at.isoformat(),
                'uploader': student_image.uploader.username if student_image.uploader else 'Anonymous',
                'image_path': student_image.image.url  # Using the original image URL
            }

            self.search_engine.process_and_add_files([{
                "type": "image",
                "path": file_path,
                "metadata": metadata
            }])
            return True
        except Exception as e:
            logger.error(f"Image processing error: {str(e)}")
            return False

    def _process_document(self, request, file, file_path, unique_file_id):
        try:
            processed_document = self.doc_processor.process_document(file_path)
            student_doc = StudentImage.objects.create(
                unique_id=unique_file_id,
                file=file,
                uploader=request.user if request.user.is_authenticated else None,
                file_type='document'
            )

            metadata = {
                'unique_id': unique_file_id,
                'filename': file.name,
                'uploaded_at': student_doc.uploaded_at.isoformat(),
                'uploader': student_doc.uploader.username if student_doc.uploader else 'Anonymous'
            }

            processed_document['metadata'] = metadata

            self.search_engine.process_and_add_files([{
                "type": "document",
                "processed_document": processed_document,
                "metadata": metadata
            }])

            for chunk in processed_document.get('text_chunks', []):
                TextChunk.objects.create(
                    parent_file=student_doc,
                    text=chunk['text']
                )
            return True
        except Exception as e:
            logger.error(f"Document processing error: {str(e)}")
            return False

def upload_image(request):
    processor = FileProcessor()
    if request.method == 'POST':
        files = request.FILES.getlist('files')
        if not files:
            messages.error(request, "Please select at least one file to upload.")
            return render(request, 'image_search/upload_image.html')

        success_count = sum(1 for file in files if processor.process_file(request, file))
        if success_count > 0:
            messages.success(request, f"Successfully uploaded {success_count} files!")
            return redirect('search_images')
        else:
            messages.error(request, "No files were successfully uploaded.")
    return render(request, 'image_search/upload_image.html')

def search_images(request):
    processor = FileProcessor()
    query_text = request.GET.get('query', '').strip()
    context = {'query': query_text}

    if not query_text:
        messages.info(request, "Enter a search term to find images and documents.")
        return render(request, 'image_search/search_images.html', context)

    try:
        results = processor.search_engine.search(query_text)
        image_results = []
        document_results = []

        # Process images
        for result in results.get('images', []):
            metadata = result.get('metadata', {})
            image_results.append({
                'url': metadata.get('image_path', ''),  # Using the original image path
                'metadata': metadata
            })

        # Process documents
        for result in results.get('documents', []):
            metadata = result.get('metadata', {})
            document_results.append({
                'text': result.get('text', 'No excerpt available'),
                'metadata': metadata
            })

        context['image_results'] = image_results
        context['document_results'] = document_results

        if not image_results and not document_results:
            messages.info(request, f"No results found for '{query_text}'.")
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        messages.error(request, "An error occurred during search. Please try again.")
    return render(request, 'image_search/search_images.html', context)

def download_file(request, unique_file_id, file_type):
    try:
        file_obj = StudentImage.objects.get(unique_id=unique_file_id, file_type=file_type)
        file_path = file_obj.image.path if file_type == 'image' else file_obj.file.path
        filename = file_obj.image.name if file_type == 'image' else file_obj.file.name

        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            messages.error(request, "File not found.")
            return redirect('search_images')

        logger.info(f"Serving file download: {filename}")
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=filename)
    except StudentImage.DoesNotExist:
        logger.error(f"File with ID {unique_file_id} not found.")
        messages.error(request, "File not found.")
        return redirect('search_images')
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        messages.error(request, "An error occurred during download.")
        return redirect('search_images')

def home_redirect(request):
    return redirect('upload_image')