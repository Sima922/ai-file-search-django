from django import forms
from .models import StudentImage


class FileUploadForm(forms.ModelForm):
    """
    Form for uploading files to the StudentImage model, supporting multiple file uploads.
    """
    file_path = forms.FileField(
        widget=forms.ClearableFileInput(attrs={'multiple': True}),
        required=True,
        label="Upload Files",
        help_text="You can select multiple files at once."
    )

    class Meta:
        model = StudentImage
        fields = []  # No model fields are directly mapped for bulk uploads.

    def clean_file_path(self):
        files = self.files.getlist('file_path')
        if not files:
            raise forms.ValidationError("Please upload at least one file.")
        
        allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'pdf', 'docx', 'txt', 'pptx']
        for file in files:
            if not file.name.split('.')[-1].lower() in allowed_extensions:
                raise forms.ValidationError(f"Unsupported file type: {file.name}")
        
        return files
