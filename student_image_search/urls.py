from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from image_search import views  # Import views from the image_search app
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home_redirect, name='home_redirect'),  # Redirect root URL
    path('images/', include('image_search.urls')),  # Include image_search app URLs
]
# Add media URL configuration only during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)