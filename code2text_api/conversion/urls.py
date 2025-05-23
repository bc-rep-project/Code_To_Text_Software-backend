"""
URL configuration for conversion app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ConversionViewSet

router = DefaultRouter()
router.register(r'', ConversionViewSet, basename='conversion')

urlpatterns = [
    path('', include(router.urls)),
] 