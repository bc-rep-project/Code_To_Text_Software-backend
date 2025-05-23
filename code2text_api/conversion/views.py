"""
API views for the conversion app.
"""

import os
import logging
import shutil
import zipfile
from datetime import datetime
from django.conf import settings
from django.http import FileResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Conversion
from .serializers import ConversionSerializer
from .tasks import convert_repository_to_text
from repository.models import Repository

logger = logging.getLogger(__name__)

class ConversionViewSet(viewsets.ModelViewSet):
    """
    API endpoint for code conversions.
    """
    serializer_class = ConversionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Get conversions for the current user."""
        return Conversion.objects.filter(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """
        Create a new conversion for a repository.
        """
        repository_id = request.data.get('repository')
        if not repository_id:
            return Response(
                {'error': 'Repository ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            repository = Repository.objects.get(
                id=repository_id,
                user=request.user
            )
        except Repository.DoesNotExist:
            return Response(
                {'error': 'Repository not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if repository is ready for conversion
        if repository.status != 'ready':
            return Response(
                {'error': 'Repository is not ready for conversion'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create conversion instance
        conversion = Conversion.objects.create(
            repository=repository,
            user=request.user,
            status='pending'
        )
        
        # Start conversion task
        convert_repository_to_text.delay(conversion.id)
        
        return Response(
            ConversionSerializer(conversion).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """
        Get the status of a conversion.
        """
        conversion = self.get_object()
        return Response({
            'status': conversion.status,
            'start_time': conversion.start_time,
            'end_time': conversion.end_time,
            'duration': conversion.duration
        })
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """
        Download a converted repository.
        """
        conversion = self.get_object()
        
        # Check if conversion is complete
        if not conversion.is_complete:
            return Response(
                {'error': 'Conversion is not complete'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not conversion.result_path or not os.path.exists(conversion.result_path):
            return Response(
                {'error': 'Conversion result not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create a zip file of the converted repository
        zip_file_path = os.path.join(
            settings.MEDIA_ROOT,
            f"conversion_{conversion.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip"
        )
        
        try:
            # Create zip file
            with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(conversion.result_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Get relative path for zip structure
                        rel_path = os.path.relpath(file_path, conversion.result_path)
                        zipf.write(file_path, rel_path)
            
            # Update download count
            conversion.download_count += 1
            conversion.save()
            
            # Return the zip file
            return FileResponse(
                open(zip_file_path, 'rb'),
                as_attachment=True,
                filename=f"{conversion.repository.name}_converted.zip"
            )
        except Exception as e:
            logger.error(f"Error creating zip file: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        finally:
            # Clean up zip file (will be deleted after response is sent)
            if os.path.exists(zip_file_path):
                try:
                    os.remove(zip_file_path)
                except Exception as e:
                    logger.error(f"Error deleting zip file: {str(e)}") 