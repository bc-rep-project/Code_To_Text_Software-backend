"""
URL configuration for Google Drive integration.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    GoogleDriveAuthView,
    DriveFileViewSet,
    DriveUploadView
)

router = DefaultRouter()
router.register(r'files', DriveFileViewSet, basename='drive-file')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', GoogleDriveAuthView.as_view(), name='gdrive-auth'),
    path('upload/', DriveUploadView.as_view(), name='gdrive-upload'),
]