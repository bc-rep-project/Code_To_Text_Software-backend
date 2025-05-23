"""
URL configuration for repository monitoring.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MonitoringJobViewSet

router = DefaultRouter()
router.register(r'', MonitoringJobViewSet, basename='monitoring')

urlpatterns = [
    path('', include(router.urls)),
] 