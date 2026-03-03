from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class StudentImage(models.Model):
    """
    Model to store uploaded files (images or documents) along with associated metadata.
    """
    # Unique identifier for tracking files across the system
    unique_id = models.CharField(max_length=36, unique=True, null=False, blank=False)

    # ForeignKey to track which user uploaded the file; allows nulls for anonymous uploads
    uploader = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    # File fields to store both images and documents
    file = models.FileField(upload_to='student_files/', null=True, blank=True)
    image = models.ImageField(upload_to='student_images/', null=True, blank=True)

    # Date and time of upload
    uploaded_at = models.DateTimeField(default=timezone.now)

    # JSON field to store embeddings for image or document
    embedding = models.JSONField(null=True, blank=True)

    # Thumbnail path
    thumbnail = models.CharField(max_length=255, null=True, blank=True)

    # Metadata JSON field for flexible metadata storage
    metadata = models.JSONField(null=True, blank=True)

    # Download tracking
    has_downloaded = models.BooleanField(default=False)

    # File type choices
    FILE_TYPE_CHOICES = [
        ('image', 'Image'),
        ('document', 'Document'),
    ]
    file_type = models.CharField(
        max_length=20, 
        choices=FILE_TYPE_CHOICES, 
        default='image'
    )

    def __str__(self):
        """Return a string representation of the file."""
        uploader_name = self.uploader.username if self.uploader else "Anonymous"
        return f"{self.file_type.capitalize()} by {uploader_name} on {self.uploaded_at}"

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Student File'
        verbose_name_plural = 'Student Files'


class TextChunk(models.Model):
    """
    Model to store chunks of text extracted from documents, along with metadata.
    """
    # ForeignKey to associate text chunks with the main file
    parent_file = models.ForeignKey(
        StudentImage, 
        on_delete=models.CASCADE, 
        related_name="text_chunks"
    )

    # The actual text of the chunk
    text = models.TextField()

    # Character position metadata
    start_char = models.IntegerField(null=True, blank=True)
    end_char = models.IntegerField(null=True, blank=True)

    # Embedding vector for the text chunk
    embedding = models.JSONField(null=True, blank=True)

    # Optional metadata for the text chunk
    metadata = models.JSONField(null=True, blank=True)

    def __str__(self):
        """Return a string representation of the text chunk."""
        parent_name = (
            self.parent_file.file.name if self.parent_file.file 
            else self.parent_file.image.name
        )
        return f"Text Chunk from {parent_name} ({self.start_char or 0}-{self.end_char or 0})"

    class Meta:
        verbose_name = 'Text Chunk'
        verbose_name_plural = 'Text Chunks'


class ImageMetadata(models.Model):
    """
    Model to store metadata for images extracted from documents or uploaded directly.
    """
    # ForeignKey to associate metadata with the parent file
    parent_file = models.ForeignKey(
        StudentImage, 
        on_delete=models.CASCADE, 
        related_name="image_metadata"
    )

    # Path or identifier for the extracted image
    image_path = models.CharField(max_length=255)

    # Embedding vector for the image
    embedding = models.JSONField(null=True, blank=True)

    # Additional metadata (e.g., dimensions, format)
    metadata = models.JSONField(null=True, blank=True)

    def __str__(self):
        """Return a string representation of the image metadata."""
        parent_name = (
            self.parent_file.file.name if self.parent_file.file 
            else self.parent_file.image.name
        )
        return f"Image Metadata for {parent_name} - {self.image_path}"

    class Meta:
        verbose_name = 'Image Metadata'
        verbose_name_plural = 'Image Metadata'