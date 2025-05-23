"""
API views for Google Drive integration.
"""

import logging
import os
import zipfile
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from .models import DriveFile
from .serializers import (
    DriveFileSerializer,
    GoogleDriveUploadSerializer,
    GoogleAuthCallbackSerializer
)
from .utils import (
    check_google_credentials,
    refresh_google_token_if_needed,
    upload_file_to_drive,
    create_drive_folder
)
from conversion.models import Conversion
from users.utils import refresh_google_token

logger = logging.getLogger(__name__)

class GoogleDriveAuthView(APIView):
    """
    API endpoint for Google Drive authentication.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Check if the current user has valid Google Drive credentials.
        """
        user = request.user
        
        # Check if user has Google credentials
        if not user.google_access_token:
            return Response({'authenticated': False})
        
        # Check if token is valid
        is_valid = check_google_credentials(user.google_access_token)
        
        if not is_valid and user.google_refresh_token:
            # Try to refresh the token
            try:
                refresh_google_token(user)
                is_valid = True
            except Exception as e:
                logger.error(f"Error refreshing Google token: {str(e)}")
                is_valid = False
        
        return Response({'authenticated': is_valid})
    
    def post(self, request):
        """
        Process Google authentication callback.
        """
        serializer = GoogleAuthCallbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Process authentication in users app
        from users.views import GoogleAuthView
        return GoogleAuthView().post(request)


class DriveFileViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Google Drive files.
    """
    serializer_class = DriveFileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Get Drive files for the current user."""
        return DriveFile.objects.filter(user=self.request.user)


class DriveUploadView(APIView):
    """
    API endpoint for uploading files to Google Drive.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Upload a converted repository to Google Drive.
        """
        serializer = GoogleDriveUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        conversion_id = serializer.validated_data['conversion_id']
        folder_name = serializer.validated_data.get('folder_name')
        
        # Get the conversion
        try:
            conversion = Conversion.objects.get(
                id=conversion_id,
                user=request.user
            )
        except Conversion.DoesNotExist:
            return Response(
                {'error': 'Conversion not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if conversion is complete
        if not conversion.is_complete:
            return Response(
                {'error': 'Conversion is not complete'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if result path exists
        if not conversion.result_path or not os.path.exists(conversion.result_path):
            return Response(
                {'error': 'Conversion result not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user has Google credentials
        user = request.user
        if not user.google_access_token:
            return Response(
                {'error': 'Google Drive not authenticated'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Refresh token if needed
        try:
            refresh_google_token_if_needed(user)
        except Exception as e:
            logger.error(f"Error refreshing Google token: {str(e)}")
            return Response(
                {'error': 'Failed to refresh Google token'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        try:
            # Create a zip file of the converted repository
            zip_file_path = os.path.join(
                settings.MEDIA_ROOT,
                f"drive_upload_{conversion.id}.zip"
            )
            
            # Create zip file
            with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(conversion.result_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Get relative path for zip structure
                        rel_path = os.path.relpath(file_path, conversion.result_path)
                        zipf.write(file_path, rel_path)
            
            # Use repository name if folder name not provided
            if not folder_name:
                folder_name = f"{conversion.repository.name}_converted"
            
            # Create folder in Google Drive
            folder_id = create_drive_folder(user.google_access_token, folder_name)
            
            # Upload zip file to Google Drive
            file_info = upload_file_to_drive(
                user.google_access_token,
                zip_file_path,
                f"{folder_name}.zip",
                folder_id
            )
            
            # Create DriveFile record
            drive_file = DriveFile.objects.create(
                user=user,
                conversion=conversion,
                file_id=file_info['id'],
                file_name=file_info['name'],
                file_url=file_info['webViewLink'],
                mime_type=file_info['mimeType']
            )
            
            # Update conversion
            conversion.uploaded_to_drive = True
            conversion.drive_file_id = file_info['id']
            conversion.drive_file_url = file_info['webViewLink']
            conversion.save()
            
            return Response(DriveFileSerializer(drive_file).data)
        
        except Exception as e:
            logger.error(f"Error uploading to Google Drive: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        finally:
            # Clean up zip file
            if os.path.exists(zip_file_path):
                try:
                    os.remove(zip_file_path)
                except Exception as e:
                    logger.error(f"Error deleting zip file: {str(e)}") 