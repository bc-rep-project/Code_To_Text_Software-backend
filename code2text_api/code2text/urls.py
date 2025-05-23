"""
URL configuration for code2text project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/repository/', include('repository.urls')),
    path('api/convert/', include('conversion.urls')),
    path('api/auth/', include('users.urls')),
    path('api/drive/', include('gdrive.urls')),
    path('api/monitor/', include('repository.monitor_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) 