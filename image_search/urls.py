from django.urls import path
from . import views

urlpatterns = [
    # Home redirect
    path('', views.home_redirect, name='home'),
    
    # Upload image page
    path('upload/', views.upload_image, name='upload_image'),
    
    # Search images page
    path('search/', views.search_images, name='search_images'),
    
    # Download file route with unique_file_id and file_type
    path('download/<str:unique_file_id>/<str:file_type>/', 
         views.download_file, 
         name='download_file'),
]